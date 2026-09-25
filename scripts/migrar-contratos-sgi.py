#!/usr/bin/env python3
"""Migra o Módulo de Contratos do SGI SPI (10.23.1.220) para o contratos-spi.

Lê o pacote gerado por `scripts/extrair-contratos-sgi.py` (ou pelo `deploy/sql/backup-modulo-contratos.sh`
do SGI) e carrega empresas, contratos, orçamento, execução, reajustes, prorrogações, anexos e auditoria.

Regras (docs/migracao-sgi.md):
- os UUIDs de origem são preservados;
- usuários (`*UserId`) são convertidos pelo `usuarios.csv`, casando login ou id externo (AD);
  quem não existir aqui é criado inativo, sem senha;
- fotografias (itens da medição, itens do reajuste, nomes nas ciências, formulário copiado) não são
  recalculadas;
- competências entram como estão (períodos pelo aniversário do contrato);
- anexos são copiados para ANEXOS_DIRETORIO com o SHA-256 conferido.

Uso (como o usuário do projeto, na pasta backend/):
    .venv/bin/python ../scripts/migrar-contratos-sgi.py <pacote>            # ensaio: carrega, confere e desfaz
    .venv/bin/python ../scripts/migrar-contratos-sgi.py <pacote> --gravar   # grava de verdade
    ... --gravar --substituir   # virada: apaga os dados do módulo aqui e recarrega (mesma transação)
"""

import argparse
import csv
import glob
import hashlib
import json
import shutil
import sys
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
csv.field_size_limit(sys.maxsize)

from sqlalchemy import func, select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.anexo import Anexo  # noqa: E402
from app.models.auditoria import RegistroAuditoria  # noqa: E402
from app.models.contratos import (  # noqa: E402
    AlteracaoQuantidade, ApontamentoPrevisao, AvaliacaoCompetencia, Checklist, CienciaAlteracao, CienciaMedicao,
    CienciaProrrogacao, Competencia, ConsultaCadin, Contrato, DesignacaoEquipe, DocumentoContrato, DocumentoMensal,
    EmpresaContratada, FormularioAvaliacao, ItemAlteracao, ItemChecklist, ItemContrato, ItemMedicao, ItemReajuste,
    LimitePrevisao, MemoriaMedicao, MemoriaReajuste, MovimentoNotaEmpenho, NotaEmpenho, PrepostoEmpresa, PrevisaoVigencia,
    ProcessoProrrogacao, Prorrogacao, Reajuste, SelecaoNotaEmpenho,
)
from app.models.contratos.execucao import ETAPAS  # noqa: E402
from app.models.usuario import OrigemUsuario, Usuario  # noqa: E402
from app.schemas.contratos.execucao import DefinicaoFormulario  # noqa: E402
from app.services import servico_anexos  # noqa: E402
from app.services.contratos import valores  # noqa: E402
from app.services.contratos.catalogo_documentos import POR_CODIGO  # noqa: E402
from app.services.contratos.servico_contratos import vigencias  # noqa: E402
from app.services.servico_auditoria import valor_json  # noqa: E402

# --- De-para de valores ------------------------------------------------------------------------

PAPEIS = {
    "Manager": "gestor", "ManagerSubstitute": "gestor_suplente",
    "AdministrativeInspector": "fiscal_administrativo", "AdministrativeInspectorSubstitute": "fiscal_administrativo_suplente",
    "TechnicalInspector": "fiscal_tecnico", "TechnicalInspectorSubstitute": "fiscal_tecnico_suplente",
}
ETAPAS_SGI = {
    "Measurement": "medicao", "Evaluation": "avaliacao", "Invoice": "nota_fiscal", "Cadin": "cadin", "Checklist": "checklist",
    "Download": "consolidado", "BankOrder": "ordem_bancaria", "Completed": "concluida",
}
PERIODICIDADES = {"Monthly": 1, "Bimonthly": 2, "Quarterly": 3, "Semiannual": 6, "Semiannually": 6, "Annual": 12, "Yearly": 12}
SITUACOES_CONTRATO = {"Active": "ativo", "Expiring": "a_vencer", "Ended": "encerrado", "Suspended": "suspenso"}
SITUACOES_REAJUSTE = {"Draft": "rascunho", "Completed": "concluido", "Cancelled": "cancelado"}
SITUACOES_ALTERACAO = {"Draft": "rascunho", "AwaitingAcknowledgements": "aguardando_ciencias", "Completed": "concluida", "Cancelled": "cancelada"}
TIPOS_ALTERACAO = {"Addition": "aditamento", "Suppression": "supressao"}
TIPOS_ITEM = {"Continuous": "continuo", "OnDemand": "sob_demanda"}
CATEGORIAS = {
    "contract-important": "contrato-documento",
    "contract-extension": "contrato-prorrogacao-termo",
    "contract-extension-report": "contrato-prorrogacao-parecer",
    "contract-adjustment-memory": "contrato-reajuste-memoria",
    "contract-adjustment-evidence": "contrato-reajuste-evidencia",
    "contract-adjustment-apostille": "contrato-reajuste-apostilamento",
    "contract-execution-checklist": "contrato-execucao-checklist",
    "contract-execution-measurement-memory": "contrato-execucao-memoria",
    "contract-execution-cadin-certificate": "contrato-execucao-cadin-certidao",
    "contract-execution-cadin-communication": "contrato-execucao-cadin-email",
    "contract-execution-invoice": "contrato-execucao-nf",
    "contract-execution-additional-invoice": "contrato-execucao-nf-adicional",
    "contract-execution-consolidated": "contrato-execucao-consolidado",
    "contract-execution-evaluation": "contrato-execucao-avaliacao",
    "contract-execution-evaluation-signed": "contrato-execucao-avaliacao-assinada",
    "contract-execution-evaluation-reconsideration": "contrato-execucao-reconsideracao",
    "contract-execution-bank-order": "contrato-execucao-ob",
}
PRIMEIRO_CODIGO_TERMO = 24


# --- Leitura do pacote -------------------------------------------------------------------------

class Pacote:
    def __init__(self, pasta: Path):
        self.pasta = pasta

    def tabela(self, nome: str) -> list[dict[str, str]]:
        arquivos = glob.glob(str(self.pasta / "dados" / f"*_{nome}.csv"))
        if not arquivos:
            return []
        with open(arquivos[0], encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))


