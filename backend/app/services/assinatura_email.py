# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar a assinatura de e-mail institucional (PNG em alta resolução e HTML copiável).
"""Assinatura de e-mail institucional.

Trazida do app `assinatura_e_mail` do servidor de aplicações da SPI, com estas melhorias:
- o PNG é **desenhado por inteiro** (brasão, filetes, ícones e textos) em 3× (1692×471, exibido a 564 px) e suavizado,
  em vez de pintar retângulos brancos sobre um modelo raster de 564×157;
- texto longo **quebra em até duas linhas** (cargo e departamento) ou é **abreviado com "…"**, sempre com aviso, em vez de
  encolher até ficar ilegível;
- a fonte (Bitstream Vera) vem com o reportlab: não depende de fonte instalada no servidor;
- celular e andar/lado são opcionais e **saem na imagem** (o app antigo pedia o celular e nunca o desenhava);
- há uma versão em **HTML** (texto selecionável, e-mail e telefone clicáveis) para colar na assinatura do Outlook ou do webmail;
- os dados institucionais (secretaria, endereço, prefixo do telefone) ficam na configuração.

Nada aqui grava no perfil: os dados do perfil só pré-preenchem o formulário.
"""

import base64
import io
import re
from dataclasses import dataclass, field
from functools import lru_cache
from html import escape
from pathlib import Path

import reportlab
from PIL import Image, ImageDraw, ImageFont

from app.core.configuracao import obter_configuracao
from app.models.usuario import Usuario

LARGURA, ALTURA = 564, 157  # tamanho "de e-mail", em pixels
ESCALA_FINAL = 3  # o PNG entregue tem 1692×471 (nítido em telas de alta densidade)
SUPER = 2  # desenha em 6× e reduz para 3× (suavização das bordas)
ESCALA = ESCALA_FINAL * SUPER

PRETO = "#000000"
TEXTO = "#1f2937"
ICONE = "#6b7280"

RECURSOS = Path(__file__).resolve().parents[1] / "recursos"
BRASAO = RECURSOS / "assinatura" / "sp_brasao.png"
BRASAO_EMAIL = RECURSOS / "brasao-email.png"
FONTES = Path(reportlab.__file__).resolve().parent / "fonts"
ARQUIVO_FONTE = {"regular": "Vera.ttf", "bold": "VeraBd.ttf"}

# Área de texto à direita do divisor (em pixels de 1×)
X_TEXTO = 236
LARGURA_TEXTO = 320
OBRIGATORIOS = {"nome_completo": "nome", "cargo": "cargo", "email": "e-mail"}


class ErroAssinatura(Exception):
    """Dados insuficientes para montar a assinatura (vira 400)."""


@dataclass
class OpcoesAssinatura:
    incluir_celular: bool = False
    incluir_andar_lado: bool = False


@dataclass
class Resultado:
    png: bytes
    html: str
    avisos: list[str] = field(default_factory=list)


# --- Dados --------------------------------------------------------------------------------------

def dados_em_vigor(usuario: Usuario) -> dict[str, str]:
    """Dados do perfil **em vigor** (o que a CGP já validou); o que está pendente de validação não entra."""
    return {
        "nome_completo": usuario.nome_completo or "", "cargo": usuario.cargo or "", "departamento": usuario.departamento or "",
        "email": usuario.email or "", "ramal": usuario.ramal or "", "celular": usuario.celular or "",
        "andar": usuario.andar or "", "lado": usuario.predio or "",
    }


def campos_faltando(dados: dict[str, str]) -> list[str]:
    """Rótulos dos campos obrigatórios que estão vazios."""
    return [rotulo for campo, rotulo in OBRIGATORIOS.items() if not (dados.get(campo) or "").strip()]


def telefone_ramal(ramal: str) -> str:
    """"8178" → "(11) 3702-8178" (o prefixo vem da configuração)."""
    ramal = (ramal or "").strip()
    return f"{obter_configuracao().assinatura_telefone_prefixo}{ramal}" if ramal else ""


def formatar_celular(celular: str) -> str:
    """11999998888 → (11) 99999-8888; fora desse padrão, devolve como digitado."""
    digitos = re.sub(r"\D", "", celular or "")
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return (celular or "").strip()


def localizacao(dados: dict[str, str]) -> str:
    """"5º andar · Lado B" (partes ausentes são omitidas)."""
    andar, lado = (dados.get("andar") or "").strip(), (dados.get("lado") or "").strip()
    partes = []
    if andar:
        partes.append("Subsolo" if andar.lower() == "subsolo" else f"{andar}º andar")
    if lado:
        partes.append(f"Lado {lado}")
    return " · ".join(partes)


