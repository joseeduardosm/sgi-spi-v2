// Criado por José Eduardo Santana Martins
// Este arquivo serve para tipar os dados do módulo Patrimônio (espelham os schemas de /api/patrimonio).

export type SituacaoBem = 'ativo' | 'em_manutencao' | 'inservivel' | 'extraviado' | 'baixado';
export type OrigemBem = 'proprio' | 'terceiros';
export type GarantiaBem = 'indefinida' | 'vigente' | 'vencida';
export type Agrupamento = 'andar' | 'sala' | 'setor' | 'grupo';
export type MotivoBaixa = 'alienacao' | 'doacao' | 'transferencia' | 'inutilizacao' | 'extravio';

export const ROTULOS_SITUACAO: Record<SituacaoBem, string> = { ativo: 'Ativo', em_manutencao: 'Em manutenção', inservivel: 'Inservível', extraviado: 'Extraviado', baixado: 'Baixado' };
export const ROTULOS_GARANTIA: Record<GarantiaBem, string> = { indefinida: 'Indefinida', vigente: 'Vigente', vencida: 'Vencida' };
export const ROTULOS_CONSERVACAO: Record<number, string> = { 1: 'Péssimo', 2: 'Ruim', 3: 'Regular', 4: 'Bom', 5: 'Ótimo' };
export const ROTULOS_MOTIVO_BAIXA: Record<MotivoBaixa, string> = { alienacao: 'Alienação', doacao: 'Doação', transferencia: 'Transferência', inutilizacao: 'Inutilização', extravio: 'Extravio' };
/** Categorias do bem inservível (classificação do desfazimento, Decreto 9.373/2018): rótulo e resumo. */
export type CategoriaInservivel = 'ocioso' | 'recuperavel' | 'antieconomico' | 'irrecuperavel';
export const CATEGORIAS_INSERVIVEL: { codigo: CategoriaInservivel; rotulo: string; descricao: string }[] = [
  { codigo: 'ocioso', rotulo: 'Ocioso', descricao: 'Em perfeitas condições de uso, mas não está sendo aproveitado.' },
  { codigo: 'recuperavel', rotulo: 'Recuperável', descricao: 'Não está em condições de uso, mas a recuperação é possível e o custo não passa de 50% do valor de mercado.' },
  { codigo: 'antieconomico', rotulo: 'Antieconômico', descricao: 'Manutenção onerosa ou rendimento precário (uso prolongado, desgaste ou obsolescência); recuperar custa mais de 50% do valor de mercado.' },
  { codigo: 'irrecuperavel', rotulo: 'Irrecuperável', descricao: 'Não pode mais ser usado para o fim a que se destina, por perda das características ou inviabilidade econômica de recuperação.' },
];
/** Rótulo curto da categoria (vazio se não houver). */
export function rotuloCategoria(codigo: string | null | undefined): string {
  return CATEGORIAS_INSERVIVEL.find((c) => c.codigo === codigo)?.rotulo ?? '';
}

export const ROTULOS_STATUS: Record<string, string> = {
  pendente: 'Pendente', autorizada: 'Autorizada', concluida: 'Concluída', recusada: 'Recusada', cancelada: 'Cancelada', rascunho: 'Rascunho', aprovada: 'Aprovada', parcial: 'Aprovada em parte',
};
/** Cor (índice da paleta dos marcadores de Tarefas) de cada situação do bem e de cada status. */
export const COR_SITUACAO: Record<SituacaoBem, number> = { ativo: 10, em_manutencao: 3, inservivel: 2, extraviado: 1, baixado: 0 };
export const COR_STATUS: Record<string, number> = { pendente: 3, autorizada: 4, concluida: 10, recusada: 1, cancelada: 0, rascunho: 0, aprovada: 10, parcial: 3 };

export interface AcessoPatrimonio { usuario_id: number; pode_operar: boolean; pode_administrar: boolean }

export interface Localizacao {
  id: string; pai_id: string | null; tipo: 'predio' | 'andar' | 'lado' | 'sala' | 'reservado'; nome: string; codigo: string | null; rotulo: string;
  andar: number | null; lado: string | null; setor_id: number | null; setor_nome: string | null; responsavel_id: number | null; responsavel_nome: string | null;
  deposito_inservivel: boolean; ativo: boolean; total_bens: number;
}

/** Prefixo que vem antes do número da chapa (SPI, SLT...). */
export interface PrefixoChapa { id: string; codigo: string; padrao: boolean; ativo: boolean }

export interface Grupo { id: string; codigo: string; nome: string; vida_util_meses: number | null; residual_percentual: string; deprecia: boolean; ativo: boolean }

export interface Bem {
  id: string; chapa: string | null; rotulo: string; descricao: string; localizacao_id: string; sala_codigo: string | null; sala_rotulo: string; andar: number | null; setor_nome: string | null;
  responsavel_id: number | null; responsavel_nome: string | null; conservacao: number; situacao: SituacaoBem; origem: OrigemBem; grupo_id: string | null; grupo_nome: string | null;
  uge: string | null; ua: string | null; divisao: string | null; valor_aquisicao: string | null; valor_atual: string | null; valor_efetivo: string | null;
  data_aquisicao: string | null; garantia_meses: number | null; garantia_fim: string | null; situacao_garantia: GarantiaBem; vence_em_90_dias: boolean;
  marca: string | null; modelo: string | null; numero_serie: string | null; nota_fiscal: string | null; fornecedor: string | null; observacoes: string | null;
  criado_por_nome: string | null; classificacao_pendente: boolean; categoria_inservivel?: CategoriaInservivel | null; em_movimentacao: boolean; dados_contabeis_pendentes: boolean; fotos: { id: string; nome: string }[]; avisos: string[];
  criado_em: string; atualizado_em: string; baixado_em: string | null;
}
export interface ListaBens { total: number; pagina: number; itens: Bem[] }

