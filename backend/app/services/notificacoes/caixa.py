# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras das notificações: envio, caixa de entrada, ciência, avisos automáticos e e-mail.
"""Notificações internas (caixa de notificações de cada usuário).

- **Avulsa:** qualquer usuário autenticado envia para usuários; setores inteiros exigem SuperRoot ou ACL
  `notificacoes-setores` ≥ CONTROLE_TOTAL. Setores viram a lista de membros e ninguém recebe duas vezes.
- **Automática:** `notificar` é o ponto único usado pelos módulos (contratos, lembretes). A `chave`
  impede repetir o mesmo aviso para o mesmo destinatário; `encerrar` resolve avisos de pendência quando
  a ação é feita no sistema.
- **Estados da entrega:** entregue → visualizada (ao abrir) → ciente ("Li e estou ciente") ou encerrada
  (pendência resolvida). Nenhuma mensagem bloqueia a navegação.
- **E-mail (opcional):** usa o servidor SMTP ativo e o e-mail do perfil; o resultado fica na entrega.

Este módulo não importa serviços de contratos (eles é que chamam `notificar`), para não criar ciclos.
"""

import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import FabricaSessao, agora_utc
from app.core.configuracao import obter_configuracao
from app.models.acl import NivelAcl
from app.models.notificacao import EntregaNotificacao, Notificacao
from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario
from app.services.notificacoes import despacho, preferencias
from app.services.notificacoes.catalogo import EVENTOS
from app.services.notificacoes.layout_email import html_email, html_mensagem, previa_mensagem  # noqa: F401 - reexportados pelo pacote
from app.services.servico_acl import resolver_acesso
from app.services.servico_auditoria import auditar

RECURSO_SETORES = "notificacoes-setores"
ROTULOS_PRIORIDADE = {"baixa": "Baixa", "normal": "Normal", "alta": "Alta", "critica": "Crítica"}
ROTULOS_CATEGORIA = {
    "comunicado": "Comunicado", "prazo": "Prazo", "pendencia": "Pendência", "revisao": "Revisão",
    "atribuicao": "Atribuição", "indisponibilidade": "Indisponibilidade", "normativo": "Normativo",
}


class ErroNotificacao(Exception):
    """Regra das notificações violada; `status` é o código HTTP e `codigo` o código do erro da API."""

    def __init__(self, detalhe: str, status: int = 400, codigo: str = "invalido") -> None:
        super().__init__(detalhe)
        self.status, self.codigo = status, codigo


@dataclass
class DadosEnvio:
    """Notificacao avulsa a enviar (já validada pelo schema)."""
    assunto: str
    corpo: str
    prioridade: str
    categoria: str
    usuarios_ids: list[int]
    setores_ids: list[int]
    expira_em: datetime | None
    link: str | None


def _nome(usuario: Usuario) -> str:
    return usuario.nome_completo or usuario.login


def _normalizar(texto: str) -> str:
    """Minúsculas sem acentos, para a busca ("Medição" encontra "medicao")."""
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def _agora_comparavel(valor: datetime | None) -> datetime | None:
    """Datas do SQLite voltam sem fuso: compara tudo em UTC sem fuso."""
    return valor.replace(tzinfo=None) if valor is not None and valor.tzinfo else valor


def _ativa(entrega: EntregaNotificacao, agora: datetime) -> bool:
    """A mensagem ainda não expirou."""
    expira = _agora_comparavel(entrega.notificacao.expira_em)
    return expira is None or expira > _agora_comparavel(agora)


def pendente(entrega: EntregaNotificacao) -> bool:
    """Sem ciência e sem encerramento automático."""
    return entrega.ciente_em is None and entrega.encerrada_em is None


# ---------------------------------------------------------------------------------------------
# Envio
# ---------------------------------------------------------------------------------------------

