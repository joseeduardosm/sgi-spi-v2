# Criado por José Eduardo Santana Martins
# Este arquivo serve para montar o layout oficial dos e-mails do SGI SPI (brasão, cabeçalho institucional e rodapé).
"""Layout oficial dos e-mails do SGI SPI.

Todos os e-mails do sistema (mensageria, avisos dos contratos, teste do servidor SMTP) usam `pagina`:
- cabeçalho com o **brasão** do Estado (imagem embutida, `cid:brasao-spi`: aparece sem depender de acesso à
  rede interna nem do bloqueio de imagens externas do Outlook), "GOVERNO DO ESTADO DE SÃO PAULO" e
  "Secretaria de Parcerias em Investimentos", com o filete vermelho institucional;
- título, conteúdo e, se houver, o botão de acesso ao sistema;
- rodapé com "SGI SPI – Sistema de Gestão Integrada" e a nota de mensagem automática.

HTML em tabelas e estilos inline (compatível com Outlook e webmails). `servico_smtp.enviar_email` anexa o
brasão sempre que o HTML o referencia.
"""

import base64
import re
from functools import lru_cache
from html import escape
from pathlib import Path

from app.services.cliente_smtp import ImagemEmbutida

CID_BRASAO = "brasao-spi"
ARQUIVO_BRASAO = Path(__file__).resolve().parents[1] / "recursos" / "brasao-email.png"
VERMELHO = "#b0222e"
NOTA_PADRAO = "Mensagem automática do SGI SPI. Não responda a este e-mail."


@lru_cache(maxsize=1)
def imagem_brasao() -> ImagemEmbutida:
    """Brasão do Estado para o cabeçalho (embutido no e-mail)."""
    return ImagemEmbutida(cid=CID_BRASAO, conteudo=ARQUIVO_BRASAO.read_bytes(), tipo="image/png")


# --- Texto formatado (`## título`, `- lista`, `**negrito**`) → HTML do e-mail -------------------------------------------

ESTILO_P = "margin:0 0 12px;font-size:14px;line-height:1.6;color:#2b3137"
ESTILO_H2 = f"margin:20px 0 8px;font-size:15px;color:{VERMELHO}"
ESTILO_UL = "margin:0 0 12px;padding-left:20px;font-size:14px;line-height:1.55;color:#2b3137"


