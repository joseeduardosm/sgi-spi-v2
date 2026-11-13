/**
 * =============================================================================
 * ARQUIVO: copiar-formatado.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Copiar para a área de transferência um texto em HTML mantendo a formatação
 * (negrito, alinhamento), para que o usuário cole direto no SEI ou no Word.
 *
 * RESUMO TÉCNICO:
 * Exporta a função assíncrona copiarFormatado(html). Ela monta um ClipboardItem
 * com duas versões do conteúdo (text/html e text/plain). Se o navegador não
 * suportar ClipboardItem, ou se a gravação falhar, cai no texto puro.
 *
 * FINALIDADE DE NEGÓCIO:
 * Despachos, e-mails e portarias gerados pelo SGI precisam ir para o SEI
 * (sistema de processo eletrônico) sem que o servidor tenha de refazer a
 * formatação à mão, evitando retrabalho e erro de digitação.
 *
 * CONTEXTO NO SISTEMA:
 * Usada pelas telas de contratos que oferecem o botão "Copiar" de textos
 * prontos (modelos de despacho, e-mail de OB, CADIN, portarias etc.).
 *
 * =============================================================================
 */

/**
 * Copia o HTML formatado e, por garantia, o texto puro: no SEI ou no Word, o negrito e o alinhamento vêm junto.
 *
 * @param html Trecho HTML já pronto (ex.: o corpo de um despacho).
 * @returns Promessa resolvida quando a cópia termina; erros de permissão são engolidos (não quebram a tela).
 */
export async function copiarFormatado(html: string): Promise<void> {
  // Para obter o texto puro equivalente, o HTML é colocado num <div> temporário
  // ligado ao documento: só assim o innerText respeita quebras de linha e blocos.
  const caixa = document.createElement('div');
  caixa.innerHTML = html;
  document.body.appendChild(caixa);
  const texto = caixa.innerText;
  caixa.remove();
  // ClipboardItem permite gravar o mesmo conteúdo em vários formatos ao mesmo tempo;
  // o programa que recebe a colagem escolhe o melhor (o SEI pega o HTML).
  // Navegadores antigos não têm ClipboardItem: nesse caso, item fica nulo e só o texto é copiado.
  const item = typeof ClipboardItem !== 'undefined'
    ? new ClipboardItem({ 'text/html': new Blob([html], { type: 'text/html' }), 'text/plain': new Blob([texto], { type: 'text/plain' }) })
    : null;
  try {
    await (item ? navigator.clipboard.write([item]) : navigator.clipboard.writeText(texto));
  } catch {
    // Se o navegador recusar o formato rico (permissão, página sem foco), tenta ao menos o texto puro;
    // um segundo erro é ignorado para não exibir falha técnica ao usuário.
    await navigator.clipboard?.writeText(texto).catch(() => undefined);
  }
}