def pode_enviar_setores(sessao: Session, usuario: Usuario) -> bool:
    """SuperRoot ou CONTROLE_TOTAL no recurso `notificacoes-setores`."""
    return resolver_acesso(sessao, usuario, RECURSO_SETORES) == NivelAcl.CONTROLE_TOTAL


def _publicar(sessao: Session, notificacao: Notificacao, destinatarios: list[Usuario], *, evento: str, forcar_email: bool = False) -> list[EntregaNotificacao]:
    """Cria uma entrega (com a fotografia do texto e os canais escolhidos por cada destinatário) e agenda o despacho depois do commit."""
    notificacao.evento = evento
    notificacao.id = notificacao.id or uuid.uuid4()
    canais = preferencias.canais_por_destinatario(
        sessao, [u.id for u in destinatarios], evento, contrato_id=notificacao.contrato_id, tarefa_id=notificacao.tarefa_id, agora=notificacao.publicada_em,
    )
    if forcar_email:
        # Aviso institucional que sai por e-mail para todos, sem depender da preferência (ex.: parabéns de aniversário)
        for c in canais.values():
            c.email, c.email_resumo = True, False
    entregas = [
        EntregaNotificacao(
            id=uuid.uuid4(), destinatario_id=u.id, assunto_copia=notificacao.assunto, corpo_copia=notificacao.corpo, entregue_em=notificacao.publicada_em,
            canal_email=canais[u.id].email, canal_navegador=canais[u.id].navegador, canal_desktop=canais[u.id].desktop, email_resumo=canais[u.id].email_resumo,
        )
        for u in destinatarios
    ]
    notificacao.entregas.extend(entregas)
    sessao.add(notificacao)
    if any(e.canal_email or e.canal_navegador for e in entregas):
        despacho.agendar(sessao, notificacao.id)
    return entregas


def enviar_avulsa(sessao: Session, dados: DadosEnvio, autor: Usuario) -> Notificacao:
    """Notificacao escrita por um usuário para usuários e (com permissão) setores."""
    if dados.setores_ids and not pode_enviar_setores(sessao, autor):
        raise ErroNotificacao("Você não tem permissão para enviar mensagens para setores inteiros.", 403, "acl_negado")
    if dados.expira_em is not None and _agora_comparavel(dados.expira_em) <= _agora_comparavel(agora_utc()):
        raise ErroNotificacao("A data de expiração deve estar no futuro.")
    ids = set(dados.usuarios_ids)
    if dados.setores_ids:
        ids |= set(sessao.scalars(select(MembroSetor.usuario_id).where(MembroSetor.setor_id.in_(dados.setores_ids))))
    destinatarios = list(sessao.scalars(select(Usuario).where(Usuario.id.in_(ids), Usuario.ativo.is_(True)))) if ids else []
    if not destinatarios:
        raise ErroNotificacao("Selecione ao menos um destinatário ativo.")
    mensagem = Notificacao(
        assunto=dados.assunto, corpo=dados.corpo, prioridade=dados.prioridade, categoria=dados.categoria,
        autor_id=autor.id, autor_nome=_nome(autor), publicada_em=agora_utc(), expira_em=dados.expira_em,
        link=dados.link, origem="avulsa",
    )
    _publicar(sessao, mensagem, destinatarios, evento="comunicados.mensagem")
    auditar(sessao, autor.login, "notificacao.enviar", dados.assunto, autor_id=autor.id, alvo_tipo="notificacao", alvo_id=mensagem.id,
            dados={"destinatarios": len(destinatarios), "setores": dados.setores_ids})
    sessao.commit()
    return mensagem


