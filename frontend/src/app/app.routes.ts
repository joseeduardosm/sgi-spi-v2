import { Routes } from '@angular/router';

import { guardaAcl, guardaPerfil } from './core/acesso/acesso.guards';
import { guardaAutenticacao, guardaPapel, guardaVisitante } from './core/autenticacao/autenticacao.guards';

export const rotas: Routes = [
  {
    path: 'login',
    loadComponent: () =>
      import('./shared/layout/layout-publico/layout-publico.component').then((m) => m.LayoutPublicoComponent),
    canActivate: [guardaVisitante],
    children: [
      {
        path: '',
        title: 'Entrar | Contratos SPI',
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
        title: 'Início | Contratos SPI',
        loadComponent: () => import('./features/inicio/inicio.component').then((m) => m.InicioComponent),
      },
      {
        path: 'perfil',
        title: 'Meu perfil | Contratos SPI',
        loadComponent: () => import('./features/perfil/perfil.component').then((m) => m.PerfilComponent),
      },
      {
        path: 'usuarios',
        title: 'Usuários | Contratos SPI',
        canActivate: [guardaAcl],
        data: { acl: 'usuarios' },
        loadComponent: () => import('./features/usuarios/usuarios.component').then((m) => m.UsuariosComponent),
      },
      {
        path: 'setores',
        title: 'Setores | Contratos SPI',
        canActivate: [guardaAcl],
        data: { acl: 'setores' },
        loadComponent: () => import('./features/setores/setores.component').then((m) => m.SetoresComponent),
      },
      {
        // Módulo de contratos: todas as telas exigem ACL `contratos` (a API valida o nível de cada ação)
        path: 'contratos',
        canActivate: [guardaAcl],
        data: { acl: 'contratos' },
        loadChildren: () => import('./features/contratos/contratos.routes').then((m) => m.ROTAS_CONTRATOS),
      },
      {
        path: 'admin/acl',
        title: 'Controle de acesso | Contratos SPI',
        canActivate: [guardaPapel],
        data: { papeis: ['SuperRoot'] },
        loadComponent: () => import('./features/administracao/acl/acl.component').then((m) => m.AclComponent),
      },
      {
        path: 'admin/ldap',
        title: 'Diretórios LDAP | Contratos SPI',
        canActivate: [guardaPapel],
        data: { papeis: ['SuperRoot'] },
        loadComponent: () =>
          import('./features/administracao/ldap/diretorios-ldap.component').then((m) => m.DiretoriosLdapComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
