import { OrigemUsuario } from '../../core/modelos/usuario.model';

/** Contratos de /api/usuarios e /api/autenticacao/perfil (ver docs/endpoints/usuarios.md). */
export interface DadosPerfil {
  nome_completo: string;
  email: string;
  ramal: string;
  celular: string;
  cargo: string;
  departamento: string;
  andar: string;
  predio: string;
  data_nascimento: string | null;
  gestor_id: number | null;
}

export interface PerfilLeitura extends DadosPerfil {
  gestor_nome: string | null;
  perfil_revisado_em: string | null;
}

export interface DetalheUsuario {
  id: number;
  login: string;
  ativo: boolean;
  superusuario: boolean;
  origem: OrigemUsuario;
  possui_senha_local: boolean;
  diretorio_nome: string | null;
  id_externo: string | null;
  perfil: PerfilLeitura;
  perfil_completo: boolean;
  revisao_obrigatoria: boolean;
  setores: string[];
  ultimo_acesso_em: string | null;
  criado_em: string;
  atualizado_em: string;
}

export interface PaginaUsuarios {
  itens: DetalheUsuario[];
  total: number;
  pagina: number;
  tamanho_pagina: number;
}

export interface CriacaoUsuario {
  login: string;
  senha: string;
  ativo: boolean;
  superusuario: boolean;
  perfil: DadosPerfil;
}

export interface AlteracaoUsuario {
  senha: string | null;
  ativo: boolean;
  superusuario: boolean;
  perfil: DadosPerfil;
}

export const ROTULOS_PERFIL: Record<string, string> = {
  nome_completo: 'Nome completo',
  email: 'E-mail',
  ramal: 'Ramal',
  celular: 'Celular',
  cargo: 'Cargo',
  departamento: 'Departamento',
  andar: 'Andar',
  predio: 'Prédio',
  data_nascimento: 'Data de nascimento',
  gestor_id: 'Gestor imediato',
};

export const CAMPOS_OBRIGATORIOS_PERFIL = ['nome_completo', 'email', 'ramal', 'cargo', 'departamento', 'andar', 'predio'];
