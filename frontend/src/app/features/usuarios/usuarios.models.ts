// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos de dados da API de usuários e do perfil institucional.

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

/** Perfil devolvido pela API (com o nome do gestor e a data da última revalidação). */
/** Setor oferecido no combobox "Departamento" (GET /api/autenticacao/perfil/opcoes-departamento). */
export interface OpcaoDepartamento {
  id: number;
  nome: string;
  /** Profundidade na hierarquia (0 = raiz). */
  nivel: number;
}

export interface PerfilLeitura extends DadosPerfil {
  gestor_nome: string | null;
  perfil_revisado_em: string | null;
}

/** Usuário completo, como aparece na administração. */
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

/** Uma página da listagem, com o total para a paginação. */
export interface PaginaUsuarios {
  itens: DetalheUsuario[];
  total: number;
  pagina: number;
  tamanho_pagina: number;
}

/** Corpo para criar uma conta local. */
export interface CriacaoUsuario {
  login: string;
  senha: string;
  ativo: boolean;
  superusuario: boolean;
  perfil: DadosPerfil;
}

/** Corpo para alterar um usuário (senha nula mantém a atual). */
export interface AlteracaoUsuario {
  senha: string | null;
  ativo: boolean;
  superusuario: boolean;
  perfil: DadosPerfil;
}

/** Nomes legíveis dos campos do perfil (usados em mensagens de pendência). */
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

/** Campos que precisam estar preenchidos para o perfil ficar "em dia". */
export const CAMPOS_OBRIGATORIOS_PERFIL = ['nome_completo', 'email', 'ramal', 'cargo', 'departamento', 'andar', 'predio'];
