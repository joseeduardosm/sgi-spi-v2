// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir o mapa de rotas (endereços) da aplicação e quem pode acessar cada uma.

import { inject } from '@angular/core';
import { Routes } from '@angular/router';

import { guardaAcl, guardaPainelExecutivo, guardaPerfil } from './core/acesso/acesso.guards';
import { guardaAutenticacao, guardaContaRoot, guardaPapel, guardaVisitante } from './core/autenticacao/autenticacao.guards';
import { AutenticacaoService } from './core/autenticacao/autenticacao.service';

/**
 * Mapa de rotas do portal.
 *
 * - `loadComponent`/`loadChildren` carregam o código da tela só quando ela é aberta (lazy loading),
 *   deixando a primeira carga mais leve.
 * - `canActivate` recebe as guardas: funções que decidem se a navegação pode continuar
 *   (usuário logado, perfil em dia, ACL do módulo, papel SuperRoot).
 * - `title` é o texto da aba do navegador.
 */
export const rotas: Routes = [
  {
    // Tela de login, dentro do layout público; `guardaVisitante` manda quem já está logado para o início
    path: 'login',
    loadComponent: () =>
      import('./shared/layout/layout-publico/layout-publico.component').then((m) => m.LayoutPublicoComponent),
    canActivate: [guardaVisitante],
    children: [
      {
        path: '',
        title: 'Entrar | SGI SPI',
        loadComponent: () => import('./features/auth/login/login.component').then((m) => m.LoginComponent),
      },
    ],
  },
  {
    // Portal de notícias para visitantes (sem login): página inicial, arquivo e notícia, no layout público do portal.
    // Quem está logado não passa por aqui (`canMatch`) e vê as mesmas telas dentro do layout com barra lateral.
    path: '',
    canMatch: [() => !inject(AutenticacaoService).autenticado()],
    loadComponent: () => import('./shared/layout/layout-portal/layout-portal.component').then((m) => m.LayoutPortalComponent),
    children: [
      { path: '', pathMatch: 'full', title: 'Notícias | SGI SPI', loadComponent: () => import('./features/noticias/publico/portal.component').then((m) => m.PortalComponent) },
      // A gestão exige login: o visitante vai para a tela de entrada e volta depois
      { path: 'noticias/gestao', canActivate: [guardaAutenticacao], children: [] },
      { path: 'noticias/gestao/**', canActivate: [guardaAutenticacao], children: [] },
      { path: 'noticias', title: 'Todas as notícias | SGI SPI', loadComponent: () => import('./features/noticias/publico/arquivo-noticias.component').then((m) => m.ArquivoNoticiasComponent) },
      { path: 'noticias/:slug', title: 'Notícia | SGI SPI', loadComponent: () => import('./features/noticias/publico/noticia.component').then((m) => m.NoticiaComponent) },
      // Qualquer outra página exige login
      { path: '**', canActivate: [guardaAutenticacao], children: [] },
    ],
  },
  {
    // Rotas autenticadas, exibidas dentro do layout com barra lateral.
    // Cada módulo novo entra como filho desta rota e ganha um item em core/navegacao/navegacao.ts.
    path: '',
    loadComponent: () =>
      import('./shared/layout/layout-autenticado/layout-autenticado.component').then((m) => m.LayoutAutenticadoComponent),
    canActivate: [guardaAutenticacao],
    // Com o perfil pendente, só /perfil fica acessível
    canActivateChild: [guardaPerfil],
    children: [
      {
        // Página inicial: o portal de notícias (o mesmo que o visitante vê, aqui com a barra lateral)
        path: '',
        pathMatch: 'full',
        title: 'Início | SGI SPI',
        loadComponent: () => import('./features/noticias/publico/portal.component').then((m) => m.PortalComponent),
      },
      {
        // Gestão de notícias: a API confere o papel (redator ou aprovador) na ACL `noticias`
        path: 'noticias/gestao',
        loadChildren: () => import('./features/noticias/noticias.routes').then((m) => m.ROTAS_GESTAO_NOTICIAS),
      },
      { path: 'noticias', title: 'Todas as notícias | SGI SPI', loadComponent: () => import('./features/noticias/publico/arquivo-noticias.component').then((m) => m.ArquivoNoticiasComponent) },
      { path: 'noticias/:slug', title: 'Notícia | SGI SPI', loadComponent: () => import('./features/noticias/publico/noticia.component').then((m) => m.NoticiaComponent) },
      {
        // Caixa de mensagens: todo usuário autenticado (sem ACL)
        path: 'mensagens',
        title: 'Caixa de mensagens | SGI SPI',
        loadComponent: () => import('./features/mensagens/mensagens.component').then((m) => m.MensagensComponent),
      },
      {
        path: 'perfil',
        title: 'Meu perfil | SGI SPI',
        loadComponent: () => import('./features/perfil/perfil.component').then((m) => m.PerfilComponent),
      },
      // Módulos protegidos pela ACL: `data.acl` informa o slug do recurso conferido por `guardaAcl`
      {
        path: 'usuarios',
        title: 'Usuários | SGI SPI',
        canActivate: [guardaAcl],
        data: { acl: 'usuarios' },
        loadComponent: () => import('./features/usuarios/usuarios.component').then((m) => m.UsuariosComponent),
      },
      {
        // Página do usuário: `novo` (conta local) ou o id (edição)
        path: 'usuarios/:id',
        title: 'Usuário | SGI SPI',
        canActivate: [guardaAcl],
        data: { acl: 'usuarios' },
        loadComponent: () => import('./features/usuarios/usuario-edicao.component').then((m) => m.UsuarioEdicaoComponent),
      },
      {
        path: 'setores',
        title: 'Setores | SGI SPI',
        canActivate: [guardaAcl],
        data: { acl: 'setores' },
        loadComponent: () => import('./features/setores/setores.component').then((m) => m.SetoresComponent),
      },
      {
        // Assinatura de e-mail institucional: todo usuário autenticado (os dados vêm do perfil em vigor)
        path: 'assinatura-email',
        title: 'Assinatura de e-mail | SGI SPI',
        loadComponent: () => import('./features/assinatura/assinatura-email.component').then((m) => m.AssinaturaEmailComponent),
      },
      {
        // Módulo RH: todo usuário autenticado (as telas de CGP e autorizador conferem o papel na API)
        path: 'rh',
        loadChildren: () => import('./features/rh/rh.routes').then((m) => m.ROTAS_RH),
      },
      {
        // Módulo Protocolo: numeração institucional; cada rota confere o recurso ACL `protocolo` e a API confere em toda ação
        path: 'protocolo',
        loadChildren: () => import('./features/protocolo/protocolo.routes').then((m) => m.ROTAS_PROTOCOLO),
      },
      {
        // Módulo Contratações (ETP e TR): cada rota confere o recurso ACL `contratacoes`; o papel em cada documento é conferido pela API
        path: 'contratacoes',
        loadChildren: () => import('./features/contratacoes/contratacoes.routes').then((m) => m.ROTAS_CONTRATACOES),
      },
      {
        // Painel Executivo: slides de contratos, RH e tarefas; a guarda consulta a API (sem regras na ACL, só o SuperRoot)
        path: 'painel-executivo',
        canActivate: [guardaPainelExecutivo],
        title: 'Painel Executivo | SGI SPI',
        loadComponent: () => import('./features/painel-executivo/pagina-painel-executivo.component').then((m) => m.PaginaPainelExecutivoComponent),
      },
      {
        // Diretório de ramais (cartões de visita): todo usuário autenticado
        path: 'ramais',
        loadChildren: () => import('./features/diretorio/diretorio.routes').then((m) => m.ROTAS_DIRETORIO),
      },
      {
        // Módulo Melhorias: todo usuário vê as próprias sugestões; a triagem confere o acesso na API (ACL `melhorias`)
        path: 'melhorias',
        loadChildren: () => import('./features/melhorias/melhorias.routes').then((m) => m.ROTAS_MELHORIAS),
      },
      {
        // Módulo Tarefas: todo usuário autenticado (a API confere o papel em cada tarefa e equipe)
        path: 'tarefas',
        loadChildren: () => import('./features/tarefas/tarefas.routes').then((m) => m.ROTAS_TAREFAS),
      },
      {
        // Módulo de contratos: todas as telas exigem ACL `contratos` (a API valida o nível de cada ação)
        path: 'contratos',
        canActivate: [guardaAcl],
        data: { acl: 'contratos' },
        loadChildren: () => import('./features/contratos/contratos.routes').then((m) => m.ROTAS_CONTRATOS),
      },
      // Administração: só para o papel SuperRoot
      {
        path: 'admin/acl',
        title: 'Controle de acesso | SGI SPI',
        canActivate: [guardaPapel],
        data: { papeis: ['SuperRoot'] },
        loadComponent: () => import('./features/administracao/acl/acl.component').then((m) => m.AclComponent),
      },
      {
        path: 'admin/ldap',
        title: 'Diretórios LDAP | SGI SPI',
        canActivate: [guardaPapel],
        data: { papeis: ['SuperRoot'] },
        loadComponent: () =>
          import('./features/administracao/ldap/diretorios-ldap.component').then((m) => m.DiretoriosLdapComponent),
      },
      {
        path: 'admin/smtp',
        title: 'Servidores SMTP | SGI SPI',
        canActivate: [guardaPapel],
        data: { papeis: ['SuperRoot'] },
        loadComponent: () =>
          import('./features/administracao/smtp/servidores-smtp.component').then((m) => m.ServidoresSmtpComponent),
      },
      {
        path: 'admin/glpi',
        title: 'Integração GLPI | SGI SPI',
        canActivate: [guardaPapel],
        data: { papeis: ['SuperRoot'] },
        loadComponent: () =>
          import('./features/administracao/glpi/integracao-glpi.component').then((m) => m.IntegracaoGlpiComponent),
      },
      {
        // Mensageria (e-mail de changelog): exclusiva da conta root
        path: 'admin/mensageria',
        title: 'Mensageria | SGI SPI',
        canActivate: [guardaContaRoot],
        loadComponent: () =>
          import('./features/administracao/mensageria/mensageria.component').then((m) => m.MensageriaComponent),
      },
    ],
  },
  // Qualquer endereço desconhecido volta para o início
  { path: '**', redirectTo: '' },
];
