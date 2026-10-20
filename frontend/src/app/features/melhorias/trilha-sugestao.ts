// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar a trilha de uma sugestão de melhoria (recebida → em análise → aceita → concluída) para quem a enviou.

import { EstadoEtapa, EtapaTrilha } from '../../shared/componentes/trilha-etapas/trilha-etapas.component';

/** Recebida → Em análise → Aceita → Concluída; recusada marca o passo da decisão. */
export function trilhaSugestao(situacao: string): EtapaTrilha[] {
  const ordem: Record<string, number> = { nova: 0, em_analise: 1, aceita: 2, recusada: 2, concluida: 3 };
  const posicao = ordem[situacao] ?? 0;
  const estado = (i: number): EstadoEtapa => (i < posicao ? 'concluida' : i === posicao ? (situacao === 'concluida' ? 'concluida' : 'atual') : 'bloqueada');
  return [
    { id: 'nova', rotulo: 'Recebida', estado: estado(0), subtitulo: estado(0) === 'atual' ? 'aguardando a triagem' : undefined },
    { id: 'analise', rotulo: 'Em análise', estado: estado(1) },
    { id: 'decisao', rotulo: 'Aceita', estado: situacao === 'recusada' ? 'recusada' : estado(2), subtitulo: situacao === 'recusada' ? 'recusada' : undefined },
    { id: 'concluida', rotulo: 'Concluída', estado: situacao === 'concluida' ? 'concluida' : 'bloqueada' },
  ];
}
