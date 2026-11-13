/**
 * =============================================================================
 * ARQUIVO: trilha-importacao.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Montar as etapas da trilha exibida nas importações por planilha: baixar o
 * modelo, enviar, conferir a prévia e confirmar.
 *
 * RESUMO TÉCNICO:
 * Exporta a função pura trilhaImportacao(), que recebe se há arquivo e a
 * prévia da API e devolve a lista EtapaTrilha com o estado de cada passo
 * (concluida, atual, aguardando ou bloqueada).
 *
 * FINALIDADE DE NEGÓCIO:
 * Mostra ao usuário em que ponto da importação ele está e deixa claro que só
 * é possível confirmar quando a prévia não tem erros.
 *
 * CONTEXTO NO SISTEMA:
 * Usada por importacao-modelo-xlsx.component.ts e pela importação de
 * contratos; o desenho fica no componente compartilhado app-trilha-etapas.
 *
 * =============================================================================
 */

import { EtapaTrilha } from '../../../shared/componentes/trilha-etapas/trilha-etapas.component';

/** Passo atual a partir do estado da janela: com a prévia sem erros pronta, falta só confirmar; com erros, a conferência continua em andamento. */
export function trilhaImportacao(temArquivo: boolean, previa: { pode_importar: boolean } | null): EtapaTrilha[] {
  // lida = a API já devolveu a prévia; ok = a prévia não tem erros e pode ser gravada
  const lida = previa !== null;
  const ok = !!previa?.pode_importar;
  return [
    { id: 'modelo', rotulo: 'Baixar o modelo e preencher', estado: temArquivo ? 'concluida' : 'atual' },
    { id: 'enviar', rotulo: 'Enviar a planilha', estado: lida ? 'concluida' : temArquivo ? 'atual' : 'aguardando' },
    { id: 'previa', rotulo: 'Conferir a prévia', estado: ok ? 'concluida' : lida ? 'atual' : 'aguardando', subtitulo: lida && !ok ? 'corrija os erros' : undefined },
    { id: 'confirmar', rotulo: 'Confirmar a importação', estado: ok ? 'atual' : 'bloqueada' },
  ];
}
