/**
 * Formatos brasileiros usados nas telas: R$ com 2 casas, quantidades com até 4 casas,
 * datas dd/mm/aaaa e competências mm/aaaa. A API envia valores decimais como texto
 * (ex.: "1234.50") para não perder precisão; estas funções aceitam texto ou número.
 */

const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const quantidade = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 4 });
const percentual = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 2 });

type Numerico = number | string | null | undefined;

function numero(valor: Numerico): number | null {
  if (valor === null || valor === undefined || valor === '') return null;
  const convertido = typeof valor === 'number' ? valor : Number(valor);
  return Number.isFinite(convertido) ? convertido : null;
}

export function formatarMoeda(valor: Numerico, vazio = 'R$ -'): string {
  const n = numero(valor);
  return n === null ? vazio : moeda.format(n);
}

export function formatarQuantidade(valor: Numerico, vazio = '—'): string {
  const n = numero(valor);
  return n === null ? vazio : quantidade.format(n);
}

/** `valor` em pontos percentuais (ex.: 12.5 → "12,5%"). */
export function formatarPercentual(valor: Numerico, vazio = '—'): string {
  const n = numero(valor);
  return n === null ? vazio : `${percentual.format(n)}%`;
}

/** Data sem hora `AAAA-MM-DD` → `dd/mm/aaaa`, sem passar por `Date` (evita erro de fuso). */
export function formatarData(valor: string | null | undefined, vazio = '—'): string {
  const partes = /^(\d{4})-(\d{2})-(\d{2})/.exec(valor ?? '');
  return partes ? `${partes[3]}/${partes[2]}/${partes[1]}` : vazio;
}

/** Competência `AAAA-MM` ou `AAAA-MM-01` → `mm/aaaa`. */
export function formatarCompetencia(valor: string | null | undefined, vazio = '—'): string {
  const partes = /^(\d{4})-(\d{2})/.exec(valor ?? '');
  return partes ? `${partes[2]}/${partes[1]}` : vazio;
}

/** Tamanho de arquivo legível (ex.: 1258291 → "1,2 MB"). */
export function formatarTamanho(bytes: number | null | undefined): string {
  if (!bytes) return '0 KB';
  const unidades = ['B', 'KB', 'MB', 'GB'];
  let valor = bytes;
  let indice = 0;
  while (valor >= 1024 && indice < unidades.length - 1) {
    valor /= 1024;
    indice++;
  }
  return `${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: indice === 0 ? 0 : 1 }).format(valor)} ${unidades[indice]}`;
}

/** Data de hoje no fuso do navegador, no formato AAAA-MM-DD. */
export function hojeIso(): string {
  const agora = new Date();
  return `${agora.getFullYear()}-${String(agora.getMonth() + 1).padStart(2, '0')}-${String(agora.getDate()).padStart(2, '0')}`;
}