/** Corpo do cadastro; `id_cliente` identifica o envio feito no aparelho (o reenvio offline não duplica). */
export interface DadosBem {
  /** Prefixo da chapa: com ele, `chapa` é só o número e o servidor junta (SPI + 231 = SPI000231). */
  prefixo?: string | null;
  id_cliente?: string; chapa: string | null; descricao: string; localizacao_id: string; conservacao: number; situacao: 'ativo' | 'em_manutencao'; origem: OrigemBem;
  grupo_id?: string | null; uge?: string | null; ua?: string | null; divisao?: string | null; valor_aquisicao?: string | null; valor_atual?: string | null;
  data_aquisicao?: string | null; garantia_meses?: number | null; marca?: string | null; modelo?: string | null; numero_serie?: string | null;
  nota_fiscal?: string | null; fornecedor?: string | null; observacoes?: string | null;
}

export interface Evento {
  id: string; tipo: string; campo: string | null; valor_anterior: string | null; valor_novo: string | null; autor_nome: string; origem: string | null; texto: string;
  dados: Record<string, unknown> | null; ocorrido_em: string;
}

export interface ItemMovimentacao { bem_id: string; chapa: string | null; numero_serie: string | null; rotulo: string; descricao: string; origem_codigo: string | null; origem_rotulo: string; recebido_em: string | null }
export interface Movimentacao {
  id: string; status: string; destino_id: string; destino_codigo: string | null; destino_rotulo: string; motivo: string; solicitante_id: number | null; solicitante_nome: string;
  solicitada_em: string; decidido_por_nome: string | null; decidido_em: string | null; motivo_recusa: string | null; concluida_em: string | null; itens: ItemMovimentacao[];
}

export interface ItemClassificacao {
  id: string; bem_id: string; chapa: string | null; numero_serie: string | null; rotulo: string; descricao: string; sala_rotulo: string; situacao_anterior: string | null; justificativa: string | null; categoria?: CategoriaInservivel | null; anexo_nome: string | null;
  /** Informações do bem, para pesquisar dentro da lista. */
  marca?: string | null; modelo?: string | null; grupo_nome?: string | null; responsavel_nome?: string | null; nota_fiscal?: string | null; fornecedor?: string | null; observacoes?: string | null;
  resultado: 'aprovado' | 'recusado' | null;
}
export interface Classificacao {
  id: string; numero: number; tipo: 'inservivel' | 'extraviado'; status: string; solicitante_id: number | null; solicitante_nome: string; criada_em: string; enviada_em: string | null;
  decidido_por_nome: string | null; decidido_em: string | null; motivo_recusa: string | null; itens: ItemClassificacao[];
  /** Pessoas com quem a lista foi compartilhada (fazem tudo o que o solicitante faz, menos aprová-la). */
  colaboradores?: { id: number; nome: string }[];
}

export interface ItemBaixa {
  id: string; bem_id: string; chapa: string | null; numero_serie: string | null; rotulo: string; descricao: string; situacao_anterior: string | null; valor_aquisicao: string | null; motivo: MotivoBaixa | null; processo: string | null;
  resultado: 'aprovado' | 'recusado' | null;
}
export interface Baixa {
  id: string; numero: number; status: string; solicitante_id: number | null; solicitante_nome: string; criada_em: string; enviada_em: string | null; decidido_por_nome: string | null;
  decidido_em: string | null; motivo_recusa: string | null; tem_termo: boolean; itens: ItemBaixa[];
  /** Pessoas com quem a baixa foi compartilhada (fazem tudo o que o solicitante faz, menos aprová-la). */
  colaboradores?: { id: number; nome: string }[];
}

export interface IndicadoresPatrimonio {
  total_bens: number; valor_aquisicao: string; valor_atual: string; fora_garantia: number; aguardando_baixa: number; solicitacoes_pendentes: number;
  dados_contabeis_pendentes: number; movimentacoes_em_aberto: number;
}
export interface LinhaGarantia { id: string; chapa: string | null; rotulo: string; descricao: string; sala: string; fim_garantia: string | null; dias: number | null; vence_em_90_dias: boolean }
export interface PainelPatrimonio {
  indicadores: IndicadoresPatrimonio; agrupar_por: Agrupamento; grupos: { chave: string; rotulo: string; quantidade: number; valor: string }[];
  fora_garantia: LinhaGarantia[]; vencendo_90_dias: LinhaGarantia[]; contabeis_pendentes: { id: string; chapa: string | null; rotulo: string; descricao: string; sala: string }[];
}

/** Filtros da lista de bens (viram parâmetros da consulta e da URL). */
export interface FiltrosBens {
  q?: string; situacao?: SituacaoBem | ''; localizacao_id?: string; grupo_id?: string; conservacao?: number | ''; garantia?: GarantiaBem | ''; contabeis_pendentes?: boolean; pagina?: number; tamanho?: number;
  /** Coluna e sentido da ordenação (feita no servidor, vale para todas as páginas). */
  ordenar_por?: string; direcao?: 'asc' | 'desc';
}
