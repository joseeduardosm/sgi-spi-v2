"""Metadados dos arquivos anexados. O conteúdo fica em disco (ver `servico_anexos`)."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc


class Anexo(Base):
    __tablename__ = "anexos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nome_original: Mapped[str] = mapped_column(String(255))
    # Caminho relativo ao diretório de anexos (AAAA/MM/<uuid>.pdf)
    chave_armazenamento: Mapped[str] = mapped_column(String(300), unique=True)
    tipo_conteudo: Mapped[str] = mapped_column(String(150))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    tamanho: Mapped[int] = mapped_column(BigInteger)
    # Origem do anexo, com prefixo do módulo (ex.: `contrato-documento`, `contrato-execucao-nf`)
    categoria: Mapped[str] = mapped_column(String(100), index=True)
    enviado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Contrato dono do arquivo (sem chave estrangeira: o registro do anexo sobrevive à exclusão do contrato)
    contrato_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    excluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
