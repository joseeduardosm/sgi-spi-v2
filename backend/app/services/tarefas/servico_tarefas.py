# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras do Módulo Tarefas: permissões, pipeline, prazo, transferência, linha do tempo, carga e avisos.
"""Regras do Módulo Tarefas (tudo conferido no servidor).

**Papéis numa tarefa**
- *envolvidos*: responsável e participantes (executam; a carga conta para cada um);
- *liderança*: dono e líderes da equipe da tarefa **e das equipes acima dela** (equipe pai), além do SuperRoot;
- *criador*: quem cadastrou.

**Pipeline** (`mover`)
| De → Para | Quem |
|---|---|
| a_fazer → em_andamento ("Iniciar") / em_andamento → a_fazer | envolvidos e liderança |
| em_andamento → em_validacao ("Entregar") | envolvidos (sem equipe: vai direto a concluída) |
| em_validacao → concluida ("Validar") | liderança |
| em_validacao → em_andamento ("Devolver") | liderança, com motivo |
| a_fazer/em_andamento → concluida | liderança |
| concluida → em_andamento ("Reabrir") | liderança, com motivo |

Prazo só muda por `alterar_prazo`, com justificativa. Transferência: para membros da equipe (a liderança pode enviar
a qualquer usuário ativo). Carga = peso da prioridade × urgência do prazo, só para a_fazer e em_andamento.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import BinaryIO

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.tarefas import (
    AnexoEventoTarefa, EquipeTarefas, EventoTarefa, ItemChecklistTarefa, LiderEquipeTarefas, MarcadorTarefa,
    MembroEquipeTarefas, ParticipanteTarefa, Tarefa,
)
from app.models.usuario import Usuario
from app.services import servico_anexos, servico_mensagens
from app.services.servico_auditoria import auditar

ROTULOS_STATUS = {"a_fazer": "A fazer", "em_andamento": "Em andamento", "em_validacao": "Em validação", "concluida": "Concluída"}
ROTULOS_PRIORIDADE = {"baixa": "Baixa", "normal": "Normal", "alta": "Alta", "critica": "Crítica"}
PESOS = {"baixa": 1, "normal": 3, "alta": 5, "critica": 8}
OPERACIONAIS = ("a_fazer", "em_andamento")
MAXIMO_ANEXOS = 5
DIAS_VALIDACAO_PARADA = 2


class ErroTarefa(Exception):
    """Regra violada: 400 (ou `status` 403/404/409)."""

    def __init__(self, detalhe: str, status: int = 400, codigo: str = "invalido") -> None:
        super().__init__(detalhe)
        self.status, self.codigo = status, codigo


def _nome(usuario: Usuario | None) -> str:
    return (usuario.nome_completo or usuario.login) if usuario else "Sistema"


def _data_hora(valor: datetime) -> str:
    from zoneinfo import ZoneInfo

    return valor.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")


def _comparavel(valor: datetime) -> datetime:
    """SQLite devolve datas sem fuso: trata como UTC para comparar."""
    from datetime import timezone

    return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------------------------
# Papéis
# ---------------------------------------------------------------------------------------------

def cadeia_equipes(sessao: Session, equipe: EquipeTarefas | None) -> list[EquipeTarefas]:
    """A equipe e as equipes acima dela (protegido contra ciclos)."""
    resultado, vistos = [], set()
    while equipe is not None and equipe.id not in vistos:
        vistos.add(equipe.id)
        resultado.append(equipe)
        equipe = sessao.get(EquipeTarefas, equipe.equipe_pai_id) if equipe.equipe_pai_id else None
    return resultado


def lideranca(sessao: Session, equipe: EquipeTarefas | None) -> set[int]:
    """Dono e líderes da equipe e das equipes acima dela."""
    ids: set[int] = set()
    for e in cadeia_equipes(sessao, equipe):
        if e.dono_id:
            ids.add(e.dono_id)
        ids |= {l.usuario_id for l in e.lideres}
    return ids


def membros(equipe: EquipeTarefas | None) -> set[int]:
    if equipe is None:
        return set()
    return {m.usuario_id for m in equipe.membros} | {l.usuario_id for l in equipe.lideres} | ({equipe.dono_id} if equipe.dono_id else set())


def envolvidos(tarefa: Tarefa) -> set[int]:
    ids = {p.usuario_id for p in tarefa.participantes}
    if tarefa.responsavel_id:
        ids.add(tarefa.responsavel_id)
    return ids


def eh_lider(sessao: Session, usuario: Usuario, tarefa: Tarefa) -> bool:
    if usuario.superusuario:
        return True
    if tarefa.equipe is None:
        # Tarefa pessoal: quem criou atua como liderança (valida, devolve, reabre)
        return usuario.id == tarefa.criado_por_id
    return usuario.id in lideranca(sessao, tarefa.equipe)


def pode_ver(sessao: Session, usuario: Usuario, tarefa: Tarefa) -> bool:
    return (
        usuario.superusuario or usuario.id in envolvidos(tarefa) or usuario.id == tarefa.criado_por_id
        or usuario.id in membros(tarefa.equipe) or eh_lider(sessao, usuario, tarefa)
    )


def pode_editar(sessao: Session, usuario: Usuario, tarefa: Tarefa) -> bool:
    return usuario.id in envolvidos(tarefa) or usuario.id == tarefa.criado_por_id or eh_lider(sessao, usuario, tarefa)


def acoes(sessao: Session, usuario: Usuario, tarefa: Tarefa) -> list[str]:
    """Ações que o usuário pode fazer agora (a tela mostra só essas)."""
    lider, editor = eh_lider(sessao, usuario, tarefa), pode_editar(sessao, usuario, tarefa)
    executor = usuario.id in envolvidos(tarefa) or lider
    s = tarefa.status
    lista: list[str] = []
    if editor and s != "concluida":
        lista += ["editar", "prazo", "transferir"]
    if editor:
        lista.append("comentar")
    if executor and s == "a_fazer":
        lista.append("iniciar")
    if executor and s == "em_andamento":
        lista += ["pausar", "entregar"]
    if lider and s == "em_validacao":
        lista += ["validar", "devolver"]
    if lider and s in OPERACIONAIS:
        lista.append("concluir")
    if lider and s == "concluida":
        lista.append("reabrir")
    if lider or usuario.id == tarefa.criado_por_id:
        lista.append("excluir")
    return lista


def _exigir(condicao: bool, detalhe: str) -> None:
    if not condicao:
        raise ErroTarefa(detalhe, 403, "sem_permissao")


def obter(sessao: Session, usuario: Usuario, numero: int) -> Tarefa:
    tarefa = sessao.scalar(select(Tarefa).where(Tarefa.numero == numero))
    if tarefa is None or not pode_ver(sessao, usuario, tarefa):
        # Sem permissão, responde como inexistente (não revela que a tarefa existe)
        raise ErroTarefa("Tarefa não encontrada.", 404, "nao_encontrado")
    return tarefa


# ---------------------------------------------------------------------------------------------
# Linha do tempo e avisos
# ---------------------------------------------------------------------------------------------

def _evento(sessao: Session, tarefa: Tarefa, tipo: str, autor: Usuario | None, titulo: str, texto: str = "", **dados) -> EventoTarefa:
    evento = EventoTarefa(tarefa_id=tarefa.id, tipo=tipo, autor_id=autor.id if autor else None, autor_nome=_nome(autor),
                          titulo=titulo, texto=texto, dados={k: v for k, v in dados.items() if v is not None}, criado_em=agora_utc())
    sessao.add(evento)
    return evento


def _link(tarefa: Tarefa) -> str:
    return f"/tarefas/{tarefa.numero}"


def _avisar(sessao: Session, ids: set[int], assunto: str, corpo: str, tarefa: Tarefa, chave: str, autor: Usuario | None = None,
            prioridade: str = "normal", categoria: str = "atribuicao", janela: bool = False) -> None:
    servico_mensagens.notificar(
        sessao, list(ids), assunto, corpo, chave=chave, categoria=categoria, prioridade=prioridade, link=_link(tarefa),
        email=True, autor=autor, abrir_em_janela=janela,
    )


def _rotulo(tarefa: Tarefa) -> str:
    return f"#{tarefa.numero} {tarefa.titulo}"


# ---------------------------------------------------------------------------------------------
# Cadastro e edição
# ---------------------------------------------------------------------------------------------

@dataclass
class DadosTarefa:
    titulo: str
    descricao: str
    prazo: datetime
    prioridade: str = "normal"
    equipe_id: uuid.UUID | None = None
    responsavel_id: int | None = None
    participantes_ids: tuple[int, ...] = ()
    marcadores_ids: tuple[uuid.UUID, ...] = ()


def _usuario_ativo(sessao: Session, usuario_id: int) -> Usuario:
    u = sessao.get(Usuario, usuario_id)
    if u is None or not u.ativo:
        raise ErroTarefa("Pessoa inexistente ou inativa.")
    return u


def _conferir_pessoas(sessao: Session, autor: Usuario, equipe: EquipeTarefas | None, ids: set[int]) -> None:
    """Numa equipe, responsável e participantes são da equipe (a liderança pode incluir qualquer usuário ativo)."""
    for i in ids:
        _usuario_ativo(sessao, i)
    if equipe is not None and not autor.superusuario and autor.id not in lideranca(sessao, equipe):
        fora = ids - membros(equipe)
        if fora:
            raise ErroTarefa("Só é possível atribuir a tarefa a membros da equipe. Peça à liderança para incluir outras pessoas.")


def _marcadores(sessao: Session, equipe: EquipeTarefas | None, ids: tuple[uuid.UUID, ...]) -> list[MarcadorTarefa]:
    lista = list(sessao.scalars(select(MarcadorTarefa).where(MarcadorTarefa.id.in_(ids)))) if ids else []
    for m in lista:
        if m.equipe_id is not None and (equipe is None or m.equipe_id != equipe.id):
            raise ErroTarefa(f"O marcador \"{m.nome}\" é de outra equipe.")
    return lista


def criar(sessao: Session, autor: Usuario, dados: DadosTarefa) -> Tarefa:
    equipe = sessao.get(EquipeTarefas, dados.equipe_id) if dados.equipe_id else None
    if dados.equipe_id and (equipe is None or not equipe.ativa):
        raise ErroTarefa("Equipe inexistente ou inativa.")
    if equipe is not None and not autor.superusuario:
        _exigir(autor.id in membros(equipe) or autor.id in lideranca(sessao, equipe), "Só membros e liderança da equipe cadastram tarefas nela.")
    responsavel = dados.responsavel_id or autor.id
    pessoas = {responsavel, *dados.participantes_ids}
    _conferir_pessoas(sessao, autor, equipe, pessoas)
    numero = (sessao.scalar(select(func.max(Tarefa.numero))) or 0) + 1
    tarefa = Tarefa(
        numero=numero, titulo=dados.titulo, descricao=dados.descricao, equipe_id=equipe.id if equipe else None, criado_por_id=autor.id,
        responsavel_id=responsavel, prazo=dados.prazo, prazo_original=dados.prazo, prioridade=dados.prioridade,
        ordem=-numero, criado_em=agora_utc(),
    )
    tarefa.equipe = equipe
    tarefa.participantes = [ParticipanteTarefa(usuario_id=i) for i in sorted(pessoas)]
    tarefa.marcadores = _marcadores(sessao, equipe, dados.marcadores_ids)
    sessao.add(tarefa)
    sessao.flush()
    _evento(sessao, tarefa, "criada", autor, "Tarefa criada", prazo=dados.prazo.isoformat(), responsavel=_nome(sessao.get(Usuario, responsavel)))
    _avisar(sessao, pessoas, f"Nova tarefa: {_rotulo(tarefa)}",
            f"{_nome(autor)} atribuiu a você a tarefa {_rotulo(tarefa)}, com prazo em {_data_hora(dados.prazo)} "
            f"(prioridade {ROTULOS_PRIORIDADE[dados.prioridade].lower()}).", tarefa, f"tarefa-criada:{tarefa.id}", autor=autor)
    auditar(sessao, autor.login, "tarefas.criar", _rotulo(tarefa), autor_id=autor.id, alvo_tipo="tarefa", alvo_id=tarefa.id)
    sessao.commit()
    return tarefa


def _versao(tarefa: Tarefa, versao: int | None) -> None:
    if versao is not None and versao != tarefa.versao:
        raise ErroTarefa("A tarefa foi alterada por outra pessoa. Recarregue a página e tente de novo.", 409, "conflito")


def editar(sessao: Session, autor: Usuario, tarefa: Tarefa, titulo: str, descricao: str, prioridade: str,
           participantes_ids: tuple[int, ...], marcadores_ids: tuple[uuid.UUID, ...], versao: int | None) -> Tarefa:
    _exigir(pode_editar(sessao, autor, tarefa) and tarefa.status != "concluida", "Você não pode editar esta tarefa.")
    _versao(tarefa, versao)
    novos = {tarefa.responsavel_id, *participantes_ids} - {None}
    _conferir_pessoas(sessao, autor, tarefa.equipe, novos - envolvidos(tarefa))
    mudancas = {}
    for campo, valor in (("titulo", titulo), ("descricao", descricao), ("prioridade", prioridade)):
        if getattr(tarefa, campo) != valor:
            mudancas[campo] = {"de": getattr(tarefa, campo), "para": valor}
            setattr(tarefa, campo, valor)
    antes = envolvidos(tarefa)
    if novos != antes:
        tarefa.participantes = [p for p in tarefa.participantes if p.usuario_id in novos] + [
            ParticipanteTarefa(usuario_id=i) for i in sorted(novos - antes)]
        entrou = novos - antes
        mudancas["participantes"] = {"entraram": sorted(_nome(sessao.get(Usuario, i)) for i in entrou),
                                     "sairam": sorted(_nome(sessao.get(Usuario, i)) for i in antes - novos)}
        if entrou:
            _avisar(sessao, entrou, f"Você entrou na tarefa {_rotulo(tarefa)}", f"{_nome(autor)} incluiu você como participante da tarefa {_rotulo(tarefa)}.",
                    tarefa, f"tarefa-participante:{tarefa.id}:{tarefa.versao}", autor=autor)
    marcadores = _marcadores(sessao, tarefa.equipe, marcadores_ids)
    if {m.id for m in marcadores} != {m.id for m in tarefa.marcadores}:
        mudancas["marcadores"] = {"de": sorted(m.nome for m in tarefa.marcadores), "para": sorted(m.nome for m in marcadores)}
        tarefa.marcadores = marcadores
    if mudancas:
        tarefa.versao += 1
        _evento(sessao, tarefa, "editada", autor, "Tarefa editada", campos=mudancas)
    sessao.commit()
    return tarefa


def alterar_prazo(sessao: Session, autor: Usuario, tarefa: Tarefa, novo: datetime, justificativa: str, versao: int | None) -> Tarefa:
    _exigir(pode_editar(sessao, autor, tarefa) and tarefa.status != "concluida", "Você não pode alterar o prazo desta tarefa.")
    _versao(tarefa, versao)
    if not justificativa.strip():
        raise ErroTarefa("Informe a justificativa da mudança de prazo.")
    anterior = tarefa.prazo
    if _comparavel(anterior) == _comparavel(novo):
        raise ErroTarefa("O novo prazo é igual ao atual.")
    tarefa.prazo, tarefa.versao = novo, tarefa.versao + 1
    _evento(sessao, tarefa, "prazo", autor, "Prazo alterado", justificativa.strip(), de=anterior.isoformat(), para=novo.isoformat())
    _avisar(sessao, envolvidos(tarefa), f"Prazo alterado: {_rotulo(tarefa)}",
            f"{_nome(autor)} alterou o prazo de {_data_hora(anterior)} para {_data_hora(novo)}.\n\nJustificativa: {justificativa.strip()}",
            tarefa, f"tarefa-prazo:{tarefa.id}:{tarefa.versao}", autor=autor)
    sessao.commit()
    return tarefa


# ---------------------------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------------------------

ACOES_PIPELINE = {
    "iniciar": ("a_fazer", "em_andamento"),
    "pausar": ("em_andamento", "a_fazer"),
    "entregar": ("em_andamento", "em_validacao"),
    "validar": ("em_validacao", "concluida"),
    "devolver": ("em_validacao", "em_andamento"),
    "concluir": (None, "concluida"),
    "reabrir": ("concluida", "em_andamento"),
}
EXIGEM_MOTIVO = ("devolver", "reabrir")


def mover(sessao: Session, autor: Usuario, tarefa: Tarefa, acao: str, texto: str = "", versao: int | None = None) -> Tarefa:
    if acao not in ACOES_PIPELINE:
        raise ErroTarefa("Ação desconhecida.")
    _versao(tarefa, versao)
    if acao not in acoes(sessao, autor, tarefa):
        de = ROTULOS_STATUS[tarefa.status]
        raise ErroTarefa(f"Não é possível \"{acao}\" esta tarefa agora (situação: {de}), ou você não tem permissão para isso.", 403, "sem_permissao")
    texto = (texto or "").strip()
    if acao in EXIGEM_MOTIVO and not texto:
        raise ErroTarefa("Informe o motivo.")
    de, para = tarefa.status, ACOES_PIPELINE[acao][1]
    # Tarefa sem equipe não passa por validação: a entrega já conclui
    if acao == "entregar" and tarefa.equipe is None:
        para = "concluida"
    agora = agora_utc()
    if tarefa.em_andamento_desde is not None:
        tarefa.segundos_em_andamento += max(0, int((agora - _comparavel(tarefa.em_andamento_desde)).total_seconds()))
        tarefa.em_andamento_desde = None
    if para == "em_andamento":
        tarefa.em_andamento_desde = agora
        tarefa.iniciada_em = tarefa.iniciada_em or agora
    if para == "em_validacao":
        tarefa.entregue_em = agora
    tarefa.concluida_em = agora if para == "concluida" else None
    tarefa.status, tarefa.versao = para, tarefa.versao + 1
    tipo = {"entregar": "entregue", "validar": "validada", "devolver": "devolvida", "reabrir": "reaberta"}.get(acao, "status")
    titulos = {
        "iniciar": "Tarefa iniciada", "pausar": "Tarefa voltou para A fazer", "entregar": "Entregue para validação",
        "validar": "Entrega validada: tarefa concluída", "devolver": "Entrega devolvida", "concluir": "Tarefa concluída pela liderança",
        "reabrir": "Tarefa reaberta",
    }
    if acao == "entregar" and para == "concluida":
        tipo, titulos["entregar"] = "status", "Tarefa concluída"
    _evento(sessao, tarefa, tipo, autor, titulos[acao], texto, de=de, para=para)
    _avisos_pipeline(sessao, autor, tarefa, acao, para, texto)
    sessao.commit()
    return tarefa


def _avisos_pipeline(sessao: Session, autor: Usuario, tarefa: Tarefa, acao: str, para: str, texto: str) -> None:
    executores = envolvidos(tarefa)
    lideres = lideranca(sessao, tarefa.equipe) if tarefa.equipe else ({tarefa.criado_por_id} - {None})
    prefixo_validacao = f"tarefa-validacao:{tarefa.id}:"
    if acao == "entregar" and para == "em_validacao":
        _avisar(sessao, lideres, f"Aguardando validação: {_rotulo(tarefa)}",
                f"{_nome(autor)} entregou a tarefa {_rotulo(tarefa)} para validação." + (f"\n\nComentário: {texto}" if texto else ""),
                tarefa, f"{prefixo_validacao}{tarefa.versao}", autor=autor, categoria="pendencia", prioridade="alta")
        return
    # Qualquer saída de "em validação" encerra os avisos de validação pendente
    servico_mensagens.encerrar(sessao, prefixo=prefixo_validacao)
    servico_mensagens.encerrar(sessao, prefixo=f"tarefa-validacao-parada:{tarefa.id}:")
    if acao == "validar":
        _avisar(sessao, executores, f"Entrega validada: {_rotulo(tarefa)}", f"{_nome(autor)} validou a entrega. A tarefa {_rotulo(tarefa)} está concluída.",
                tarefa, f"tarefa-validada:{tarefa.id}:{tarefa.versao}", autor=autor, categoria="comunicado")
    elif acao == "devolver":
        _avisar(sessao, executores, f"Entrega devolvida: {_rotulo(tarefa)}",
                f"{_nome(autor)} devolveu a tarefa {_rotulo(tarefa)} para ajustes.\n\nMotivo: {texto}",
                tarefa, f"tarefa-devolvida:{tarefa.id}:{tarefa.versao}", autor=autor, categoria="pendencia", prioridade="alta")
    elif acao == "reabrir":
        _avisar(sessao, executores, f"Tarefa reaberta: {_rotulo(tarefa)}", f"{_nome(autor)} reabriu a tarefa {_rotulo(tarefa)}.\n\nMotivo: {texto}",
                tarefa, f"tarefa-reaberta:{tarefa.id}:{tarefa.versao}", autor=autor, categoria="pendencia")
    elif acao in ("concluir",) or (acao == "entregar" and para == "concluida"):
        _avisar(sessao, executores | lideres, f"Tarefa concluída: {_rotulo(tarefa)}", f"{_nome(autor)} concluiu a tarefa {_rotulo(tarefa)}.",
                tarefa, f"tarefa-concluida:{tarefa.id}:{tarefa.versao}", autor=autor, categoria="comunicado")
    if para == "concluida":
        servico_mensagens.encerrar(sessao, prefixo=f"tarefa-prazo-aviso:{tarefa.id}:")


# ---------------------------------------------------------------------------------------------
# Transferência, comentários, checklist e exclusão
# ---------------------------------------------------------------------------------------------

def transferir(sessao: Session, autor: Usuario, tarefa: Tarefa, para_id: int, justificativa: str, novo_prazo: datetime | None,
               versao: int | None) -> Tarefa:
    _exigir("transferir" in acoes(sessao, autor, tarefa), "Você não pode transferir esta tarefa.")
    _versao(tarefa, versao)
    if not justificativa.strip():
        raise ErroTarefa("Informe a justificativa da transferência.")
    destino = _usuario_ativo(sessao, para_id)
    if destino.id == tarefa.responsavel_id:
        raise ErroTarefa("Essa pessoa já é a responsável.")
    lider = eh_lider(sessao, autor, tarefa)
    if tarefa.equipe is not None and not lider and destino.id not in membros(tarefa.equipe):
        raise ErroTarefa("Transferência só para membros da equipe. Para outra pessoa, peça à liderança.")
    anterior = sessao.get(Usuario, tarefa.responsavel_id) if tarefa.responsavel_id else None
    tarefa.participantes = [p for p in tarefa.participantes if p.usuario_id != tarefa.responsavel_id] + (
        [] if destino.id in envolvidos(tarefa) else [ParticipanteTarefa(usuario_id=destino.id)])
    tarefa.responsavel_id = destino.id
    prazo_anterior = tarefa.prazo
    if novo_prazo is not None and _comparavel(novo_prazo) != _comparavel(tarefa.prazo):
        tarefa.prazo = novo_prazo
    tarefa.versao += 1
    _evento(sessao, tarefa, "transferida", autor, f"Transferida de {_nome(anterior)} para {_nome(destino)}", justificativa.strip(),
            de=_nome(anterior), para=_nome(destino), prazo_de=prazo_anterior.isoformat() if tarefa.prazo != prazo_anterior else None,
            prazo_para=tarefa.prazo.isoformat() if tarefa.prazo != prazo_anterior else None)
    _avisar(sessao, {destino.id}, f"Tarefa transferida para você: {_rotulo(tarefa)}",
            f"{_nome(autor)} transferiu a você a tarefa {_rotulo(tarefa)} (prazo {_data_hora(tarefa.prazo)}).\n\nJustificativa: {justificativa.strip()}",
            tarefa, f"tarefa-transferida:{tarefa.id}:{tarefa.versao}", autor=autor)
    sessao.commit()
    return tarefa


def comentar(sessao: Session, autor: Usuario, tarefa: Tarefa, texto: str, arquivos: list[tuple[str, BinaryIO]]) -> EventoTarefa:
    _exigir("comentar" in acoes(sessao, autor, tarefa), "Você não pode comentar nesta tarefa.")
    texto = (texto or "").strip()
    if not texto and not arquivos:
        raise ErroTarefa("Escreva um comentário ou anexe um arquivo.")
    if len(arquivos) > MAXIMO_ANEXOS:
        raise ErroTarefa(f"Envie no máximo {MAXIMO_ANEXOS} arquivos por vez.")
    titulo = "Comentário" if texto else ("Anexo" if len(arquivos) == 1 else f"{len(arquivos)} anexos")
    evento = _evento(sessao, tarefa, "comentario", autor, titulo, texto)
    sessao.flush()
    try:
        for nome, conteudo in arquivos:
            anexo = servico_anexos.guardar_arquivo(sessao, conteudo, nome, "tarefa-comentario", autor.id)
            sessao.add(AnexoEventoTarefa(evento_id=evento.id, anexo_id=anexo.id))
    except servico_anexos.ErroAnexo as erro:
        sessao.rollback()
        raise ErroTarefa(str(erro)) from erro
    tarefa.atualizado_em = agora_utc()
    outros = (envolvidos(tarefa) | ({tarefa.criado_por_id} - {None}))
    resumo = texto[:300] + ("…" if len(texto) > 300 else "") if texto else f"{len(arquivos)} arquivo(s) anexado(s)."
    _avisar(sessao, outros, f"Novo comentário em {_rotulo(tarefa)}", f"{_nome(autor)} comentou:\n\n{resumo}",
            tarefa, f"tarefa-comentario:{evento.id}", autor=autor, categoria="comunicado")
    sessao.commit()
    return evento


def remover_evento(sessao: Session, autor: Usuario, tarefa: Tarefa, evento_id: uuid.UUID, motivo: str) -> EventoTarefa:
    _exigir(autor.superusuario, "Só um SuperRoot remove itens da linha do tempo.")
    evento = sessao.get(EventoTarefa, evento_id)
    if evento is None or evento.tarefa_id != tarefa.id:
        raise ErroTarefa("Evento não encontrado.", 404, "nao_encontrado")
    if not motivo.strip():
        raise ErroTarefa("Informe o motivo da remoção.")
    evento.removido_em, evento.removido_por_nome, evento.motivo_remocao = agora_utc(), _nome(autor), motivo.strip()
    for vinculo in evento.anexos:
        servico_anexos.descartar(vinculo.anexo)
    _evento(sessao, tarefa, "removido", autor, "Item da linha do tempo removido", motivo.strip(), evento=str(evento.id))
    sessao.commit()
    return evento


def checklist(sessao: Session, autor: Usuario, tarefa: Tarefa, acao: str, texto: str = "", item_id: uuid.UUID | None = None) -> Tarefa:
    _exigir(pode_editar(sessao, autor, tarefa), "Você não pode alterar o checklist desta tarefa.")
    if acao == "incluir":
        if not texto.strip():
            raise ErroTarefa("Escreva o item.")
        tarefa.checklist.append(ItemChecklistTarefa(texto=texto.strip()[:300], posicao=len(tarefa.checklist)))
        descricao = f"Item incluído: {texto.strip()}"
    else:
        item = next((i for i in tarefa.checklist if i.id == item_id), None)
        if item is None:
            raise ErroTarefa("Item não encontrado.", 404, "nao_encontrado")
        if acao == "marcar":
            item.concluido_em = None if item.concluido_em else agora_utc()
            descricao = f"Item {'concluído' if item.concluido_em else 'reaberto'}: {item.texto}"
        else:
            tarefa.checklist.remove(item)
            descricao = f"Item removido: {item.texto}"
    _evento(sessao, tarefa, "checklist", autor, descricao)
    sessao.commit()
    return tarefa


def excluir(sessao: Session, autor: Usuario, tarefa: Tarefa) -> None:
    _exigir("excluir" in acoes(sessao, autor, tarefa), "Só quem criou a tarefa ou a liderança pode excluí-la.")
    for prefixo in ("tarefa-", ):
        servico_mensagens.encerrar(sessao, prefixo=f"{prefixo}validacao:{tarefa.id}:")
    auditar(sessao, autor.login, "tarefas.excluir", _rotulo(tarefa), autor_id=autor.id, alvo_tipo="tarefa", alvo_id=tarefa.id)
    sessao.delete(tarefa)
    sessao.commit()


# ---------------------------------------------------------------------------------------------
# Carga, listas e indicadores
# ---------------------------------------------------------------------------------------------

def carga(tarefa: Tarefa, agora: datetime) -> float:
    """Peso da prioridade × urgência do prazo (só a fazer e em andamento)."""
    if tarefa.status not in OPERACIONAIS:
        return 0.0
    dias = (_comparavel(tarefa.prazo) - agora).total_seconds() / 86400
    urgencia = 4 if dias < 0 else 3 if dias < 3 else 2 if dias <= 7 else 1.5 if dias <= 15 else 1
    return PESOS[tarefa.prioridade] * urgencia


def faixa(pontos: float) -> str:
    return "Baixa ocupação" if pontos <= 20 else "Ocupação moderada" if pontos <= 40 else "Alta ocupação" if pontos <= 60 else "Sobrecarga crítica"


def indicadores(tarefas: list[Tarefa], agora: datetime, usuario_id: int | None = None) -> dict:
    """Totais para os cartões. Com `usuario_id`, a carga é a dessa pessoa (tarefas em que está envolvida)."""
    hoje = agora.astimezone(__import__("zoneinfo").ZoneInfo("America/Sao_Paulo")).date()
    operacionais = [t for t in tarefas if t.status in OPERACIONAIS]
    def local(d):  # noqa: E306
        return _comparavel(d).astimezone(__import__("zoneinfo").ZoneInfo("America/Sao_Paulo")).date()
    pontos = sum(carga(t, agora) for t in tarefas if usuario_id is None or usuario_id in envolvidos(t))
    return {
        "operacionais": len(operacionais),
        "atrasadas": sum(1 for t in operacionais if _comparavel(t.prazo) < agora),
        "vencem_hoje": sum(1 for t in operacionais if local(t.prazo) == hoje and _comparavel(t.prazo) >= agora),
        "criticas": sum(1 for t in operacionais if t.prioridade == "critica"),
        "em_validacao": sum(1 for t in tarefas if t.status == "em_validacao"),
        "concluidas": sum(1 for t in tarefas if t.status == "concluida"),
        "carga": round(pontos, 1),
        "faixa": faixa(pontos),
    }


def equipes_visiveis(sessao: Session, usuario: Usuario) -> list[EquipeTarefas]:
    """Equipes em que a pessoa é membro ou liderança (e as abaixo das que lidera); SuperRoot vê todas."""
    todas = list(sessao.scalars(select(EquipeTarefas).where(EquipeTarefas.ativa.is_(True)).order_by(EquipeTarefas.nome)))
    if usuario.superusuario:
        return todas
    return [e for e in todas if usuario.id in membros(e) or usuario.id in lideranca(sessao, e)]


def equipes_lideradas(sessao: Session, usuario: Usuario) -> list[EquipeTarefas]:
    return [e for e in equipes_visiveis(sessao, usuario) if usuario.superusuario or usuario.id in lideranca(sessao, e)]


def minhas(sessao: Session, usuario: Usuario) -> list[Tarefa]:
    """Tarefas em que a pessoa está envolvida ou que criou."""
    envolvida = select(ParticipanteTarefa.tarefa_id).where(ParticipanteTarefa.usuario_id == usuario.id)
    return list(sessao.scalars(select(Tarefa).where(or_(Tarefa.id.in_(envolvida), Tarefa.criado_por_id == usuario.id, Tarefa.responsavel_id == usuario.id))))


def agenda(sessao: Session, pessoa: Usuario, de: datetime, ate: datetime) -> list[Tarefa]:
    """Tarefas em que a pessoa está envolvida (responsável ou participante) para o painel de atribuição.

    Entram todas as abertas (a fazer, em andamento e em validação), qualquer que seja o prazo, e as
    concluídas dentro do período. Por decisão do usuário, quem atribui vê o título de todas elas.
    """
    envolvida = select(ParticipanteTarefa.tarefa_id).where(ParticipanteTarefa.usuario_id == pessoa.id)
    consulta = select(Tarefa).where(
        or_(Tarefa.id.in_(envolvida), Tarefa.responsavel_id == pessoa.id),
        or_(Tarefa.status != "concluida", Tarefa.concluida_em.between(de, ate)),
    )
    return sorted(sessao.scalars(consulta), key=lambda t: (_comparavel(t.prazo), t.numero))


def da_equipe(sessao: Session, usuario: Usuario, equipe_id: uuid.UUID) -> tuple[EquipeTarefas, list[Tarefa]]:
    equipe = sessao.get(EquipeTarefas, equipe_id)
    if equipe is None or equipe not in equipes_visiveis(sessao, usuario):
        raise ErroTarefa("Equipe não encontrada.", 404, "nao_encontrado")
    ids = [e.id for e in _com_subequipes(sessao, equipe)] if (usuario.superusuario or usuario.id in lideranca(sessao, equipe)) else [equipe.id]
    return equipe, list(sessao.scalars(select(Tarefa).where(Tarefa.equipe_id.in_(ids))))


def _com_subequipes(sessao: Session, equipe: EquipeTarefas) -> list[EquipeTarefas]:
    todas = list(sessao.scalars(select(EquipeTarefas)))
    resultado, fila = [equipe], [equipe.id]
    while fila:
        pai = fila.pop()
        for e in todas:
            if e.equipe_pai_id == pai and e not in resultado:
                resultado.append(e)
                fila.append(e.id)
    return resultado


def da_pessoa(sessao: Session, usuario: Usuario, pessoa: Usuario) -> list[Tarefa]:
    """Tarefas de uma pessoa, vistas por ela mesma, pelo SuperRoot ou pela liderança (só as das equipes lideradas)."""
    tarefas = minhas(sessao, pessoa)
    if usuario.superusuario or usuario.id == pessoa.id:
        return tarefas
    visiveis = [t for t in tarefas if t.equipe is not None and usuario.id in lideranca(sessao, t.equipe)]
    if not visiveis and not any(pessoa.id in membros(e) for e in equipes_lideradas(sessao, usuario)):
        raise ErroTarefa("Pessoa fora das equipes que você lidera.", 403, "sem_permissao")
    return visiveis


def carga_das_pessoas(sessao: Session, ids: set[int], agora: datetime) -> dict[int, dict]:
    """Carga e contagens por pessoa (seletor de responsável e visão da liderança)."""
    resultado = {i: {"carga": 0.0, "a_fazer": 0, "em_andamento": 0, "atrasadas": 0} for i in ids}
    if not ids:
        return resultado
    linhas = sessao.execute(select(ParticipanteTarefa.usuario_id, Tarefa).join(Tarefa, Tarefa.id == ParticipanteTarefa.tarefa_id)
                            .where(ParticipanteTarefa.usuario_id.in_(ids), Tarefa.status.in_(OPERACIONAIS)))
    for usuario_id, tarefa in linhas:
        r = resultado[usuario_id]
        r["carga"] += carga(tarefa, agora)
        r[tarefa.status] += 1
        r["atrasadas"] += int(_comparavel(tarefa.prazo) < agora)
    for r in resultado.values():
        r["carga"] = round(r["carga"], 1)
        r["faixa"] = faixa(r["carga"])
    return resultado


# ---------------------------------------------------------------------------------------------
# Lembretes diários (timer das 07:00)
# ---------------------------------------------------------------------------------------------

def lembrar(sessao: Session, dia: date) -> dict[str, int]:
    """Vence amanhã e atrasadas → envolvidos; validação parada há 2+ dias → liderança (janela que não bloqueia)."""
    agora = agora_utc()
    contagem = {"vencem_amanha": 0, "atrasadas": 0, "validacao_parada": 0}
    for tarefa in sessao.scalars(select(Tarefa).where(Tarefa.status.in_(OPERACIONAIS))):
        prazo = _comparavel(tarefa.prazo).astimezone(__import__("zoneinfo").ZoneInfo("America/Sao_Paulo")).date()
        if prazo == dia + timedelta(days=1):
            _avisar(sessao, envolvidos(tarefa), f"Vence amanhã: {_rotulo(tarefa)}", f"A tarefa {_rotulo(tarefa)} vence amanhã, {_data_hora(tarefa.prazo)}.",
                    tarefa, f"tarefa-prazo-aviso:{tarefa.id}:amanha:{prazo}", categoria="prazo")
            contagem["vencem_amanha"] += 1
        elif prazo < dia:
            _avisar(sessao, envolvidos(tarefa), f"Tarefa atrasada: {_rotulo(tarefa)}",
                    f"A tarefa {_rotulo(tarefa)} passou do prazo ({_data_hora(tarefa.prazo)}). Atualize o andamento ou peça nova data.",
                    tarefa, f"tarefa-prazo-aviso:{tarefa.id}:atrasada:{dia}", categoria="prazo", prioridade="alta")
            contagem["atrasadas"] += 1
    limite = agora - timedelta(days=DIAS_VALIDACAO_PARADA)
    for tarefa in sessao.scalars(select(Tarefa).where(Tarefa.status == "em_validacao", Tarefa.entregue_em <= limite)):
        lideres = lideranca(sessao, tarefa.equipe) if tarefa.equipe else ({tarefa.criado_por_id} - {None})
        _avisar(sessao, lideres, f"Validação pendente há {DIAS_VALIDACAO_PARADA}+ dias: {_rotulo(tarefa)}",
                f"A entrega da tarefa {_rotulo(tarefa)} aguarda sua validação desde {_data_hora(tarefa.entregue_em)}. Valide ou devolva com o motivo.",
                tarefa, f"tarefa-validacao-parada:{tarefa.id}:{tarefa.versao}", categoria="pendencia", prioridade="alta", janela=True)
        contagem["validacao_parada"] += 1
    sessao.commit()
    return contagem


# ---------------------------------------------------------------------------------------------
# Equipes, marcadores e ordem
# ---------------------------------------------------------------------------------------------

def pode_configurar(usuario: Usuario, equipe: EquipeTarefas) -> bool:
    """Composição da equipe: dono ou SuperRoot."""
    return usuario.superusuario or equipe.dono_id == usuario.id


def salvar_equipe(sessao: Session, autor: Usuario, equipe_id: uuid.UUID | None, nome: str, equipe_pai_id: uuid.UUID | None,
                  lideres_ids: list[int], membros_ids: list[int]) -> EquipeTarefas:
    """Cria (quem cria é o dono) ou altera a equipe (dono ou SuperRoot)."""
    if equipe_id is None:
        equipe = EquipeTarefas(nome=nome, dono_id=autor.id, criado_em=agora_utc())
        sessao.add(equipe)
    else:
        equipe = sessao.get(EquipeTarefas, equipe_id)
        if equipe is None or not equipe.ativa:
            raise ErroTarefa("Equipe não encontrada.", 404, "nao_encontrado")
        _exigir(pode_configurar(autor, equipe), "Só o dono da equipe (ou um SuperRoot) altera a composição.")
        equipe.nome = nome
    if equipe_pai_id is not None:
        pai = sessao.get(EquipeTarefas, equipe_pai_id)
        if pai is None:
            raise ErroTarefa("Equipe superior inexistente.")
        if equipe.id is not None and any(e.id == equipe.id for e in cadeia_equipes(sessao, pai)):
            raise ErroTarefa("Uma equipe não pode ficar abaixo dela mesma.")
    equipe.equipe_pai_id = equipe_pai_id
    for i in set(lideres_ids) | set(membros_ids):
        _usuario_ativo(sessao, i)
    equipe.lideres = [LiderEquipeTarefas(usuario_id=i) for i in sorted(set(lideres_ids))]
    equipe.membros = [MembroEquipeTarefas(usuario_id=i) for i in sorted(set(membros_ids) - set(lideres_ids))]
    sessao.flush()
    auditar(sessao, autor.login, "tarefas.equipe", nome, autor_id=autor.id, alvo_tipo="tarefa-equipe", alvo_id=equipe.id,
            dados={"lideres": sorted(set(lideres_ids)), "membros": sorted(set(membros_ids))})
    sessao.commit()
    return equipe


def excluir_equipe(sessao: Session, autor: Usuario, equipe_id: uuid.UUID) -> None:
    """Desativa a equipe (as tarefas continuam, sem equipe ativa para novas)."""
    equipe = sessao.get(EquipeTarefas, equipe_id)
    if equipe is None or not equipe.ativa:
        raise ErroTarefa("Equipe não encontrada.", 404, "nao_encontrado")
    _exigir(pode_configurar(autor, equipe), "Só o dono da equipe (ou um SuperRoot) exclui a equipe.")
    if sessao.scalar(select(func.count()).select_from(Tarefa).where(Tarefa.equipe_id == equipe.id, Tarefa.status != "concluida")):
        raise ErroTarefa("A equipe ainda tem tarefas em aberto. Conclua ou transfira antes de excluir.")
    equipe.ativa = False
    auditar(sessao, autor.login, "tarefas.equipe.excluir", equipe.nome, autor_id=autor.id, alvo_tipo="tarefa-equipe", alvo_id=equipe.id)
    sessao.commit()


def salvar_marcador(sessao: Session, autor: Usuario, equipe_id: uuid.UUID, nome: str, cor: str, marcador_id: uuid.UUID | None = None) -> MarcadorTarefa:
    """Marcadores são da equipe e criados pela liderança."""
    equipe = sessao.get(EquipeTarefas, equipe_id)
    if equipe is None:
        raise ErroTarefa("Equipe não encontrada.", 404, "nao_encontrado")
    _exigir(autor.superusuario or autor.id in lideranca(sessao, equipe), "Só a liderança da equipe cria marcadores.")
    marcador = sessao.get(MarcadorTarefa, marcador_id) if marcador_id else MarcadorTarefa(equipe_id=equipe.id)
    if marcador is None or marcador.equipe_id != equipe.id:
        raise ErroTarefa("Marcador não encontrado.", 404, "nao_encontrado")
    repetido = sessao.scalar(select(MarcadorTarefa).where(MarcadorTarefa.equipe_id == equipe.id, func.lower(MarcadorTarefa.nome) == nome.lower()))
    if repetido is not None and repetido.id != marcador.id:
        raise ErroTarefa("Já existe um marcador com esse nome na equipe.", 409, "conflito")
    marcador.nome, marcador.cor = nome, cor
    sessao.add(marcador)
    sessao.commit()
    return marcador


def excluir_marcador(sessao: Session, autor: Usuario, marcador_id: uuid.UUID) -> None:
    marcador = sessao.get(MarcadorTarefa, marcador_id)
    if marcador is None:
        raise ErroTarefa("Marcador não encontrado.", 404, "nao_encontrado")
    equipe = sessao.get(EquipeTarefas, marcador.equipe_id) if marcador.equipe_id else None
    _exigir(autor.superusuario or (equipe is not None and autor.id in lideranca(sessao, equipe)), "Só a liderança da equipe exclui marcadores.")
    sessao.delete(marcador)
    sessao.commit()


def reordenar(sessao: Session, autor: Usuario, numeros: list[int]) -> None:
    """Nova ordem manual (arrastar): só tarefas que a pessoa pode editar; as demais são ignoradas."""
    tarefas = {t.numero: t for t in sessao.scalars(select(Tarefa).where(Tarefa.numero.in_(numeros)))}
    for posicao, numero in enumerate(numeros):
        tarefa = tarefas.get(numero)
        if tarefa is not None and pode_editar(sessao, autor, tarefa):
            tarefa.ordem = posicao
    sessao.commit()
