// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas do Módulo RH.

import { Routes } from '@angular/router';

/** Telas do RH. As de CGP e autorizador conferem o papel na API (403 para quem não tem). */
export const ROTAS_RH: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'ferias' },
  {
    path: 'ferias',
    title: 'Férias e licença-prêmio | SGI SPI',
    loadComponent: () => import('./ferias.component').then((m) => m.FeriasComponent),
  },
  {
    path: 'painel-afastamentos',
    title: 'Painel de afastamentos | SGI SPI',
    loadComponent: () => import('./painel-afastamentos.component').then((m) => m.PainelAfastamentosComponent),
  },
  {
    path: 'validacoes',
    title: 'Validações de cadastro | SGI SPI',
    loadComponent: () => import('./validacoes.component').then((m) => m.ValidacoesComponent),
  },
  {
    // Feriados e pontos facultativos: todos veem; só a CGP cadastra
    path: 'feriados',
    title: 'Feriados e pontos facultativos | SGI SPI',
    loadComponent: () => import('./feriados.component').then((m) => m.FeriadosComponent),
  },
  {
    path: 'parametros',
    title: 'Parâmetros do RH | SGI SPI',
    loadComponent: () => import('./parametros.component').then((m) => m.ParametrosComponent),
  },
];
