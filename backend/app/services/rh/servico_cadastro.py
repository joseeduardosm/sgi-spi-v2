# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras da atualização cadastral validada pela CGP.
"""Atualização cadastral (Funcionalidade 1 do Módulo RH).

- O usuário comum confirma ou atualiza o perfil todo mês. Cada campo alterado vira uma `AlteracaoCadastral`
  **pendente**: o valor em vigor continua o anterior até a CGP validar.
- A CGP **valida** (o valor proposto passa a valer) ou **recusa** com justificativa e correção (o valor
  corrigido passa a valer e o usuário recebe um e-mail).
- Alterações feitas pela CGP ou pelo SuperRoot valem na hora e entram no histórico como validadas.
- Superior imediato: obrigatório (exceto para quem a CGP marcar como topo da hierarquia), não pode ser o
  próprio usuário nem formar ciclo (A superior de B e B superior de A, direta ou indiretamente).
"""

import re
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.rh import AlteracaoCadastral, DadosFuncionais
from app.models.usuario import Usuario
from app.schemas.usuarios import DadosPerfil
from app.services import servico_mensagens
from app.services.rh.papeis import SemPermissaoRh, dados_funcionais, eh_cgp, exigir_cgp, usuarios_cgp
from app.services.servico_auditoria import auditar

CAMPOS = ("nome_completo", "email", "ramal", "celular", "cargo", "departamento", "andar", "predio", "data_nascimento", "gestor_id")
ROTULOS = {
    "nome_completo": "Nome completo", "email": "E-mail", "ramal": "Ramal", "celular": "Celular", "cargo": "Cargo",
    "departamento": "Departamento", "andar": "Andar", "predio": "Lado", "data_nascimento": "Data de nascimento",
    "gestor_id": "Superior imediato",
}
PADRAO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ErroCadastro(Exception):
    """Regra do cadastro violada (vira 400; `status` pode indicar 404)."""

    def __init__(self, detalhe: str, status: int = 400, codigo: str = "invalido") -> None:
        super().__init__(detalhe)
        self.status, self.codigo = status, codigo


def _nome(usuario: Usuario | None) -> str:
    return (usuario.nome_completo or usuario.login) if usuario else "—"


# --- Conversão dos valores (texto no histórico) -------------------------------------------------

def para_texto(campo: str, valor) -> str | None:
    if valor is None or valor == "":
        return None
    if campo == "data_nascimento":
        return valor.isoformat() if isinstance(valor, date) else str(valor)
    return str(valor)


def de_texto(campo: str, texto: str | None):
    """Valor do campo a partir do texto guardado no histórico."""
    if campo == "gestor_id":
        return int(texto) if texto else None
    if campo == "data_nascimento":
        return date.fromisoformat(texto) if texto else None
    return texto or ""


def rotulo_valor(sessao: Session, campo: str, texto: str | None) -> str:
    """Valor para exibir (o superior imediato pelo nome, datas em dd/mm/aaaa)."""
    if not texto:
        return "—"
    if campo == "gestor_id":
        return _nome(sessao.get(Usuario, int(texto)))
    if campo == "data_nascimento":
        return date.fromisoformat(texto).strftime("%d/%m/%Y")
    return texto


# --- Superior imediato --------------------------------------------------------------------------

def validar_superior(sessao: Session, usuario_id: int, gestor_id: int | None, obrigatorio: bool) -> None:
    """Superior obrigatório (quando for o caso), diferente do próprio usuário e sem ciclo na hierarquia."""
    if gestor_id is None:
        if obrigatorio:
            raise ErroCadastro("Informe o superior imediato.")
        return
    if gestor_id == usuario_id:
        raise ErroCadastro("Você não pode ser o seu próprio superior imediato.")
    gestor = sessao.get(Usuario, gestor_id)
    if gestor is None or not gestor.ativo:
        raise ErroCadastro("Superior imediato inválido ou inativo.")
    # Sobe a cadeia a partir do superior escolhido: chegar ao usuário é um ciclo
    vistos, atual = set(), gestor
    while atual is not None and atual.gestor_id is not None and atual.id not in vistos:
        vistos.add(atual.id)
        if atual.gestor_id == usuario_id:
            raise ErroCadastro(
                f"{_nome(gestor)} não pode ser seu superior imediato: você já é superior dele(a) na hierarquia (direta ou indiretamente)."
            )
        atual = sessao.get(Usuario, atual.gestor_id)