def texto(v: str | None) -> str:
    return v or ""


def nulo(v: str | None) -> str | None:
    return v if v not in (None, "") else None


def id_(v: str | None) -> uuid.UUID | None:
    return uuid.UUID(v) if nulo(v) else None


def inteiro(v: str | None) -> int | None:
    return int(v) if nulo(v) else None


def decimal(v: str | None, padrao: Decimal | None = Decimal(0)) -> Decimal | None:
    return Decimal(v) if nulo(v) else padrao


def booleano(v: str | None) -> bool:
    return (v or "").lower() in ("t", "true", "1")


def instante(v: str | None) -> datetime | None:
    if not nulo(v):
        return None
    v = v.replace(" ", "T", 1)
    if v[-3] in "+-" and v[-6] != ":" and ":" not in v[-3:]:
        v += ":00"
    return datetime.fromisoformat(v)


def dia(v: str | None) -> date | None:
    if not nulo(v):
        return None
    return date.fromisoformat(v[:10])


def json_(v: str | None, padrao):
    return json.loads(v) if nulo(v) else padrao


def chave(d: dict, nome: str):
    """Lê a chave do JSON sem diferenciar maiúsculas de minúsculas (o SGI mistura PascalCase e camelCase)."""
    for k, v in d.items():
        if k.lower() == nome.lower():
            return v
    return None


# --- Conversões de JSON ------------------------------------------------------------------------

def definicao(origem: dict, contexto: str | None = None) -> dict:
    """Converte a definição do formulário. `contexto` (ex.: `"Qualidade" do contrato 015/2026`) liga o aviso de regra violada."""
    grupos = sorted(chave(origem, "Groups") or [], key=lambda g: chave(g, "Order") or 0)
    dados = {
        "escala": [{"valor": str(chave(n, "Value")), "legenda": texto(chave(n, "Label"))} for n in chave(origem, "Scale") or []],
        "faixas": [
            {"minimo": str(chave(f, "Minimum")), "maximo": None if chave(f, "Maximum") is None else str(chave(f, "Maximum")),
             "percentual": str(chave(f, "Percentage"))}
            for f in chave(origem, "Ranges") or []
        ],
        "grupos": [
            {"id": chave(g, "Id"), "nome": texto(chave(g, "Name")),
             "itens": [{"id": chave(i, "Id"), "nome": texto(chave(i, "Name")), "descricao": texto(chave(i, "Description")),
                        "peso": str(chave(i, "Weight"))}
                       for i in sorted(chave(g, "Items") or [], key=lambda i: chave(i, "Order") or 0)]}
            for g in grupos
        ],
    }
    # Valida pelas mesmas regras da API e normaliza; ids de grupos e itens são mantidos (as respostas apontam para eles)
    try:
        normalizada = valor_json(DefinicaoFormulario.model_validate(dados).model_dump())
        for g_orig, g in zip(dados["grupos"], normalizada["grupos"]):
            g["id"] = g_orig["id"]
            for i_orig, i in zip(g_orig["itens"], g["itens"]):
                i["id"] = i_orig["id"]
        return normalizada
    except ValueError as erro:
        if contexto:
            motivos = "; ".join(e["msg"].removeprefix("Value error, ") for e in erro.errors()) if hasattr(erro, "errors") else str(erro)
            avisos.append(f"formulário {contexto} importado como está, mas fora das regras daqui: {motivos}")
        return dados


def respostas(origem: list) -> list:
    return [{"item_id": chave(r, "ItemId"), "nota": str(chave(r, "Grade")), "justificativa": texto(chave(r, "Justification"))}
            for r in origem or []]


# --- Migração ----------------------------------------------------------------------------------

avisos: list[str] = []


