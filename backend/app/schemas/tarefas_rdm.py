"""
===============================================================================
ARQUIVO: tarefas_rdm.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Definir o formulário da RDM (Requisição de Mudança) das tarefas e os formatos
de leitura dela (resumo para o selo, leitura completa e linha da lista).

RESUMO TÉCNICO:
Schemas pydantic aninhados: cada seção do formulário é uma classe
(Identificacao, Categorizacao, Abrangencia, Janela etc.) e FormularioRdm junta
todas. As seções seguem a matriz da Prodesp (FORM_RDM-V2.2_CAS1, arquivo
`apoio/rdm/RDM - SPI - Modelo.xlsx`); o que só existe no formulário de
inspiração (`SPI - Formulário de RDM-modelo.pdf`) fica em `complementares` e
vai no anexo "Informações complementares" do PDF. Os textos têm limite de
tamanho e as listas de opções (Literal) são as da planilha.

FINALIDADE DE NEGÓCIO:
Toda mudança em ambiente de TI (instalar, alterar, desinstalar) precisa de uma
RDM aprovada pela liderança antes da execução. Este arquivo garante que o
formulário preenchido no SGI tenha os mesmos campos e opções da matriz oficial,
para que o PDF gerado seja aceito sem retrabalho.

CONTEXTO NO SISTEMA:
Usado pelas rotas de RDM do módulo Tarefas (`app/api/routes/tarefas.py`) e pelo
serviço que salva, envia, aprova/reprova e gera o PDF da RDM. O resumo
(RdmResumo) aparece também no quadro de tarefas e no Protocolo.

===============================================================================
"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# Listas de opções da matriz (validação de dados da planilha).
# Ficam como tuplas para que o serviço e o PDF possam listar as opções na
# mesma ordem da planilha oficial da Prodesp.
TIPOS = ("PROGRAMADA", "PRÉ-APROVADA", "EMERGENCIAL")
ACOES = ("INSTALAÇÃO", "DESINSTALAÇÃO", "ALTERAÇÃO", "EXCLUSÃO")
FINALIDADES = ("CORREÇÃO", "EVOLUÇÃO", "PREVENÇÃO")
PRIORIDADES = ("CRÍTICA", "ALTA", "MÉDIA", "BAIXA")
NIVEIS = ("ALTO", "MÉDIO", "BAIXO")
ETAPAS = ("HOMOLOGAÇÃO", "EXECUÇÃO", "VALIDAÇÃO")
ACOES_CONHECIMENTO = ("CRIAÇÃO", "ALTERAÇÃO", "EXCLUSÃO", "NÃO SE APLICA")
DOCUMENTOS_CONHECIMENTO = ("INVENTÁRIO", "PROCEDIMENTO", "BASE DE CONHECIMENTO", "PLANO DE ESCALONAMENTO", "REGISTRO DE ERRO CONHECIDO")
# Do formulário de inspiração (vão no anexo complementar)
CATEGORIAS = ("Infraestrutura", "Rede", "Servidores", "Segurança", "Sistemas", "Banco de dados", "Telefonia", "Outros")
IMPACTOS_PREVISTOS = ("Baixo", "Médio", "Alto", "Crítico")
PRE_REQUISITOS = (
    "Backup realizado e validado, quando aplicável", "Configurações atuais registradas", "Acessos e permissões disponíveis",
    "Equipes envolvidas comunicadas", "Plano de execução validado", "Plano de rollback definido", "Janela de mudança acordada",
)

def Texto():  # noqa: N802 - campo de texto longo (um Field novo por campo)
    """Cria um `Field` de texto longo (até 4000 caracteres), vazio por padrão.

    É uma função (e não uma constante) porque cada campo do pydantic precisa
    do seu próprio objeto `Field`; reaproveitar o mesmo objeto em vários
    campos pode misturar as configurações entre eles.
    """
    return Field("", max_length=4000)


def Curto():  # noqa: N802 - campo de texto curto
    """Cria um `Field` de texto curto (até 300 caracteres), vazio por padrão."""
    return Field("", max_length=300)


# Observação para quem está começando: cada classe abaixo herda de
# `BaseModel` (pydantic). O pydantic valida o JSON recebido: tipos, tamanho
# máximo (`max_length`) e valores permitidos (`Literal[...]`). Se algo não
# bate, a API devolve 422 antes de chegar ao serviço. O valor "" nos Literal
# representa "ainda não escolhido" no rascunho.


class Identificacao(BaseModel):
    """Seção 1 da RDM: quem pede, quando, de que área e o tipo da mudança."""
    data_solicitacao: date | None = None
    solicitante: str = Curto()
    area: str = Curto()
    tipo: Literal["", "PROGRAMADA", "PRÉ-APROVADA", "EMERGENCIAL"] = ""


class Categorizacao(BaseModel):
    """Classificação da mudança: ação, finalidade, prioridade, risco e impacto."""
    acao: Literal["", "INSTALAÇÃO", "DESINSTALAÇÃO", "ALTERAÇÃO", "EXCLUSÃO"] = ""
    finalidade: Literal["", "CORREÇÃO", "EVOLUÇÃO", "PREVENÇÃO"] = ""
    prioridade: Literal["", "CRÍTICA", "ALTA", "MÉDIA", "BAIXA"] = ""
    risco: Literal["", "ALTO", "MÉDIO", "BAIXO"] = ""
    impacto: Literal["", "ALTO", "MÉDIO", "BAIXO"] = ""


class Abrangencia(BaseModel):
    """Quem e o que a mudança atinge, e se haverá indisponibilidade."""
    departamentos: str = Texto()
    usuarios_internos: str = Field("", max_length=60)
    usuarios_externos: str = Field("", max_length=60)
    ics: str = Field("", max_length=4000, description="Itens de configuração impactados (serviços, sistemas, equipamentos).")
    indisponibilidade: Literal["", "SIM", "NÃO"] = ""
    tempo_indisponibilidade: str = Curto()


class LinhaCronograma(BaseModel):
    """Uma linha do cronograma (homologação, execução ou validação)."""
    etapa: Literal["HOMOLOGAÇÃO", "EXECUÇÃO", "VALIDAÇÃO"]
    inicio: str = Field("", max_length=60)
    duracao: str = Field("", max_length=60)
    termino: str = Field("", max_length=60)


class Janela(BaseModel):
    """Janela de mudança: início, fim e tempo previsto de implantação."""
    inicio_data: date | None = None
    # Horas ficam como texto curto ("22:00") porque vêm assim do formulário
    inicio_hora: str = Field("", max_length=10)
    fim_data: date | None = None
    fim_hora: str = Field("", max_length=10)
    tempo: str = Field("", max_length=60, description="Tempo de implantação (ex.: 03 horas).")


class AtividadeExecucao(BaseModel):
    """Um passo do plano de execução, com quem executa e em que etapa."""
    atividade: str = Field("", max_length=1000)
    executor: str = Curto()
    etapa: Literal["HOMOLOGAÇÃO", "EXECUÇÃO", "VALIDAÇÃO"] = "EXECUÇÃO"


class LinhaComunicacao(BaseModel):
    """Uma linha do plano de comunicação: quem avisar, quando, como e por quem."""
    quem: str = Curto()
    momento: str = Curto()
    meio: str = Curto()
    responsavel: str = Curto()


class AtividadeRollback(BaseModel):
    """Um passo do plano de retorno (rollback), caso a mudança dê errado."""
    atividade: str = Field("", max_length=1000)
    tempo: str = Field("", max_length=60)
    executor: str = Curto()


class LinhaConhecimento(BaseModel):
    """Documento de gestão do conhecimento afetado pela mudança e o que fazer com ele."""
    tipo_documento: Literal["INVENTÁRIO", "PROCEDIMENTO", "BASE DE CONHECIMENTO", "PLANO DE ESCALONAMENTO", "REGISTRO DE ERRO CONHECIDO"]
    acao: Literal["", "CRIAÇÃO", "ALTERAÇÃO", "EXCLUSÃO", "NÃO SE APLICA"] = ""
    responsavel: str = Curto()


class Complementares(BaseModel):
    """Só do formulário de inspiração: vão no anexo "Informações complementares" do PDF."""
    categoria: str = Field("", max_length=60)
    descricao_tecnica: str = Texto()
    responsavel_execucao: str = Curto()
    equipes_envolvidas: str = Curto()
    impacto_previsto: Literal["", "Baixo", "Médio", "Alto", "Crítico"] = ""
    riscos: str = Texto()
    medidas_preventivas: str = Texto()
    procedimentos_validacao: str = Texto()
    criterios_sucesso: str = Texto()
    pre_requisitos: list[str] = Field(default_factory=list, description="Itens do checklist de pré-requisitos marcados.")
    responsavel_analise_tecnica: str = Curto()
    observacoes_adicionais: str = Texto()


class FormularioRdm(BaseModel):
    """Corpo de `PUT …/rdm` e `POST …/rdm/enviar`."""
    # `default_factory` cria uma seção vazia nova para cada formulário (evita
    # que dois formulários compartilhem o mesmo objeto). Os `max_length` das
    # listas limitam quantas linhas cada tabela da RDM pode ter.
    titulo: str = Field("", max_length=300, description="Assunto da mudança (vai no rótulo: \"RDM SGI 00001/2026 - Título\").")
    identificacao: Identificacao = Field(default_factory=Identificacao)
    objetivo: str = Texto()
    justificativa: str = Texto()
    categorizacao: Categorizacao = Field(default_factory=Categorizacao)
    abrangencia: Abrangencia = Field(default_factory=Abrangencia)
    cronograma: list[LinhaCronograma] = Field(default_factory=list, max_length=10)
    janela: Janela = Field(default_factory=Janela)
    plano_execucao: list[AtividadeExecucao] = Field(default_factory=list, max_length=100)
    comunicacao: list[LinhaComunicacao] = Field(default_factory=list, max_length=30)
    rollback: list[AtividadeRollback] = Field(default_factory=list, max_length=50)
    rollback_justificativa: str = Texto()
    conhecimento: list[LinhaConhecimento] = Field(default_factory=list, max_length=10)
    conhecimento_observacoes: str = Texto()
    complementares: Complementares = Field(default_factory=Complementares)


class RdmResumo(BaseModel):
    """Selo da RDM na tarefa, no quadro e no Protocolo."""
    rotulo: str = Field(..., description="\"RDM SGI 00001/2026 - Título\" (sem número enquanto rascunho).")
    # Situações possíveis: rascunho (ainda não enviada), pendente (enviada,
    # aguardando decisão), aprovada, reprovada e concluida.
    situacao: Literal["rascunho", "pendente", "aprovada", "reprovada", "concluida"]


class RdmLeitura(BaseModel):
    """A RDM de uma tarefa (`GET …/rdm`)."""
    tarefa_numero: int
    tarefa_titulo: str
    existe: bool = Field(..., description="Falso: ainda não há RDM; `formulario` vem com os valores iniciais.")
    numero: str = Field("", description="\"00001/2026\" depois do primeiro envio.")
    rotulo: str
    situacao: Literal["rascunho", "pendente", "aprovada", "reprovada", "concluida"]
    formulario: FormularioRdm
    enviada_em: datetime | None = None
    enviada_por_nome: str = ""
    decidida_em: datetime | None = None
    decidida_por_nome: str = ""
    motivo_reprovacao: str = ""
    tem_pdf: bool = False
    # As duas permissões abaixo são calculadas pelo serviço para a pessoa que
    # fez a requisição; a tela usa para mostrar ou esconder os botões.
    pode_editar: bool = Field(..., description="Pode salvar e enviar (responsáveis com a tarefa em andamento, RDM em rascunho ou reprovada).")
    pode_decidir: bool = Field(..., description="Pode aprovar ou reprovar (liderança, RDM pendente).")


class ReprovacaoRdm(BaseModel):
    """Corpo da reprovação de uma RDM: o motivo é obrigatório."""
    motivo: str = Field(..., min_length=1, max_length=4000)


class RdmListada(BaseModel):
    """Linha da lista de RDMs (`GET /api/tarefas/rdms`)."""
    # A situação aqui não inclui "rascunho": a lista traz RDMs já enviadas.
    id: uuid.UUID
    numero: str
    titulo: str
    rotulo: str
    situacao: Literal["pendente", "aprovada", "reprovada", "concluida"]
    tarefa_numero: int
    tarefa_titulo: str
    equipe: str | None
    enviada_em: datetime | None
    enviada_por_nome: str
    decidida_em: datetime | None
    decidida_por_nome: str
