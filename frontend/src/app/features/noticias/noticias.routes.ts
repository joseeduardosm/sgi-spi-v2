// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas da gestão de notícias (lista, editor e configuração do portal).

import { Routes } from '@angular/router';

export const ROTAS_GESTAO_NOTICIAS: Routes = [
  { path: '', title: 'Notícias | SGI SPI', loadComponent: () => import('./gestao/lista-gestao.component').then((m) => m.ListaGestaoComponent) },
  { path: 'portal', title: 'Configurar portal | SGI SPI', loadComponent: () => import('./gestao/configuracao-portal.component').then((m) => m.ConfiguracaoPortalComponent) },
  { path: 'nova', title: 'Nova notícia | SGI SPI', loadComponent: () => import('./gestao/editor-noticia.component').then((m) => m.EditorNoticiaComponent) },
  { path: ':id', title: 'Notícia | SGI SPI', loadComponent: () => import('./gestao/editor-noticia.component').then((m) => m.EditorNoticiaComponent) },
];
