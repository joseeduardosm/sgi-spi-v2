// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar a trilha de etapas de uma notícia (rascunho → revisão → aprovada → publicada) a partir da situação que a API informa.

import { EstadoEtapa, EtapaTrilha } from '../../shared/componentes/trilha-etapas/trilha-etapas.component';

interface DadosNoticia { situacao: string; visivel?: boolean; publicar_em?: string | null }

/** Rascunho → Em revisão → Aprovada → Publicada (no portal). Devolvida volta ao passo 1; arquivada tira do portal. */
export function trilhaNoticia(n: DadosNoticia): EtapaTrilha[] {
  const ordem: Record<string, number> = { rascunho: 0, devolvida: 0, em_revisao: 1, aprovada: 2, arquivada: 3 };
  const posicao = ordem[n.situacao] ?? 0;
  const publicada = n.situacao === 'aprovada' && !!n.visivel;
  const estado = (i: number): EstadoEtapa => (i < posicao ? 'concluida' : i === posicao ? 'atual' : 'bloqueada');
  return [
    { id: 'rascunho', rotulo: 'Rascunho', estado: estado(0), subtitulo: n.situacao === 'devolvida' ? 'devolvida: ajustar' : undefined },
    { id: 'revisao', rotulo: 'Em revisão', estado: estado(1), subtitulo: estado(1) === 'atual' ? 'aprovador' : undefined },
    { id: 'aprovada', rotulo: 'Aprovada', estado: n.situacao === 'aprovada' ? 'concluida' : n.situacao === 'arquivada' ? 'concluida' : estado(2) },
    { id: 'publicada', rotulo: 'Publicada no portal', estado: publicada ? 'concluida' : n.situacao === 'arquivada' ? 'recusada' : n.situacao === 'aprovada' ? 'atual' : 'bloqueada',
      subtitulo: publicada ? 'no portal' : n.situacao === 'arquivada' ? 'arquivada' : n.situacao === 'aprovada' ? 'agendada' : undefined },
  ];
}
