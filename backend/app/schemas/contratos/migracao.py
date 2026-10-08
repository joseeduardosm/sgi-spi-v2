# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados da importação do SGI SPI.
"""Importação do Módulo de Contratos do SGI SPI (`/api/contratos/migracao-sgi`)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class InicioMigracaoSgi(BaseModel):
    """Senhas de SSH pedidas na tela para rodar a importação (usadas só durante a execução)."""
    senha_origem: str = Field(..., min_length=1, max_length=256, description="Senha do usuário SSH no SGI (origem). Não é gravada.")
    senha_destino: str = Field(..., min_length=1, max_length=256, description="Senha do usuário SSH neste servidor (destino). Não é gravada.")


class EstadoMigracaoSgi(BaseModel):
    """Andamento da importação, consultado periodicamente pela tela."""
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


# --- Rascunho de um contrato do SGI (botão "Importar do SGI" da conta root) ---------------------

class PedidoRascunhoSgi(BaseModel):
    """Número do contrato no SGI e a senha do SSH de lá (usada só nesta leitura)."""
    numero: str = Field(..., pattern=r"^\s*\d{1,4}/\d{4}\s*$", description="Número no SGI, `NNN/AAAA` (ex.: `010/2024`).", examples=["010/2024"])
    senha_origem: str = Field(..., min_length=1, max_length=256, description="Senha do usuário SSH no SGI, também usada no sudo de lá. Não é gravada.")


class EmpresaRascunho(BaseModel):
    """Empresa do contrato no SGI. `id` preenchido = já cadastrada aqui (pelo CNPJ)."""
    id: str | None = Field(None, description="Id da empresa daqui com o mesmo CNPJ; nulo = precisa ser cadastrada.")
    cnpj: str
    razao_social: str
    nome_fantasia: str = ""
    endereco: str = ""
    ativa_aqui: bool = Field(True, description="Falso = a empresa existe aqui, mas está inativa (reative-a antes de salvar).")


class PrepostoRascunho(BaseModel):
    """Preposto ativo da empresa no SGI (cadastrado junto com a empresa, se ela for nova)."""
    cpf: str = ""
    nome: str
    telefone: str = ""
    email: str = ""
    cargo: str = ""


class MembroRascunho(BaseModel):
    """Integrante vigente da equipe no SGI, convertido para o usuário daqui."""
    papel: Literal["gestor", "gestor_suplente", "fiscal_administrativo", "fiscal_administrativo_suplente", "fiscal_tecnico", "fiscal_tecnico_suplente"]
    usuario_id: int
    login: str
    nome: str


class ItemRascunho(BaseModel):
    """Item como está no SGI (quantidades e valores em texto decimal, como a API recebe)."""
    descricao: str
    tipo: Literal["continuo", "sob_demanda"]
    calcula_pro_rata: bool
    codigo_classe: str = ""
    codigo_natureza_despesa: str = ""
    codigo_siafisico: str = ""
    codigo_catmat_catser: str = ""
    quantidade_mensal: str
    quantidade_total: str
    valor_unitario: str


class RascunhoContratoSgi(BaseModel):
    """Contrato do SGI pronto para preencher o formulário de cadastro. **Nada é gravado.**"""
    numero: str
    apelido: str
    objeto: str
    data_inicio: str
    vigencia_inicial_meses: int
    vigencia_maxima_meses: int
    periodicidade_meses: int
    mes_reajuste: int
    sei_gestao_numero: str
    sei_gestao_link: str
    sei_execucao_numero: str
    sei_execucao_link: str
    empresa: EmpresaRascunho
    prepostos: list[PrepostoRascunho]
    equipe: list[MembroRascunho]
    itens: list[ItemRascunho]
    avisos: list[str] = Field([], description="O que não veio ou precisa de atenção (usuário sem conta aqui, prorrogações, execução…).")
