/**
 * =============================================================================
 * ARQUIVO: rdm.models.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Definir os tipos da RDM (Requisição de Mudança) das tarefas e as listas de
 * opções da matriz da Prodesp.
 *
 * RESUMO TÉCNICO:
 * Interfaces TypeScript que espelham os schemas da API (FormularioRdm,
 * RdmLeitura, RdmResumo, RdmListada), o tipo SituacaoRdm, o mapa SITUACOES_RDM
 * (rótulo e cor do selo de cada situação) e constantes com as opções dos
 * campos de escolha do formulário.
 *
 * FINALIDADE DE NEGÓCIO:
 * A RDM segue o modelo FORM_RDM-V2.2_CAS1 da Prodesp. Centralizar aqui as
 * opções garante que o formulário, a lista de RDMs e o PDF usem os mesmos
 * termos (tipo, ação, finalidade, prioridade, risco, impacto e etapas).
 *
 * CONTEXTO NO SISTEMA:
 * Usado por rdm-tarefa.component.ts, pela lista de RDMs do Módulo Tarefas e
 * por TarefasApiService. Os campos precisam bater com os schemas de RDM do
 * backend (backend/app/schemas/tarefas.py).
 *
 * =============================================================================
 */

/**
 * Situações da RDM ao longo do fluxo: rascunho (em edição), pendente
 * (enviada, aguardando a liderança), aprovada, reprovada (volta para ajuste
 * e reenvio) e concluída (mudança implantada).
 */
export type SituacaoRdm = 'rascunho' | 'pendente' | 'aprovada' | 'reprovada' | 'concluida';

// Linhas das tabelas do formulário. Os campos de data/hora do cronograma e
// os tempos são texto livre, como na planilha original da Prodesp.
export interface LinhaCronograma { etapa: string; inicio: string; duracao: string; termino: string }
export interface AtividadeExecucao { atividade: string; executor: string; etapa: string }
export interface LinhaComunicacao { quem: string; momento: string; meio: string; responsavel: string }
export interface AtividadeRollback { atividade: string; tempo: string; executor: string }
export interface LinhaConhecimento { tipo_documento: string; acao: string; responsavel: string }

/** Formulário da RDM: seções da matriz FORM_RDM-V2.2_CAS1 e as informações complementares (anexo do PDF). */
export interface FormularioRdm {
  titulo: string;
  identificacao: { data_solicitacao: string | null; solicitante: string; area: string; tipo: string };
  objetivo: string;
  justificativa: string;
  categorizacao: { acao: string; finalidade: string; prioridade: string; risco: string; impacto: string };
  abrangencia: { departamentos: string; usuarios_internos: string; usuarios_externos: string; ics: string; indisponibilidade: string; tempo_indisponibilidade: string };
  cronograma: LinhaCronograma[];
  janela: { inicio_data: string | null; inicio_hora: string; fim_data: string | null; fim_hora: string; tempo: string };
  plano_execucao: AtividadeExecucao[];
  comunicacao: LinhaComunicacao[];
  rollback: AtividadeRollback[];
  rollback_justificativa: string;
  conhecimento: LinhaConhecimento[];
  conhecimento_observacoes: string;
  complementares: {
    categoria: string; descricao_tecnica: string; responsavel_execucao: string; equipes_envolvidas: string; impacto_previsto: string;
    riscos: string; medidas_preventivas: string; procedimentos_validacao: string; criterios_sucesso: string; pre_requisitos: string[];
    responsavel_analise_tecnica: string; observacoes_adicionais: string;
  };
}

/**
 * Resposta de leitura da RDM de uma tarefa. `existe` é falso quando a tarefa
 * ainda não tem RDM (a API devolve um formulário pré-preenchido). As
 * permissões `pode_editar` e `pode_decidir` são calculadas no backend e só
 * mostram ou escondem botões na tela.
 */
export interface RdmLeitura {
  tarefa_numero: number; tarefa_titulo: string; existe: boolean; numero: string; rotulo: string; situacao: SituacaoRdm; formulario: FormularioRdm;
  enviada_em: string | null; enviada_por_nome: string; decidida_em: string | null; decidida_por_nome: string; motivo_reprovacao: string;
  tem_pdf: boolean; pode_editar: boolean; pode_decidir: boolean;
}

/** Resumo da RDM mostrado junto da tarefa (rótulo e situação). */
export interface RdmResumo { rotulo: string; situacao: SituacaoRdm }

/** Linha da lista geral de RDMs (com a tarefa e a equipe de origem). */
export interface RdmListada {
  id: string; numero: string; titulo: string; rotulo: string; situacao: SituacaoRdm; tarefa_numero: number; tarefa_titulo: string; equipe: string | null;
  enviada_em: string | null; enviada_por_nome: string; decidida_em: string | null; decidida_por_nome: string;
}

/** Rótulo e cor (`data-chamado` do `.selo-status`) de cada situação: amarela, vermelha, laranja e verde (decisão do usuário). */
export const SITUACOES_RDM: Record<SituacaoRdm, { rotulo: string; cor: string }> = {
  rascunho: { rotulo: 'Rascunho', cor: 'neutro' },
  pendente: { rotulo: 'Aguardando aprovação', cor: 'alerta' },
  reprovada: { rotulo: 'Reprovada', cor: 'perigo' },
  aprovada: { rotulo: 'Aprovada', cor: 'atencao' },
  concluida: { rotulo: 'Concluída e implantada', cor: 'sucesso' },
};

// Listas de opções da matriz da Prodesp
export const TIPOS_RDM = ['PROGRAMADA', 'PRÉ-APROVADA', 'EMERGENCIAL'];
export const ACOES_RDM = ['INSTALAÇÃO', 'DESINSTALAÇÃO', 'ALTERAÇÃO', 'EXCLUSÃO'];
export const FINALIDADES_RDM = ['CORREÇÃO', 'EVOLUÇÃO', 'PREVENÇÃO'];
export const PRIORIDADES_RDM = ['CRÍTICA', 'ALTA', 'MÉDIA', 'BAIXA'];
export const NIVEIS_RDM = ['ALTO', 'MÉDIO', 'BAIXO'];
export const ETAPAS_RDM = ['HOMOLOGAÇÃO', 'EXECUÇÃO', 'VALIDAÇÃO'];
export const ACOES_CONHECIMENTO_RDM = ['CRIAÇÃO', 'ALTERAÇÃO', 'EXCLUSÃO', 'NÃO SE APLICA'];
// Do formulário de inspiração (vão no anexo complementar)
export const CATEGORIAS_RDM = ['Infraestrutura', 'Rede', 'Servidores', 'Segurança', 'Sistemas', 'Banco de dados', 'Telefonia', 'Outros'];
export const IMPACTOS_PREVISTOS_RDM = ['Baixo', 'Médio', 'Alto', 'Crítico'];
export const PRE_REQUISITOS_RDM = [
  'Backup realizado e validado, quando aplicável', 'Configurações atuais registradas', 'Acessos e permissões disponíveis',
  'Equipes envolvidas comunicadas', 'Plano de execução validado', 'Plano de rollback definido', 'Janela de mudança acordada',
];
