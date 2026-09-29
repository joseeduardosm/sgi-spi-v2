// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir o mapa de rotas (endereços) da aplicação e quem pode acessar cada uma.

import { Routes } from '@angular/router';

import { guardaAcl, guardaPerfil } from './core/acesso/acesso.guards';
import { guardaAutenticacao, guardaContaRoot, guardaPapel, guardaVisitante } from './core/autenticacao/autenticacao.guards';

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
        path: '',
        title: 'Início | SGI SPI',
        loadComponent: () => import('./features/inicio/inicio.component').then((m) => m.InicioComponent),
      },
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
        // Módulo RH: todo usuário autenticado (as telas de CGP e autorizador conferem o papel na API)
        path: 'rh',
        loadChildren: () => import('./features/rh/rh.routes').then((m) => m.ROTAS_RH),
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