def notificar(
    sessao: Session, destinatarios_ids: list[int], assunto: str, corpo: str, *, chave: str, categoria: str = "comunicado",
    prioridade: str = "normal", link: str | None = None, contrato_id: uuid.UUID | None = None, tarefa_id: uuid.UUID | None = None,
    abrir_em_janela: bool = False, autor: Usuario | None = None, evento: str, forcar_email: bool = False,
) -> Notificacao | None:
    """Aviso automático (sem commit: grava junto com a operação que o originou).

    Não repete a `chave` para quem já recebeu e não avisa o próprio autor da ação (exceto janelas).
    `evento` é obrigatório e precisa existir no catálogo (`catalogo.EVENTOS`): é por ele que cada pessoa escolhe os canais (e-mail, navegador,
    desktop). A caixa recebe sempre. `forcar_email=True` faz o e-mail sair para todos os destinatários, sem depender da preferência (só para avisos institucionais, como o parabéns). Devolve a notificação criada, ou None se ninguém precisar receber.
    """
    if evento not in EVENTOS:
        raise ErroNotificacao(f"Evento de notificação desconhecido: {evento!r}. Cadastre-o em notificacoes/catalogo.py.", 500, "evento_desconhecido")
    ids = {i for i in destinatarios_ids if i is not None}
    if autor is not None and not abrir_em_janela:
        ids.discard(autor.id)
    if not ids:
        return None
    ja_receberam = set(sessao.scalars(
        select(EntregaNotificacao.destinatario_id).join(Notificacao).where(Notificacao.chave == chave, EntregaNotificacao.destinatario_id.in_(ids))
    ))
    # Mensagens ainda pendentes na sessão (mesma transação) também contam
    for obj in sessao.new:
        if isinstance(obj, Notificacao) and obj.chave == chave:
            ja_receberam |= {e.destinatario_id for e in obj.entregas}
    ids -= ja_receberam
    destinatarios = list(sessao.scalars(select(Usuario).where(Usuario.id.in_(ids), Usuario.ativo.is_(True)))) if ids else []
    if not destinatarios:
        return None
    mensagem = Notificacao(
        assunto=assunto[:300], corpo=corpo, prioridade=prioridade, categoria=categoria,
        autor_id=None, autor_nome="Sistema", publicada_em=agora_utc(), link=link, origem="automatica",
        chave=chave, contrato_id=contrato_id, tarefa_id=tarefa_id, abrir_em_janela=abrir_em_janela,
    )
    _publicar(sessao, mensagem, destinatarios, evento=evento, forcar_email=forcar_email)
    return mensagem


def encerrar(sessao: Session, *, chave: str | None = None, prefixo: str | None = None) -> int:
    """Encerra (sem exigir ciência) as entregas pendentes dos avisos com a chave ou o prefixo informado."""
    consulta = select(EntregaNotificacao).join(Notificacao).where(EntregaNotificacao.ciente_em.is_(None), EntregaNotificacao.encerrada_em.is_(None))
    if chave is not None:
        consulta = consulta.where(Notificacao.chave == chave)
    elif prefixo is not None:
        consulta = consulta.where(Notificacao.chave.startswith(prefixo, autoescape=True))
    else:
        return 0
    agora = agora_utc()
    entregas = list(sessao.scalars(consulta))
    for entrega in entregas:
        entrega.encerrada_em = agora
    return len(entregas)


# ---------------------------------------------------------------------------------------------
# Caixa de entrada
# ---------------------------------------------------------------------------------------------

def _na_caixa(entrega: EntregaNotificacao, limite: datetime) -> bool:
    """Pendente fica sempre; ciente ou encerrada há mais de N meses sai da caixa (continua no banco, para auditoria)."""
    if pendente(entrega):
        return True
    resolvida = max(d for d in (_agora_comparavel(entrega.ciente_em), _agora_comparavel(entrega.encerrada_em)) if d is not None)
    return resolvida >= _agora_comparavel(limite)


