// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos de dados da API de diretórios LDAP.

/** Contratos de /api/ldap/diretorios (ver docs/endpoints/ldap.md). */
export interface DiretorioLdap {
  id: string;
  nome: string;
  servidor: string;
  porta: number;
  usar_ssl: boolean;
  base_dn: string;
  bind_dn: string;
  ativo: boolean;
  ultimo_teste_em: string | null;
  ultimo_teste_ok: boolean | null;
  ultima_latencia_ms: number | null;
  ultimo_erro: string | null;
  ultima_sincronizacao_em: string | null;
  ultima_sincronizacao_ok: boolean | null;
  ultima_sincronizacao_mensagem: string | null;
  criado_em: string;
  atualizado_em: string;
}

/** Corpo para cadastrar ou alterar um diretório. */
export interface GravacaoDiretorio {
  nome: string;
  servidor: string;
  porta: number;
  usar_ssl: boolean;
  base_dn: string;
  bind_dn: string;
  senha_bind: string | null;
  ativo: boolean;
}

/** Resultado de um teste de conexão. */
export interface ResultadoTeste {
  sucesso: boolean;
  latencia_ms: number;
  mensagem: string;
}

/** Resumo de uma sincronização de usuários. */
export interface ResultadoSincronizacao {
  encontrados: number;
  criados: number;
  atualizados: number;
  desativados: number;
  ignorados: number;
  sincronizado_em: string;
}
