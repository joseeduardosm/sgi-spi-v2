# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a rota de verificação de disponibilidade da API.
"""Rota pública `GET /api/saude`, usada por monitoramento e pelo script de deploy para saber se a API subiu."""

from fastapi import APIRouter

from app.core.configuracao import obter_configuracao
from app.schemas.comum import RespostaSaude

roteador = APIRouter(tags=["Sistema"])


@roteador.get("/saude", response_model=RespostaSaude, summary="Verificar disponibilidade da API")
def verificar_saude() -> RespostaSaude:
    """Responde "ok" com a versão da API. Não consulta o banco: indica só que o processo está no ar."""
    config = obter_configuracao()
    return RespostaSaude(situacao="ok", versao=config.versao_aplicacao, homologacao=config.modo_homologacao)
