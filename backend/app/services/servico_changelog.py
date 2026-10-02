# Criado por José Eduardo Santana Martins
# Este arquivo serve para montar e enviar o e-mail de changelog (novidades do SGI SPI) a partir do CHANGELOG.md.
"""E-mail de changelog da mensageria (exclusivo da conta root).

Fluxo:
1. `rascunho` lê o `CHANGELOG.md` da raiz do projeto e junta as entradas **posteriores à última data já enviada a
   todos** (na primeira vez, só a entrada mais recente). O texto sai num formato simples, editável na tela:
   `## Título` (subtítulo), `- item` (lista; dois espaços por nível) e `**negrito**`.
2. A conta root edita o assunto e o texto; `html_email` gera a prévia no layout oficial (brasão, cabeçalho
   institucional, botão de acesso e rodapé).
3. `registrar_envio` grava o envio e `processar_envio` (em segundo plano) manda um e-mail por destinatário: todos os
   usuários ativos com e-mail, os usuários e setores escolhidos (sistêmicos ou institucionais; um setor inclui os
   membros, quem o tem como Departamento e os setores filhos) ou só um endereço de teste. Só o envio a todos muda a
   data do próximo rascunho.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import FabricaSessao, agora_utc
from app.core.configuracao import obter_configuracao
from app.models.envio_changelog import EnvioChangelog
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.services import modelo_email, servico_smtp
from app.services.modelo_email import corpo_html, corpo_texto
from app.services.cliente_smtp import Mensagem as EmailSmtp
from app.services.servico_auditoria import auditar
from app.services.servico_smtp import SemServidorAtivo

# backend/app/services → raiz do projeto
ARQUIVO_CHANGELOG = Path(__file__).resolve().parents[3] / "CHANGELOG.md"

# Seções do CHANGELOG com o nome usado no e-mail (linguagem de usuário)
SECOES = {"adicionado": "Novidades", "alterado": "Melhorias", "corrigido": "Correções", "removido": "Removido"}
TITULO_DATA = re.compile(r"^##\s+(.+)$")
DATA = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


class ErroChangelog(Exception):
    """Envio impossível (vira 400)."""


@dataclass
class Entrada:
    """Uma data do CHANGELOG (`## AAAA-MM-DD`) com o texto dela."""
    data: date
    linhas: list[str]


@dataclass
class Rascunho:
    assunto: str
    corpo: str
    desde: date | None
    ate: date | None
    datas: list[date]


def ler_entradas(texto: str) -> list[Entrada]:
    """Entradas do CHANGELOG, da mais recente para a mais antiga. Um título "A a B" vale pela última data."""
    entradas: list[Entrada] = []
    atual: Entrada | None = None
    for linha in texto.splitlines():
        titulo = TITULO_DATA.match(linha)
        if titulo:
            datas = DATA.findall(titulo.group(1))
            atual = Entrada(date(*map(int, datas[-1])), []) if datas else None
            if atual:
                entradas.append(atual)
            continue
        if atual is not None:
            atual.linhas.append(linha)
    return entradas


def _texto_amigavel(linhas: list[str]) -> list[str]:
    """Converte a seção do CHANGELOG no formato do e-mail: seções renomeadas, sem crases, migrações e endpoints."""
    saida: list[str] = []
    for linha in linhas:
        secao = re.match(r"^###\s+(.+)$", linha)
        if secao:
            nome = SECOES.get(secao.group(1).strip().lower(), secao.group(1).strip())
            if saida and saida[-1] != "":
                saida.append("")
            saida.append(f"## {nome}")
            continue
        conteudo = linha.strip().lstrip("-").strip().lower()
        # Detalhes técnicos que não interessam ao usuário final
        if conteudo.startswith(("migração", "migrações", "endpoint", "nova variável", "novas variáveis")):
            continue
        saida.append(linha.replace("`", "").rstrip())
    # Sem linhas em branco repetidas nem nas pontas
    limpo: list[str] = []
    for linha in saida:
        if linha == "" and (not limpo or limpo[-1] == ""):
            continue
        limpo.append(linha)
    while limpo and limpo[-1] == "":
        limpo.pop()
    return limpo


def _ultimo_envio_geral(sessao: Session) -> date | None:
    return sessao.scalar(select(func.max(EnvioChangelog.ate_data)).where(EnvioChangelog.destino == "todos"))


def rascunho(sessao: Session, arquivo: Path | None = None) -> Rascunho:
    """Assunto e texto sugeridos com as entradas do CHANGELOG ainda não enviadas a todos."""
    caminho = arquivo or ARQUIVO_CHANGELOG
    entradas = ler_entradas(caminho.read_text(encoding="utf-8")) if caminho.exists() else []
    desde = _ultimo_envio_geral(sessao)
    novas = [e for e in entradas if desde is None or e.data > desde]
    if desde is None:
        novas = novas[:1]
    if not novas:
        return Rascunho("SGI SPI – Novidades do sistema", "Não há novidades no CHANGELOG desde o último envio.", desde, None, [])
    ate = novas[0].data
    corpo = ["Olá!", "", "Confira as novidades do SGI SPI – Sistema de Gestão Integrada:"]
    # Da mais antiga para a mais recente, com a data quando houver mais de uma
    for entrada in reversed(novas):
        corpo.append("")
        if len(novas) > 1:
            corpo += [f"## Atualização de {entrada.data:%d/%m/%Y}", ""]
        corpo += _texto_amigavel(entrada.linhas)
    corpo += ["", "Dúvidas ou sugestões: fale com a equipe do SGI SPI."]
    return Rascunho(f"SGI SPI – Novidades de {ate:%d/%m/%Y}", "\n".join(corpo), desde, ate, [e.data for e in novas])


# ---------------------------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------------------------

def html_email(assunto: str, corpo: str) -> str:
    """E-mail completo no layout oficial."""
    return modelo_email.pagina(
        assunto, corpo_html(corpo), link_url=obter_configuracao().url_publica.rstrip("/") + "/", rotulo_link="Acessar o SGI SPI",
        sobretitulo="Novidades do sistema",
        nota_rodape="Comunicado do SGI SPI enviado a todos os usuários. Não responda a este e-mail.",
    )


def html_previa(assunto: str, corpo: str) -> str:
    """O mesmo e-mail, com o brasão embutido como `data:` (o navegador não conhece `cid:`)."""
    return modelo_email.para_previa(html_email(assunto, corpo))


# ---------------------------------------------------------------------------------------------
# Envio
# ---------------------------------------------------------------------------------------------

def _emails(usuarios) -> list[str]:
    """E-mails dos usuários (sem repetição, na ordem do nome; quem não tem e-mail fica de fora)."""
    vistos: dict[str, str] = {}
    for usuario in sorted(usuarios, key=lambda u: (u.nome_completo or u.login).lower()):
        email = (usuario.email or "").strip()
        if email and email.lower() not in vistos:
            vistos[email.lower()] = email
    return list(vistos.values())


def destinatarios(sessao: Session) -> list[str]:
    """E-mails de todos os usuários ativos."""
    return _emails(sessao.scalars(select(Usuario).where(Usuario.ativo.is_(True))))


def selecionados(sessao: Session, usuarios_ids: list[int], setores_ids: list[int]) -> tuple[list[str], str]:
    """E-mails dos usuários escolhidos e das pessoas dos setores escolhidos (membros ou com o setor, ou um setor filho,
    como Departamento), e a descrição da seleção para o histórico."""
    from app.services.rh.papeis import setor_com_descendentes, usuarios_dos_setores

    usuarios = list(sessao.scalars(select(Usuario).where(Usuario.id.in_(usuarios_ids), Usuario.ativo.is_(True)))) if usuarios_ids else []
    escolhidos = list(sessao.scalars(select(Setor).where(Setor.id.in_(setores_ids)))) if setores_ids else []
    pessoas = {u.id: u for u in usuarios}
    pessoas.update({u.id: u for u in usuarios_dos_setores(sessao, setor_com_descendentes(sessao, [s.id for s in escolhidos]))})
    partes = []
    if usuarios:
        partes.append("usuários: " + ", ".join(sorted((u.nome_completo or u.login) for u in usuarios)))
    if escolhidos:
        partes.append("setores: " + ", ".join(sorted(s.nome for s in escolhidos)))
    return _emails(pessoas.values()), "; ".join(partes)


def registrar_envio(sessao: Session, autor: Usuario, assunto: str, corpo: str, destino: str, email_teste: str | None,
                    ate_data: date | None, usuarios_ids: list[int] = (), setores_ids: list[int] = ()) -> tuple[EnvioChangelog, list[str]]:
    """Grava o envio (com o total de destinatários) e devolve a lista de e-mails a processar."""
    descricao = None
    if destino == "todos":
        lista = destinatarios(sessao)
    elif destino == "selecionados":
        lista, descricao = selecionados(sessao, list(usuarios_ids), list(setores_ids))
        if not lista:
            raise ErroChangelog("Nenhum destinatário ativo com e-mail entre os usuários e setores escolhidos.")
    else:
        lista = [email_teste or ""]
    envio = EnvioChangelog(
        assunto=assunto, corpo=corpo, destino=destino, destino_descricao=descricao, ate_data=ate_data if destino == "todos" else None,
        total=len(lista), enviados=0, falhas=0, enviado_por_id=autor.id, enviado_por_nome=autor.nome_completo or autor.login,
    )
    sessao.add(envio)
    sessao.flush()
    auditar(sessao, autor.login, "mensageria.changelog", assunto, f"destino={destino} total={len(lista)} {descricao or ''}".strip(),
            autor_id=autor.id, alvo_tipo="envio_changelog", alvo_id=envio.id)
    sessao.commit()
    return envio, lista


def processar_envio(envio_id: uuid.UUID, lista: list[str]) -> None:
    """Tarefa em segundo plano: um e-mail por destinatário (ninguém vê o endereço dos outros)."""
    with FabricaSessao() as sessao:
        envio = sessao.get(EnvioChangelog, envio_id)
        if envio is None:
            return
        html, texto = html_email(envio.assunto, envio.corpo), corpo_texto(envio.corpo)
        erros: list[str] = []
        for email in lista:
            try:
                resultado = servico_smtp.enviar_email(sessao, EmailSmtp(para=[email], assunto=envio.assunto, texto=texto, html=html))
                ok, motivo = resultado.sucesso, resultado.mensagem
            except SemServidorAtivo as erro:
                ok, motivo = False, str(erro)
            if ok:
                envio.enviados += 1
            else:
                envio.falhas += 1
                erros.append(f"{email}: {motivo}")
        envio.erros = "\n".join(erros) or None
        envio.concluido_em = agora_utc()
        sessao.commit()


def historico(sessao: Session, limite: int = 30) -> list[EnvioChangelog]:
    """Últimos envios, do mais recente para o mais antigo."""
    return list(sessao.scalars(select(EnvioChangelog).order_by(EnvioChangelog.criado_em.desc()).limit(limite)))
