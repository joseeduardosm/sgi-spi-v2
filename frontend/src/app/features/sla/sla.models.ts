// Criado por José Eduardo Santana Martins
// Este arquivo serve para os tipos e textos do SLA de prazos (usados por Tarefas, Melhorias e pela tela de administração).

export type SituacaoSla = 'no_prazo' | 'em_risco' | 'estourado' | 'cumprido' | 'cumprido_fora';

export const ROTULOS_SLA: Record<SituacaoSla, string> = {
  no_prazo: 'No prazo', em_risco: 'Em risco', estourado: 'Estourado', cumprido: 'Cumprido', cumprido_fora: 'Cumprido fora do prazo',
};

/** SLA de um item: prazos em dias úteis a partir do dia da criação (resposta = primeiro atendimento; resolução = conclusão). */
export interface SlaItem {
  meta_resposta_dias: number;
  meta_resolucao_dias: number;
  prazo_resposta: string;
  prazo_resolucao: string;
  respondido_em: string | null;
  resolvido_em: string | null;
  situacao_resposta: SituacaoSla;
  situacao_resolucao: SituacaoSla;
}

/** Linha da política de SLA (a tela de administração edita estas linhas). */
export interface PoliticaSla {
  modulo: 'tarefas' | 'melhorias';
  prioridade: '' | 'baixa' | 'normal' | 'alta' | 'critica';
  dias_uteis_resposta: number;
  dias_uteis_resolucao: number;
  ativo: boolean;
}

/** Texto curto para o selo: "Resolução: em risco (até 12/10)". */
export function textoSla(item: SlaItem, parte: 'resposta' | 'resolucao'): string {
  const situacao = parte === 'resposta' ? item.situacao_resposta : item.situacao_resolucao;
  const prazo = parte === 'resposta' ? item.prazo_resposta : item.prazo_resolucao;
  const [, mes, dia] = prazo.split('-');
  return `${parte === 'resposta' ? 'Resposta' : 'Resolução'}: ${ROTULOS_SLA[situacao].toLowerCase()} (prazo ${dia}/${mes})`;
}