def migrar(pacote: Pacote, sessao, gravar: bool) -> dict:
    # Usuários: Id do SGI → id local
    locais = list(sessao.scalars(select(Usuario)))
    por_login = {u.login.lower(): u for u in locais}
    por_externo = {u.id_externo.lower(): u for u in locais if u.id_externo}
    sgi_usuarios = {r["Id"]: r for r in pacote.tabela("usuarios") or _usuarios_csv(pacote)}
    mapa_usuarios: dict[str, int | None] = {}
    criados: list[str] = []

    def usuario(v: str | None) -> int | None:
        if not nulo(v):
            return None
        if v in mapa_usuarios:
            return mapa_usuarios[v]
        origem = sgi_usuarios.get(v)
        if origem is None:
            avisos.append(f"usuário {v} do SGI não está no usuarios.csv: referência ficou vazia")
            mapa_usuarios[v] = None
            return None
        local = por_login.get(texto(origem["Username"]).lower()) or por_externo.get(texto(origem["ExternalId"]).lower())
        if local is None and "ldap" not in texto(origem["Origin"]).lower() and booleano(origem["IsSuperuser"]):
            # Conta administrativa local do SGI (ex.: `admin`) = conta administrativa local daqui (`root`)
            local = next((u for u in locais if u.superusuario and u.origem == OrigemUsuario.LOCAL), None)
        if local is None:
            ldap = "ldap" in texto(origem["Origin"]).lower()
            local = Usuario(
                login=origem["Username"], hash_senha=None, ativo=False, superusuario=False,
                origem=OrigemUsuario.LDAP if ldap else OrigemUsuario.LOCAL, id_externo=nulo(origem["ExternalId"]),
                nome_completo=texto(origem["FullName"])[:200], email=texto(origem["Email"])[:254],
                departamento=texto(origem["Department"])[:150], cargo=texto(origem["JobTitle"])[:150],
            )
            sessao.add(local)
            sessao.flush()
            por_login[local.login.lower()] = local
            criados.append(local.login)
        mapa_usuarios[v] = local.id
        return local.id

    # Anexos: dono (contrato) de cada arquivo, apurado pelas tabelas que o referenciam
    dono_anexo: dict[uuid.UUID, uuid.UUID] = {}

    def anexo(v: str | None, contrato_id: uuid.UUID) -> uuid.UUID | None:
        ident = id_(v)
        if ident:
            dono_anexo.setdefault(ident, contrato_id)
        return ident

    t = pacote.tabela
    contador = Counter()

    # 1-2 Empresas e prepostos
    for r in t("contract_companies"):
        sessao.add(EmpresaContratada(id=id_(r["Id"]), cnpj="".join(filter(str.isdigit, r["Cnpj"])), razao_social=r["CorporateName"],
                                     nome_fantasia=texto(r["TradeName"]), endereco=texto(r.get("Address")), ativa=booleano(r["Active"]),
                                     criado_em=instante(r["CreatedAt"]), atualizado_em=instante(r["UpdatedAt"])))
        contador["empresas"] += 1
    sessao.flush()
    for r in t("company_representatives"):
        sessao.add(PrepostoEmpresa(id=id_(r["Id"]), empresa_id=id_(r["CompanyId"]), cpf="".join(filter(str.isdigit, r["Cpf"])),
                                   nome=r["Name"], telefone=texto(r["Phone"]), email=texto(r["Email"]), cargo=texto(r["JobTitle"]),
                                   ativo=booleano(r["Active"]), criado_em=instante(r["CreatedAt"]), atualizado_em=instante(r["UpdatedAt"])))
        contador["prepostos"] += 1

    # 3 Metadados dos anexos (o arquivo é copiado no fim, só quando grava)
    linhas_anexos = t("stored_attachments")
    for r in linhas_anexos:
        categoria = CATEGORIAS.get(r["Category"], "contrato-legado-" + r["Category"].removeprefix("contract-"))[:100]
        sessao.add(Anexo(id=id_(r["Id"]), nome_original=r["OriginalName"][:255], chave_armazenamento=r["StorageKey"],
                         tipo_conteudo=texto(r["ContentType"]) or "application/pdf", sha256=r["Sha256"].lower(), tamanho=int(r["Size"]),
                         categoria=categoria, enviado_por_id=usuario(r["UploadedByUserId"]),
                         excluido_em=instante(r["DeletedAt"]), criado_em=instante(r["CreatedAt"])))
        contador["anexos"] += 1
    sessao.flush()

    # 4-7 Contratos, equipe, itens e documentos importantes
    # A fotografia do valor reajustado só vale enquanto a vigência reajustada for a atual (a prorrogação a descarta)
    vigencia_atual = Counter(r["ContractId"] for r in t("contract_term_extensions"))
    reajustada = {r["ContractId"]: int(r["VigencySequence"]) for r in t("contract_adjustments") if r["Status"] == "Completed"}
    contratos: dict[str, Contrato] = {}
    for r in t("contracts"):
        fotografia_vale = reajustada.get(r["Id"]) == vigencia_atual[r["Id"]] + 1
        periodicidade = r["ExecutionPeriodicity"]
        c = Contrato(
            id=id_(r["Id"]), sequencial=int(r["Sequence"]), ano=int(r["Year"]), empresa_id=id_(r["CompanyId"]),
            apelido=texto(r["Nickname"]), objeto=r["Object"], data_inicio=dia(r["StartDate"]), data_fim=dia(r["EndDate"]),
            vigencia_inicial_meses=int(r["InitialTermMonths"]), vigencia_maxima_meses=int(r["MaximumTermMonths"]),
            periodicidade_meses=int(periodicidade) if periodicidade.isdigit() else PERIODICIDADES[periodicidade],
            mes_reajuste=int(r["AdjustmentMonth"]), sei_gestao_numero=texto(r["ManagementSeiNumber"]), sei_gestao_link=texto(r["ManagementSeiUrl"]),
            sei_execucao_numero=texto(r["ExecutionSeiNumber"]), sei_execucao_link=texto(r["ExecutionSeiUrl"]),
            situacao_forcada=SITUACOES_CONTRATO.get(r["ForcedStatus"]) if nulo(r["ForcedStatus"]) else None,
            valor_global_reajustado=decimal(r["AdjustedGlobalValue"], None) if fotografia_vale else None, criador_id=usuario(r["CreatorUserId"]),
            criado_em=instante(r["CreatedAt"]), atualizado_em=instante(r["UpdatedAt"]),
        )
        sessao.add(c)
        contratos[r["Id"]] = c
        contador["contratos"] += 1
    sessao.flush()
    for r in t("contract_role_assignments"):
        usuario_id = usuario(r["UserId"])
        if usuario_id is None:
            avisos.append(f"designação {r['Id']} sem usuário correspondente: ignorada")
            continue
        sessao.add(DesignacaoEquipe(id=id_(r["Id"]), contrato_id=id_(r["ContractId"]), usuario_id=usuario_id, papel=PAPEIS[r["Role"]],
                                    nome_usuario=texto(r["UserDisplayName"]) or sgi_usuarios.get(r["UserId"], {}).get("FullName", ""),
                                    valido_de=instante(r["ValidFrom"]), valido_ate=instante(r["ValidUntil"]), criado_em=instante(r["CreatedAt"])))
        contador["equipe"] += 1
    itens_sgi: dict[str, dict] = {}
    for r in t("contract_items"):
        itens_sgi[r["Id"]] = r
        sessao.add(ItemContrato(
            id=id_(r["Id"]), contrato_id=id_(r["ContractId"]), ordem=int(r["Order"]), descricao=r["Description"], tipo=TIPOS_ITEM[r["Type"]],
            calcula_pro_rata=booleano(r["CalculatesProRata"]), codigo_classe=texto(r["ClassCode"]), codigo_natureza_despesa=texto(r["ExpenseNatureCode"]),
            codigo_siafisico=texto(r["SiafisicoCode"]), codigo_catmat_catser=texto(r["CatmatCatserCode"]),
            quantidade_mensal=decimal(r["MonthlyQuantity"]), quantidade_total=decimal(r["TotalQuantity"]),
            quantidade_executada=decimal(r["ExecutedQuantity"]), valor_unitario=decimal(r["UnitPrice"]),
            criado_em=instante(r["CreatedAt"]), atualizado_em=instante(r["UpdatedAt"]),
        ))
        contador["itens"] += 1
    for r in t("contract_documents"):
        if not nulo(r["AttachmentId"]):
            continue  # o SGI grava as 23 posições do catálogo; aqui só existem as que têm PDF
        codigo = int(r["TypeCode"])
        titulo = texto(r["Title"]) or (POR_CODIGO[codigo].titulo if codigo in POR_CODIGO else f"Documento {codigo:03d}")
        sessao.add(DocumentoContrato(id=id_(r["Id"]), contrato_id=id_(r["ContractId"]), codigo_tipo=codigo, titulo=titulo[:300],
                                     anexo_id=anexo(r["AttachmentId"], id_(r["ContractId"])), enviado_em=instante(r["UploadedAt"]),
                                     enviado_por_id=usuario(r["UploadedByUserId"]), criado_em=instante(r["CreatedAt"])))
        contador["documentos"] += 1

    # 8 Prorrogações registradas (o termo também entra nos documentos importantes, 024+)
    proximo_codigo: dict[str, int] = defaultdict(lambda: PRIMEIRO_CODIGO_TERMO)
    for r in sorted(t("contract_term_extensions"), key=lambda r: (r["ContractId"], r["StartDate"])):
        codigo = proximo_codigo[r["ContractId"]]
        proximo_codigo[r["ContractId"]] += 1
        contrato_id = id_(r["ContractId"])
        numero = texto(r["AddendumNumber"]).strip()
        anexo_id = anexo(r["AttachmentId"], contrato_id)
        sessao.add(DocumentoContrato(contrato_id=contrato_id, codigo_tipo=codigo, anexo_id=anexo_id,
                                     titulo=f"Termo Aditivo{' nº ' + numero if numero else ''} — prorrogação de {r['Months']} mês(es)",
                                     enviado_em=instante(r["CreatedAt"]), enviado_por_id=usuario(r["CreatedByUserId"]), criado_em=instante(r["CreatedAt"])))
        sessao.add(Prorrogacao(id=id_(r["Id"]), contrato_id=contrato_id, meses=int(r["Months"]), assinada_em=dia(r["SignedAt"]),
                               numero_termo=numero, fim_anterior=dia(r["PreviousEndDate"]), data_inicio=dia(r["StartDate"]),
                               data_fim=dia(r["NewEndDate"]), anexo_id=anexo_id, codigo_documento=codigo,
                               criado_por_id=usuario(r["CreatedByUserId"]), criado_em=instante(r["CreatedAt"])))
        contador["prorrogacoes"] += 1
    sessao.flush()

    # 9-11 Previsão orçamentária
    for r in t("contract_forecast_vigencies"):
        sessao.add(PrevisaoVigencia(id=id_(r["Id"]), contrato_id=id_(r["ContractId"]), sequencia_vigencia=int(r["VigencySequence"]),
                                    salva=booleano(r["IsSaved"]), salva_em=instante(r["SavedAt"]), salva_por_id=usuario(r["SavedByUserId"]),
                                    criado_em=instante(r["CreatedAt"])))
        contador["previsoes"] += 1
    sessao.flush()
    for r in t("contract_forecast_item_limits"):
        sessao.add(LimitePrevisao(id=id_(r["Id"]), previsao_id=id_(r["ForecastId"]), item_id=id_(r["ContractItemId"]),
                                  quantidade_total=decimal(r["TotalQuantity"])))
    for r in t("contract_forecast_allocations"):
        sessao.add(ApontamentoPrevisao(id=id_(r["Id"]), previsao_id=id_(r["ForecastId"]), item_id=id_(r["ContractItemId"]),
                                       competencia=dia(r["Competence"]), quantidade=decimal(r["Quantity"])))
        contador["apontamentos"] += 1

    # 12 Notas de Empenho
    for r in t("contract_commitment_notes"):
        sessao.add(NotaEmpenho(id=id_(r["Id"]), contrato_id=id_(r["ContractId"]), numero=r["Number"], valor_original=decimal(r["OriginalValue"]),
                               criado_por_id=usuario(r["CreatedByUserId"]), criado_em=instante(r["CreatedAt"]), atualizado_em=instante(r["UpdatedAt"])))
        contador["notas_empenho"] += 1

    numero_contrato = {r["Id"]: f"{int(r['Sequence']):03d}/{r['Year']}" for r in t("contracts")}

    # 13-15 Configuração da execução
    for r in t("contract_execution_checklists"):
        sessao.add(Checklist(id=id_(r["Id"]), contrato_id=id_(r["ContractId"]), versao=int(r["Version"]), nome=r["Name"], ativo=booleano(r["IsActive"]),
                             ativado_em=instante(r["ActivatedAt"]), criado_por_id=usuario(r["CreatedByUserId"]),
                             criado_por_nome=texto(r["CreatedByName"]), excluido_em=instante(r["DeletedAt"]), criado_em=instante(r["CreatedAt"])))
    sessao.flush()
    for r in t("contract_execution_checklist_items"):
        sessao.add(ItemChecklist(id=id_(r["Id"]), checklist_id=id_(r["ChecklistId"]), ordem=int(r["Order"]), nome=r["Name"],
                                 observacao=texto(r.get("Observation"))))
    for r in t("contract_execution_evaluation_forms"):
        sessao.add(FormularioAvaliacao(id=id_(r["Id"]), contrato_id=id_(r["ContractId"]), versao=int(r["Version"]), nome=r["Name"],
                                       ativo=booleano(r["IsActive"]), definicao=definicao(json_(r["DefinitionJson"], {}), f'"{r["Name"]}" (versão {r["Version"]}) do contrato {numero_contrato.get(r["ContractId"], "?")}'),
                                       ativado_em=instante(r["ActivatedAt"]), criado_por_id=usuario(r["CreatedByUserId"]),
                                       criado_por_nome=texto(r["CreatedByName"]), criado_em=instante(r["CreatedAt"])))
    sessao.flush()

    # 16 Competências (vigência apurada pelas datas: inicial + prorrogações)
    sessao.expire_all()
    competencias: dict[str, Competencia] = {}
    reconhecimentos = defaultdict(list)
    for r in t("contract_execution_acknowledgements"):
        reconhecimentos[r["CompetenceId"]].append(instante(r["AcknowledgedAt"]))
    for r in t("contract_execution_competences"):
        contrato = sessao.get(Contrato, id_(r["ContractId"]))
        inicio = dia(r["PeriodStart"])
        sequencia = next((v.sequencia for v in vigencias(contrato) if v.inicio <= inicio <= v.fim), 1)
        etapa = ETAPAS_SGI[r["CurrentStage"]]
        passou_da_nf = ETAPAS.index(etapa) > ETAPAS.index("nota_fiscal")
        contrato_id = contrato.id
        c = Competencia(
            id=id_(r["Id"]), contrato_id=contrato_id, sequencia_vigencia=sequencia, competencia=dia(r["Competence"]),
            periodo_inicio=inicio, periodo_fim=dia(r["PeriodEnd"]), etapa_atual=etapa, tipo="regular",
            medicao_iniciada_em=min(reconhecimentos[r["Id"]], default=None) or instante(r["MeasurementCompletedAt"]),
            medicao_concluida_em=instante(r["MeasurementCompletedAt"]),
            nf_anexo_id=anexo(r["InvoiceAttachmentId"], contrato_id), nf_numero=texto(r["InvoiceNumber"]),
            nf_recebida_em=dia(r["InvoiceReceivedDate"]), prazo_pagamento_dias=inteiro(r["PaymentTermDays"]),
            origem_valor_nf={"Measurement": "medicao", "Manual": "manual"}.get(r["InvoiceValueOrigin"]),
            nf_valor_bruto=decimal(r["InvoiceGrossValue"], None), nf_retencao_ir=decimal(r["IncomeTaxWithholding"]),
            nf_retencao_inss=decimal(r["InssWithholding"]), nf_retencao_iss=decimal(r["IssWithholding"]),
            nf_retencao_pis=decimal(r["PisPasepWithholding"]), nf_retencao_cofins=decimal(r["CofinsWithholding"]),
            nf_adicional_anexo_id=anexo(r["AdditionalInvoiceAttachmentId"], contrato_id), nf_adicional_numero=texto(r["AdditionalInvoiceNumber"]),
            nf_adicional_valor_bruto=decimal(r["AdditionalInvoiceGrossValue"], None),
            nf_adicional_retencao_ir=decimal(r["AdditionalIncomeTaxWithholding"]), nf_adicional_retencao_inss=decimal(r["AdditionalInssWithholding"]),
            nf_adicional_retencao_iss=decimal(r["AdditionalIssWithholding"]), nf_adicional_retencao_pis=decimal(r["AdditionalPisPasepWithholding"]),
            nf_adicional_retencao_cofins=decimal(r["AdditionalCofinsWithholding"]),
            # O SGI não grava o fim da etapa da NF: a data mais próxima disponível é a do documento consolidado ou da OB
            nf_concluida_em=(instante(r["ConsolidatedAt"]) or instante(r["BankOrderUploadedAt"]) or instante(r["UpdatedAt"])) if passou_da_nf else None,
            consolidado_anexo_id=anexo(r["ConsolidatedAttachmentId"], contrato_id), consolidado_em=instante(r["ConsolidatedAt"]),
            ob_anexo_id=anexo(r["BankOrderAttachmentId"], contrato_id), ob_enviada_em=instante(r["BankOrderUploadedAt"]),
            concluida_em=instante(r["BankOrderUploadedAt"]) if etapa == "concluida" else None,
            criado_em=instante(r["CreatedAt"]), atualizado_em=instante(r["UpdatedAt"]),
        )
        sessao.add(c)
        competencias[r["Id"]] = c
        contador["competencias"] += 1
    sessao.flush()
    contrato_da_competencia = {k: c.contrato_id for k, c in competencias.items()}

    # 17-22 Etapas da competência
    for r in t("contract_execution_measurement_items"):
        item = itens_sgi.get(r["ContractItemId"])
        mensal = decimal(item["MonthlyQuantity"]) if item else Decimal(0)
        prevista = decimal(r["PlannedQuantity"])
        tipo = TIPOS_ITEM[item["Type"]] if item else "continuo"
        fator = (prevista / mensal).quantize(Decimal("0.00000001")) if tipo == "continuo" and mensal else Decimal(1)
        sessao.add(ItemMedicao(id=id_(r["Id"]), competencia_id=id_(r["CompetenceId"]), item_id=id_(r["ContractItemId"]), ordem=int(r["Order"]),
                               descricao=r["Description"], tipo=tipo, calcula_pro_rata=booleano(item["CalculatesProRata"]) if item else True,
                               valor_unitario=decimal(r["UnitPrice"]), fator_meses=fator, quantidade_prevista=prevista,
                               quantidade_medida=decimal(r["MeasuredQuantity"])))
        contador["itens_medicao"] += 1
    for r in t("contract_execution_acknowledgements"):
        sessao.add(CienciaMedicao(id=id_(r["Id"]), competencia_id=id_(r["CompetenceId"]), usuario_id=usuario(r["UserId"]), nome=texto(r["UserName"]),
                                  papel=PAPEIS.get(r["Role"], r["Role"]), registrada_em=instante(r["AcknowledgedAt"])))
    for r in t("contract_execution_memories"):
        sessao.add(MemoriaMedicao(id=id_(r["Id"]), competencia_id=id_(r["CompetenceId"]), versao=int(r["Version"]),
                                  anexo_id=anexo(r["PdfAttachmentId"], contrato_da_competencia[r["CompetenceId"]]), hash_origem=texto(r["SourceHash"])[:64],
                                  criado_por_id=usuario(r["CreatedByUserId"]), criado_em=instante(r["CreatedAt"])))
    for r in t("contract_execution_cadin_checks"):
        dono = contrato_da_competencia[r["CompetenceId"]]
        sessao.add(ConsultaCadin(id=id_(r["Id"]), competencia_id=id_(r["CompetenceId"]), possui_pendencia=booleano(r["HasPendingIssue"]),
                                 pendencia=texto(r["PendingIssue"]), texto_notificacao=texto(r["NotificationText"]),
                                 certidao_anexo_id=anexo(r["CertificateAttachmentId"], dono), email_anexo_id=anexo(r["CommunicationEmailAttachmentId"], dono),
                                 criado_por_id=usuario(r["CreatedByUserId"]), criado_por_nome=texto(r["CreatedByName"]), criado_em=instante(r["CreatedAt"])))
    for r in t("contract_execution_checklist_documents"):
        sessao.add(DocumentoMensal(id=id_(r["Id"]), competencia_id=id_(r["CompetenceId"]), checklist_id=id_(r["ChecklistId"]), ordem=int(r["Order"]),
                                   nome=r["Name"], observacao=texto(r.get("Observation")),
                                   anexo_id=anexo(r["AttachmentId"], contrato_da_competencia[r["CompetenceId"]]),
                                   enviado_em=instante(r["UploadedAt"]), enviado_por_id=usuario(r["UploadedByUserId"])))
    for r in t("contract_execution_evaluations"):
        dono = contrato_da_competencia[r["CompetenceId"]]
        iniciais, do_gestor = json_(r["InspectorResponsesJson"], []), json_(r["ManagerResponsesJson"], [])
        assinaturas = [
            # O ateste tem três postos (gestor e fiscais); o suplente que assinou "em exercício" ocupa o posto do titular
            {"papel": PAPEIS.get(chave(a, "Role"), chave(a, "Role")).removesuffix("_suplente"), "usuario_id": usuario(str(chave(a, "UserId"))) if chave(a, "UserId") is not None else None,
             "nome": texto(chave(a, "Name")), "ciencia_em": chave(a, "AcknowledgedAt")}
            for a in json_(r["AttestationSignaturesJson"], [])
        ]
        sessao.add(AvaliacaoCompetencia(
            id=id_(r["Id"]), competencia_id=id_(r["CompetenceId"]), formulario_id=id_(r["FormId"]), definicao=definicao(json_(r["DefinitionJson"], {})),
            respostas_iniciais=respostas(iniciais), avaliador_inicial_id=usuario(r["InspectorUserId"]),
            avaliacao_inicial_em=instante(r["UpdatedAt"]) if iniciais else None,
            respostas_gestor=respostas(do_gestor), complemento_gestor=texto(r["ManagerComplement"]), gestor_id=usuario(r["ManagerUserId"]),
            avaliacao_gestor_em=instante(r["ManagerAcknowledgedAt"]) or (instante(r["UpdatedAt"]) if do_gestor else None),
            assinaturas=assinaturas, assinaturas_definidas_em=instante(r["UpdatedAt"]) if assinaturas else None,
            pdf_gerado_anexo_id=anexo(r["GeneratedPdfAttachmentId"], dono), pdf_assinado_anexo_id=anexo(r["SignedPdfAttachmentId"], dono),
            concluida_em=instante(r["CompletedAt"]), reconsideracoes=inteiro(r["ReconsiderationCount"]) or 0,
            reconsideracao_anexo_id=anexo(r["ReconsiderationJustificationAttachmentId"], dono),
        ))
        contador["avaliacoes"] += 1

    # NEs apontadas por competência (tabela criada no SGI em 24/09/2026), em ordem de consumo
    for r in t("contract_execution_commitment_note_selections"):
        sessao.add(SelecaoNotaEmpenho(competencia_id=id_(r["CompetenceId"]), nota_id=id_(r["CommitmentNoteId"]), ordem=int(r["Order"]) + 1))
        contador["selecoes_ne"] += 1
    # 23 Extrato das NEs
    for r in t("contract_commitment_note_movements"):
        sessao.add(MovimentoNotaEmpenho(id=id_(r["Id"]), nota_id=id_(r["CommitmentNoteId"]), competencia_id=id_(r["CompetenceId"]),
                                        tipo="pagamento" if r["Type"] in ("Pagamento", "Payment") else "estorno",
                                        debito=decimal(r["Debit"]), criado_em=instante(r["CreatedAt"])))
        contador["movimentos_ne"] += 1

    # 24-26 Reajustes
    for r in t("contract_adjustments"):
        dono = id_(r["ContractId"])
        sessao.add(Reajuste(
            id=id_(r["Id"]), contrato_id=dono, sequencia_vigencia=int(r["VigencySequence"]), vigencia_inicio=dia(r["VigencyStartDate"]),
            vigencia_fim=dia(r["VigencyEndDate"]), mes_referencia=dia(r["ReferenceMonth"]), situacao=SITUACOES_REAJUSTE[r["Status"]],
            base_atual=decimal(r["CurrentMonthlyBase"]), base_reajustada=decimal(r["AdjustedMonthlyBase"]),
            valor_global_atual=decimal(r["CurrentGlobalValue"]), valor_global_reajustado=decimal(r["AdjustedGlobalValue"]),
            evidencia_anexo_id=anexo(r["EvidenceAttachmentId"], dono), apostilamento_anexo_id=anexo(r["ApostilleAttachmentId"], dono),
            criado_por_id=usuario(r["CreatedByUserId"]), concluido_em=instante(r["CompletedAt"]), cancelado_em=instante(r["CancelledAt"]),
            criado_em=instante(r["CreatedAt"]),
        ))
        contador["reajustes"] += 1
    sessao.flush()
    dono_reajuste = {r["Id"]: id_(r["ContractId"]) for r in t("contract_adjustments")}
    for r in t("contract_adjustment_items"):
        item = itens_sgi.get(r["ContractItemId"])
        sessao.add(ItemReajuste(id=id_(r["Id"]), reajuste_id=id_(r["AdjustmentId"]), item_id=id_(r["ContractItemId"]), ordem=int(r["Order"]),
                                descricao=r["Description"], tipo=TIPOS_ITEM[item["Type"]] if item else "continuo",
                                quantidade_mensal=decimal(r["MonthlyQuantity"]), valor_unitario_atual=decimal(r["CurrentUnitPrice"]),
                                indice_percentual=decimal(r["AdjustmentIndex"]), valor_referencial=decimal(r["ReferenceValue"], None),
                                valor_unitario_reajustado=decimal(r["AdjustedUnitPrice"])))
    for r in t("contract_adjustment_memories"):
        dono = dono_reajuste[r["AdjustmentId"]]
        sessao.add(MemoriaReajuste(id=id_(r["Id"]), reajuste_id=id_(r["AdjustmentId"]), versao=int(r["Version"]),
                                   pdf_anexo_id=anexo(r["PdfAttachmentId"], dono), xlsx_anexo_id=anexo(r["XlsxAttachmentId"], dono),
                                   hash_origem=texto(r["SourceHash"])[:64], criado_por_id=usuario(r["CreatedByUserId"]), criado_em=instante(r["CreatedAt"])))

    # 27-29 Aditamento/supressão
    for r in t("contract_quantity_changes"):
        dono = id_(r["ContractId"])
        sessao.add(AlteracaoQuantidade(
            id=id_(r["Id"]), contrato_id=dono, tipo=TIPOS_ALTERACAO[r["Kind"]], situacao=SITUACOES_ALTERACAO[r["Status"]],
            sequencia_vigencia=int(r["VigencySequence"]), vigencia_inicio=dia(r["VigencyStartDate"]), vigencia_fim=dia(r["VigencyEndDate"]),
            mes_efeito=dia(r["EffectiveMonth"]), valor_global_original=decimal(r["OriginalGlobalValue"]), impacto_valor=decimal(r["ImpactValue"]),
            impacto_percentual=decimal(r["ImpactPercentage"]), justificativa_anexo_id=anexo(r["TechnicalJustificationAttachmentId"], dono),
            autorizacao_anexo_id=anexo(r["ExpenseAuthorizerApprovalAttachmentId"], dono), de_acordo_anexo_id=anexo(r["ContractorAgreementAttachmentId"], dono),
            termo_anexo_id=anexo(r["AddendumAttachmentId"], dono), memoria_pdf_anexo_id=anexo(r["MemoryPdfAttachmentId"], dono),
            memoria_xlsx_anexo_id=anexo(r["MemoryXlsxAttachmentId"], dono), criado_por_id=usuario(r["CreatedByUserId"]),
            concluida_em=instante(r["CompletedAt"]), cancelada_em=instante(r["CancelledAt"]), criado_em=instante(r["CreatedAt"]),
        ))
    sessao.flush()
    for r in t("contract_quantity_change_items"):
        sessao.add(ItemAlteracao(id=id_(r["Id"]), alteracao_id=id_(r["QuantityChangeId"]), item_id=id_(r["ContractItemId"]), ordem=int(r["Order"]),
                                 descricao=r["Description"], tipo=TIPOS_ITEM.get(r["Type"], r["Type"]), valor_unitario=decimal(r["UnitPrice"]),
                                 quantidade_original=decimal(r["OriginalQuantity"]), quantidade_nova=decimal(r["NewQuantity"]),
                                 impacto_valor=decimal(r["ImpactValue"])))
    for r in t("contract_quantity_change_acknowledgements"):
        sessao.add(CienciaAlteracao(id=id_(r["Id"]), alteracao_id=id_(r["QuantityChangeId"]), usuario_id=usuario(r["UserId"]),
                                    nome=texto(r["UserName"]), papel=PAPEIS.get(r["Role"], r["Role"]), registrada_em=instante(r["AcknowledgedAt"])))

    # 30-31 Processos de prorrogação (rascunhos e pareceres emitidos)
    for r in t("contract_extension_processes"):
        dono = id_(r["ContractId"])
        situacao = "concluido" if r["Status"] == "Completed" else "rascunho"
        plano = [
            {"item_id": chave(p, "contractItemId"),
             "limite": str(sum(Decimal(str(chave(a, "quantity") or 0)) for a in chave(p, "allocations") or [])),
             "apontamentos": {chave(a, "competence")[:10]: str(chave(a, "quantity")) for a in chave(p, "allocations") or []}}
            for p in json_(r["DemandPlanJson"], [])
        ]
        sessao.add(ProcessoProrrogacao(
            id=id_(r["Id"]), contrato_id=dono, situacao=situacao, meses=inteiro(r["Months"]), plano_sob_demanda=plano,
            avaliacao_geral=texto(r["GeneralExecution"]), resumo_qualidade=texto(r["QualitySummary"]), historico_ocorrencias=texto(r["OccurrenceHistory"]),
            reclamacoes=texto(r["ComplaintsAndActions"]), atendimento_chamados=texto(r["CallsAndObligations"]), parecer=texto(r["ExtensionOpinion"]),
            relatorio_anexo_id=anexo(r["ReportAttachmentId"], dono), prorrogacao_id=id_(r["ExtensionId"]),
            criado_por_id=usuario(r["CreatedByUserId"]), criado_em=instante(r["CreatedAt"]), atualizado_em=instante(r["UpdatedAt"]),
        ))
    sessao.flush()
    for r in t("contract_extension_acknowledgements"):
        sessao.add(CienciaProrrogacao(id=id_(r["Id"]), processo_id=id_(r["ProcessId"]), usuario_id=usuario(r["UserId"]), nome=texto(r["UserName"]),
                                      papel=PAPEIS.get(r["Role"], r["Role"]), registrada_em=instante(r["AcknowledgedAt"])))

    # 32 Auditoria: entra como histórico (dados.legado); o histórico por campo só lê `dados.campos`
    for r in t("audit_events"):
        tipo = "empresa" if r["ResourceType"] == "ContractCompany" else "contrato"
        sessao.add(RegistroAuditoria(ocorrido_em=instante(r["CreatedAt"]), autor=texto(r["ActorName"])[:150], autor_id=usuario(r["ActorId"]),
                                     acao=("sgi." + r["Action"])[:80], alvo=f"{r['ResourceType']} {r['ResourceId']}"[:255],
                                     detalhes="Importado do SGI SPI", alvo_tipo=tipo, alvo_id=r["ResourceId"][:64],
                                     dados={"legado": json_(r["PayloadJson"], {}), "correlacao": nulo(r["CorrelationId"])}))
        contador["auditoria"] += 1
    sessao.flush()

    # Dono de cada anexo (a exclusão do contrato descarta os arquivos dele)
    for anexo_id, contrato_id in dono_anexo.items():
        registro = sessao.get(Anexo, anexo_id)
        if registro is None:
            avisos.append(f"anexo {anexo_id} referenciado, mas ausente do pacote")
        else:
            registro.contrato_id = contrato_id
    orfaos = [r["Id"] for r in linhas_anexos if id_(r["Id"]) not in dono_anexo]
    if orfaos:
        avisos.append(f"{len(orfaos)} anexo(s) do pacote sem referência nas tabelas do módulo")
    sessao.flush()

    contador["usuarios_criados"] = len(criados)
    if criados:
        avisos.append("usuários criados inativos (não existiam aqui): " + ", ".join(sorted(criados)))
    return dict(contador)