def superior_obrigatorio(sessao: Session, usuario: Usuario) -> bool:
    """Só a conta root e quem a CGP marcou como topo da hierarquia estão dispensados (os SuperRoot não)."""
    from app.services.servico_perfil import dispensado

    if dispensado(usuario):
        return False
    dados = dados_funcionais(sessao, usuario.id)
    return not (dados and dados.sem_superior)


# --- Pendências ---------------------------------------------------------------------------------

def pendentes_do_usuario(sessao: Session, usuario_id: int) -> list[AlteracaoCadastral]:
    return list(sessao.scalars(
        select(AlteracaoCadastral).where(AlteracaoCadastral.usuario_id == usuario_id, AlteracaoCadastral.status == "pendente")
        .order_by(AlteracaoCadastral.solicitada_em)
    ))


def valores_pendentes(sessao: Session, usuario_id: int) -> dict[str, object]:
    """{campo: valor proposto} das alterações pendentes (usado para liberar o bloqueio mensal)."""
    return {a.campo: de_texto(a.campo, a.valor_proposto) for a in pendentes_do_usuario(sessao, usuario_id)}


def _registrar(sessao: Session, usuario: Usuario, campo: str, novo, autor: Usuario, status: str) -> AlteracaoCadastral:
    """Nova alteração do campo; a pendente anterior do mesmo campo fica `substituida`."""
    for anterior in sessao.scalars(select(AlteracaoCadastral).where(
        AlteracaoCadastral.usuario_id == usuario.id, AlteracaoCadastral.campo == campo, AlteracaoCadastral.status == "pendente",
    )):
        anterior.status = "substituida"
    alteracao = AlteracaoCadastral(
        usuario_id=usuario.id, campo=campo, valor_anterior=para_texto(campo, getattr(usuario, campo)), valor_proposto=para_texto(campo, novo),
        status=status, solicitada_em=agora_utc(), solicitada_por_id=autor.id, solicitada_por_nome=_nome(autor),
    )
    if status == "validada":
        alteracao.analisada_por_id, alteracao.analisada_por_nome, alteracao.analisada_em = autor.id, _nome(autor), agora_utc()
    sessao.add(alteracao)
    return alteracao


def revisar_perfil(sessao: Session, usuario: Usuario, dados: DadosPerfil) -> Usuario:
    """Confirmação mensal do próprio perfil.

    Usuário comum: cada campo diferente do valor em vigor vira alteração pendente (o valor em vigor não muda);
    voltar ao valor em vigor descarta a pendência do campo. CGP e SuperRoot: vale na hora.
    """
    from app.services.servico_perfil import validar_localizacao

    erro_local = validar_localizacao(dados.andar, dados.predio, usuario.andar or "", usuario.predio or "")
    if erro_local:
        raise ErroCadastro(erro_local)
    validar_superior(sessao, usuario.id, dados.gestor_id, superior_obrigatorio(sessao, usuario))
    direto = eh_cgp(sessao, usuario)
    novas: list[AlteracaoCadastral] = []
    for campo in CAMPOS:
        novo = getattr(dados, campo)
        atual = getattr(usuario, campo)
        if para_texto(campo, novo) == para_texto(campo, atual):
            # Voltou ao valor em vigor: a proposta pendente do campo deixa de valer
            for pendente in sessao.scalars(select(AlteracaoCadastral).where(
                AlteracaoCadastral.usuario_id == usuario.id, AlteracaoCadastral.campo == campo, AlteracaoCadastral.status == "pendente",
            )):
                pendente.status = "substituida"
            continue
        # Mesma proposta que já está pendente: nada muda
        if not direto and any(a.campo == campo and a.valor_proposto == para_texto(campo, novo) for a in pendentes_do_usuario(sessao, usuario.id)):
            continue
        novas.append(_registrar(sessao, usuario, campo, novo, usuario, "validada" if direto else "pendente"))
        if direto:
            setattr(usuario, campo, novo)
    # LinkedIn é divulgação voluntária do próprio usuário: vale na hora, sem validação da CGP
    usuario.linkedin = dados.linkedin
    usuario.perfil_revisado_em = agora_utc()
    auditar(sessao, usuario.login, "usuario.revisar-perfil", usuario.login,
            dados={"alteracoes": [a.campo for a in novas], "pendentes": not direto and bool(novas)})
    if novas and not direto:
        campos = ", ".join(ROTULOS[a.campo] for a in novas)
        servico_mensagens.notificar(
            sessao, [u.id for u in usuarios_cgp(sessao)], f"{_nome(usuario)} alterou seu cadastro e aguarda validação da CGP",
            f"{_nome(usuario)} alterou os campos: {campos}. As alterações aguardam validação da CGP.",
            chave=f"cadastro:{usuario.id}:{agora_utc():%Y%m%d%H%M%S%f}", categoria="revisao", prioridade="normal",
            link=f"/rh/validacoes?usuario={usuario.id}", email=True,
        )
    sessao.commit()
    return usuario


