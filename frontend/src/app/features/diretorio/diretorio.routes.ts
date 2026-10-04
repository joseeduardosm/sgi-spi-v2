// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas do Diretório (tela de ramais em cartões de visita).

import { Routes } from '@angular/router';

export const ROTAS_DIRETORIO: Routes = [
  { path: '', title: 'Ramais | SGI SPI', loadComponent: () => import('./ramais.component').then((m) => m.RamaisComponent) },
];
