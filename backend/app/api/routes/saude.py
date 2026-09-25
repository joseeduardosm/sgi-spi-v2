# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a rota de verificação de disponibilidade da API.

from fastapi import APIRouter

from app.core.configuracao import obter_configuracao
from app.schemas.comum import RespostaSaude

roteador = APIRouter(tags=["Sistema"])


@roteador.get("/saude", response_model=RespostaSaude, summary="Verificar disponibilidade da API")
def verificar_saude() -> RespostaSaude:
    return RespostaSaude(situacao="ok", versao=obter_configuracao().versao_aplicacao)
