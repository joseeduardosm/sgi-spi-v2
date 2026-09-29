# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras da mensageria: envio, caixa de entrada, ciência, avisos automáticos e e-mail.
"""Mensageria interna (caixa de mensagens de cada usuário).

- **Avulsa:** qualquer usuário autenticado envia para usuários; setores inteiros exigem SuperRoot ou ACL
  `mensageria-setores` ≥ CONTROLE_TOTAL. Setores viram a lista de membros e ninguém recebe duas vezes.
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
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import FabricaSessao, agora_utc
from app.core.configuracao import obter_configuracao
from app.models.acl import NivelAcl
from app.models.mensagem import EntregaMensagem, Mensagem
from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario
from app.services import modelo_email, servico_smtp
from app.services.cliente_smtp import Mensagem as EmailSmtp
from app.services.servico_acl import resolver_acesso
from app.services.servico_auditoria import auditar
from app.services.servico_smtp import SemServidorAtivo

RECURSO_SETORES = "mensageria-setores"
ROTULOS_PRIORIDADE = {"baixa": "Baixa", "normal": "Normal", "alta": "Alta", "critica": "Crítica"}
ROTULOS_CATEGORIA = {
    "comunicado": "Comunicado", "prazo": "Prazo", "pendencia": "Pendência", "revisao": "Revisão",
    "atribuicao": "Atribuição", "indisponibilidade": "Indisponibilidade", "normativo": "Normativo",
}


class ErroMensagem(Exception):
    """Regra da mensageria violada; `status` é o código HTTP e `codigo` o código do erro da API."""

    def __init__(self, detalhe: str, status: int = 400, codigo: str = "invalido") -> None:
        super().__init__(detalhe)
        self.status, self.codigo = status, codigo


@dataclass
class DadosEnvio:
    """Mensagem avulsa a enviar (já validada pelo schema)."""
    assunto: str
    corpo: str
    prioridade: str
    categoria: str
    usuarios_ids: list[int]
    setores_ids: list[int]
    expira_em: datetime | None
    link: str | None
    enviar_email: bool


def _nome(usuario: Usuario) -> str:
    return usuario.nome_completo or usuario.login


def _normalizar(texto: str) -> str:
    """Minúsculas sem acentos, para a busca ("Medição" encontra "medicao")."""
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def _agora_comparavel(valor: datetime | None) -> datetime | None:
    """Datas do SQLite voltam sem fuso: compara tudo em UTC sem fuso."""
    return valor.replace(tzinfo=None) if valor is not None and valor.tzinfo else valor


def _ativa(entrega: EntregaMensagem, agora: datetime) -> bool:
    """A mensagem ainda não expirou."""
    expira = _agora_comparavel(entrega.mensagem.expira_em)
    return expira is None or expira > _agora_comparavel(agora)


def pendente(entrega: EntregaMensagem) -> bool:
    """Sem ciência e sem encerramento automático."""
    return entrega.ciente_em is None and entrega.encerrada_em is None


# ---------------------------------------------------------------------------------------------
# Envio
# ---------------------------------------------------------------------------------------------

def pode_enviar_setores(sessao: Session, usuario: Usuario) -> bool:
    """SuperRoot ou CONTROLE_TOTAL no recurso `mensageria-setores`."""
    return resolver_acesso(sessao, usuario, RECURSO_SETORES) == NivelAcl.CONTROLE_TOTAL


def _publicar(sessao: Session, mensagem: Mensagem, destinatarios: list[Usuario]) -> list[EntregaMensagem]:
    """Cria uma entrega (com a fotografia do texto) para cada destinatário."""
    entregas = [
        EntregaMensagem(destinatario_id=u.id, assunto_copia=mensagem.assunto, corpo_copia=mensagem.corpo, entregue_em=mensagem.publicada_em)
        for u in destinatarios
    ]
    mensagem.entregas.extend(entregas)
    sessao.add(mensagem)
    return entregas


def enviar_avulsa(sessao: Session, dados: DadosEnvio, autor: Usuario) -> Mensagem:
    """Mensagem escrita por um usuário para usuários e (com permissão) setores."""
    if dados.setores_ids and not pode_enviar_setores(sessao, autor):
        raise ErroMensagem("Você não tem permissão para enviar mensagens para setores inteiros.", 403, "acl_negado")
    if dados.expira_em is not None and _agora_comparavel(dados.expira_em) <= _agora_comparavel(agora_utc()):
        raise ErroMensagem("A data de expiração deve estar no futuro.")
    ids = set(dados.usuarios_ids)
    if dados.setores_ids:
        ids |= set(sessao.scalars(select(MembroSetor.usuario_id).where(MembroSetor.setor_id.in_(dados.setores_ids))))
    destinatarios = list(sessao.scalars(select(Usuario).where(Usuario.id.in_(ids), Usuario.ativo.is_(True)))) if ids else []
    if not destinatarios:
        raise ErroMensagem("Selecione ao menos um destinatário ativo.")
    mensagem = Mensagem(
        assunto=dados.assunto, corpo=dados.corpo, prioridade=dados.prioridade, categoria=dados.categoria,
        autor_id=autor.id, autor_nome=_nome(autor), publicada_em=agora_utc(), expira_em=dados.expira_em,
        link=dados.link, origem="avulsa", enviar_email=dados.enviar_email,
    )
    _publicar(sessao, mensagem, destinatarios)
    auditar(sessao, autor.login, "mensagem.enviar", dados.assunto, autor_id=autor.id, alvo_tipo="mensagem", alvo_id=mensagem.id,
            dados={"destinatarios": len(destinatarios), "setores": dados.setores_ids, "email": dados.enviar_email})
    sessao.commit()
    return mensagem


def notificar(
    sessao: Session, destinatarios_ids: list[int], assunto: str, corpo: str, *, chave: str, categoria: str = "comunicado",
    prioridade: str = "normal", link: str | None = None, contrato_id: uuid.UUID | None = None, abrir_em_janela: bool = False,
    email: bool = False, autor: Usuario | None = None,
) -> Mensagem | None:
    """Aviso automático (sem commit: grava junto com a operação que o originou).

    Não repete a `chave` para quem já recebeu e não avisa o próprio autor da ação (exceto janelas).
    Devolve a mensagem criada, ou None se ninguém precisar receber.
    """
    ids = {i for i in destinatarios_ids if i is not None}
    if autor is not None and not abrir_em_janela:
        ids.discard(autor.id)
    if not ids:
        return None
    ja_receberam = set(sessao.scalars(
        select(EntregaMensagem.destinatario_id).join(Mensagem).where(Mensagem.chave == chave, EntregaMensagem.destinatario_id.in_(ids))
    ))
    # Mensagens ainda pendentes na sessão (mesma transação) também contam
    for obj in sessao.new:
        if isinstance(obj, Mensagem) and obj.chave == chave:
            ja_receberam |= {e.destinatario_id for e in obj.entregas}
    ids -= ja_receberam
    destinatarios = list(sessao.scalars(select(Usuario).where(Usuario.id.in_(ids), Usuario.ativo.is_(True)))) if ids else []
    if not destinatarios:
        return None
    mensagem = Mensagem(
        assunto=assunto[:300], corpo=corpo, prioridade=prioridade, categoria=categoria,
        autor_id=None, autor_nome="Sistema", publicada_em=agora_utc(), link=link, origem="automatica",
        chave=chave, contrato_id=contrato_id, abrir_em_janela=abrir_em_janela, enviar_email=email,
    )
    _publicar(sessao, mensagem, destinatarios)
    return mensagem


def encerrar(sessao: Session, *, chave: str | None = None, prefixo: str | None = None) -> int:
    """Encerra (sem exigir ciência) as entregas pendentes dos avisos com a chave ou o prefixo informado."""
    consulta = select(EntregaMensagem).join(Mensagem).where(EntregaMensagem.ciente_em.is_(None), EntregaMensagem.encerrada_em.is_(None))
    if chave is not None:
        consulta = consulta.where(Mensagem.chave == chave)
    elif prefixo is not None:
        consulta = consulta.where(Mensagem.chave.startswith(prefixo, autoescape=True))
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

def _entregas_do_usuario(sessao: Session, usuario: Usuario) -> list[EntregaMensagem]:
    """Entregas não expiradas do usuário, da mais recente para a mais antiga."""
    entregas = sessao.scalars(
        select(EntregaMensagem).where(EntregaMensagem.destinatario_id == usuario.id)
        .options(selectinload(EntregaMensagem.mensagem)).order_by(EntregaMensagem.entregue_em.desc())
    )
    agora = agora_utc()
    return [e for e in entregas if _ativa(e, agora)]


def resumo(sessao: Session, usuario: Usuario) -> tuple[int, int, EntregaMensagem | None]:
    """(pendentes, não lidas, próxima janela a abrir)."""
    entregas = _entregas_do_usuario(sessao, usuario)
    janelas = [e for e in entregas if e.mensagem.abrir_em_janela and e.visualizada_em is None and pendente(e)]
    return (
        sum(1 for e in entregas if pendente(e)),
        sum(1 for e in entregas if e.visualizada_em is None),
        min(janelas, key=lambda e: e.entregue_em) if janelas else None,
    )


def listar(sessao: Session, usuario: Usuario, estado: str, busca: str, pagina: int, tamanho: int) -> tuple[list[EntregaMensagem], int]:
    """Caixa de entrada filtrada (pendentes, cientes ou todas) e pesquisada sem diferenciar acentos."""
    entregas = _entregas_do_usuario(sessao, usuario)
    if estado == "pendentes":
        entregas = [e for e in entregas if pendente(e)]
    elif estado == "cientes":
        entregas = [e for e in entregas if not pendente(e)]
    termo = _normalizar(busca.strip())
    if termo:
        entregas = [e for e in entregas if termo in _normalizar(f"{e.assunto_copia} {e.corpo_copia} {e.mensagem.autor_nome}")]
    inicio = (pagina - 1) * tamanho
    return entregas[inicio:inicio + tamanho], len(entregas)


def _entrega(sessao: Session, usuario: Usuario, entrega_id: uuid.UUID) -> EntregaMensagem:
    """Entrega do próprio usuário; de outra pessoa (ou inexistente) é 404."""
    entrega = sessao.scalar(
        select(EntregaMensagem).where(EntregaMensagem.id == entrega_id, EntregaMensagem.destinatario_id == usuario.id)
        .options(selectinload(EntregaMensagem.mensagem))
    )
    if entrega is None:
        raise ErroMensagem("Mensagem não encontrada.", 404, "nao_encontrado")
    return entrega


def abrir(sessao: Session, usuario: Usuario, entrega_id: uuid.UUID) -> EntregaMensagem:
    """Abre a mensagem e registra a primeira visualização."""
    entrega = _entrega(sessao, usuario, entrega_id)
    if entrega.visualizada_em is None:
        entrega.visualizada_em = agora_utc()
        sessao.commit()
    return entrega


def registrar_ciencia(sessao: Session, usuario: Usuario, entrega_id: uuid.UUID) -> EntregaMensagem:
    """"Li e estou ciente": também conta como visualizada. Repetir não muda a data."""
    entrega = _entrega(sessao, usuario, entrega_id)
    agora = agora_utc()
    entrega.visualizada_em = entrega.visualizada_em or agora
    if entrega.ciente_em is None:
        entrega.ciente_em = agora
        auditar(sessao, usuario.login, "mensagem.ciencia", entrega.assunto_copia, autor_id=usuario.id,
                alvo_tipo="mensagem", alvo_id=entrega.mensagem_id)
    sessao.commit()
    return entrega


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

def enviadas(sessao: Session, autor: Usuario, pagina: int, tamanho: int) -> tuple[list[Mensagem], int]:
    """Mensagens avulsas do autor, da mais recente para a mais antiga."""
    mensagens = list(sessao.scalars(
        select(Mensagem).where(Mensagem.autor_id == autor.id, Mensagem.origem == "avulsa")
        .options(selectinload(Mensagem.entregas)).order_by(Mensagem.publicada_em.desc())
    ))
    inicio = (pagina - 1) * tamanho
    return mensagens[inicio:inicio + tamanho], len(mensagens)


def enviada(sessao: Session, autor: Usuario, mensagem_id: uuid.UUID) -> tuple[Mensagem, dict[int, Usuario]]:
    """Mensagem do autor (ou qualquer uma, para o SuperRoot) e os usuários destinatários."""
    mensagem = sessao.scalar(select(Mensagem).where(Mensagem.id == mensagem_id).options(selectinload(Mensagem.entregas)))
    if mensagem is None or (mensagem.autor_id != autor.id and not autor.superusuario):
        raise ErroMensagem("Mensagem não encontrada.", 404, "nao_encontrado")
    ids = [e.destinatario_id for e in mensagem.entregas]
    usuarios = {u.id: u for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(ids)))} if ids else {}
    return mensagem, usuarios


def lembrar_pendentes(sessao: Session, autor: Usuario, mensagem_id: uuid.UUID) -> list[uuid.UUID]:
    """Ids das entregas ainda sem ciência (o e-mail de lembrete sai em segundo plano)."""
    mensagem, _ = enviada(sessao, autor, mensagem_id)
    pendentes = [e.id for e in mensagem.entregas if pendente(e)]
    if not pendentes:
        raise ErroMensagem("Todos os destinatários já registraram ciência.")
    auditar(sessao, autor.login, "mensagem.lembrar", mensagem.assunto, autor_id=autor.id, alvo_tipo="mensagem", alvo_id=mensagem.id,
            dados={"pendentes": len(pendentes)})
    sessao.commit()
    return pendentes


# ---------------------------------------------------------------------------------------------
# E-mail
# ---------------------------------------------------------------------------------------------

def _url(link: str | None) -> str:
    base = obter_configuracao().url_publica.rstrip("/")
    return f"{base}{link}" if link else f"{base}/mensagens"


def html_email(titulo: str, paragrafos: list[str], link: str | None, rotulo_link: str = "Abrir no SGI SPI") -> str:
    """E-mail da mensageria no layout oficial (brasão, cabeçalho institucional, botão de acesso e rodapé)."""
    return modelo_email.pagina(
        titulo, modelo_email.paragrafos(paragrafos), link_url=_url(link), rotulo_link=rotulo_link, sobretitulo="Comunicação institucional",
        nota_rodape="Mensagem do SGI SPI. Leia e registre sua ciência na caixa de mensagens do sistema; não responda a este e-mail.",
    )


def enviar_email_da_entrega(sessao: Session, entrega: EntregaMensagem, prefixo_assunto: str = "") -> None:
    """Envia a entrega por e-mail ao destinatário e grava o resultado (sem commit)."""
    usuario = sessao.get(Usuario, entrega.destinatario_id)
    entrega.email_enviado_em = agora_utc()
    if usuario is None or not (usuario.email or "").strip():
        entrega.email_ok, entrega.email_erro = False, "Destinatário sem e-mail cadastrado no perfil."
        return
    mensagem = entrega.mensagem
    assunto = f"{prefixo_assunto}{entrega.assunto_copia}"
    texto = f"{entrega.corpo_copia}\n\nEnviada por {mensagem.autor_nome}.\n{_url(mensagem.link)}"
    html = html_email(entrega.assunto_copia, [entrega.corpo_copia, f"Enviada por {mensagem.autor_nome}."], mensagem.link)
    try:
        resultado = servico_smtp.enviar_email(sessao, EmailSmtp(para=[usuario.email.strip()], assunto=assunto, texto=texto, html=html))
        entrega.email_ok, entrega.email_erro = resultado.sucesso, None if resultado.sucesso else resultado.mensagem
    except SemServidorAtivo as erro:
        entrega.email_ok, entrega.email_erro = False, str(erro)


def enviar_emails(mensagem_id: uuid.UUID, entregas_ids: list[uuid.UUID] | None = None, prefixo_assunto: str = "") -> None:
    """Tarefa em segundo plano: envia a mensagem por e-mail (a todas as entregas ou às informadas)."""
    with FabricaSessao() as sessao:
        entregas = sessao.scalars(
            select(EntregaMensagem).where(EntregaMensagem.mensagem_id == mensagem_id).options(selectinload(EntregaMensagem.mensagem))
        )
        for entrega in entregas:
            if entregas_ids is None or entrega.id in entregas_ids:
                enviar_email_da_entrega(sessao, entrega, prefixo_assunto)
        sessao.commit()
