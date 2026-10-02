// Criado por José Eduardo Santana Martins
// Este arquivo serve para descrever os dados de Contratações (ETP e TR) trocados com a API.

export type TipoDocumento = 'etp' | 'tr';
export type Situacao = 'rascunho' | 'em_revisao' | 'concluido';
export type TipoItem = 'item' | 'subitem' | 'inciso' | 'alinea' | 'subsecao';
export type Papel = 'administrador' | 'criador' | 'editor' | 'revisor';

export const ROTULOS_TIPO: Record<TipoDocumento, string> = { etp: 'ETP', tr: 'TR' };
export const ROTULOS_SITUACAO: Record<Situacao, string> = { rascunho: 'Rascunho', em_revisao: 'Em revisão', concluido: 'Concluído' };
export const ROTULOS_ITEM: Record<TipoItem, string> = { item: 'Item', subitem: 'Subitem', inciso: 'Inciso', alinea: 'Alínea', subsecao: 'Subseção' };
export const ROTULOS_PAPEL: Record<Papel, string> = { administrador: 'Administração', criador: 'Criador', editor: 'Editor', revisor: 'Revisor' };

export interface DocumentoResumo {
  id: string;
  tipo: TipoDocumento;
  nome: string;
  processo: string;
  link_sei: string | null;
  situacao: Situacao;
  criador_id: number | null;
  criador_nome: string;
  contrato_id: string | null;
  contrato_numero: string | null;
  criado_em: string;
  atualizado_em: string;
  meu_papel: Papel;
  revisoes_abertas: number;
}

export interface ListaDocumentos {
  pode_criar: boolean;
  itens: DocumentoResumo[];
}

export interface LinhaTr {
  id: string;
  ordem: number;
  descricao: string;
  siafisico: string;
  catser_catmat: string;
  unidade: string;
  quantidade_mensal: string;
  quantidade_objeto: string;
}

export interface Revisao {
  id: string;
  autor_nome: string;
  comentario: string;
  conteudo_original: string;
  conteudo_proposto: string | null;
  conteudo_proposto_html: string | null;
  aplicada_em: string | null;
  aplicada_por_nome: string | null;
  resolvida_em: string | null;
  resolvida_por_nome: string | null;
  criada_em: string;
}

export interface ComentarioImportado {
  autor: string;
  comentado_em: string | null;
  comentario: string;
  trecho: string;
}

export interface ItemDocumento {
  id: string;
  secao_id: string;
  pai_id: string | null;
  tipo: TipoItem;
  ordem: number;
  marcador: string;
  conteudo: string;
  conteudo_html: string | null;
  precisa_revisao: boolean;
  revisoes: Revisao[];
  comentarios_importados: ComentarioImportado[];
  linhas_tabela: LinhaTr[];
  tem_tabela_tr: boolean;
}

export interface SecaoDocumento {
  id: string;
  ordem: number;
  titulo: string;
  itens: ItemDocumento[];
}

export interface Membro {
  usuario_id: number;
  nome: string;
  login: string;
  papel: 'editor' | 'revisor';
}

export interface DocumentoContratacao extends DocumentoResumo {
  pode_editar: boolean;
  pode_gerir: boolean;
  pode_revisar: boolean;
  secoes: SecaoDocumento[];
  membros: Membro[];
}

export interface Conferencia {
  pode_concluir: boolean;
  bloqueios: string[];
  alertas: string[];
}

export interface PainelContratacoes {
  total: number;
  por_situacao: Record<string, number>;
  por_tipo: Record<string, number>;
  revisoes_abertas: number;
  sem_vinculo: number;
}

export interface Versao {
  numero: number;
  tipo: string;
  tipo_rotulo: string;
  resumo: string;
  autor_nome: string;
  criada_em: string;
}

export interface VersaoDetalhe extends Versao {
  foto: { nome: string; processo: string; situacao: string; secoes: { id: string; ordem: number; titulo: string }[]; itens: { id: string; secao_id: string; pai_id: string | null; tipo: TipoItem; ordem: number; conteudo: string; conteudo_html: string | null }[] };
}

export interface AlteracaoItem {
  id: string;
  mudanca: 'incluido' | 'removido' | 'alterado' | 'movido';
  marcador: string;
  marcador_antes?: string;
  secao: string;
  tipo: TipoItem;
  html?: string;
  diferenca?: string;
}

export interface Alteracoes {
  versao: number;
  contra: number | null;
  resumo: Record<string, number>;
  secoes: { id: string; mudanca: string; titulo: string; titulo_antes?: string }[];
  itens: AlteracaoItem[];
  metadados: { campo: string; antes: string; depois: string }[];
}

export interface EntradaHistorico {
  id: string;
  mudanca: 'criou' | 'editou' | 'moveu' | 'removeu' | 'restaurou';
  autor_nome: string;
  ocorrido_em: string;
  detalhe: string;
  antes_html: string | null;
  depois_html: string | null;
  diferenca: string;
}

export interface PreviaImportacao {
  arquivo: string;
  nome_sugerido: string;
  processo_sugerido: string;
  sha256: string;
  secoes: { id_cliente: string; titulo: string; itens: { id_cliente: string; pai_id_cliente: string | null; tipo: TipoItem; conteudo: string; precisa_revisao: boolean; aviso: string | null; comentarios: unknown[] }[] }[];
  avisos: string[];
  totais: { secoes: number; itens: number; tabelas: number; para_revisar: number; comentarios: number };
  documento_id: string | null;
}

export interface PreviaLote {
  itens: { tipo: TipoItem; conteudo: string; profundidade: number }[];
}
