# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir a tabela com os metadados dos arquivos anexados.
"""Metadados dos arquivos anexados. O conteúdo fica em disco (ver `servico_anexos`).

Guardar só os metadados no banco mantém a base leve; o arquivo em si fica no diretório de
anexos, identificado pela `chave_armazenamento`. O SHA-256 permite conferir a integridade
(usado, por exemplo, na migração do SGI) e detectar arquivos repetidos.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc


class Anexo(Base):
    """Um arquivo enviado (hoje sempre PDF) e quem o enviou."""
    __tablename__ = "anexos"

    # Chave primária UUID gerada pela aplicação (não pelo banco)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Nome do arquivo como veio do computador do usuário (usado só para exibição)
    nome_original: Mapped[str] = mapped_column(String(255))
    # Caminho relativo ao diretório de anexos (AAAA/MM/<uuid>.pdf)
    chave_armazenamento: Mapped[str] = mapped_column(String(300), unique=True)
    # Tipo MIME (ex.: application/pdf), tamanho em bytes e hash do conteúdo
    tipo_conteudo: Mapped[str] = mapped_column(String(150))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    tamanho: Mapped[int] = mapped_column(BigInteger)
    # Origem do anexo, com prefixo do módulo (ex.: `contrato-documento`, `contrato-execucao-nf`)
    categoria: Mapped[str] = mapped_column(String(100), index=True)
    enviado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Contrato dono do arquivo (sem chave estrangeira: o registro do anexo sobrevive à exclusão do contrato)
    contrato_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    # Exclusão lógica: preenchido quando o anexo é substituído ou removido; o arquivo continua guardado
    excluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