def _usuarios_csv(pacote: Pacote) -> list[dict]:
    with open(pacote.pasta / "usuarios.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def conferir(pacote: Pacote, sessao) -> list[str]:
    """Confere por contrato: débitos das NEs, etapas das competências e quantidades (divergência impede gravar).

    O valor global calculado aqui é comparado com a fotografia do SGI só como aviso: os dois sistemas contam
    os meses de formas diferentes (aqui, mês a mês com 30/360 e pró-rata por item).
    """
    problemas = []
    t = pacote.tabela
    debitos = defaultdict(Decimal)
    for r in t("contract_commitment_note_movements"):
        debitos[r["CommitmentNoteId"]] += Decimal(r["Debit"])
    for r in t("contract_commitment_notes"):
        nota = sessao.get(NotaEmpenho, id_(r["Id"]))
        if nota.consumido != debitos[r["Id"]]:
            problemas.append(f"NE {nota.numero}: débitos {nota.consumido} ≠ {debitos[r['Id']]}")
    for r in t("contract_execution_competences"):
        c = sessao.get(Competencia, id_(r["Id"]))
        if c.etapa_atual != ETAPAS_SGI[r["CurrentStage"]]:
            problemas.append(f"competência {r['Id']}: etapa {c.etapa_atual}")
    for nome, modelo, filtro in (("contracts", Contrato, None), ("contract_items", ItemContrato, None),
                                 ("contract_execution_competences", Competencia, None), ("contract_execution_measurement_items", ItemMedicao, None),
                                 ("contract_adjustment_items", ItemReajuste, None), ("stored_attachments", Anexo, Anexo.categoria.like("contrato%"))):
        consulta = select(func.count()).select_from(modelo)
        if filtro is not None:
            consulta = consulta.where(filtro)
        aqui, la = sessao.scalar(consulta), len(t(nome))
        if aqui < la:
            problemas.append(f"{nome}: {aqui} aqui × {la} no SGI")
    # Valor global por contrato (o SGI não grava o calculado; comparamos com a fotografia do reajuste quando existe)
    for r in t("contracts"):
        contrato = sessao.get(Contrato, id_(r["Id"]))
        calculado = valores.valor_global_vigencia(contrato, vigencias(contrato)[-1])
        fotografia = contrato.valor_global_reajustado
        if fotografia is not None and abs(calculado - fotografia) > Decimal("0.05"):
            avisos.append(f"contrato {contrato.numero}: valor global calculado {calculado} × {fotografia} gravado pelo SGI no reajuste")
    return problemas


def limpar_modulo(sessao) -> set[str]:
    """Remove os dados do módulo e devolve as chaves dos arquivos que eles usavam.

    Os arquivos só saem do disco depois do commit (`remover_arquivos`): se a transação falhar, nada se perde.
    """
    chaves = set(sessao.scalars(select(Anexo.chave_armazenamento).where(Anexo.categoria.like("contrato%"))))
    # As tabelas filhas saem pelo ON DELETE CASCADE do banco
    sessao.execute(Contrato.__table__.delete())
    sessao.execute(EmpresaContratada.__table__.delete())
    sessao.execute(Anexo.__table__.delete().where(Anexo.categoria.like("contrato%")))
    sessao.execute(RegistroAuditoria.__table__.delete().where(RegistroAuditoria.acao.like("sgi.%")))
    sessao.flush()
    return chaves


def remover_arquivos(chaves: set[str]) -> int:
    raiz = servico_anexos.diretorio_anexos().resolve()
    removidos = 0
    for chave_arquivo in chaves:
        arquivo = (raiz / chave_arquivo).resolve()
        if arquivo.is_relative_to(raiz) and arquivo.is_file():
            arquivo.unlink()
            removidos += 1
    return removidos


def copiar_arquivos(pacote: Pacote) -> tuple[int, list[str]]:
    destino = servico_anexos.diretorio_anexos()
    copiados, problemas = 0, []
    for r in pacote.tabela("stored_attachments"):
        origem = pacote.pasta / "anexos" / r["StorageKey"]
        if not origem.is_file():
            problemas.append(f"arquivo ausente no pacote: {r['StorageKey']}")
            continue
        if hashlib.sha256(origem.read_bytes()).hexdigest() != r["Sha256"].lower():
            problemas.append(f"SHA-256 divergente: {r['StorageKey']}")
            continue
        alvo = destino / r["StorageKey"]
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if not alvo.exists():
            shutil.copy2(origem, alvo)
        copiados += 1
    return copiados, problemas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pacote", type=Path)
    parser.add_argument("--gravar", action="store_true", help="grava; sem esta opção é só um ensaio (tudo é desfeito)")
    parser.add_argument("--substituir", action="store_true", help="apaga antes os contratos, empresas, anexos e a auditoria migrada")
    parser.add_argument("--apenas-limpar", action="store_true", help="só apaga os dados do módulo (e os arquivos deles); o pacote é ignorado")
    args = parser.parse_args()
    pacote = Pacote(args.pacote)
    antigas: set[str] = set()

    with FabricaSessao() as sessao:
        existentes = sessao.scalar(select(func.count()).select_from(Contrato))
        if args.apenas_limpar:
            antigas = limpar_modulo(sessao)
            sessao.commit()
            print(f"Módulo limpo: {existentes} contrato(s) e {remover_arquivos(antigas)} arquivo(s) removidos.")
            return
        if existentes and args.substituir:
            antigas = limpar_modulo(sessao)
            print(f"Dados anteriores do módulo removidos ({existentes} contrato(s)).")
        elif existentes:
            sys.exit(f"ERRO: já existem {existentes} contrato(s) no banco. Use --substituir para recarregar o módulo.")
        contagem = migrar(pacote, sessao, args.gravar)
        sessao.expire_all()
        problemas = conferir(pacote, sessao)
        print("Carga:", json.dumps(contagem, ensure_ascii=False))
        for aviso in avisos:
            print("  aviso:", aviso)
        if problemas:
            print("CONFERÊNCIA COM DIVERGÊNCIAS:")
            for p in problemas:
                print("  -", p)
        else:
            print("Conferência: débitos das NEs, etapas, quantidades e valores gravados batem com o SGI.")
        if not args.gravar or problemas:
            sessao.rollback()
            if args.gravar:
                sys.exit("Nada foi gravado por causa das divergências.")
            print("Ensaio: nada foi gravado.")
            return
        copiados, falhas = copiar_arquivos(pacote)
        if falhas:
            sessao.rollback()
            sys.exit("Arquivos com problema, nada foi gravado:\n" + "\n".join(falhas))
        sessao.commit()
        # Arquivos da carga anterior que não vieram de novo
        novas = {r["StorageKey"] for r in pacote.tabela("stored_attachments")}
        remover_arquivos(antigas - novas)
        print(f"Gravado. {copiados} arquivo(s) de anexo em {servico_anexos.diretorio_anexos()}.")


if __name__ == "__main__":
    main()