def situacao_campos(sessao: Session, usuario: Usuario) -> dict[str, dict]:
    """Por campo: proposta pendente (se houver) e a última validação/correção."""
    resultado: dict[str, dict] = {}
    historico = sessao.scalars(select(AlteracaoCadastral).where(
        AlteracaoCadastral.usuario_id == usuario.id, AlteracaoCadastral.status.in_(("pendente", "validada", "recusada")),
    ).order_by(AlteracaoCadastral.solicitada_em))
    for a in historico:
        item = resultado.setdefault(a.campo, {"pendente": False, "valor_proposto": None, "valor_proposto_rotulo": None,
                                              "validado_por": None, "validado_em": None, "corrigido": False})
        if a.status == "pendente":
            item.update(pendente=True, valor_proposto=a.valor_proposto, valor_proposto_rotulo=rotulo_valor(sessao, a.campo, a.valor_proposto))
        else:
            item.update(validado_por=a.analisada_por_nome, validado_em=a.analisada_em, corrigido=a.status == "recusada")
    return resultado


# --- CGP ----------------------------------------------------------------------------------------

def pendencias(sessao: Session, autor: Usuario) -> list[tuple[Usuario, list[AlteracaoCadastral]]]:
    """Usuários com alterações pendentes, dos pedidos mais antigos para os mais novos."""
    exigir_cgp(sessao, autor)
    grupos: dict[int, list[AlteracaoCadastral]] = {}
    for a in sessao.scalars(select(AlteracaoCadastral).where(AlteracaoCadastral.status == "pendente").order_by(AlteracaoCadastral.solicitada_em)):
        grupos.setdefault(a.usuario_id, []).append(a)
    usuarios = {u.id: u for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(list(grupos))))} if grupos else {}
    return [(usuarios[i], lista) for i, lista in grupos.items() if i in usuarios]


def historico(sessao: Session, usuario_id: int) -> list[AlteracaoCadastral]:
    return list(sessao.scalars(
        select(AlteracaoCadastral).where(AlteracaoCadastral.usuario_id == usuario_id).order_by(AlteracaoCadastral.solicitada_em.desc())
    ))


def _alteracao_pendente(sessao: Session, alteracao_id: uuid.UUID) -> AlteracaoCadastral:
    alteracao = sessao.get(AlteracaoCadastral, alteracao_id)
    if alteracao is None:
        raise ErroCadastro("Alteração não encontrada.", 404, "nao_encontrado")
    if alteracao.status != "pendente":
        raise ErroCadastro("Esta alteração já foi analisada.")
    return alteracao


def _encerrar_aviso_se_concluido(sessao: Session, usuario_id: int) -> None:
    sessao.flush()
    if not pendentes_do_usuario(sessao, usuario_id):
        servico_mensagens.encerrar(sessao, prefixo=f"cadastro:{usuario_id}:")
        # Também os avisos "quer baixar a folha de ponto, mas tem alterações aguardando validação"
        servico_mensagens.encerrar(sessao, prefixo=f"folha-ponto:validacao:{usuario_id}:")


