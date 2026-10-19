// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos do usuário usados em várias partes do frontend.

/** Papéis conhecidos pela aplicação. Novos papéis devem ser adicionados aqui e na API. */
export type Papel = 'SuperRoot';

/** Como a conta autentica: senha local, AD (LDAP) ou as duas. */
export type OrigemUsuario = 'local' | 'ldap' | 'local_ldap';

/** Perfil de acesso do usuário (aparece no menu do usuário). */
export interface PerfilSessao {
  id: number;
  nome: string;
}

/** SuperRoot que está personificando o usuário da sessão. */
export interface PersonificadorSessao {
  id: number;
  login: string;
  nome_completo: string;
}

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
  /** Conta administrativa principal (login root): única com acesso às Notificações do sistema. */
  conta_root?: boolean;
  /** Tema da interface escolhido pelo usuário (`auto` segue o sistema operacional). */
  tema?: 'claro' | 'escuro' | 'auto';
  /** Perfis ativos do usuário (para alternar no menu do usuário) e o que vale agora. */
  perfis?: PerfilSessao[];
  perfil_ativo?: PerfilSessao | null;
  /** Preenchido quando um SuperRoot está personificando este usuário. */
  personificado_por?: PersonificadorSessao | null;
}

/** Forma reduzida usada em seletores (`OpcaoUsuario` da API). */
export interface OpcaoUsuario {
  id: number;
  login: string;
  nome_completo: string;
  cargo: string;
  ativo: boolean;
}

/** Textos exibidos para cada origem de conta. */
export const ROTULOS_ORIGEM: Record<OrigemUsuario, string> = {
  local: 'Local',
  ldap: 'LDAP',
  local_ldap: 'Local + LDAP',
};