def _entregas_do_usuario(sessao: Session, usuario: Usuario, *, somente_desktop: bool = False) -> list[EntregaNotificacao]:
    """Entregas não expiradas do usuário (e ainda na caixa), da mais recente para a mais antiga.

    `somente_desktop` serve ao cliente Windows (SGI Alertas): só as entregas em que a pessoa ligou o canal Desktop.
    """
    consulta = select(EntregaNotificacao).where(EntregaNotificacao.destinatario_id == usuario.id)
    if somente_desktop:
        consulta = consulta.where(EntregaNotificacao.canal_desktop.is_(True))
    entregas = sessao.scalars(consulta.options(selectinload(EntregaNotificacao.notificacao)).order_by(EntregaNotificacao.entregue_em.desc()))
    agora = agora_utc()
    limite = agora - timedelta(days=30 * obter_configuracao().notificacoes_meses_na_caixa)
    return [e for e in entregas if _ativa(e, agora) and _na_caixa(e, limite)]


def resumo(sessao: Session, usuario: Usuario, *, somente_desktop: bool = False) -> tuple[int, int, EntregaNotificacao | None]:
    """(pendentes, não lidas, próxima janela a abrir)."""
    entregas = _entregas_do_usuario(sessao, usuario, somente_desktop=somente_desktop)
    janelas = [e for e in entregas if e.notificacao.abrir_em_janela and e.visualizada_em is None and pendente(e)]
    return (
        sum(1 for e in entregas if pendente(e)),
        sum(1 for e in entregas if e.visualizada_em is None),
        min(janelas, key=lambda e: e.entregue_em) if janelas else None,
    )


def listar(sessao: Session, usuario: Usuario, estado: str, busca: str, pagina: int, tamanho: int, *, somente_desktop: bool = False) -> tuple[list[EntregaNotificacao], int]:
    """Caixa de entrada filtrada (pendentes, cientes ou todas) e pesquisada sem diferenciar acentos."""
    entregas = _entregas_do_usuario(sessao, usuario, somente_desktop=somente_desktop)
    if estado == "pendentes":
        entregas = [e for e in entregas if pendente(e)]
    elif estado == "cientes":
        entregas = [e for e in entregas if not pendente(e)]
    termo = _normalizar(busca.strip())
    if termo:
        entregas = [e for e in entregas if termo in _normalizar(f"{e.assunto_copia} {e.corpo_copia} {e.notificacao.autor_nome}")]
    inicio = (pagina - 1) * tamanho
    return entregas[inicio:inicio + tamanho], len(entregas)


def _entrega(sessao: Session, usuario: Usuario, entrega_id: uuid.UUID) -> EntregaNotificacao:
    """Entrega do próprio usuário; de outra pessoa (ou inexistente) é 404."""
    entrega = sessao.scalar(
        select(EntregaNotificacao).where(EntregaNotificacao.id == entrega_id, EntregaNotificacao.destinatario_id == usuario.id)
        .options(selectinload(EntregaNotificacao.notificacao))
    )
    if entrega is None:
        raise ErroNotificacao("Notificacao não encontrada.", 404, "nao_encontrado")
    return entrega


def abrir(sessao: Session, usuario: Usuario, entrega_id: uuid.UUID) -> EntregaNotificacao:
    """Abre a mensagem e registra a primeira visualização."""
    entrega = _entrega(sessao, usuario, entrega_id)
    if entrega.visualizada_em is None:
        entrega.visualizada_em = agora_utc()
        sessao.commit()
    return entrega


def registrar_ciencia(sessao: Session, usuario: Usuario, entrega_id: uuid.UUID) -> EntregaNotificacao:
    """"Li e estou ciente": também conta como visualizada. Repetir não muda a data."""
    entrega = _entrega(sessao, usuario, entrega_id)
    agora = agora_utc()
    entrega.visualizada_em = entrega.visualizada_em or agora
    if entrega.ciente_em is None:
        entrega.ciente_em = agora
        auditar(sessao, usuario.login, "notificacao.ciencia", entrega.assunto_copia, autor_id=usuario.id,
                alvo_tipo="notificacao", alvo_id=entrega.notificacao_id)
    sessao.commit()
    return entrega