def validar(sessao: Session, alteracao_id: uuid.UUID, autor: Usuario) -> AlteracaoCadastral:
    """A proposta passa a valer."""
    exigir_cgp(sessao, autor)
    alteracao = _aplicar_validacao(sessao, alteracao_id, autor)
    sessao.commit()
    return alteracao


def validar_lote(sessao: Session, ids: list[uuid.UUID], autor: Usuario) -> tuple[list[uuid.UUID], list[tuple[uuid.UUID, str]]]:
    """Valida várias alterações de uma vez. Cada uma num savepoint: a que falhar (já analisada, superior em ciclo)
    volta ao estado anterior e é devolvida em `erros`, sem impedir as demais."""
    exigir_cgp(sessao, autor)
    validadas: list[uuid.UUID] = []
    erros: list[tuple[uuid.UUID, str]] = []
    for alteracao_id in dict.fromkeys(ids):
        ponto = sessao.begin_nested()
        try:
            _aplicar_validacao(sessao, alteracao_id, autor)
            ponto.commit()
            validadas.append(alteracao_id)
        except ErroCadastro as erro:
            ponto.rollback()
            erros.append((alteracao_id, str(erro)))
    sessao.commit()
    return validadas, erros


def _aplicar_validacao(sessao: Session, alteracao_id: uuid.UUID, autor: Usuario) -> AlteracaoCadastral:
    """Aplica a proposta (sem commit)."""
    alteracao = _alteracao_pendente(sessao, alteracao_id)
    usuario = sessao.get(Usuario, alteracao.usuario_id)
    valor = de_texto(alteracao.campo, alteracao.valor_proposto)
    if alteracao.campo == "gestor_id":
        validar_superior(sessao, usuario.id, valor, False)
    setattr(usuario, alteracao.campo, valor)
    alteracao.status, alteracao.analisada_por_id, alteracao.analisada_por_nome, alteracao.analisada_em = "validada", autor.id, _nome(autor), agora_utc()
    auditar(sessao, autor.login, "rh.cadastro.validar", usuario.login, autor_id=autor.id, alvo_tipo="usuario", alvo_id=str(usuario.id),
            dados={"campo": alteracao.campo, "valor": alteracao.valor_proposto})
    _encerrar_aviso_se_concluido(sessao, usuario.id)
    return alteracao


def _validar_correcao(sessao: Session, usuario: Usuario, campo: str, texto: str | None):
    """Converte e confere o valor corrigido pela CGP."""
    texto = (texto or "").strip() or None
    try:
        valor = de_texto(campo, texto)
    except ValueError as erro:
        raise ErroCadastro("Valor corrigido inválido para o campo.") from erro
    if campo == "email" and valor and not PADRAO_EMAIL.match(valor):
        raise ErroCadastro("E-mail corrigido inválido.")
    if campo == "gestor_id":
        validar_superior(sessao, usuario.id, valor, False)
    return valor, para_texto(campo, valor)


def recusar(sessao: Session, alteracao_id: uuid.UUID, justificativa: str, valor_corrigido: str | None, autor: Usuario) -> AlteracaoCadastral:
    """A CGP recusa com justificativa e informa a correção, que passa a valer; o usuário recebe um e-mail."""
    exigir_cgp(sessao, autor)
    if not (justificativa or "").strip():
        raise ErroCadastro("Informe a justificativa da recusa.")
    alteracao = _alteracao_pendente(sessao, alteracao_id)
    usuario = sessao.get(Usuario, alteracao.usuario_id)
    valor, texto = _validar_correcao(sessao, usuario, alteracao.campo, valor_corrigido)
    setattr(usuario, alteracao.campo, valor)
    alteracao.status, alteracao.justificativa, alteracao.valor_corrigido = "recusada", justificativa.strip(), texto
    alteracao.analisada_por_id, alteracao.analisada_por_nome, alteracao.analisada_em = autor.id, _nome(autor), agora_utc()
    rotulo = ROTULOS[alteracao.campo]
    servico_mensagens.notificar(
        sessao, [usuario.id], f"Alteração do seu cadastro recusada: {rotulo}",
        f"A CGP recusou a alteração do campo {rotulo} ({rotulo_valor(sessao, alteracao.campo, alteracao.valor_proposto)}).\n\n"
        f"Justificativa: {alteracao.justificativa}\n\nCorreção feita: {rotulo_valor(sessao, alteracao.campo, texto)}",
        chave=f"cadastro-recusa:{alteracao.id}", categoria="revisao", prioridade="alta", link="/perfil", email=True,
    )
    auditar(sessao, autor.login, "rh.cadastro.recusar", usuario.login, autor_id=autor.id, alvo_tipo="usuario", alvo_id=str(usuario.id),
            dados={"campo": alteracao.campo, "proposto": alteracao.valor_proposto, "corrigido": texto, "justificativa": alteracao.justificativa})
    _encerrar_aviso_se_concluido(sessao, usuario.id)
    sessao.commit()
    return alteracao


