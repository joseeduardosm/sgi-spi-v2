// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas do módulo Manuais (estantes, livro e página).

import { Routes } from '@angular/router';

import { guardaAcl } from '../../core/acesso/acesso.guards';

export const ROTAS_MANUAIS: Routes = [
  { path: '', title: 'Manuais | SGI SPI', canActivate: [guardaAcl], data: { acl: 'manuais' }, loadComponent: () => import('./manuais.component').then((m) => m.ManuaisComponent) },
  { path: 'livros/:id', title: 'Manual | SGI SPI', canActivate: [guardaAcl], data: { acl: 'manuais' }, loadComponent: () => import('./livro.component').then((m) => m.LivroComponent) },
  { path: 'paginas/:id', title: 'Manual | SGI SPI', canActivate: [guardaAcl], data: { acl: 'manuais' }, loadComponent: () => import('./pagina.component').then((m) => m.PaginaComponent) },
];
