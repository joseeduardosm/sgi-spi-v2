// Criado por José Eduardo Santana Martins
// Este arquivo serve para escrever um valor em reais por extenso (ex.: 497.982,68 → "Quatrocentos e Noventa e Sete Mil, Novecentos e Oitenta e Dois Reais e Sessenta e Oito Centavos").

const UNIDADES = ['', 'um', 'dois', 'três', 'quatro', 'cinco', 'seis', 'sete', 'oito', 'nove', 'dez', 'onze', 'doze', 'treze', 'catorze', 'quinze', 'dezesseis', 'dezessete', 'dezoito', 'dezenove'];
const DEZENAS = ['', '', 'vinte', 'trinta', 'quarenta', 'cinquenta', 'sessenta', 'setenta', 'oitenta', 'noventa'];
const CENTENAS = ['', 'cento', 'duzentos', 'trezentos', 'quatrocentos', 'quinhentos', 'seiscentos', 'setecentos', 'oitocentos', 'novecentos'];
/** Escalas de cada grupo de três dígitos, da menor para a maior: [singular, plural]. */
const ESCALAS: [string, string][] = [['', ''], ['mil', 'mil'], ['milhão', 'milhões'], ['bilhão', 'bilhões'], ['trilhão', 'trilhões']];

/** Um grupo de 1 a 999 por extenso, em minúsculas. */
function grupo(n: number): string {
  if (n === 100) return 'cem';
  const partes: string[] = [];
  const c = Math.floor(n / 100);
  const resto = n % 100;
  if (c) partes.push(CENTENAS[c]);
  if (resto) partes.push(resto < 20 ? UNIDADES[resto] : DEZENAS[Math.floor(resto / 10)] + (resto % 10 ? ' e ' + UNIDADES[resto % 10] : ''));
  return partes.join(' e ');
}

/** Número inteiro (0 a 999 trilhões) por extenso, em minúsculas. Grupos separados por vírgula, ou por "e" quando o que sobra é menor que 100 ou uma centena exata. */
function inteiro(n: number): string {
  if (n === 0) return 'zero';
  const grupos: { valor: number; escala: number }[] = [];
  for (let i = 0, resto = n; resto > 0; i++, resto = Math.floor(resto / 1000)) {
    const valor = resto % 1000;
    if (valor) grupos.unshift({ valor, escala: i });
  }
  let texto = '';
  grupos.forEach((g, i) => {
    const [singular, plural] = ESCALAS[g.escala];
    // "mil" sozinho (1.000), nunca "um mil"
    const nome = g.escala === 1 && g.valor === 1 ? 'mil' : `${grupo(g.valor)}${g.escala ? ' ' + (g.valor === 1 ? singular : plural) : ''}`;
    if (i === 0) { texto = nome; return; }
    const seguinte = g.valor;
    const ultimo = i === grupos.length - 1;
    // "e" quando o último grupo é menor que 100 ou centena exata; vírgula nos demais casos
    texto += (ultimo && (seguinte < 100 || seguinte % 100 === 0) ? ' e ' : ', ') + nome;
  });
  return texto;
}

/** Primeira letra de cada palavra em maiúscula, menos "e" e "de". */
function titulo(texto: string): string {
  return texto.replace(/(^|[\s,])([a-zà-ú]+)/g, (_, antes: string, palavra: string) => antes + (palavra === 'e' || palavra === 'de' ? palavra : palavra[0].toUpperCase() + palavra.slice(1)));
}

/** Valor em reais por extenso, com reais e centavos: `497982.68` → "Quatrocentos e Noventa e Sete Mil, Novecentos e Oitenta e Dois Reais e Sessenta e Oito Centavos". */
export function valorPorExtenso(valor: number | string): string {
  const total = Math.round(Math.abs(Number(valor)) * 100);
  const reais = Math.floor(total / 100);
  const centavos = total % 100;
  const partes: string[] = [];
  if (reais > 0 || centavos === 0) {
    // "de reais" quando termina em milhão, bilhão... exatos ("Um Milhão de Reais")
    const redondo = reais >= 1_000_000 && reais % 1_000_000 === 0;
    partes.push(`${inteiro(reais)} ${reais === 1 ? 'real' : redondo ? 'de reais' : 'reais'}`);
  }
  if (centavos > 0) partes.push(`${inteiro(centavos)} ${centavos === 1 ? 'centavo' : 'centavos'}`);
  return titulo(partes.join(' e '));
}