def salvar_funcionais(sessao: Session, usuario_id: int, dados: dict, autor: Usuario, commit: bool = True) -> DadosFuncionais:
    """Campos exclusivos da CGP: autorizador, substituto, topo da hierarquia, período aquisitivo, LP, jornada, horários e documentos."""
    exigir_cgp(sessao, autor)
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise ErroCadastro("Usuário não encontrado.", 404, "nao_encontrado")
    for campo in ("autorizador_id", "substituto_id"):
        alvo = dados.get(campo)
        if alvo is not None:
            if alvo == usuario_id:
                raise ErroCadastro("O usuário não pode ser o próprio autorizador nem o próprio substituto.")
            outro = sessao.get(Usuario, alvo)
            if outro is None or not outro.ativo:
                raise ErroCadastro("Autorizador ou substituto inválido ou inativo.")
    registro = sessao.get(DadosFuncionais, usuario_id) or DadosFuncionais(usuario_id=usuario_id)
    # Início do período aquisitivo: "DD/MM" → dia e mês
    dados = dict(dados)
    if "inicio_periodo_aquisitivo" in dados:
        from app.services.rh.servico_periodos import ler_inicio

        try:
            dados["inicio_aquisitivo_dia"], dados["inicio_aquisitivo_mes"] = ler_inicio(dados.pop("inicio_periodo_aquisitivo"))
        except ValueError as erro:
            raise ErroCadastro(str(erro)) from erro
    antes = {c: getattr(registro, c, None) for c in dados}
    for campo, valor in dados.items():
        setattr(registro, campo, valor)
    registro.atualizado_por_id, registro.atualizado_por_nome, registro.atualizado_em = autor.id, _nome(autor), agora_utc()
    sessao.add(registro)
    from app.services.rh.folha_ponto import encerrar_aviso_dados

    encerrar_aviso_dados(sessao, registro)
    auditar(sessao, autor.login, "rh.cadastro.funcionais", usuario.login, autor_id=autor.id, alvo_tipo="usuario", alvo_id=str(usuario_id),
            dados={"campos": {c: {"de": antes[c], "para": dados[c]} for c in dados if antes[c] != dados[c]}})
    if commit:
        sessao.commit()
    else:
        sessao.flush()
    return registro


__all__ = ["ErroCadastro", "SemPermissaoRh"]


def ajustar_periodo_vigente(sessao: Session, usuario_id: int, dias_creditados: int, autor: Usuario, commit: bool = True):
    """A CGP ajusta os dias creditados do período aquisitivo vigente (ex.: férias gozadas antes do sistema)."""
    from app.services.rh import servico_afastamentos, servico_periodos

    exigir_cgp(sessao, autor)
    periodo = servico_periodos.vigente(sessao, usuario_id, servico_afastamentos.hoje())
    if periodo is None:
        raise ErroCadastro("Informe antes o início do período aquisitivo deste usuário.")
    antes = periodo.dias_creditados
    periodo.dias_creditados, periodo.origem, periodo.ajustado_por_nome = dias_creditados, "ajuste_cgp", _nome(autor)
    auditar(sessao, autor.login, "rh.ferias.ajuste_periodo", f"usuario={usuario_id}", autor_id=autor.id, alvo_tipo="usuario",
            alvo_id=str(usuario_id), dados={"periodo": periodo.inicio, "de": antes, "para": dias_creditados})
    if commit:
        sessao.commit()
    return periodo
