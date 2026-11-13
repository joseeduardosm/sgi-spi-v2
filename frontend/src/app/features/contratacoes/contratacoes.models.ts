// Criado por José Eduardo Santana Martins
// Este arquivo serve para descrever os dados de Contratações (ETP e TR) trocados com a API.

/** Tipo do documento: ETP (Estudo Técnico Preliminar) ou TR (Termo de Referência). */
export type TipoDocumento = 'etp' | 'tr';
/** Situação do documento no fluxo: rascunho → em revisão → concluído. */
export type Situacao = 'rascunho' | 'em_revisao' | 'concluido';
/** Nível do item na árvore da seção (item, subitem, inciso, alínea ou subseção), como na redação de normas. */
export type TipoItem = 'item' | 'subitem' | 'inciso' | 'alinea' | 'subsecao';
/** Papel da pessoa logada no documento; define o que ela pode fazer (editar, revisar, gerir). */
export type Papel = 'administrador' | 'criador' | 'editor' | 'revisor';

// Textos exibidos na tela para cada valor técnico vindo da API.
export const ROTULOS_TIPO: Record<TipoDocumento, string> = { etp: 'ETP', tr: 'TR' };
export const ROTULOS_SITUACAO: Record<Situacao, string> = { rascunho: 'Rascunho', em_revisao: 'Em revisão', concluido: 'Concluído' };
export const ROTULOS_ITEM: Record<TipoItem, string> = { item: 'Item', subitem: 'Subitem', inciso: 'Inciso', alinea: 'Alínea', subsecao: 'Subseção' };
export const ROTULOS_PAPEL: Record<Papel, string> = { administrador: 'Administração', criador: 'Criador', editor: 'Editor', revisor: 'Revisor' };

/** Linha da lista de documentos: dados básicos, vínculo com contrato, papel da pessoa e revisões pendentes. */
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

/** Resposta da listagem: os documentos e se a pessoa pode criar um novo. */
export interface ListaDocumentos {
  pode_criar: boolean;
  itens: DocumentoResumo[];
}

/**
 * Linha da tabela de itens do TR (objeto da contratação). Quantidades chegam como texto para não perder casas decimais.
 * siafisico e catser_catmat são os códigos do item nos catálogos de compras (SIAFÍSICO e CATSER/CATMAT).
 */
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

/**
 * Revisão (sugestão ou comentário) feita por um revisor sobre um item. Pode trazer um texto proposto;
 * aplicada_em indica que a sugestão foi aceita no texto; resolvida_em, que a revisão foi encerrada.
 */
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

/** Comentário que veio do arquivo Word importado (autor, data e o trecho comentado). */
export interface ComentarioImportado {
  autor: string;
  comentado_em: string | null;
  comentario: string;
  trecho: string;
}

/**
 * Item de uma seção, com texto simples (conteudo) e formatado (conteudo_html), posição na árvore (pai_id, ordem),
 * marcador numerado calculado pela API, revisões e, no TR, a tabela de itens.
 */
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

/** Seção do documento com os itens em ordem. */
export interface SecaoDocumento {
  id: string;
  ordem: number;
  titulo: string;
  /** Orientação a quem preenche: só na tela (não vai para a cópia nem para o Word/PDF). */
  descricao: string;
  itens: ItemDocumento[];
}

/** Pessoa convidada para o documento, como editora ou revisora. */
export interface Membro {
  usuario_id: number;
  nome: string;
  login: string;
  papel: 'editor' | 'revisor';
}

/** Documento completo aberto na tela, com as permissões da pessoa logada, seções e membros. */
export interface DocumentoContratacao extends DocumentoResumo {
  pode_editar: boolean;
  pode_gerir: boolean;
  pode_revisar: boolean;
  secoes: SecaoDocumento[];
  membros: Membro[];
}

/** Resultado da conferência antes de concluir: bloqueios impedem a conclusão; alertas só avisam. */
export interface Conferencia {
  pode_concluir: boolean;
  bloqueios: string[];
  alertas: string[];
}

/** Números do painel de andamento no topo da lista (totais por situação e tipo, revisões abertas, sem contrato). */
export interface PainelContratacoes {
  total: number;
  por_situacao: Record<string, number>;
  por_tipo: Record<string, number>;
  revisoes_abertas: number;
  sem_vinculo: number;
}

/** Versão salva do documento na linha do tempo (número, tipo do evento, resumo e autor). */
export interface Versao {
  numero: number;
  tipo: string;
  tipo_rotulo: string;
  resumo: string;
  autor_nome: string;
  criada_em: string;
}

/** Versão com a "foto" completa do documento naquele momento (usada para visualizar e restaurar). */
export interface VersaoDetalhe extends Versao {
  foto: { nome: string; processo: string; situacao: string; secoes: { id: string; ordem: number; titulo: string }[]; itens: { id: string; secao_id: string; pai_id: string | null; tipo: TipoItem; ordem: number; conteudo: string; conteudo_html: string | null }[] };
}

/** O que aconteceu com um item entre duas versões; diferenca traz o HTML com o retirado e o incluído marcados. */
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

/** Comparação de uma versão com outra (contra): resumo, seções, itens e campos gerais que mudaram. */
export interface Alteracoes {
  versao: number;
  contra: number | null;
  resumo: Record<string, number>;
  secoes: { id: string; mudanca: string; titulo: string; titulo_antes?: string }[];
  itens: AlteracaoItem[];
  metadados: { campo: string; antes: string; depois: string }[];
}

/** Evento no histórico de um item (quem criou, editou, moveu, removeu ou restaurou), com antes e depois. */
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

/**
 * Prévia da importação de um arquivo Word: a estrutura que seria criada (com ids provisórios do cliente),
 * avisos e totais. sha256 é a impressão digital do arquivo enviado.
 */
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

/** Prévia de itens colados em lote: o tipo e a profundidade que cada linha vai ter na árvore. */
export interface PreviaLote {
  itens: { tipo: TipoItem; conteudo: string; profundidade: number }[];
}
