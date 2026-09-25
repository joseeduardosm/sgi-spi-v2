"""Importação do Módulo de Contratos do SGI SPI (`/api/contratos/migracao-sgi`)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class InicioMigracaoSgi(BaseModel):
    senha_origem: str = Field(..., min_length=1, max_length=256, description="Senha do usuário SSH no SGI (origem). Não é gravada.")
    senha_destino: str = Field(..., min_length=1, max_length=256, description="Senha do usuário SSH neste servidor (destino). Não é gravada.")


class EstadoMigracaoSgi(BaseModel):
    situacao: Literal["ociosa", "executando", "concluida", "erro"]
    etapa: str | None = Field(None, description="`iniciando`, `extraindo`, `carregando` ou `concluida`.")
    mensagem: str = ""
    origem: str = Field(..., description="Usuário e servidor de origem (ex.: `administrador@10.23.1.220`).")
    destino: str = Field(..., description="Usuário e servidor de destino.")
    iniciada_em: datetime | None = None
    concluida_em: datetime | None = None
    iniciada_por: str | None = None
    resultado: dict[str, int] | None = Field(None, description="Quantidade carregada por tipo (empresas, contratos, competências, anexos…).")
    avisos: list[str] = []
    log: list[str] = Field([], description="Últimas linhas do registro da execução.")
