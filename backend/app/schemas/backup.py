# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir os formatos de entrada e saída do backup geral do sistema (Administração › Backup).
"""Schemas do backup geral (banco + anexos)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BackupGuardado(BaseModel):
    """Um backup guardado no servidor (`dados/backups`)."""
    nome: str = Field(..., description="Nome do arquivo .zip (usado no download).")
    tamanho: int = Field(..., description="Tamanho em bytes.")
    criado_em: datetime
    antes_da_importacao: bool = Field(..., description="Gerado automaticamente antes de uma importação (o estado que foi substituído).")


class AndamentoBackup(BaseModel):
    """Situação da última operação (gerar ou importar), que roda em segundo plano."""
    operacao: Literal["gerar", "importar"] | None = None
    situacao: Literal["em_andamento", "concluido", "erro", "reiniciando"] | None = Field(
        None, description="`reiniciando`: a importação terminou e a API está reiniciando; consulte `GET /api/saude` até voltar.")
    mensagem: str = ""
    arquivo: str | None = Field(None, description="Backup gerado (ou, na importação, o backup automático do estado anterior).")
    etapa: str | None = Field(None, description="Etapa atual. Gerar: `banco`, `anexos`, `finalizar`. Importar: `guardar` (backup do estado atual), "
                                                "`banco`, `anexos`, `migracoes`, `reiniciar`. No erro, a etapa em que parou.")
    percentual: float | None = Field(None, description="Quanto da operação já foi feito, de 0 a 100 (barra do modal de andamento).")
    atualizado_em: datetime | None = None


class LinkDownloadBackup(BaseModel):
    """Endereço assinado para o navegador baixar o backup direto."""
    url: str = Field(..., description="Caminho relativo (`/api/admin/backups/arquivo/{nome}/baixar?chave=…`).")
    expira_em: datetime


class PainelBackup(BaseModel):
    """Tela Administração › Backup."""
    backups: list[BackupGuardado]
    andamento: AndamentoBackup


class ManifestoBackup(BaseModel):
    """O que o backup enviado declara sobre si (conferido antes de importar)."""
    gerado_em: str | None = None
    servidor: str | None = None
    ambiente: str | None = None
    versao: str | None = None
    revisao_banco: str | None = None
    gerado_por: str | None = None
    anexos: int | None = None
