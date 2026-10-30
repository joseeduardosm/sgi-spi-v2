// Criado por José Eduardo Santana Martins
// Este arquivo serve para copiar um texto em HTML com a formatação (negrito, alinhamento) para colar no SEI ou no Word.

/** Copia o HTML formatado e, por garantia, o texto puro: no SEI ou no Word, o negrito e o alinhamento vêm junto. */
export async function copiarFormatado(html: string): Promise<void> {
  const caixa = document.createElement('div');
  caixa.innerHTML = html;
  document.body.appendChild(caixa);
  const texto = caixa.innerText;
  caixa.remove();
  const item = typeof ClipboardItem !== 'undefined'
    ? new ClipboardItem({ 'text/html': new Blob([html], { type: 'text/html' }), 'text/plain': new Blob([texto], { type: 'text/plain' }) })
    : null;
  try {
    await (item ? navigator.clipboard.write([item]) : navigator.clipboard.writeText(texto));
  } catch {
    await navigator.clipboard?.writeText(texto).catch(() => undefined);
  }
}
