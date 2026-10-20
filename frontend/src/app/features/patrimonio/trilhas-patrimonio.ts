// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar as trilhas de etapas do Patrimônio (movimentação, listas de inservíveis/extraviados e baixa) a partir do que a API informa.

import { EstadoEtapa, EtapaTrilha } from '../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { Baixa, Classificacao, Movimentacao } from './patrimonio.models';

/** Solicitada → Autorizada → Recebimento (x de y bens) → Concluída. Recusada e cancelada marcam o passo em que pararam. */
export function trilhaMovimentacao(m: Movimentacao): EtapaTrilha[] {
  const recebidos = m.itens.filter((i) => i.recebido_em).length;
  const recusada = m.status === 'recusada';
  const cancelada = m.status === 'cancelada';
  const autorizada = ['autorizada', 'concluida'].includes(m.status);
  const autorizacao: EstadoEtapa = autorizada ? 'concluida' : recusada ? 'recusada' : cancelada ? 'bloqueada' : 'atual';
  const recebimento: EstadoEtapa = m.status === 'concluida' ? 'concluida' : m.status === 'autorizada' ? 'atual' : 'bloqueada';
  return [
    { id: 'solicitada', rotulo: 'Solicitada', estado: 'concluida', titulo: `${m.solicitante_nome} · ${m.solicitada_em}`, subtitulo: `por ${m.solicitante_nome}` },
    { id: 'autorizada', rotulo: 'Autorizada', estado: autorizacao, subtitulo: recusada ? 'recusada' : cancelada ? 'cancelada' : autorizacao === 'atual' ? 'controle total' : undefined },
    { id: 'recebimento', rotulo: 'Recebimento', estado: recebimento, subtitulo: autorizada ? `${recebidos} de ${m.itens.length} recebidos` : undefined },
    { id: 'concluida', rotulo: 'Concluída', estado: m.status === 'concluida' ? 'concluida' : 'bloqueada' },
  ];
}

/** Rascunho → Enviada para aprovação → Decisão (aprovada / em parte / recusada) → Bem classificado. */
export function trilhaClassificacao(c: Classificacao): EtapaTrilha[] {
  const enviada = c.status !== 'rascunho';
  const decidida = ['aprovada', 'parcial', 'recusada'].includes(c.status);
  const desfecho = c.status === 'aprovada' ? 'aprovada' : c.status === 'parcial' ? 'aprovada em parte' : c.status === 'recusada' ? 'recusada' : 'controle total';
  const classificado = c.status === 'aprovada' || c.status === 'parcial';
  const alvo = c.tipo === 'inservivel' ? 'inservível' : 'extraviado';
  return [
    { id: 'rascunho', rotulo: 'Rascunho', estado: enviada ? 'concluida' : 'atual', subtitulo: enviada ? 'montada' : 'incluir, justificar e enviar' },
    { id: 'enviada', rotulo: 'Enviada para aprovação', estado: enviada ? 'concluida' : 'bloqueada' },
    { id: 'decisao', rotulo: 'Decisão', estado: c.status === 'recusada' ? 'recusada' : decidida ? 'concluida' : enviada ? 'atual' : 'bloqueada', subtitulo: enviada ? desfecho : undefined },
    { id: 'classificado', rotulo: `Bem ${alvo}`, estado: classificado ? 'concluida' : 'bloqueada', subtitulo: classificado ? 'situação do bem atualizada' : undefined },
  ];
}

/** Rascunho (herda a lista) → Aguardando aceite da autoridade → Concluída (PDF do de acordo / D.O.E. anexado). */
export function trilhaBaixa(b: Baixa): EtapaTrilha[] {
  const enviada = b.status !== 'rascunho';
  const concluida = b.status === 'concluida';
  const recusada = b.status === 'recusada';
  return [
    { id: 'rascunho', rotulo: 'Rascunho', estado: enviada ? 'concluida' : 'atual', subtitulo: enviada ? 'termo gerado' : 'motivo e processo' },
    { id: 'aceite', rotulo: 'Aguardando aceite da autoridade', estado: concluida ? 'concluida' : recusada ? 'recusada' : enviada ? 'atual' : 'bloqueada', subtitulo: recusada ? 'recusada' : enviada && !concluida ? 'termo no SEI' : undefined },
    { id: 'concluida', rotulo: 'Concluída', estado: concluida ? 'concluida' : 'bloqueada', subtitulo: concluida ? 'PDF do de acordo anexado' : 'anexar o PDF (D.O.E.)' },
  ];
}
