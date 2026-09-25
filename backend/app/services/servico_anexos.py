# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar anexos em disco, validar PDFs e entregar os downloads.
"""Armazenamento de anexos PDF em disco, com metadados na tabela `anexos`.

Regras: somente PDF não vazio (assinatura `%PDF-`), até `ANEXOS_TAMANHO_MAXIMO_MB`, com SHA-256
calculado no envio. O arquivo é gravado primeiro em um temporário e movido ao destino, para que
um envio interrompido não deixe arquivo parcial com nome definitivo.
"""

import hashlib
import os
import re
import tempfile
import unicodedata
import uuid
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.core.configuracao import obter_configuracao
from app.models.anexo import Anexo

ASSINATURA_PDF = b"%PDF-"
TIPO_PDF = "application/pdf"
TAMANHO_BLOCO = 1024 * 1024


class ErroAnexo(Exception):
    """Arquivo recusado (não é PDF, vazio ou grande demais)."""


def diretorio_anexos() -> Path:
    return Path(obter_configuracao().anexos_diretorio)


def tamanho_maximo() -> int:
    return obter_configuracao().anexos_tamanho_maximo_mb * 1024 * 1024


def _blocos(origem: BinaryIO) -> Iterator[bytes]:
    while bloco := origem.read(TAMANHO_BLOCO):
        yield bloco


def guardar_pdf(
    sessao: Session, origem: BinaryIO, nome_original: str, categoria: str, enviado_por_id: int | None, contrato_id: uuid.UUID | None = None
) -> Anexo:
    """Valida e grava o PDF; devolve o `Anexo` já adicionado à sessão (sem commit)."""
    limite = tamanho_maximo()
    agora = agora_utc()
    identificador = uuid.uuid4()
    chave = f"{agora:%Y}/{agora:%m}/{identificador.hex}.pdf"
    destino = diretorio_anexos() / chave
    destino.parent.mkdir(parents=True, exist_ok=True)

    resumo = hashlib.sha256()
    tamanho = 0
    inicio = b""
    descritor, caminho_temporario = tempfile.mkstemp(dir=destino.parent, suffix=".parcial")
    try:
        with os.fdopen(descritor, "wb") as temporario:
            for bloco in _blocos(origem):
                if len(inicio) < len(ASSINATURA_PDF):
                    inicio += bloco[: len(ASSINATURA_PDF) - len(inicio)]
                tamanho += len(bloco)
                if tamanho > limite:
                    raise ErroAnexo(f"O arquivo excede o limite de {obter_configuracao().anexos_tamanho_maximo_mb} MB.")
                resumo.update(bloco)
                temporario.write(bloco)
        if tamanho == 0:
            raise ErroAnexo("O arquivo está vazio.")
        if inicio != ASSINATURA_PDF:
            raise ErroAnexo("Envie um arquivo PDF.")
        os.replace(caminho_temporario, destino)
    except BaseException:
        Path(caminho_temporario).unlink(missing_ok=True)
        raise

    anexo = Anexo(
        id=identificador,
        nome_original=(nome_original or "documento.pdf")[:255],
        chave_armazenamento=chave,
        tipo_conteudo=TIPO_PDF,
        sha256=resumo.hexdigest(),
        tamanho=tamanho,
        categoria=categoria,
        enviado_por_id=enviado_por_id,
        contrato_id=contrato_id,
    )
    sessao.add(anexo)
    return anexo


def guardar_pdf_gerado(
    sessao: Session, conteudo: bytes, nome: str, categoria: str, gerado_por_id: int | None, contrato_id: uuid.UUID | None = None
) -> Anexo:
    """Grava um PDF produzido pelo próprio sistema (memórias, pareceres, consolidados)."""
    return guardar_pdf(sessao, BytesIO(conteudo), nome, categoria, gerado_por_id, contrato_id)


def guardar_arquivo_gerado(
    sessao: Session, conteudo: bytes, nome: str, tipo_conteudo: str, categoria: str, gerado_por_id: int | None,
    contrato_id: uuid.UUID | None = None,
) -> Anexo:
    """Grava um arquivo produzido pelo sistema que não é PDF (ex.: memórias em XLSX)."""
    agora = agora_utc()
    identificador = uuid.uuid4()
    extensao = Path(nome).suffix.lower() or ".bin"
    chave = f"{agora:%Y}/{agora:%m}/{identificador.hex}{extensao}"
    destino = diretorio_anexos() / chave
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)
    anexo = Anexo(
        id=identificador, nome_original=nome[:255], chave_armazenamento=chave, tipo_conteudo=tipo_conteudo,
        sha256=hashlib.sha256(conteudo).hexdigest(), tamanho=len(conteudo), categoria=categoria, enviado_por_id=gerado_por_id,
        contrato_id=contrato_id,
    )
    sessao.add(anexo)
    return anexo


def caminho(anexo: Anexo) -> Path:
    return diretorio_anexos() / anexo.chave_armazenamento


def nome_seguro(nome: str) -> str:
    """Nome de arquivo sem acentos nem caracteres problemáticos para download."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    limpo = re.sub(r"[^A-Za-z0-9._-]+", "_", sem_acento).strip("._")
    return limpo or "documento.pdf"


def resposta_download(anexo: Anexo, nome_download: str | None = None) -> FileResponse:
    """Resposta HTTP com o arquivo. Levanta `ErroAnexo` se o arquivo sumiu do disco."""
    arquivo = caminho(anexo)
    if anexo.excluido_em is not None or not arquivo.is_file():
        raise ErroAnexo("O arquivo não está mais disponível.")
    return FileResponse(arquivo, media_type=anexo.tipo_conteudo, filename=nome_seguro(nome_download or anexo.nome_original))


def descartar(anexo: Anexo) -> None:
    """Exclusão lógica: o arquivo permanece em disco para auditoria."""
    anexo.excluido_em = agora_utc()
