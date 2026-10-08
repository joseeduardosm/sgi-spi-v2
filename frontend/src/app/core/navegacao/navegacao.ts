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
          // O clique abre o painel do módulo; o item fica ativo em qualquer tela sob /contratos
          { id: 'contratos', rotulo: 'Contratos', rota: '/contratos', destino: '/contratos/painel', acl: 'contratos' },
          // RH: férias e licença-prêmio para todos; painel, validações e parâmetros conforme o papel
          { id: 'rh', rotulo: 'RH', rota: '/rh', destino: '/rh/ferias' },
          // Tarefas: minhas tarefas, equipes e liderança
          // Notícias: gestão editorial do portal (a página inicial é o próprio portal)
          { id: 'noticias', rotulo: 'Notícias', rota: '/noticias/gestao', acl: 'noticias' },
          { id: 'tarefas', rotulo: 'Tarefas', rota: '/tarefas' },
          // Reserva de Espaços: agenda de salas e anfiteatro para todos; a fila e o painel aparecem só para fiscais
          { id: 'reserva-espacos', rotulo: 'Reserva de Espaços', rota: '/reserva-espacos' },
          // Manuais: instruções do BookStack lidas dentro do portal (ACL `manuais`; sem regras, todo usuário logado)
          { id: 'manuais', rotulo: 'Manuais', rota: '/manuais', acl: 'manuais' },
          // Melhorias: minhas sugestões para todos; triagem para quem tem CONTROLE_TOTAL em `melhorias`
          { id: 'melhorias', rotulo: 'Melhorias', rota: '/melhorias' },
          // Painel Executivo: gráficos de contratos, RH e tarefas para a Diretoria (acesso decidido pela API)
          { id: 'painel-executivo', rotulo: 'Painel Executivo', rota: '/painel-executivo', painelExecutivo: true },
          // Ramais: diretório em cartões de visita, para todos
          { id: 'ramais', rotulo: 'Ramais', rota: '/ramais' },
          // Protocolo: numeração institucional (ofícios, portarias, resoluções); aparece para quem tem o recurso ACL `protocolo`
          { id: 'protocolo', rotulo: 'Protocolo', rota: '/protocolo', acl: 'protocolo' },
          // Contratações: ETP e TR com revisão e versões; aparece para quem tem o recurso ACL `contratacoes`
          { id: 'contratacoes', rotulo: 'Contratações', rota: '/contratacoes', acl: 'contratacoes' },
        ],
        textoVazio: 'Nenhum módulo disponível ainda',
      },
      { id: 'mensagens', rotulo: 'Mensagens', icone: 'sino', rota: '/mensagens' },
      // Abrir Chamado: abre o modal que cria o chamado no GLPI (ACL `abrir-chamado`, sem regras: todos os usuários)
      { id: 'abrir-chamado', rotulo: 'Abrir Chamado', icone: 'ajuda', acao: 'abrir-chamado', acl: 'abrir-chamado' },
      { id: 'usuarios', rotulo: 'Usuários', icone: 'usuarios', rota: '/usuarios', acl: 'usuarios' },
      { id: 'setores', rotulo: 'Setores', icone: 'organograma', rota: '/setores', acl: 'setores' },
      // Documentação interativa da API (nova aba): visível a quem tem o recurso de ACL `documentacao-api` (nasce fechado)
      {
        id: 'api',
        rotulo: 'Documentação da API',
        icone: 'codigo',
        acl: 'documentacao-api',
        filhos: [
          { id: 'api-swagger', rotulo: 'Swagger (OpenAPI)', href: '/api/documentacao', novaAba: true },
          { id: 'api-redoc', rotulo: 'ReDoc', href: '/api/redoc', novaAba: true },
        ],
      },
      // Gerenciar atalhos fixos da barra lateral (ACL `atalhos`, recurso fechado: só quem o SuperRoot liberar)
      { id: 'gerenciar-atalhos', rotulo: 'Gerenciar atalhos', icone: 'alfinete', rota: '/admin/atalhos', acl: 'atalhos' },
      { id: 'sla-prazos', rotulo: 'SLA de prazos', icone: 'alfinete', rota: '/admin/sla', acl: 'sla' },
    ],
  },
  {
    // Seção visível só para o SuperRoot
    legenda: 'Administração',
    papeis: ['SuperRoot'],
    itens: [
      { id: 'acl', rotulo: 'Controle de acesso', icone: 'escudo', rota: '/admin/acl' },
      { id: 'ldap', rotulo: 'Diretórios LDAP', icone: 'banco-dados', rota: '/admin/ldap' },
      { id: 'smtp', rotulo: 'Servidores SMTP', icone: 'envelope', rota: '/admin/smtp' },
      { id: 'glpi', rotulo: 'Integração GLPI', icone: 'ajuda', rota: '/admin/glpi' },
      { id: 'bookstack', rotulo: 'Integração BookStack', icone: 'arquivo', rota: '/admin/bookstack' },
      // Mensageria (e-mail de changelog): só a conta root
      { id: 'mensageria', rotulo: 'Mensageria', icone: 'megafone', rota: '/admin/mensageria', somenteRoot: true },
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
