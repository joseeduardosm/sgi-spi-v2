// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar os marcadores (chips) da competência atual e das etapas abertas de cada contrato na carteira.

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

const COR_CINZA = 0;
const COR_VERMELHO = 1;
const COR_AMARELO = 3;
const COR_AZUL = 4;
const COR_ROXO = 5;
const COR_TEAL = 7;
const COR_VERDE = 10;

/** Cor de cada etapa em andamento (as etapas depois da nota fiscal ficam em teal). */
const COR_ETAPA: Record<string, number> = {
  medicao: COR_AZUL, avaliacao: COR_ROXO, nota_fiscal: COR_AZUL, retencao: COR_TEAL, cadin: COR_TEAL, checklist: COR_TEAL, consolidado: COR_ROXO, ordem_bancaria: COR_VERDE,
};

/**
 * Marcadores do contrato na carteira, **uma linha por competência**.
 * - Com competências já iniciadas (em andamento): uma linha `(MM/AAAA - etapa)` para cada uma (etapas abertas juntas separadas por " + "), mais "Atrasada" na linha da atrasada.
 * - Sem nenhuma iniciada: a competência atual (disponível ou pendente), "Em dia" ou "Sem competências".
 */
export function marcadoresCompetencia(
  c: Pick<ResumoContrato, 'id' | 'sem_competencias' | 'competencia_atual'> & { competencias_em_andamento?: CompetenciaAtualCarteira[] },
): MarcadorCompetencia[][] {
  if (c.sem_competencias) return [[{ texto: 'Sem competências', cor: COR_CINZA, titulo: 'A execução do contrato ainda não foi gerada' }]];
  const rotaDe = (identificador: string) => ['/contratos', c.id, 'execucao', identificador];
  const andamento = c.competencias_em_andamento ?? [];
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
