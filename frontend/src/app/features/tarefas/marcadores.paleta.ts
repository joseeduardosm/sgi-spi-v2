// Criado por José Eduardo Santana Martins
// Este arquivo serve para guardar a paleta de 12 cores dos marcadores das tarefas (a mesma do backend e do Odoo).

/** Cor de um marcador: borda, fundo suave e texto escuro. O índice 0 é o cinza neutro. */
export interface CorMarcador { borda: string; fundo: string; texto: string }

export const PALETA_MARCADORES: readonly CorMarcador[] = [
  { borda: '#8f8f8f', fundo: '#d7d7d7', texto: '#3d3d3d' },
  { borda: '#d76a58', fundo: '#fedbd5', texto: '#6b1f15' },
  { borda: '#cc7724', fundo: '#fedec5', texto: '#5c3003' },
  { borda: '#c09910', fundo: '#f4dc9d', texto: '#4c3b04' },
  { borda: '#179dc5', fundo: '#c2ecfe', texto: '#044457' },
  { borda: '#b271c6', fundo: '#ebcaf6', texto: '#542662' },
  { borda: '#af8563', fundo: '#f2e1d4', texto: '#4d3827' },
  { borda: '#17a49d', fundo: '#aef4ee', texto: '#034744' },
  { borda: '#5d8ee4', fundo: '#c3d9fe', texto: '#193a76' },
  { borda: '#d06792', fundo: '#fec5d9', texto: '#671d3f' },
  { borda: '#4ca65a', fundo: '#bae5bd', texto: '#044b18' },
  { borda: '#8f7ede', fundo: '#e4e1fe', texto: '#3e2f72' },
];

/** Classe CSS da pílula do marcador (definida em `styles/_tarefas.scss`). */
export function classeMarcador(indice: number | undefined | null): string {
  const i = Number.isInteger(indice) && (indice as number) >= 0 && (indice as number) < PALETA_MARCADORES.length ? (indice as number) : 1;
  return `marcador-tarefa marcador-cor-${i}`;
}

/** Texto sem acentos e em minúsculas (para filtrar marcadores digitando). */
export function semAcento(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}
