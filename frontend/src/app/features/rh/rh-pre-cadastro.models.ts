// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos de dados da ficha de pré-cadastro do RH.

export type StatusFicha = 'rascunho' | 'aguardando_conta' | 'vinculado' | 'cancelado';

export const ROTULOS_STATUS_FICHA: Record<StatusFicha, string> = { rascunho: 'Rascunho', aguardando_conta: 'Aguardando a conta', vinculado: 'Vinculada', cancelado: 'Cancelada' };

export interface Formacao { nivel: string; curso: string; instituicao: string; ano_conclusao: number | null; em_andamento: boolean }
export interface Experiencia { empresa: string; cargo: string; inicio: string | null; fim: string | null; descricao: string }

/** Campos de texto e data da ficha (iguais na leitura e na gravação). */
export interface CamposFicha {
  nome_completo: string; nome_social: string; data_nascimento: string | null; sexo: string; estado_civil: string; nacionalidade: string; naturalidade_cidade: string;
  naturalidade_uf: string; nome_mae: string; nome_pai: string;
  cpf: string; rg_numero: string; rg_orgao: string; rg_uf: string; rg_emissao: string | null; cin: string; pis_pasep: string; titulo_numero: string; titulo_zona: string;
  titulo_secao: string; ctps_numero: string; ctps_serie: string; ctps_uf: string; cnh: string;
  email_pessoal: string; telefone: string; celular: string; emergencia_nome: string; emergencia_parentesco: string; emergencia_telefone: string;
  cep: string; logradouro: string; numero: string; complemento: string; bairro: string; cidade: string; uf: string;
  vinculo_tipo: string; orgao_origem: string; cargo_origem: string; rs_pv: string; inicio_previsto: string | null; cargo_id: number | null; observacoes: string;
}

export interface GravacaoFicha extends CamposFicha {
  login_proposto: string | null; status: 'rascunho' | 'aguardando_conta'; formacoes: Formacao[]; experiencias: Experiencia[];
}

export interface LeituraFicha extends CamposFicha {
  id: number; status: StatusFicha; login_proposto: string | null; usuario_id: number | null; usuario_nome: string | null; vinculado_em: string | null; enviada_em: string | null; validado_em: string | null; cargo_rotulo: string | null;
  criado_em: string; atualizado_em: string; formacoes: Formacao[]; experiencias: Experiencia[];
}

export interface ResumoFicha {
  id: number; nome_completo: string; status: StatusFicha; login_proposto: string | null; usuario_id: number | null; cargo_rotulo: string | null; inicio_previsto: string | null; enviada_em: string | null; validado_em: string | null; atualizado_em: string;
}

export interface LoginDisponivel { login: string; disponivel: boolean; verificado_no_ad: boolean; motivo: 'livre' | 'formato' | 'usuario' | 'ficha' | 'ad' | 'ad_indisponivel'; detalhe: string }

/** Ficha em branco para o formulário de nova ficha. */
export function fichaVazia(): GravacaoFicha {
  return {
    nome_completo: '', nome_social: '', data_nascimento: null, sexo: '', estado_civil: '', nacionalidade: 'Brasileira', naturalidade_cidade: '', naturalidade_uf: '', nome_mae: '', nome_pai: '',
    cpf: '', rg_numero: '', rg_orgao: '', rg_uf: '', rg_emissao: null, cin: '', pis_pasep: '', titulo_numero: '', titulo_zona: '', titulo_secao: '', ctps_numero: '', ctps_serie: '', ctps_uf: '', cnh: '',
    email_pessoal: '', telefone: '', celular: '', emergencia_nome: '', emergencia_parentesco: '', emergencia_telefone: '',
    cep: '', logradouro: '', numero: '', complemento: '', bairro: '', cidade: '', uf: '',
    vinculo_tipo: '', orgao_origem: '', cargo_origem: '', rs_pv: '', inicio_previsto: null, cargo_id: null, observacoes: '',
    login_proposto: null, status: 'rascunho', formacoes: [], experiencias: [],
  };
}

export interface LinhaImportacaoFicha { linha: number; nome: string; cpf: string; login_proposto: string; cargo_pretendido: string; erros: string[]; ficha_id: number | null }
export interface ResultadoImportacaoFichas { total: number; com_erro: number; gravado: boolean; linhas: LinhaImportacaoFicha[] }
