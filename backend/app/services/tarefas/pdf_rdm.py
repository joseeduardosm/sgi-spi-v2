# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar o PDF da RDM aprovada: a matriz da Prodesp (FORM_RDM-V2.2_CAS1) na identidade visual do SGI.
"""PDF do Formulário de Requisição de Mudança (RDM).

Segue as 13 seções da matriz (`apoio/rdm/RDM - SPI - Modelo.xlsx`), com o cabeçalho dela, e acrescenta o anexo
"Informações complementares" com o que só existe no formulário de inspiração. O rodapé de todas as páginas é
"Preenchido via SGI SPI - Aprovado por [nome] - [cargo] - [setor] - dd/mm/aaaa hh:mm:ss" (decisão do usuário).
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.models.tarefas import RdmTarefa, Tarefa
from app.schemas.tarefas_rdm import FormularioRdm
from app.services.documentos.pdf import DocumentoPdf

FUSO = ZoneInfo("America/Sao_Paulo")
DIAS_SEMANA = ("Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo")
# Cabeçalho da matriz da Prodesp (linhas 4 a 7 da planilha)
CABECALHO_MATRIZ = (
    "FORM_RDM-V2.2_CAS1",
    "Gerência de Operações e Serviços Tecnológicos - GOI",
    "Coordenadoria Atendimento e Suporte a Servidores I - CAS1",
    "Serviço de Administração e Suporte de Redes e Telecom - SAST / Coordenadoria Suporte Ambiente",
)


def _data(valor: date | None) -> str:
    return valor.strftime("%d/%m/%Y") if valor else ""


def _dia_semana(valor: date | None) -> str:
    return DIAS_SEMANA[valor.weekday()] if valor else ""


def rotulo(rdm: RdmTarefa) -> str:
    """"RDM SGI 00001/2026 - Título" (sem o número enquanto a RDM não foi enviada)."""
    numero = f"RDM SGI {rdm.numero}" if rdm.numero else "RDM SGI (sem número)"
    return f"{numero} - {rdm.titulo}" if rdm.titulo else numero


def rodape(rdm: RdmTarefa) -> str:
    quando = rdm.decidida_em.astimezone(FUSO).strftime("%d/%m/%Y %H:%M:%S") if rdm.decidida_em else ""
    return " - ".join(p for p in ("Preenchido via SGI SPI", f"Aprovado por {rdm.decidida_por_nome}", rdm.decidida_por_cargo, rdm.decidida_por_setor, quando) if p)


def gerar(rdm: RdmTarefa, tarefa: Tarefa) -> bytes:
    """Monta o PDF da RDM aprovada e devolve os bytes."""
    f = FormularioRdm.model_validate(rdm.dados or {})
    doc = DocumentoPdf(titulo="FORMULÁRIO DE REQUISIÇÃO DE MUDANÇA", subtitulo=" · ".join(CABECALHO_MATRIZ), rodape=rodape(rdm))
    doc.campos([("RDM", rotulo(rdm)), ("Tarefa", f"#{tarefa.numero} {tarefa.titulo}")], colunas=2)

    doc.secao("1. IDENTIFICAÇÃO")
    i = f.identificacao
    doc.tabela(["NÚMERO", "TIPO", "ASSUNTO", "REQUISITANTE", "ÁREA/DEPARTAMENTO"], [[f"RDM SGI {rdm.numero}", i.tipo, f.titulo, i.solicitante, i.area]], [1.2, 1, 2.4, 1.4, 1.4])

    doc.secao("2. OBJETIVO")
    doc.campos([("Objetivo", f.objetivo), ("Data", _data(i.data_solicitacao))], colunas=2)
    doc.secao("3. JUSTIFICATIVA")
    doc.paragrafo(f.justificativa or "—")

    doc.secao("4. CATEGORIZAÇÃO")
    c = f.categorizacao
    doc.tabela(["AÇÃO", "FINALIDADE", "PRIORIDADE", "RISCO", "IMPACTO"], [[c.acao, c.finalidade, c.prioridade, c.risco, c.impacto]])

    doc.secao("5. ABRANGÊNCIA")
    a = f.abrangencia
    doc.tabela(["DEPARTAMENTOS AFETADOS", "USUÁRIOS INTERNOS", "USUÁRIOS EXTERNOS"], [[a.departamentos, a.usuarios_internos, a.usuarios_externos]], [3, 1, 1])
    doc.tabela(["ICs IMPACTADOS", "INDISPONIBILIDADE", "TEMPO DE INDISPONIBILIDADE"], [[a.ics, a.indisponibilidade, a.tempo_indisponibilidade]], [3, 1, 1])

    doc.secao("6. CRONOGRAMA")
    por_etapa = {l.etapa: l for l in f.cronograma}
    doc.tabela(["ETAPA", "INÍCIO", "DURAÇÃO", "TÉRMINO"],
               [[e, por_etapa[e].inicio if e in por_etapa else "", por_etapa[e].duracao if e in por_etapa else "", por_etapa[e].termino if e in por_etapa else ""]
                for e in ("HOMOLOGAÇÃO", "EXECUÇÃO", "VALIDAÇÃO")], [2, 1.5, 1, 1.5])

    doc.secao("7. JANELA DE IMPLANTAÇÃO")
    j = f.janela
    doc.tabela(["", "DIA DA SEMANA", "DATA", "HORA", "TEMPO DE IMPLANTAÇÃO"],
               [["INÍCIO", _dia_semana(j.inicio_data), _data(j.inicio_data), j.inicio_hora, j.tempo],
                ["FIM", _dia_semana(j.fim_data), _data(j.fim_data), j.fim_hora, ""]], [1, 1.4, 1.2, 1, 1.6])

    doc.secao("8. PLANO DE EXECUÇÃO e VALIDAÇÃO")
    doc.tabela(["ATIVIDADE (S)", "EXECUTOR (ES)", "ETAPA"], [[l.atividade, l.executor, l.etapa] for l in f.plano_execucao] or [["—", "", ""]], [5, 1.4, 1.2])

    doc.secao("9. PLANO DE COMUNICAÇÃO")
    doc.tabela(["QUEM SERÁ COMUNICADO / ÁREA DE ATUAÇÃO", "EM QUE MOMENTO (ATIVIDADE)", "MEIO UTILIZADO", "RESPONSÁVEL"],
               [[l.quem, l.momento, l.meio, l.responsavel] for l in f.comunicacao] or [["—", "", "", ""]], [2.5, 2, 1.2, 1.2])

    doc.secao("10. PLANO DE REMEDIAÇÃO (ROLLBACK)")
    doc.tabela(["ATIVIDADE (S)", "TEMPO ESTIMADO", "EXECUTOR (ES)"], [[l.atividade, l.tempo, l.executor] for l in f.rollback] or [["—", "", ""]], [5, 1.2, 1.4])
    doc.tabela(["JUSTIFICATIVA", "APROVADOR"], [[f.rollback_justificativa, rdm.decidida_por_nome]], [5, 2])

    doc.secao("11. GESTÃO DO CONHECIMENTO")
    por_documento = {l.tipo_documento: l for l in f.conhecimento}
    doc.tabela(["AÇÃO", "TIPO DE DOCUMENTO", "RESPONSÁVEL"],
               [[por_documento[d].acao if d in por_documento else "-", d, por_documento[d].responsavel if d in por_documento else ""]
                for d in ("INVENTÁRIO", "PROCEDIMENTO", "BASE DE CONHECIMENTO", "PLANO DE ESCALONAMENTO", "REGISTRO DE ERRO CONHECIDO")], [1.5, 2.5, 2])
    doc.campos([("OBSERVAÇÕES", f.conhecimento_observacoes)], colunas=1)

    doc.secao("12. APROVAÇÃO")
    quando = rdm.decidida_em.astimezone(FUSO).strftime("%d/%m/%Y %H:%M:%S") if rdm.decidida_em else ""
    doc.tabela(["DATA", "RESPONSÁVEL", "CARGO", "SETOR"], [[quando, rdm.decidida_por_nome, rdm.decidida_por_cargo, rdm.decidida_por_setor]], [1.2, 2, 2, 2])
    doc.campos([("ASSINATURA", "Aprovado eletronicamente no SGI SPI (ver rodapé).")], colunas=1)

    doc.secao("13. RESULTADO PÓS IMPLEMENTAÇÃO")
    doc.campos([("RESULTADO FINAL", ""), ("OBSERVAÇÕES (detalhar os motivos em caso de \"Conclusão com Ressalvas\" ou \"Falha\")", "")], colunas=1)

    # Anexo: o que só existe no formulário de inspiração (não tem lugar na matriz da Prodesp)
    x = f.complementares
    doc.nova_pagina()
    doc.secao("ANEXO — INFORMAÇÕES COMPLEMENTARES")
    doc.paragrafo("Informações do formulário web do SGI que não têm campo na matriz FORM_RDM-V2.2_CAS1.")
    doc.campos([
        ("Categoria", x.categoria), ("Impacto previsto", x.impacto_previsto),
        ("Responsável pela execução", x.responsavel_execucao), ("Equipes envolvidas", x.equipes_envolvidas),
    ], colunas=2)
    doc.campos([
        ("Responsável pela análise técnica", x.responsavel_analise_tecnica), ("Descrição técnica / escopo", x.descricao_tecnica), ("Riscos identificados", x.riscos), ("Medidas preventivas", x.medidas_preventivas),
        ("Procedimentos de validação", x.procedimentos_validacao), ("Critérios de sucesso", x.criterios_sucesso),
        ("Pré-requisitos atendidos", "\n".join(f"• {p}" for p in x.pre_requisitos)), ("Observações adicionais", x.observacoes_adicionais),
    ], colunas=1)
    return doc.gerar()


def nome_arquivo(rdm: RdmTarefa) -> str:
    """"RDM-SGI-00001-2026.pdf"."""
    return f"RDM-SGI-{(rdm.numero or 'rascunho').replace('/', '-')}.pdf"


def agora_local() -> datetime:
    return datetime.now(FUSO)
