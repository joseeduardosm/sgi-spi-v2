// Criado por José Eduardo Santana Martins
// Este arquivo serve para preparar os arquivos colados (Ctrl+V) num comentário: nome dos prints, formatos aceitos e limite de arquivos.

/** Extensões aceitas nos anexos de comentário (as mesmas do botão Anexar). */
export const EXTENSOES_ANEXO = new Set(['pdf', 'docx', 'xlsx', 'pptx', 'odt', 'ods', 'odp', 'doc', 'xls', 'ppt', 'png', 'jpg', 'jpeg', 'txt', 'csv']);
export const MAXIMO_ANEXOS = 5;

function carimbo(agora: Date): string {
  const d = (n: number) => String(n).padStart(2, '0');
  return `${agora.getFullYear()}${d(agora.getMonth() + 1)}${d(agora.getDate())}-${d(agora.getHours())}${d(agora.getMinutes())}${d(agora.getSeconds())}`;
}

export interface ResultadoColagem {
  /** Arquivos que ficam no comentário (os atuais mais os colados aceitos, até o limite). */
  arquivos: File[];
  /** Quantos colados não eram de um formato aceito. */
  recusados: number;
  /** Havia mais arquivos do que o limite: os que passaram do limite foram descartados. */
  excedeu: boolean;
}

/**
 * Print colado vem como "image.png" (ou sem nome): vira "captura-AAAAMMDD-HHMMSS.png" (com "-1", "-2" quando são vários). Outros arquivos
 * mantêm o nome; formatos fora da lista são recusados e o total nunca passa de 5.
 */
export function prepararArquivosColados(colados: File[], atuais: File[], agora = new Date()): ResultadoColagem {
  const aceitos: File[] = [];
  let recusados = 0;
  colados.forEach((arquivo, i) => {
    const extensao = (arquivo.name.split('.').pop() ?? '').toLowerCase();
    const semNome = !arquivo.name || /^image\.(png|jpe?g)$/i.test(arquivo.name);
    if (!EXTENSOES_ANEXO.has(extensao) && !(semNome && /^image\/(png|jpeg)$/.test(arquivo.type))) { recusados += 1; return; }
    if (semNome) {
      const sufixo = arquivo.type === 'image/jpeg' ? 'jpg' : 'png';
      aceitos.push(new File([arquivo], `captura-${carimbo(agora)}${colados.length > 1 ? '-' + (i + 1) : ''}.${sufixo}`, { type: arquivo.type }));
    } else aceitos.push(arquivo);
  });
  const todos = [...atuais, ...aceitos];
  return { arquivos: todos.slice(0, MAXIMO_ANEXOS), recusados, excedeu: todos.length > MAXIMO_ANEXOS };
}
