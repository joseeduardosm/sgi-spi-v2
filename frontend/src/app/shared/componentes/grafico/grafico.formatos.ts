// Criado por José Eduardo Santana Martins
// Este arquivo serve para formatar os valores exibidos nos gráficos (números, moeda e milhares de reais) em pt-BR.

export type FormatoGrafico = 'numero' | 'moeda' | 'moedaMil';

const NUMERO = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
const MOEDA = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

/** Formata um valor no estilo pedido. `moedaMil` recebe o valor já em milhares e mostra "R$ 12,5 mil". */
export function formatarValor(valor: number, formato: FormatoGrafico): string {
  if (formato === 'moeda') return MOEDA.format(valor);
  if (formato === 'moedaMil') return `R$ ${NUMERO.format(valor)} mil`;
  return NUMERO.format(valor);
}

/** Valor abreviado para os eixos: 1.200.000 vira "1,2 mi"; 15.000 vira "15 mil". */
export function abreviar(valor: number): string {
  const abs = Math.abs(valor);
  if (abs >= 1_000_000) return `${NUMERO.format(valor / 1_000_000)} mi`;
  if (abs >= 1_000) return `${NUMERO.format(valor / 1_000)} mil`;
  return NUMERO.format(valor);
}

/** Texto para leitores de tela: "Previsto: Jan 10, Fev 12". */
export function descreverSerie(nome: string, rotulos: string[], dados: (number | null)[], formato: FormatoGrafico): string {
  return `${nome}: ` + rotulos.map((r, i) => `${r} ${formatarValor(dados[i] ?? 0, formato)}`).join(', ');
}
