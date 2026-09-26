# Criado por José Eduardo Santana Martins
# Este arquivo serve para reunir os modelos (tabelas) do módulo de contratos.
"""Modelos do módulo de contratos (tabelas com prefixo `contratos`).

Organização dos arquivos:
- `empresa.py`: empresas contratadas e prepostos;
- `contrato.py`: contrato, itens, equipe de gestão/fiscalização e documentos importantes;
- `orcamento.py`: previsão orçamentária e Notas de Empenho;
- `execucao.py`: checklists, formulários, competências e tudo o que é registrado nas etapas;
- `alteracoes.py`: prorrogação, reajuste e aditamento/supressão;
- `diario.py`: diário de bordo (ocorrências) e glosas.

Este arquivo reexporta as classes para que o restante do código importe de um lugar só.
"""

from app.models.contratos.alteracoes import (
    AlteracaoQuantidade,
    CienciaAlteracao,
    CienciaProrrogacao,
    ItemAlteracao,
    ItemReajuste,
    MemoriaReajuste,
    ProcessoProrrogacao,
    Prorrogacao,
    Reajuste,
)
from app.models.contratos.contrato import (
    PAPEIS_EQUIPE,
    Contrato,
    DesignacaoEquipe,
    DocumentoContrato,
    ItemContrato,
)
from app.models.contratos.diario import GlosaOcorrencia, OcorrenciaDiario
from app.models.contratos.empresa import EmpresaContratada, PrepostoEmpresa
from app.models.contratos.execucao import (
    ETAPAS,
    AvaliacaoCompetencia,
    Checklist,
    CienciaMedicao,
    Competencia,
    ConsultaCadin,
    DocumentoMensal,
    FormularioAvaliacao,
    ItemChecklist,
    ItemMedicao,
    MemoriaMedicao,
    ModeloGlobal,
    SelecaoNotaEmpenho,
)
from app.models.contratos.orcamento import (
    ApontamentoPrevisao,
    LimitePrevisao,
    MovimentoNotaEmpenho,
    NotaEmpenho,
    PrevisaoVigencia,
)

__all__ = [
    "ETAPAS",
    "PAPEIS_EQUIPE",
    "AlteracaoQuantidade",
    "ApontamentoPrevisao",
    "AvaliacaoCompetencia",
    "Checklist",
    "CienciaAlteracao",
    "CienciaMedicao",
    "CienciaProrrogacao",
    "Competencia",
    "ConsultaCadin",
    "Contrato",
    "DesignacaoEquipe",
    "DocumentoContrato",
    "DocumentoMensal",
    "EmpresaContratada",
    "FormularioAvaliacao",
    "GlosaOcorrencia",
    "ItemAlteracao",
    "ItemChecklist",
    "ItemContrato",
    "ItemMedicao",
    "ItemReajuste",
    "LimitePrevisao",
    "MemoriaMedicao",
    "MemoriaReajuste",
    "ModeloGlobal",
    "MovimentoNotaEmpenho",
    "NotaEmpenho",
    "OcorrenciaDiario",
    "PrepostoEmpresa",
    "PrevisaoVigencia",
    "ProcessoProrrogacao",
    "Prorrogacao",
    "Reajuste",
    "SelecaoNotaEmpenho",
]
