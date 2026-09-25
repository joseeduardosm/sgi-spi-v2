// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os itens da barra lateral do portal.

import { SecaoNavegacao } from './navegacao.model';

/**
 * Estrutura da barra lateral.
 *
 * Para publicar um novo módulo, acrescente um filho em `modulos` (ou um item próprio)
 * apontando para a rota criada em app.routes.ts, com `acl` igual ao slug do recurso:
 *
 *   { id: 'contratos', rotulo: 'Contratos', rota: '/contratos', acl: 'contratos' }
 */
export const NAVEGACAO: SecaoNavegacao[] = [
  {
    legenda: 'Navegação',
    itens: [
      { id: 'inicio', rotulo: 'Início', icone: 'inicio', rota: '/', exata: true },
      {
        id: 'modulos',
        rotulo: 'Módulos',
        icone: 'grade',
        filhos: [
          // Um item por módulo; as funções internas (painel, empresas, modelos) ficam nos atalhos do cabeçalho do módulo
          { id: 'contratos', rotulo: 'Contratos', rota: '/contratos', acl: 'contratos' },
        ],
        textoVazio: 'Nenhum módulo disponível ainda',
      },
      { id: 'usuarios', rotulo: 'Usuários', icone: 'usuarios', rota: '/usuarios', acl: 'usuarios' },
      { id: 'setores', rotulo: 'Setores', icone: 'organograma', rota: '/setores', acl: 'setores' },
    ],
  },
  {
    // Seção visível só para o SuperRoot
    legenda: 'Administração',
    papeis: ['SuperRoot'],
    itens: [
      { id: 'acl', rotulo: 'Controle de acesso', icone: 'escudo', rota: '/admin/acl' },
      { id: 'ldap', rotulo: 'Diretórios LDAP', icone: 'banco-dados', rota: '/admin/ldap' },
      // Links externos para a documentação interativa da API (abrem em nova aba)
      {
        id: 'api',
        rotulo: 'Documentação da API',
        icone: 'codigo',
        filhos: [
          { id: 'api-swagger', rotulo: 'Swagger (OpenAPI)', href: '/api/documentacao', novaAba: true },
          { id: 'api-redoc', rotulo: 'ReDoc', href: '/api/redoc', novaAba: true },
        ],
      },
    ],
  },
];

/** Com o perfil pendente, a navegação se resume à página de perfil. */
export const NAVEGACAO_RESTRITA: SecaoNavegacao[] = [
  {
    legenda: 'Cadastro pendente',
    itens: [{ id: 'perfil', rotulo: 'Meu perfil', icone: 'usuario', rota: '/perfil' }],
  },
];
