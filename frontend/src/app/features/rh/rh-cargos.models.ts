// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos de dados de cargos, ocupações, organograma e histórico funcional do Módulo RH.

/** Tipo de cargo (CCESP, FCESP, OUTRO...). */
export interface TipoCargo { id: number; codigo: string; nome: string; ordem: number; ativo: boolean }

export interface OcupanteCargo { usuario_id: number; nome: string; login: string; inicio: string | null; ato: string; tem_foto: boolean; foto_url: string | null }

/** Uma posição (vaga) de um setor, com o ocupante vigente. */
export interface Cargo {
  id: number; setor_id: number; setor_nome: string; tipo_id: number; tipo_codigo: string; grupo: number | null; nivel: number | null; denominacao: string;
  classificacao: string; rotulo: string; ativo: boolean; ocupante: OcupanteCargo | null;
  /** Só na resposta de vagar: a ocupação encerrada (abre a tela da exoneração). */
  ocupacao_encerrada_id?: number | null;
}

export interface GravacaoCargo {
  setor_id: number; tipo_id: number; grupo: 1 | 2 | null; nivel: number | null; denominacao: string; quantidade: number; ativo: boolean;
}

export type MotivoFim = 'troca' | 'exoneracao' | 'dispensa' | 'outro';
export const ROTULOS_MOTIVO_FIM: Record<MotivoFim, string> = { troca: 'Troca de cargo', exoneracao: 'Exoneração', dispensa: 'Dispensa', outro: 'Outro motivo' };

export interface PendenciaCargo {
  usuario_id: number; nome: string; login: string; cargo_texto: string; departamento_texto: string; interpretado: boolean; sugestao: string | null; setor_id: number | null;
}

/** Líder da unidade: foto, nome e cargo. */
export interface LiderSetor { usuario_id: number; nome: string; cargo: string; foto_url: string | null }

/** Unidade do organograma. */
export interface NoOrganograma {
  setor_id: number; nome: string; sigla: string | null; tipo_unidade: string | null; lider_nome: string | null; lider: LiderSetor | null; total_posicoes: number; total_vagas: number;
  posicoes: Cargo[]; filhos: NoOrganograma[];
}

export interface OcupacaoHistorico {
  id: number; cargo_id: number; cargo_rotulo: string; setor_id: number; setor_nome: string; inicio: string | null; fim: string | null; ato: string; motivo_fim: string | null;
  ato_fim: string; registrado_por_nome: string; registrado_em: string;
}

export interface EventoHistorico { id: number; tipo: string; titulo: string; detalhe: string; ocorrido_em: string; autor_nome: string; sigiloso: boolean }

export interface HistoricoUsuario {
  usuario_id: number; nome: string; login: string; cargo_atual: string; setor_atual: string; ocupacoes: OcupacaoHistorico[]; eventos: EventoHistorico[]; tipos: Record<string, string>;
}

/** Chamados da exoneração: o inverso da nomeação (desativar a rede, recolher o crachá...). */
export interface LinkChamadoExoneracao { url: string; texto: string; chave: string | null; numero: number | null; status_nome: string | null; status_cor: string | null }
export interface LeituraExoneracao {
  ocupacao_id: number; usuario_id: number; nome: string; login: string; cargo_rotulo: string; setor_nome: string; fim: string | null; ato_fim: string;
  destino: 'glpi' | 'chamados'; servicos: Record<string, string>; sugestao: Record<string, boolean>; sugestao_da_nomeacao: boolean; chamados: LinkChamadoExoneracao[];
}
