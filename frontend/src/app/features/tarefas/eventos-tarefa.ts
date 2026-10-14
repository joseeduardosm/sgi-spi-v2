// Criado por José Eduardo Santana Martins
// Este arquivo serve para o que a linha do tempo e a visão "O que aconteceu" compartilham: ícones por tipo de evento e nomes dos dias.

/** Ícone (caminho de SVG 24x24) de cada tipo de evento da linha do tempo. */
export const ICONES_EVENTO: Record<string, string> = {
  // Escalonamento por atraso: aviso à liderança (triângulo de alerta)
  escalonada: 'M12 3 2 20h20L12 3Zm0 6v5m0 3h.01',
  criada: 'M12 5v14M5 12h14',
  editada: 'M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z',
  status: 'M5 12h14M13 6l6 6-6 6',
  entregue: 'M12 19V5M5 12l7-7 7 7',
  validada: 'M5 13l4 4L19 7',
  devolvida: 'M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-2',
  reaberta: 'M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5',
  prazo: 'M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  transferida: 'M4 7h14l-4-4M20 17H6l4 4',
  comentario: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z',
  checklist: 'M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11',
  removido: 'M18 6 6 18M6 6l12 12',
};

const DIAS_DA_SEMANA = ['domingo', 'segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado'];

/** "Hoje", "Ontem" ou "segunda-feira, 12/10" para um dia `AAAA-MM-DD` (comparado com `agora`, no horário local). */
export function rotuloDia(dia: string, agora = new Date()): string {
  const [a, m, d] = dia.split('-').map(Number);
  const data = new Date(a, m - 1, d);
  const hoje = new Date(agora.getFullYear(), agora.getMonth(), agora.getDate());
  const diferenca = Math.round((hoje.getTime() - data.getTime()) / 86_400_000);
  if (diferenca === 0) return 'Hoje';
  if (diferenca === 1) return 'Ontem';
  return `${DIAS_DA_SEMANA[data.getDay()]}, ${String(d).padStart(2, '0')}/${String(m).padStart(2, '0')}`;
}

/** Data `AAAA-MM-DD` de `agora` menos `dias` (horário local), para os filtros de período. */
export function diaRelativo(dias: number, agora = new Date()): string {
  const d = new Date(agora.getFullYear(), agora.getMonth(), agora.getDate() - dias);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
