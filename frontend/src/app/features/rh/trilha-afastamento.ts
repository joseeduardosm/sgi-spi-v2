// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar a trilha de etapas de um afastamento (férias e licença-prêmio) a partir do que a API informa.

import { EtapaTrilha, EstadoEtapa } from '../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { Afastamento } from './rh.models';

/** Solicitado → Ciência do superior → Aprovação → Gozo. Recusado marca a aprovação; cancelado interrompe a trilha (o selo diz). */
export function trilhaAfastamento(a: Afastamento): EtapaTrilha[] {
  const decidido = a.status === 'aprovado' || a.status === 'gozado';
  const recusado = a.status === 'recusado';
  // A ciência é dispensada quando não há superior (ou ele é o próprio aprovador): o pedido já nasce direto para a aprovação
  const ciencia: EstadoEtapa = a.ciencia_em ? 'concluida' : a.aguarda_ciencia ? 'atual' : 'concluida';
  const aprovacao: EstadoEtapa = decidido ? 'concluida' : recusado ? 'recusada' : a.status === 'pendente' && !a.aguarda_ciencia ? 'atual' : 'bloqueada';
  const gozo: EstadoEtapa = a.status === 'gozado' ? 'concluida' : a.status === 'aprovado' ? 'atual' : 'bloqueada';
  return [
    { id: 'solicitado', rotulo: 'Solicitado', estado: 'concluida', titulo: a.solicitado_em },
    { id: 'ciencia', rotulo: 'Ciência do superior', estado: ciencia, subtitulo: a.ciencia_em ? `por ${a.ciencia_por_nome}` : a.aguarda_ciencia ? 'ciente e de acordo' : 'dispensada' },
    { id: 'aprovacao', rotulo: 'Aprovação', estado: aprovacao, subtitulo: recusado ? 'recusado' : aprovacao === 'atual' ? 'autorizador, substituto ou CGP' : undefined },
    { id: 'gozo', rotulo: 'Gozo', estado: gozo, subtitulo: gozo === 'atual' ? 'aprovado, aguardando o período' : undefined },
  ];
}