def _inline(texto: str) -> str:
    """Escapa o HTML e aplica `**negrito**`."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape(texto))


def _tabela_html(linhas: list[str]) -> str:
    """Linhas `| a | b |` consecutivas → tabela HTML (a primeira é o cabeçalho; linhas só de `---` são ignoradas)."""
    corpo = []
    for n, linha in enumerate(linhas):
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in celulas):
            continue
        tag = "th" if n == 0 else "td"
        estilo = "padding:6px 8px;border:1px solid #e2e5e8;text-align:left;font-size:13px" + (";background:#fcecee" if tag == "th" else "")
        corpo.append("<tr>" + "".join(f'<{tag} style="{estilo}">{_inline(c)}</{tag}>' for c in celulas) + "</tr>")
    return '<table role="presentation" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:8px 0 14px;width:100%">' + "".join(corpo) + "</table>"


def corpo_html(corpo: str) -> str:
    """Texto editado → HTML do e-mail: `## ` vira subtítulo, `- ` vira lista (2 espaços por nível), `| a | b |` vira tabela, o resto parágrafo."""
    partes: list[str] = []
    nivel = 0  # listas abertas
    tabela: list[str] = []  # linhas da tabela em montagem
    for linha in corpo.splitlines() + [""]:
        if linha.lstrip().startswith("|"):
            tabela.append(linha)
            continue
        if tabela:
            partes.append(_tabela_html(tabela))
            tabela = []
        item = re.match(r"^(\s*)[-*]\s+(.*)$", linha)
        if item:
            alvo = len(item.group(1).replace("\t", "  ")) // 2 + 1
            while nivel < alvo:
                partes.append(f'<ul style="{ESTILO_UL}">')
                nivel += 1
            while nivel > alvo:
                partes.append("</ul>")
                nivel -= 1
            partes.append(f'<li style="margin:0 0 4px">{_inline(item.group(2))}</li>')
            continue
        while nivel:
            partes.append("</ul>")
            nivel -= 1
        if not linha.strip():
            continue
        titulo = re.match(r"^#{1,3}\s+(.*)$", linha)
        if titulo:
            partes.append(f'<h2 style="{ESTILO_H2}">{_inline(titulo.group(1))}</h2>')
        else:
            partes.append(f'<p style="{ESTILO_P}">{_inline(linha.strip())}</p>')
    partes += ["</ul>"] * nivel
    return "".join(partes)


def corpo_texto(corpo: str) -> str:
    """Versão em texto simples (leitores sem HTML): sem as marcas de negrito e de título."""
    return re.sub(r"^#{1,3}\s+", "", corpo.replace("**", ""), flags=re.MULTILINE)


def para_previa(html: str) -> str:
    """O mesmo e-mail com o brasão embutido como `data:` (o navegador não conhece `cid:`), para exibir na tela."""
    imagem = imagem_brasao()
    dados = f"data:{imagem.tipo};base64,{base64.b64encode(imagem.conteudo).decode()}"
    return html.replace(f"cid:{CID_BRASAO}", dados)


def paragrafos(textos: list[str]) -> str:
    """Parágrafos com as quebras de linha preservadas."""
    return "".join(
        f'<p style="margin:0 0 12px;font-size:14px;line-height:1.6;color:#2b3137;white-space:pre-line">{escape(t)}</p>' for t in textos if t
    )


def botao(url: str, rotulo: str) -> str:
    """Botão vermelho que não quebra nos clientes de e-mail (Outlook inclusive).

    A cor, o recuo e o canto arredondado ficam na célula da tabela (o Outlook ignora padding e fundo em `<a>` inline-block);
    o link só carrega o texto, sem quebra de linha.
    """
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 4px;border-collapse:separate"><tr>'
        f'<td align="center" bgcolor="{VERMELHO}" style="background:{VERMELHO};border-radius:4px;padding:12px 24px;mso-padding-alt:12px 24px">'
        f'<a href="{escape(url)}" target="_blank" style="display:block;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:18px;'
        f'font-weight:bold;color:#ffffff;text-decoration:none;white-space:nowrap">{escape(rotulo)}</a></td></tr></table>'
    )


def pagina(titulo: str, conteudo_html: str, *, link_url: str | None = None, rotulo_link: str = "Acessar o SGI SPI",
           sobretitulo: str = "", nota_rodape: str = NOTA_PADRAO) -> str:
    """E-mail completo no padrão oficial. `conteudo_html` já vem montado (use `paragrafos` para texto)."""
    botao_html = botao(link_url, rotulo_link) if link_url else ""
    sobre = (f'<p style="margin:0 0 6px;font-size:11px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;color:{VERMELHO}">'
             f"{escape(sobretitulo)}</p>") if sobretitulo else ""
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(titulo)}</title></head>
<body style="margin:0;padding:0;background:#f1f2f4">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f2f4;padding:24px 12px"><tr><td align="center">
  <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px;background:#ffffff;border:1px solid #dfe2e6;font-family:Arial,Helvetica,sans-serif">
    <tr><td style="padding:20px 28px 16px">
      <table role="presentation" cellpadding="0" cellspacing="0"><tr>
        <td style="padding-right:14px;vertical-align:middle"><img src="cid:{CID_BRASAO}" width="48" height="55" alt="Brasão do Estado de São Paulo" style="display:block;border:0"></td>
        <td style="vertical-align:middle">
          <div style="font-size:14px;font-weight:bold;letter-spacing:.5px;color:#1f262d">GOVERNO DO ESTADO DE SÃO PAULO</div>
          <div style="font-size:12px;color:#5b6570;margin-top:2px">Secretaria de Parcerias em Investimentos</div>
        </td>
      </tr></table>
    </td></tr>
    <tr><td style="height:4px;background:{VERMELHO};font-size:0;line-height:0">&nbsp;</td></tr>
    <tr><td style="padding:26px 28px 20px">
      {sobre}<h1 style="margin:0 0 16px;font-size:19px;line-height:1.35;color:#1f262d">{escape(titulo)}</h1>
      {conteudo_html}
      {botao_html}
    </td></tr>
    <tr><td style="padding:16px 28px 20px;background:#f7f8f9;border-top:1px solid #e6e8eb">
      <div style="font-size:12px;font-weight:bold;color:#3a424a">SGI SPI – Sistema de Gestão Integrada</div>
      <div style="font-size:11px;line-height:1.5;color:#7b8490;margin-top:4px">{escape(nota_rodape)}<br>
        Secretaria de Parcerias em Investimentos · Governo do Estado de São Paulo</div>
    </td></tr>
  </table>
</td></tr></table>
</body></html>"""
