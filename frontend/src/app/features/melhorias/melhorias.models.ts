// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos e os rótulos do Módulo Melhorias (sugestões dos usuários e triagem).

export type SituacaoSugestao = 'nova' | 'em_analise' | 'aceita' | 'recusada' | 'concluida';

export const ROTULOS_SITUACAO: Record<SituacaoSugestao, string> = {
  nova: 'Nova',
  em_analise: 'Em análise',
  aceita: 'Aceita',
  recusada: 'Recusada',
  concluida: 'Concluída',
};

export const ROTULOS_MODULO: Record<string, string> = {
  contratos: 'Contratos',
  rh: 'RH',
  tarefas: 'Tarefas',
  noticias: 'Notícias',
  mensagens: 'Mensagens',
  melhorias: 'Melhorias',
  administracao: 'Administração',
  perfil: 'Meu perfil',
  portal: 'Portal',
  geral: 'Geral',
};

/** Máximos aceitos pela API. */
export const MAXIMO_TEXTO = 4000;
export const MAXIMO_PRINTS = 3;

export interface PrintSugestao {
  id: string;
  nome: string;
  tamanho: number;
  url: string;
}

/** O que o autor vê da própria sugestão. */
export interface SugestaoAutor {
  id: string;
  numero: number;
  texto: string;
  tela: string;
  modulo: string;
  situacao: SituacaoSugestao;
  resposta_publica: string;
  criado_em: string;
  atualizado_em: string | null;
  prints: PrintSugestao[];
}

export interface EventoSugestao {
  descricao: string;
  situacao_anterior: string;
  situacao_nova: string;
  autor_nome: string;
  criado_em: string;
}

/** Visão da triagem (com observação interna e histórico). */
export interface SugestaoTriagem extends SugestaoAutor {
  autor_id: number | null;
  autor_nome: string;
  autor_login: string;
  observacao_interna: string;
  atualizado_por_nome: string;
  tarefa_numero: number | null;
  eventos: EventoSugestao[];
}

export interface Pagina<T> {
  itens: T[];
  total: number;
  pagina: number;
  tamanho: number;
}

export interface PaginaTriagem extends Pagina<SugestaoTriagem> {
  totais: Record<SituacaoSugestao, number>;
  modulos: string[];
}

export interface FiltrosTriagem {
  busca: string;
  situacao: SituacaoSugestao | '';
  modulo: string;
  inicio: string;
  fim: string;
}

export interface Tratamento {
  situacao: SituacaoSugestao;
  resposta_publica: string;
  observacao_interna: string;
}

export interface ConversaoTarefa {
  titulo: string;
  prazo: string;
  prioridade: 'baixa' | 'normal' | 'alta' | 'critica';
  equipe_id: string | null;
  responsavel_id: number | null;
}

/** Módulo a partir da rota (espelha a regra da API, para mostrar ao usuário antes de enviar). */
export function moduloDaTela(tela: string): string {
  const caminho = tela.split('?')[0].split('#')[0].replace(/^\/+|\/+$/g, '');
  if (!caminho) return 'portal';
  const primeiro = caminho.split('/')[0];
  const mapa: Record<string, string> = {
    contratos: 'contratos', rh: 'rh', tarefas: 'tarefas', noticias: 'noticias', mensagens: 'mensagens', melhorias: 'melhorias',
    usuarios: 'administracao', setores: 'administracao', admin: 'administracao', perfil: 'perfil',
  };
  return mapa[primeiro] ?? 'geral';
}