def _exigir(dados: dict[str, str]) -> None:
    faltam = campos_faltando(dados)
    if faltam:
        raise ErroAssinatura("Informe " + ", ".join(faltam) + " para gerar a assinatura.")


# --- Desenho ------------------------------------------------------------------------------------

@lru_cache(maxsize=64)
def _fonte(estilo: str, tamanho: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTES / ARQUIVO_FONTE[estilo]), size=round(tamanho * ESCALA))


@lru_cache(maxsize=1)
def _brasao() -> Image.Image:
    return Image.open(BRASAO).convert("RGBA")


def _largura(desenho: ImageDraw.ImageDraw, texto: str, fonte: ImageFont.FreeTypeFont) -> float:
    return desenho.textlength(texto, font=fonte)


def _abreviar(desenho, texto: str, fonte, largura: float) -> str:
    cortado = texto
    while cortado and _largura(desenho, cortado + "…", fonte) > largura * ESCALA:
        cortado = cortado[:-1]
    return cortado.rstrip() + "…"


def _linhas(desenho, texto: str, estilo: str, maximo: float, minimo: float, largura: float, max_linhas: int, rotulo: str,
            avisos: list[str]) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Maior fonte que cabe em uma linha; se nem a menor couber, quebra em até `max_linhas` e, por fim, abrevia (com aviso)."""
    tamanho = maximo
    while tamanho >= minimo - 1e-9:
        fonte = _fonte(estilo, tamanho)
        if _largura(desenho, texto, fonte) <= largura * ESCALA:
            return fonte, [texto]
        tamanho -= 0.5
    fonte = _fonte(estilo, minimo)
    palavras, linhas, atual = texto.split(), [], ""
    for palavra in palavras:
        tentativa = f"{atual} {palavra}".strip()
        if _largura(desenho, tentativa, fonte) <= largura * ESCALA or not atual:
            atual = tentativa
        else:
            linhas.append(atual)
            atual = palavra
    linhas.append(atual)
    if len(linhas) > max_linhas:
        resto = " ".join(linhas[max_linhas - 1:])
        linhas = linhas[:max_linhas - 1] + [_abreviar(desenho, resto, fonte, largura)]
        avisos.append(f"{rotulo} muito longo: abreviado na imagem.")
    elif any(_largura(desenho, linha, fonte) > largura * ESCALA for linha in linhas):
        linhas = [_abreviar(desenho, linha, fonte, largura) if _largura(desenho, linha, fonte) > largura * ESCALA else linha for linha in linhas]
        avisos.append(f"{rotulo} muito longo: abreviado na imagem.")
    return fonte, linhas


def _texto(desenho, x: float, base: float, texto: str, fonte, cor: str = TEXTO, centro: bool = False) -> None:
    """Escreve com a linha de base em `base` (coordenadas de 1×)."""
    ancora = "ms" if centro else "ls"
    desenho.text((x * ESCALA, base * ESCALA), texto, font=fonte, fill=cor, anchor=ancora)


def _retangulo(desenho, x1: float, y1: float, x2: float, y2: float, cor: str = PRETO) -> None:
    desenho.rectangle((x1 * ESCALA, y1 * ESCALA, x2 * ESCALA - 1, y2 * ESCALA - 1), fill=cor)


def _icone_envelope(desenho, x: float, y: float) -> None:
    e = ESCALA
    desenho.rounded_rectangle((x * e, y * e, (x + 16) * e, (y + 11.5) * e), radius=1.2 * e, outline=ICONE, width=round(1.1 * e))
    desenho.line([(x * e + 1.2 * e, y * e + 1.4 * e), ((x + 8) * e, (y + 7) * e), ((x + 16) * e - 1.2 * e, y * e + 1.4 * e)], fill=ICONE, width=round(1.1 * e))


def _icone_telefone(desenho, x: float, y: float) -> None:
    """Fone de telefone: curva grossa (bojo para baixo e para a esquerda) com um bocal em cada ponta."""
    e = ESCALA
    p0, p1, p2 = (x + 3.2, y + 1.8), (x + 0.5, y + 13.5), (x + 13.8, y + 11.8)
    pontos = []
    for i in range(41):
        t = i / 40
        pontos.append(((((1 - t) ** 2) * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]) * e,
                       (((1 - t) ** 2) * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) * e))
    desenho.line(pontos, fill=PRETO, width=round(2.6 * e), joint="curve")
    for ponto in (pontos[0], pontos[-1]):
        r = 2.5 * e
        desenho.ellipse((ponto[0] - r, ponto[1] - r, ponto[0] + r, ponto[1] + r), fill=PRETO)


def _icone_local(desenho, x: float, y: float) -> None:
    """Alfinete de mapa: gota com um furo no centro."""
    e = ESCALA
    cx, cy, r = (x + 7) * e, (y + 7) * e, 7 * e
    desenho.polygon([(cx - r * 0.85, cy + r * 0.45), (cx, (y + 19) * e), (cx + r * 0.85, cy + r * 0.45)], fill=ICONE)
    desenho.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ICONE)
    desenho.ellipse((cx - 2.6 * e, cy - 2.6 * e, cx + 2.6 * e, cy + 2.6 * e), fill="#ffffff")


def _desenhar(dados: dict[str, str], opcoes: OpcoesAssinatura, avisos: list[str]) -> Image.Image:
    cfg = obter_configuracao()
    imagem = Image.new("RGB", (LARGURA * ESCALA, ALTURA * ESCALA), "#ffffff")
    d = ImageDraw.Draw(imagem)

    # Esquerda: brasão e nome do Estado; divisor vertical
    brasao = _brasao()
    altura_brasao = 90
    largura_brasao = round(brasao.width * altura_brasao / brasao.height)
    reduzido = brasao.resize((largura_brasao * ESCALA, altura_brasao * ESCALA), Image.Resampling.LANCZOS)
    imagem.paste(reduzido, (round((109 - largura_brasao / 2) * ESCALA), 12 * ESCALA), reduzido)
    negrito = _fonte("bold", 10.5)
    _texto(d, 109, 120, "GOVERNO DO ESTADO", negrito, PRETO, centro=True)
    _texto(d, 109, 134, "DE SÃO PAULO", negrito, PRETO, centro=True)
    _retangulo(d, 215, 14, 216, 143)

    # Direita, parte de cima: nome, cargo, secretaria e departamento
    fonte, [nome] = _linhas(d, dados["nome_completo"], "bold", 12.5, 9.5, LARGURA_TEXTO, 1, "Nome", avisos)
    _texto(d, X_TEXTO, 30, nome, fonte, PRETO)
    fonte, linhas_cargo = _linhas(d, dados["cargo"], "regular", 10.5, 9, LARGURA_TEXTO, 2, "Cargo", avisos)
    for i, linha in enumerate(linhas_cargo):
        _texto(d, X_TEXTO, 42 + 11 * i, linha, fonte)
    _texto(d, X_TEXTO, 68, cfg.assinatura_secretaria, _linhas(d, cfg.assinatura_secretaria, "bold", 10, 8, LARGURA_TEXTO, 1, "Secretaria", [])[0])
    if (dados.get("departamento") or "").strip():
        fonte, linhas_depto = _linhas(d, dados["departamento"].strip(), "regular", 10, 9, LARGURA_TEXTO, 2, "Departamento", avisos)
        for i, linha in enumerate(linhas_depto):
            _texto(d, X_TEXTO, 81 + 11 * i, linha, fonte)

    # Divisor horizontal e contatos
    _retangulo(d, 228, 103, LARGURA, 104)
    _icone_envelope(d, 234, 107.5)
    fonte, [email] = _linhas(d, dados["email"], "regular", 10, 8, 150, 1, "E-mail", avisos)
    _texto(d, 259, 117, email, fonte)
    telefone = telefone_ramal(dados.get("ramal", ""))
    if telefone:
        _icone_telefone(d, 416, 107)
        fonte, [telefone] = _linhas(d, telefone, "regular", 10, 8, 118, 1, "Telefone", avisos)
        _texto(d, 438, 117, telefone, fonte)
    else:
        avisos.append("Sem ramal no perfil: o telefone não aparece na imagem.")
    _icone_local(d, 234, 126)
    _texto(d, 259, 133, cfg.assinatura_endereco, _linhas(d, cfg.assinatura_endereco, "regular", 9.5, 8, 155, 1, "Endereço", [])[0])
    _texto(d, 259, 144, cfg.assinatura_cidade, _linhas(d, cfg.assinatura_cidade, "regular", 9.5, 8, 155, 1, "Cidade", [])[0])

    # Direita, parte de baixo: celular e andar/lado (opcionais), alinhados ao telefone
    extras = []
    if opcoes.incluir_celular and (dados.get("celular") or "").strip():
        extras.append(f"Cel. {formatar_celular(dados['celular'])}")
    elif opcoes.incluir_celular:
        avisos.append("Sem celular no perfil: ele não aparece na imagem.")
    if opcoes.incluir_andar_lado and localizacao(dados):
        extras.append(localizacao(dados))
    elif opcoes.incluir_andar_lado:
        avisos.append("Sem andar e lado no perfil: eles não aparecem na imagem.")
    for i, extra in enumerate(extras[:2]):
        fonte, [extra] = _linhas(d, extra, "regular", 9.5, 8, 118, 1, "Contato extra", avisos)
        _texto(d, 438, 133 + 11 * i, extra, fonte)

    # Faixa inferior (dois filetes, como no modelo da SPI)
    _retangulo(d, 0, 153, LARGURA, 155)
    _retangulo(d, 0, 156, LARGURA, 157)
    return imagem.resize((LARGURA * ESCALA_FINAL, ALTURA * ESCALA_FINAL), Image.Resampling.LANCZOS)


def renderizar_png(dados: dict[str, str], opcoes: OpcoesAssinatura | None = None) -> tuple[bytes, list[str]]:
    """PNG da assinatura (1692×471) e os avisos (texto abreviado, campos ausentes)."""
    _exigir(dados)
    avisos: list[str] = []
    imagem = _desenhar(dados, opcoes or OpcoesAssinatura(), avisos)
    saida = io.BytesIO()
    imagem.save(saida, format="PNG", optimize=True, dpi=(288, 288))
    return saida.getvalue(), avisos


# --- HTML ---------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _brasao_html() -> str:
    """Brasão pequeno (data URI) para a versão em HTML: o arquivo do e-mail institucional reduzido."""
    imagem = Image.open(BRASAO_EMAIL).convert("RGBA")
    imagem.thumbnail((192, 192), Image.Resampling.LANCZOS)
    saida = io.BytesIO()
    imagem.save(saida, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(saida.getvalue()).decode("ascii")


def html_assinatura(dados: dict[str, str], opcoes: OpcoesAssinatura | None = None) -> str:
    """Assinatura em HTML de tabela, com estilos inline (Outlook e webmails); todo texto do usuário é escapado."""
    opcoes = opcoes or OpcoesAssinatura()
    _exigir(dados)
    cfg = obter_configuracao()
    e = lambda t: escape((t or "").strip())  # noqa: E731
    estilo = "font-family:Arial,Helvetica,sans-serif;"
    linhas = [
        f'<div style="{estilo}font-size:15px;font-weight:bold;color:#000000;line-height:1.3">{e(dados["nome_completo"])}</div>',
        f'<div style="{estilo}font-size:13px;color:#1f2937;line-height:1.35">{e(dados["cargo"])}</div>',
        f'<div style="{estilo}font-size:12px;font-weight:bold;color:#1f2937;line-height:1.3;padding-top:8px">{e(cfg.assinatura_secretaria)}</div>',
    ]
    if (dados.get("departamento") or "").strip():
        linhas.append(f'<div style="{estilo}font-size:12px;color:#1f2937;line-height:1.3">{e(dados["departamento"])}</div>')
    contatos = [f'<a href="mailto:{e(dados["email"])}" style="color:#1f2937;text-decoration:none">{e(dados["email"])}</a>']
    telefone = telefone_ramal(dados.get("ramal", ""))
    if telefone:
        contatos.append(f'<a href="tel:+55{re.sub(r"\D", "", telefone)}" style="color:#1f2937;text-decoration:none">{e(telefone)}</a>')
    if opcoes.incluir_celular and (dados.get("celular") or "").strip():
        celular = formatar_celular(dados["celular"])
        contatos.append(f'<a href="tel:+55{re.sub(r"\D", "", celular)}" style="color:#1f2937;text-decoration:none">Cel. {e(celular)}</a>')
    endereco = [cfg.assinatura_endereco, cfg.assinatura_cidade]
    if opcoes.incluir_andar_lado and localizacao(dados):
        endereco.append(localizacao(dados))
    linhas.append(
        f'<div style="{estilo}font-size:12px;color:#1f2937;line-height:1.45;border-top:1px solid #000000;margin-top:8px;padding-top:6px">'
        + " &nbsp;|&nbsp; ".join(contatos) + "<br>" + "<br>".join(e(t) for t in endereco) + "</div>"
    )
    return (
        f'<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;{estilo}"><tr>'
        f'<td style="padding:0 16px 0 0;border-right:1px solid #000000;text-align:center;vertical-align:middle" width="150">'
        f'<img src="{_brasao_html()}" width="72" alt="Governo do Estado de São Paulo" style="display:block;margin:0 auto 6px;border:0">'
        f'<div style="{estilo}font-size:11px;font-weight:bold;color:#000000;line-height:1.3">GOVERNO DO ESTADO<br>DE SÃO PAULO</div></td>'
        f'<td style="padding:0 0 0 16px;vertical-align:top">{"".join(linhas)}</td></tr></table>'
    )


def gerar(dados: dict[str, str], opcoes: OpcoesAssinatura | None = None) -> Resultado:
    """PNG, HTML e avisos de uma vez (usado pela prévia)."""
    png, avisos = renderizar_png(dados, opcoes)
    return Resultado(png=png, html=html_assinatura(dados, opcoes), avisos=avisos)
