# Criado por José Eduardo Santana Martins
# Este arquivo serve para reunir o que os passos da carga histórica do contrato 010/2024 têm em comum (sessão, autor, caminhos e dados fixos).
"""Apoio da carga histórica do contrato 010/2024 (Outsourcing PRODESP). Tudo é feito como o usuário jesmartins, pelas regras do sistema."""
import os
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.contratos import Contrato
from app.models.usuario import Usuario

PROCESSO = Path("/home/administrador/projeto/apoio/processos-pagamentos/SEI_021.00001802_2024_10_outsourcingProdesp")
TERMOS = PROCESSO / "termos_aditivos"
ALVO = os.environ.get("CARGA_ALVO", "ensaio")
D = Decimal


def abrir():
    """(sessão, contrato 010/2024, autor jesmartins)."""
    sessao = FabricaSessao()
    s = sessao.__enter__()
    contrato = s.scalar(select(Contrato).where(Contrato.numero == "010/2024"))
    autor = s.scalar(select(Usuario).where(Usuario.login == "jesmartins"))
    assert contrato is not None and autor is not None
    return sessao, s, contrato, autor


def arquivo(caminho: Path) -> tuple:
    """(arquivo aberto, nome) no formato que os serviços de upload esperam."""
    return open(caminho, "rb"), caminho.name
