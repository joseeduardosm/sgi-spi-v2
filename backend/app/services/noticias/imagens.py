# Criado por José Eduardo Santana Martins
# Este arquivo serve para validar imagens enviadas e gerar as versões WebP da capa (2:1) e dos atalhos.
"""Imagens do portal.

- **Capa 2:1:** o redator envia a imagem em qualquer proporção. No modo `recortar`, vale o retângulo 2:1 escolhido no
  editor (ou o maior retângulo central, se nenhum for informado). No modo `inteira`, a arte aparece inteira sobre um
  fundo desfocado dela mesma, sem cortes (bom para cartazes com texto). São geradas versões 1600×800, 800×400 e 400×200.
- **Atalho:** a imagem é reduzida para 480 px de largura, mantendo a proporção.
"""

from io import BytesIO

from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError

TAMANHOS_CAPA = (1600, 800, 400)
FORMATOS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
TAMANHO_MAXIMO = 15 * 1024 * 1024
LARGURA_MINIMA = 800


class ErroImagem(Exception):
    """Imagem recusada (formato, tamanho ou conteúdo)."""


def abrir(conteudo: bytes) -> tuple[Image.Image, str]:
    """Abre e confere a imagem pelo conteúdo; devolve a imagem (orientação corrigida, RGB) e o tipo MIME do original."""
    if not conteudo:
        raise ErroImagem("O arquivo está vazio.")
    if len(conteudo) > TAMANHO_MAXIMO:
        raise ErroImagem("A imagem passa de 15 MB.")
    try:
        imagem = Image.open(BytesIO(conteudo))
        formato = imagem.format
        imagem.load()
    except (UnidentifiedImageError, OSError) as erro:
        raise ErroImagem("O arquivo não é uma imagem válida (envie JPG, PNG ou WebP).") from erro
    if formato not in FORMATOS:
        raise ErroImagem("Formato não aceito: envie JPG, PNG ou WebP.")
    imagem = ImageOps.exif_transpose(imagem)
    return imagem.convert("RGB"), FORMATOS[formato]


def recorte_padrao(largura: int, altura: int) -> dict:
    """Maior retângulo 2:1 centralizado."""
    if largura / altura >= 2:
        w, h = altura * 2, altura
    else:
        w, h = largura, largura // 2
    return {"x": (largura - w) // 2, "y": (altura - h) // 2, "largura": w, "altura": h}


def normalizar_recorte(recorte: dict | None, largura: int, altura: int) -> dict:
    """Recorte dentro da imagem e na proporção 2:1 (ajusta a altura pela largura)."""
    if not recorte:
        return recorte_padrao(largura, altura)
    w = max(20, min(int(recorte.get("largura", largura)), largura))
    h = min(w // 2, altura)
    w = h * 2
    x = max(0, min(int(recorte.get("x", 0)), largura - w))
    y = max(0, min(int(recorte.get("y", 0)), altura - h))
    return {"x": x, "y": y, "largura": w, "altura": h}


def _webp(imagem: Image.Image) -> bytes:
    saida = BytesIO()
    imagem.save(saida, "WEBP", quality=82, method=6)
    return saida.getvalue()


def _inteira(imagem: Image.Image, largura: int) -> Image.Image:
    """Arte inteira centralizada sobre um fundo 2:1 desfocado e escurecido da própria imagem."""
    altura = largura // 2
    fundo = ImageOps.fit(imagem, (largura, altura), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=largura // 40))
    fundo = ImageEnhance.Brightness(fundo).enhance(0.72)
    frente = ImageOps.contain(imagem, (largura, altura), Image.Resampling.LANCZOS)
    fundo.paste(frente, ((largura - frente.width) // 2, (altura - frente.height) // 2))
    return fundo


def versoes_capa(imagem: Image.Image, modo: str, recorte: dict | None) -> tuple[dict[str, bytes], dict]:
    """Versões WebP da capa ({"1600": bytes, …}) e o recorte efetivamente usado."""
    usado = normalizar_recorte(recorte, imagem.width, imagem.height)
    if modo == "recortar":
        base = imagem.crop((usado["x"], usado["y"], usado["x"] + usado["largura"], usado["y"] + usado["altura"]))
        versoes = {str(t): _webp(base.resize((t, t // 2), Image.Resampling.LANCZOS)) for t in TAMANHOS_CAPA}
    else:
        versoes = {str(t): _webp(_inteira(imagem, t)) for t in TAMANHOS_CAPA}
    return versoes, usado


def versao_atalho(imagem: Image.Image) -> bytes:
    """Imagem do atalho com 480 px de largura."""
    return _webp(ImageOps.contain(imagem, (480, 480), Image.Resampling.LANCZOS))