def marcar_em_lote(sessao: Session, usuario: Usuario, ids: list[uuid.UUID], acao: str) -> int:
    """Marca várias mensagens do próprio usuário como lidas, não lidas ou cientes. Devolve quantas mudaram."""
    entregas = list(sessao.scalars(select(EntregaNotificacao).where(EntregaNotificacao.destinatario_id == usuario.id, EntregaNotificacao.id.in_(set(ids)))))
    agora, mudaram = agora_utc(), 0
    for e in entregas:
        if acao == "lida" and e.visualizada_em is None:
            e.visualizada_em, mudaram = agora, mudaram + 1
        elif acao == "nao_lida" and e.visualizada_em is not None:
            e.visualizada_em, mudaram = None, mudaram + 1
        elif acao == "ciente" and e.ciente_em is None:
            e.visualizada_em, e.ciente_em, mudaram = e.visualizada_em or agora, agora, mudaram + 1
            auditar(sessao, usuario.login, "notificacao.ciencia", e.assunto_copia, autor_id=usuario.id, alvo_tipo="notificacao", alvo_id=e.notificacao_id)
    sessao.commit()
    return mudaram


def destinatarios_disponiveis(sessao: Session, usuario: Usuario) -> tuple[list[Usuario], list[Setor], bool]:
    """Usuários ativos e, se o usuário puder, os setores ativos."""
    usuarios = list(sessao.scalars(select(Usuario).where(Usuario.ativo.is_(True))))
    usuarios.sort(key=lambda u: _normalizar(_nome(u)))
    pode = pode_enviar_setores(sessao, usuario)
    setores = sorted(sessao.scalars(select(Setor).where(Setor.ativo.is_(True))), key=lambda s: _normalizar(s.nome)) if pode else []
    return usuarios, setores, pode


# ---------------------------------------------------------------------------------------------
# Enviadas (acompanhamento de quem enviou)
# ---------------------------------------------------------------------------------------------

def enviadas(sessao: Session, autor: Usuario, pagina: int, tamanho: int) -> tuple[list[Notificacao], int]:
    """Mensagens avulsas do autor, da mais recente para a mais antiga."""
    mensagens = list(sessao.scalars(
        select(Notificacao).where(Notificacao.autor_id == autor.id, Notificacao.origem == "avulsa")
        .options(selectinload(Notificacao.entregas)).order_by(Notificacao.publicada_em.desc())
    ))
    inicio = (pagina - 1) * tamanho
    return mensagens[inicio:inicio + tamanho], len(mensagens)


def enviada(sessao: Session, autor: Usuario, notificacao_id: uuid.UUID) -> tuple[Notificacao, dict[int, Usuario]]:
    """Notificacao do autor (ou qualquer uma, para o SuperRoot) e os usuários destinatários."""
    mensagem = sessao.scalar(select(Notificacao).where(Notificacao.id == notificacao_id).options(selectinload(Notificacao.entregas)))
    if mensagem is None or (mensagem.autor_id != autor.id and not autor.superusuario):
        raise ErroNotificacao("Notificacao não encontrada.", 404, "nao_encontrado")
    ids = [e.destinatario_id for e in mensagem.entregas]
    usuarios = {u.id: u for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(ids)))} if ids else {}
    return mensagem, usuarios


def lembrar_pendentes(sessao: Session, autor: Usuario, notificacao_id: uuid.UUID) -> list[uuid.UUID]:
    """Ids das entregas ainda sem ciência (o e-mail de lembrete sai em segundo plano)."""
    mensagem, _ = enviada(sessao, autor, notificacao_id)
    pendentes = [e.id for e in mensagem.entregas if pendente(e)]
    if not pendentes:
        raise ErroNotificacao("Todos os destinatários já registraram ciência.")
    auditar(sessao, autor.login, "notificacao.lembrar", mensagem.assunto, autor_id=autor.id, alvo_tipo="notificacao", alvo_id=mensagem.id,
            dados={"pendentes": len(pendentes)})
    sessao.commit()
    return pendentes
