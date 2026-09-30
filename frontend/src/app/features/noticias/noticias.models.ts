// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos do Módulo Notícias e do portal (espelham os schemas de /api/noticias e /api/portal).

export type SituacaoNoticia = 'rascunho' | 'em_revisao' | 'aprovada' | 'devolvida' | 'arquivada';
export type ModoCapa = 'recortar' | 'inteira';

export const ROTULOS_SITUACAO: Record<SituacaoNoticia, string> = {
  rascunho: 'Rascunho', em_revisao: 'Aguardando aprovação', aprovada: 'Aprovada', devolvida: 'Devolvida', arquivada: 'Arquivada',
};

export interface Categoria { id: number; nome: string; cor: string; ordem: number; ativa: boolean }
export interface Arquivo { id: string; nome: string; tamanho: number; tipo: string; url: string }
/** URLs das versões WebP 2:1 da capa: "1600", "800", "400". */
export type Capa = Record<string, string>;

export interface NoticiaCartao {
  id: string;
  slug: string;
  titulo: string;
  linha_fina: string;
  categoria: Categoria | null;
  publicada_em: string | null;
  fixada: boolean;
  capa: Capa;
  capa_alt: string;
  capa_modo: ModoCapa;
}

export interface NoticiaPublica extends NoticiaCartao { corpo_html: string; anexos: Arquivo[]; leia_tambem: NoticiaCartao[] }
export interface PaginaNoticias { itens: NoticiaCartao[]; total: number; pagina: number; tamanho: number }

export interface Atalho { id: number; titulo: string; url: string; nova_aba: boolean; ativo: boolean; ordem: number; imagem: string | null }

export interface ConfiguracaoPortal {
  titulo: string;
  subtitulo: string;
  quantidade_slides: number;
  segundos_por_slide: number;
  passagem_automatica: boolean;
  criterio_slider: 'automatico' | 'curadoria';
  titulo_sobreposto: boolean;
  quantidade_cartoes: number;
  exibir_atalhos: boolean;
  exibir_todas: boolean;
  atualizado_em?: string | null;
  atualizado_por_nome?: string;
}

export interface Portal { configuracao: ConfiguracaoPortal; slides: NoticiaCartao[]; cartoes: NoticiaCartao[]; atalhos: Atalho[]; categorias: Categoria[] }

// --- Gestão ---------------------------------------------------------------------------------------

export interface Pessoa { id: number; nome: string; login: string }
export interface SetorResumo { id: number; nome: string }

export interface NoticiaGestaoResumo {
  id: string;
  slug: string;
  titulo: string;
  situacao: SituacaoNoticia;
  visivel: boolean;
  categoria: Categoria | null;
  autor_nome: string;
  publicar_em: string | null;
  atualizado_em: string;
  fixada: boolean;
  capa: Capa;
}

export interface NoticiaGestao extends NoticiaGestaoResumo {
  linha_fina: string;
  corpo_html: string;
  categoria_id: number | null;
  destaque_ate: string | null;
  exige_ciencia: boolean;
  usuarios_aviso: Pessoa[];
  setores_aviso: SetorResumo[];
  aviso_enviado_em: string | null;
  capa_modo: ModoCapa;
  capa_recorte: { x: number; y: number; largura: number; altura: number } | null;
  capa_alt: string;
  capa_original: string | null;
  anexos: Arquivo[];
  autor_id: number | null;
  enviada_revisao_em: string | null;
  aprovado_por_nome: string | null;
  aprovado_em: string | null;
  motivo_devolucao: string | null;
  visualizacoes: number;
  ciencia: { total: number; cientes: number } | null;
  versao: number;
  acoes: string[];
}

export interface GravacaoNoticia {
  titulo: string;
  linha_fina: string;
  corpo_html: string;
  categoria_id: number | null;
  publicar_em: string | null;
  destaque_ate: string | null;
  fixada: boolean;
  exige_ciencia: boolean;
  usuarios_aviso: number[];
  setores_aviso: number[];
  capa_alt: string;
  versao?: number;
}

export interface Revisao { versao: number; descricao: string; titulo: string; linha_fina: string; corpo_html: string; autor_nome: string; criado_em: string }
export interface Ciencias { total: number; cientes: number; pessoas: { nome: string; ciente_em: string | null }[] }
export interface PapelNoticias { nivel: string | null; redator: boolean; aprovador: boolean; aguardando_aprovacao: number; contagem: Record<string, number> }
export interface ConfiguracaoGestao { configuracao: ConfiguracaoPortal; curadoria: NoticiaCartao[]; candidatas: NoticiaCartao[] }

/** "30/09/2026" a partir de uma data ISO. */
export function dataCurta(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString('pt-BR') : '';
}

/** srcset das versões da capa (400w, 800w, 1600w). */
export function srcsetCapa(capa: Capa): string {
  return Object.entries(capa).map(([t, url]) => `${url} ${t}w`).join(', ');
}

/** Date/ISO → "aaaa-mm-ddThh:mm" no horário local (campo datetime-local). */
export function paraCampo(valor: string | Date | null): string {
  if (!valor) return '';
  const d = new Date(valor);
  const z = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}`;
}

/** Campo datetime-local → ISO (ou null se vazio). */
export function deCampo(valor: string): string | null {
  return valor ? new Date(valor).toISOString() : null;
}

/** Tamanho legível ("1,2 MB"). */
export function tamanhoLegivel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} MB`;
}
