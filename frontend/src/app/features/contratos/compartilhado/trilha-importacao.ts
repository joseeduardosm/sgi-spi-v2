// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar a trilha das importações por planilha (baixar o modelo → enviar → conferir a prévia → confirmar).

import { EtapaTrilha } from '../../../shared/componentes/trilha-etapas/trilha-etapas.component';

/** Passo atual a partir do estado da janela: com a prévia sem erros pronta, falta só confirmar; com erros, a conferência continua em andamento. */
export function trilhaImportacao(temArquivo: boolean, previa: { pode_importar: boolean } | null): EtapaTrilha[] {
  const lida = previa !== null;
  const ok = !!previa?.pode_importar;
  return [
    { id: 'modelo', rotulo: 'Baixar o modelo e preencher', estado: temArquivo ? 'concluida' : 'atual' },
    { id: 'enviar', rotulo: 'Enviar a planilha', estado: lida ? 'concluida' : temArquivo ? 'atual' : 'aguardando' },
    { id: 'previa', rotulo: 'Conferir a prévia', estado: ok ? 'concluida' : lida ? 'atual' : 'aguardando', subtitulo: lida && !ok ? 'corrija os erros' : undefined },
    { id: 'confirmar', rotulo: 'Confirmar a importação', estado: ok ? 'atual' : 'bloqueada' },
  ];
}
