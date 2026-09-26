# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato da prévia da importação de contrato por planilha XLSX.
"""Schemas da importação de contrato por planilha XLSX (`/api/contratos/importacao-xlsx`).

A prévia mostra o que foi lido da planilha, já convertido, junto com os erros (que impedem a
importação) e os avisos (que só informam). Os campos do contrato são opcionais porque uma
célula pode estar vazia ou inválida; nesse caso, o problema aparece em `erros`.
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.schemas.contratos.tipos import ValorMonetario, ValorQuantidade


class ErroImportacao(BaseModel):
    """Problema que impede a importação, com a linha da planilha em que está."""

    linha: int | None = Field(None, description="Linha da planilha (1 = primeira). Nulo para erros do arquivo como um todo.")
    campo: str = Field(..., description="Rótulo do campo na planilha (ex.: `CNPJ`, `Item 2 · Classe`).")
    mensagem: str


class ContratoPrevia(BaseModel):
    """Dados do contrato lidos da planilha (vazios quando a célula está em branco ou inválida)."""

    numero: str | None = None
    apelido: str = ""
    objeto: str = ""
    data_inicio: date | None = None
    data_fim: date | None = Field(None, description="Fim da vigência inicial, calculado (início + vigência − 1 dia).")
    vigencia_inicial_meses: int | None = None
    vigencia_maxima_meses: int | None = None
    periodicidade_meses: int | None = None
    mes_reajuste: int | None = None
    sei_gestao_numero: str = ""
    sei_gestao_link: str = ""
    sei_execucao_numero: str = ""
    sei_execucao_link: str = ""


class EmpresaPrevia(BaseModel):
    """Empresa da planilha: já cadastrada (reaproveitada sem alteração) ou nova."""

    existente: bool = Field(..., description="Verdadeiro se o CNPJ já está cadastrado; os dados cadastrados são mantidos.")
    id: uuid.UUID | None = Field(None, description="Id da empresa existente.")
    cnpj: str = Field("", description="14 dígitos, sem máscara.")
    razao_social: str = ""
    nome_fantasia: str = ""
    endereco: str = ""


class PrepostoPrevia(BaseModel):
    """Preposto da planilha: já cadastrado na empresa (reaproveitado) ou novo."""

    existente: bool
    cpf: str = Field("", description="11 dígitos, sem máscara.")
    nome: str = ""
    email: str = ""
    telefone: str = ""


class ItemPrevia(BaseModel):
    """Item financeiro lido de uma linha da tabela de itens."""

    linha: int
    descricao: str
    tipo: str | None = Field(None, description="`continuo` ou `sob_demanda`.")
    calcula_pro_rata: bool | None = None
    unidade_fornecimento: str = Field("", description="Unidade de Fornecimento (UF), se a planilha tiver a coluna.")
    codigo_classe: str = ""
    codigo_natureza_despesa: str = ""
    codigo_siafisico: str = ""
    codigo_catmat_catser: str = ""
    quantidade_mensal: ValorQuantidade | None = None
    quantidade_total: ValorQuantidade | None = Field(None, description="Só para sob demanda: teto da vigência inicial.")
    valor_unitario: ValorMonetario | None = None


class PreviaImportacao(BaseModel):
    """Resposta do `POST /previa`: o que será cadastrado e o que impede ou merece atenção."""

    contrato: ContratoPrevia
    empresa: EmpresaPrevia | None
    preposto: PrepostoPrevia | None = Field(None, description="Nulo quando o bloco do preposto está em branco.")
    itens: list[ItemPrevia]
    valor_global_estimado: ValorMonetario | None = Field(
        None, description="Contínuos: quantidade mensal × preço × vigência inicial; sob demanda: teto × preço."
    )
    erros: list[ErroImportacao]
    avisos: list[str]
    pode_importar: bool = Field(..., description="Verdadeiro quando não há erros.")
