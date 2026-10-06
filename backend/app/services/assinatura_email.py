# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar a assinatura de e-mail institucional (PNG em alta resolução e HTML copiável).
"""Assinatura de e-mail institucional (padrão GOV SP 2023).

O desenho vem de um modelo PowerPoint (`recursos/assinatura/modelo-assinatura.pptx`, o `GOV_ASSINATURA-DE-EMAIL_2023.pptx`):
`assinatura_pptx` preenche os textos do modelo e desenha a imagem **no pixel original do fundo** (sem reamostrar), então a
nitidez é a do arquivo do Governo. Para mudar o visual, basta trocar o PPTX (sem alterar código).

- Texto longo **encolhe até 80%** e, se ainda não couber, é **abreviado com "…"**, sempre com aviso.
- Celular e andar/lado são opcionais e saem numa linha a mais; o departamento vem acima da Secretaria.
- A versão em **HTML** leva a mesma imagem (o fundo do Governo é uma figura única), com o texto alternativo completo.
- Os dados institucionais (secretaria, endereço, prefixo do telefone) ficam na configuração.

Nada aqui grava no perfil: os dados do perfil só pré-preenchem o formulário.
"""

import base64
import io
import re
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from app.core.configuracao import obter_configuracao
from app.services import assinatura_pptx
from app.models.usuario import Usuario

MODELO = Path(__file__).resolve().parents[1] / "recursos" / "assinatura" / "modelo-assinatura.pptx"
LIMITE_INFERIOR = 0.75  # o texto termina até 75% da altura do slide: abaixo ficam as redes sociais e os filetes do modelo
EMU_POR_PIXEL = 9525  # largura de exibição: o slide a 96 dpi (o modelo oficial tem 564 px)

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


# --- Imagem -------------------------------------------------------------------------------------

def _campos(dados: dict[str, str], endereco_em_duas_linhas: bool, avisos: list[str]) -> dict[str, str]:
    """Textos que entram no modelo."""
    cfg = obter_configuracao()
    telefone = telefone_ramal(dados.get("ramal", ""))
    if not telefone:
        avisos.append("Sem ramal no perfil: o telefone não aparece na imagem.")
    departamento = (dados.get("departamento") or "").strip()
    separador = "\n" if endereco_em_duas_linhas else " - "
    return {
        "nome": dados["nome_completo"], "cargo": dados["cargo"],
        "orgao": f"{departamento}\n{cfg.assinatura_secretaria}" if departamento else cfg.assinatura_secretaria,
        "contato": " | ".join(p for p in (dados["email"], telefone) if p),
        "endereco": f"{cfg.assinatura_endereco}{separador}{cfg.assinatura_cidade}",
        # fichas {{campo}} para modelos novos
        "departamento": departamento, "secretaria": cfg.assinatura_secretaria, "email": dados["email"], "telefone": telefone,
        "celular": formatar_celular(dados.get("celular", "")), "andar_lado": localizacao(dados), "cidade": cfg.assinatura_cidade,
    }


def _extras(campos: dict[str, str], opcoes: OpcoesAssinatura, avisos: list[str]) -> list[str]:
    """Linha extra com celular e andar/lado (se pedidos e existentes no perfil)."""
    partes = []
    if opcoes.incluir_celular:
        if campos["celular"]:
            partes.append(f"Cel. {campos['celular']}")
        else:
            avisos.append("Sem celular no perfil: ele não aparece na imagem.")
    if opcoes.incluir_andar_lado:
        if campos["andar_lado"]:
            partes.append(campos["andar_lado"])
        else:
            avisos.append("Sem andar e lado no perfil: eles não aparecem na imagem.")
    return [" | ".join(partes)] if partes else []


def renderizar_png(dados: dict[str, str], opcoes: OpcoesAssinatura | None = None) -> tuple[bytes, list[str], int]:
    """PNG da assinatura, os avisos (texto abreviado, campos ausentes) e a largura de exibição em pixels.

    O espaço vertical do modelo é limitado (as redes sociais ficam embaixo). Tenta, nesta ordem: endereço em duas linhas com as
    linhas extras, endereço numa linha só com as extras, e por fim sem as extras (com aviso).
    """
    _exigir(dados)
    opcoes = opcoes or OpcoesAssinatura()
    try:
        tentativas = [(True, True), (False, True), (True, False), (False, False)]
        for duas_linhas, com_extras in tentativas:
            avisos: list[str] = []
            modelo = assinatura_pptx.carregar(MODELO)
            assinatura_pptx.marcar_alturas(modelo)
            campos = _campos(dados, duas_linhas, avisos)
            extras = _extras(campos, opcoes, avisos)
            quer_extras = bool(extras)
            if not com_extras:
                extras = []
            assinatura_pptx.preencher(modelo, campos, extras)
            coube = assinatura_pptx.compactar(modelo, modelo.altura * LIMITE_INFERIOR)
            if coube or (duas_linhas, com_extras) == tentativas[-1]:
                if quer_extras and not extras:
                    avisos.append("Celular e andar/lado não couberam no modelo e ficaram de fora da imagem.")
                if not coube:
                    avisos.append("O texto é maior que o espaço do modelo e pode encostar nas redes sociais.")
                break
        imagem = assinatura_pptx.desenhar(modelo, avisos)
    except assinatura_pptx.ErroModelo as erro:
        raise ErroAssinatura(str(erro)) from erro
    largura_exibicao = round(modelo.largura / EMU_POR_PIXEL)
    dpi = round(imagem.width / (modelo.largura / 914400))
    saida = io.BytesIO()
    imagem.save(saida, format="PNG", optimize=True, dpi=(dpi, dpi))
    return saida.getvalue(), list(dict.fromkeys(avisos)), largura_exibicao


# --- HTML ---------------------------------------------------------------------------------------

def html_assinatura(dados: dict[str, str], png: bytes, largura_exibicao: int, opcoes: OpcoesAssinatura | None = None) -> str:
    """Assinatura em HTML: a imagem do Governo (exibida em `largura_exibicao` px) com o texto alternativo completo."""
    cfg = obter_configuracao()
    partes = [dados["nome_completo"], dados["cargo"], (dados.get("departamento") or "").strip(), cfg.assinatura_secretaria, dados["email"],
              telefone_ramal(dados.get("ramal", "")), cfg.assinatura_endereco, cfg.assinatura_cidade]
    opcoes = opcoes or OpcoesAssinatura()
    if opcoes.incluir_celular and (dados.get("celular") or "").strip():
        partes.append(f"Cel. {formatar_celular(dados['celular'])}")
    if opcoes.incluir_andar_lado and localizacao(dados):
        partes.append(localizacao(dados))
    alternativo = escape(" – ".join(p.strip() for p in partes if p and p.strip()))
    origem = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    return (
        f'<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td style="padding:0">'
        f'<img src="{origem}" width="{largura_exibicao}" alt="{alternativo}" style="display:block;border:0;width:{largura_exibicao}px;height:auto">'
        f"</td></tr></table>"
    )


def gerar(dados: dict[str, str], opcoes: OpcoesAssinatura | None = None) -> Resultado:
    """PNG, HTML e avisos de uma vez (usado pela prévia)."""
    png, avisos, largura = renderizar_png(dados, opcoes)
    return Resultado(png=png, html=html_assinatura(dados, png, largura, opcoes), avisos=avisos)
