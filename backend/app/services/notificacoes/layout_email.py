# Criado por José Eduardo Santana Martins
# Este arquivo serve para montar o e-mail das notificações no layout oficial (individual, prévia e resumo diário ou semanal).
"""Layout dos e-mails das Notificações (brasão, cabeçalho institucional, botão de acesso e rodapé)."""

from html import escape

from app.core.configuracao import obter_configuracao
from app.services import modelo_email

NOTA_RODAPE = "Notificação do SGI SPI. Leia e registre sua ciência na caixa de notificações do sistema; não responda a este e-mail."


def url_completa(link: str | None) -> str:
    """Endereço público do sistema + o caminho interno (ou a caixa de notificações)."""
    base = obter_configuracao().url_publica.rstrip("/")
    return f"{base}{link}" if link else f"{base}/notificacoes"


def html_email(titulo: str, paragrafos: list[str], link: str | None, rotulo_link: str = "Abrir no SGI SPI") -> str:
    """E-mail das notificações no layout oficial."""
    return modelo_email.pagina(
        titulo, modelo_email.paragrafos(paragrafos), link_url=url_completa(link), rotulo_link=rotulo_link, sobretitulo="Comunicação institucional",
        nota_rodape=NOTA_RODAPE,
    )


def html_mensagem(assunto: str, corpo: str, autor_nome: str, link: str | None) -> str:
    """E-mail da notificação no mesmo layout do changelog: o texto aceita `## título`, `- lista` e `**negrito**`."""
    return modelo_email.pagina(
        assunto, modelo_email.corpo_html(corpo) + modelo_email.paragrafos([f"Enviada por {autor_nome}."]), link_url=url_completa(link),
        rotulo_link="Abrir no SGI SPI", sobretitulo="Comunicação institucional", nota_rodape=NOTA_RODAPE,
    )


def previa_mensagem(assunto: str, corpo: str, autor_nome: str, link: str | None) -> str:
    """O e-mail da notificação para exibir na tela (brasão embutido): a caixa mostra o mesmo layout."""
    return modelo_email.para_previa(html_mensagem(assunto, corpo, autor_nome, link))


def html_resumo(titulo: str, grupos: list[tuple[str, list[tuple[str, str]]]]) -> str:
    """Resumo por módulo: cada grupo é (rótulo do módulo, [(assunto, link da notificação)])."""
    partes = []
    for rotulo, itens in grupos:
        linhas = "".join(
            f'<li style="margin:0 0 6px"><a href="{escape(url, quote=True)}" style="color:#c82331;text-decoration:none">{escape(assunto)}</a></li>' for assunto, url in itens
        )
        partes.append(
            f'<h3 style="margin:18px 0 8px;font-size:15px;color:#361a1c">{escape(rotulo)} ({len(itens)})</h3>'
            f'<ul style="margin:0;padding-left:18px;font-size:14px;line-height:1.5;color:#333">{linhas}</ul>'
        )
    return modelo_email.pagina(
        titulo, "".join(partes), link_url=url_completa(None), rotulo_link="Abrir minhas notificações", sobretitulo="Resumo das notificações",
        nota_rodape=NOTA_RODAPE,
    )
