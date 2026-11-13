/**
 * =============================================================================
 * ARQUIVO: marcadores-competencia.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Montar os marcadores (chips) da competência atual e das etapas abertas de
 * cada contrato na carteira.
 *
 * RESUMO TÉCNICO:
 * Exporta a interface MarcadorCompetencia (texto, cor, título e rota opcional)
 * e a função pura marcadoresCompetencia, que devolve uma lista de linhas de
 * marcadores. As cores são índices da paleta de etiquetas de Tarefas; cada
 * etapa da execução tem a sua cor em COR_ETAPA.
 *
 * FINALIDADE DE NEGÓCIO:
 * Competência é o mês de referência da execução do contrato (medir, receber
 * nota fiscal, reter tributos, consultar CADIN, pagar). Os chips mostram ao
 * gestor, sem abrir o contrato, onde cada um está, o que está atrasado e levam
 * direto à execução daquele mês.
 *
 * CONTEXTO NO SISTEMA:
 * Consumido por carteira.component (tela Carteira de contratos). Lê os campos
 * competencia_atual e competencias_em_andamento de ResumoContrato
 * (contratos.models.ts), calculados pela API da carteira.
 *
 * =============================================================================
 */

import { ROTULOS_ETAPA } from '../compartilhado/rotulos';
import { CompetenciaAtualCarteira, ResumoContrato } from '../compartilhado/contratos.models';

/** Marcador exibido na carteira; `cor` é o índice da paleta de etiquetas de Tarefas (`classeMarcador`). */
export interface MarcadorCompetencia {
  texto: string;
  cor: number;
  titulo: string;
  /** Presente nos marcadores que levam à execução da competência. */
  rota?: string[];
}

// Índices da paleta de etiquetas de Tarefas (classeMarcador): o número escolhe a cor do chip.
const COR_CINZA = 0;
const COR_VERMELHO = 1;
const COR_AMARELO = 3;
const COR_AZUL = 4;
const COR_ROXO = 5;
const COR_TEAL = 7;
const COR_VERDE = 10;

/**
 * Cor de cada etapa em andamento (as etapas depois da nota fiscal ficam em teal).
 * Etapas da execução mensal: medição (o que foi entregue no mês), avaliação, nota fiscal, retenção de
 * tributos, CADIN (consulta ao cadastro de inadimplentes do setor público), checklist, consolidado
 * e ordem bancária (o pagamento).
 */
const COR_ETAPA: Record<string, number> = {
  medicao: COR_AZUL, avaliacao: COR_ROXO, nota_fiscal: COR_AZUL, retencao: COR_TEAL, cadin: COR_TEAL, checklist: COR_TEAL, consolidado: COR_ROXO, ordem_bancaria: COR_VERDE,
};

/**
 * Marcadores do contrato na carteira, **uma linha por competência**.
 * - Com competências já iniciadas (em andamento): uma linha `(MM/AAAA - etapa)` para cada uma (etapas abertas juntas separadas por " + "), mais "Atrasada" na linha da atrasada.
 * - Sem nenhuma iniciada: a competência atual (disponível ou pendente), "Em dia" ou "Sem competências".
 *
 * @param c Resumo do contrato vindo da API da carteira (só id, sem_competencias, competencia_atual e as em andamento).
 * @returns Lista de linhas; cada linha é uma lista de marcadores exibidos lado a lado. Função pura, sem efeitos.
 */
export function marcadoresCompetencia(
  c: Pick<ResumoContrato, 'id' | 'sem_competencias' | 'competencia_atual'> & { competencias_em_andamento?: CompetenciaAtualCarteira[] },
): MarcadorCompetencia[][] {
  if (c.sem_competencias) return [[{ texto: 'Sem competências', cor: COR_CINZA, titulo: 'A execução do contrato ainda não foi gerada' }]];
  const rotaDe = (identificador: string) => ['/contratos', c.id, 'execucao', identificador];
  const andamento = c.competencias_em_andamento ?? [];
  // Caso 1: há competências já iniciadas. Cada uma vira uma linha; a cor segue a primeira etapa aberta
  // e o rótulo técnico da etapa é trocado pelo nome legível (ROTULOS_ETAPA), se existir.
  if (andamento.length) {
    return andamento.map((comp) => {
      const rota = rotaDe(comp.identificador);
      const etapas = comp.etapas.map((e) => (ROTULOS_ETAPA as Record<string, string>)[e] ?? e);
      const linha: MarcadorCompetencia[] = [{
        texto: `${comp.rotulo} · ${etapas.join(' + ')}`, cor: COR_ETAPA[comp.etapas[0]] ?? COR_AZUL,
        titulo: `Competência ${comp.rotulo}, etapa em andamento: ${etapas.join(' + ')}. Abrir a execução`, rota,
      }];
      if (comp.atrasada) linha.push({ texto: 'Atrasada', cor: COR_VERMELHO, titulo: 'Medição não concluída há mais de 30 dias do fim do período', rota });
      return linha;
    });
  }
  // Caso 2: nenhuma iniciada. Sem competência atual = tudo concluído ("Em dia"); senão mostra a
  // competência atual e, conforme a situação, se a medição ainda não pode (pendente) ou já pode começar.
  const atual = c.competencia_atual;
  if (!atual) return [[{ texto: 'Em dia', cor: COR_VERDE, titulo: 'Nenhuma competência em aberto' }]];
  const rota = rotaDe(atual.identificador);
  const linha: MarcadorCompetencia[] = [{ texto: atual.rotulo, cor: COR_AZUL, titulo: `Competência ${atual.rotulo}: abrir a execução`, rota }];
  if (atual.situacao === 'pendente') {
    linha.push({ texto: 'Medição · Pendente', cor: COR_CINZA, titulo: 'O período da competência ainda não terminou', rota });
  } else if (atual.situacao === 'disponivel') {
    linha.push({ texto: 'Medição · Disponível', cor: COR_AMARELO, titulo: 'Liberada para medição; a medição ainda não foi iniciada', rota });
  }
  if (atual.atrasada) linha.push({ texto: 'Atrasada', cor: COR_VERMELHO, titulo: 'Medição não concluída há mais de 30 dias do fim do período', rota });
  return [linha];
}
