/** Papéis conhecidos pela aplicação. Novos papéis devem ser adicionados aqui e na API. */
export type Papel = 'SuperRoot';

export type OrigemUsuario = 'local' | 'ldap' | 'local_ldap';

/** Usuário da sessão (`UsuarioSessao` da API). */
export interface Usuario {
  id: number;
  login: string;
  nome_completo: string;
  papeis: Papel[];
  origem: OrigemUsuario;
  /** Perfil incompleto ou revalidação vencida: acesso restrito ao próprio perfil. */
  perfil_restrito?: boolean;
  campos_pendentes?: string[];
  revisao_obrigatoria?: boolean;
}

/** Forma reduzida usada em seletores (`OpcaoUsuario` da API). */
export interface OpcaoUsuario {
  id: number;
  login: string;
  nome_completo: string;
  cargo: string;
  ativo: boolean;
}

export const ROTULOS_ORIGEM: Record<OrigemUsuario, string> = {
  local: 'Local',
  ldap: 'LDAP',
  local_ldap: 'Local + LDAP',
};
