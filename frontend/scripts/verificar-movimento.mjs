// Criado por José Eduardo Santana Martins
// Este arquivo serve para impedir que telas novas voltem ao "Carregando…" em texto ou a imagens sem carregamento preguiçoso.
// Uso: npm run verificar:movimento (sai com erro se achar algo fora da regra)
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const RAIZ = join(process.cwd(), 'src', 'app');
// Imagens acima da dobra (logos e destaque das notícias) carregam na hora de propósito; as demais precisam de loading="lazy" (ou da diretiva de imagem autenticada)
const IMAGENS_IMEDIATAS = ['layout-portal.component.ts', 'cabecalho.component.html', 'slider-noticias.component.ts', 'noticia.component.ts', 'recorte-capa.component.ts'];

function arquivos(pasta) {
  return readdirSync(pasta).flatMap((nome) => {
    const caminho = join(pasta, nome);
    if (statSync(caminho).isDirectory()) return arquivos(caminho);
    return /\.(ts|html)$/.test(nome) && !nome.endsWith('.spec.ts') ? [caminho] : [];
  });
}

const problemas = [];
for (const caminho of arquivos(RAIZ)) {
  const rel = relative(RAIZ, caminho);
  const texto = readFileSync(caminho, 'utf-8');
  for (const linha of texto.split('\n')) {
    if (/Carregando|Buscando…|Pesquisando…/.test(linha) && !/^\s*(\/\/|\*|\/\*)/.test(linha) && !/aria-label="Carregando"|input\('Carregando/.test(linha) && !rel.includes('esqueleto.component')) {
      problemas.push(`${rel}: texto de carregamento ("Carregando…", "Buscando…") (use <app-esqueleto>): ${linha.trim().slice(0, 90)}`);
    }
  }
  // Só tags reais (com atributos) e fora de comentários
  const semComentarios = texto.split('\n').filter((l) => !/^\s*(\/\/|\*|\/\*)/.test(l)).join('\n');
  for (const [tag] of semComentarios.matchAll(/<img\s[^>]*>/g)) {
    if (!/loading=/.test(tag) && !/appImagemAutenticada/.test(tag) && !IMAGENS_IMEDIATAS.some((n) => rel.endsWith(n))) {
      problemas.push(`${rel}: <img> sem loading="lazy": ${tag.slice(0, 80)}`);
    }
  }
}
if (problemas.length) {
  console.error(problemas.join('\n'));
  process.exit(1);
}
console.log('Movimento OK: nenhum "Carregando…" em texto e todas as imagens com carregamento preguiçoso (ou na lista de exceções).');
