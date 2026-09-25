// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir o mapa de rotas (endereços) da aplicação e quem pode acessar cada uma.

import { Routes } from '@angular/router';

import { guardaAcl, guardaPerfil } from './core/acesso/acesso.guards';
import { guardaAutenticacao, guardaPapel, guardaVisitante } from './core/autenticacao/autenticacao.guards';

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
      // Módulos protegidos pela ACL: `data.acl` informa o slug do recurso conferido por `guardaAcl`
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
      // Administração: só para o papel SuperRoot
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
  // Qualquer endereço desconhecido volta para o início
  { path: '**', redirectTo: '' },
];
