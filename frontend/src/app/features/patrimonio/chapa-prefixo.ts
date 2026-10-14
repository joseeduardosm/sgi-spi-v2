// Criado por José Eduardo Santana Martins
// Este arquivo serve para separar e juntar prefixo e número da chapa (SPI + 231 = SPI000231), do mesmo jeito que o servidor.

/** Separa um código que já traz o prefixo (ex.: SPI000231, lido da etiqueta) em prefixo e número; nulo se não começar por nenhum prefixo conhecido. */
export function separarChapa(texto: string, prefixos: { codigo: string }[]): { prefixo: string; numero: string } | null {
  const bruto = texto.trim();
  const maiusculo = bruto.toUpperCase();
  const achado = [...prefixos].sort((a, b) => b.codigo.length - a.codigo.length).find((p) => maiusculo.startsWith(p.codigo) && maiusculo.length > p.codigo.length);
  return achado ? { prefixo: achado.codigo, numero: bruto.slice(achado.codigo.length).trim() } : null;
}

/** A chapa como o servidor vai gravar: prefixo + número com 6 dígitos (só números ganham zeros à esquerda); outro texto fica como digitado. Sem número, vazio. */
export function montarChapa(prefixo: string, numero: string): string {
  const n = numero.trim();
  if (!n) return '';
  const p = prefixo.trim().toUpperCase();
  if (!p) return n;
  const semPrefixo = n.toUpperCase().startsWith(p) && n.length > p.length ? n.slice(p.length).trim() : n;
  return p + (/^\d+$/.test(semPrefixo) ? semPrefixo.padStart(6, '0') : semPrefixo);
}
