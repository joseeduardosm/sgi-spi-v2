// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas do módulo Chamados (abrir, meus chamados, fila, painel, detalhe e Parâmetros).

import { Routes } from '@angular/router';

import { guardaChamados } from '../../core/acesso/acesso.guards';

/** Cada tela exige o seu papel (`abrir`, `atender` ou `administrar`); a API confere de novo em cada chamada. */
export const ROTAS_CHAMADOS: Routes = [
  { path: '', title: 'Abrir chamado | SGI SPI', loadComponent: () => import('./novo-chamado.component').then((m) => m.NovoChamadoComponent) },
  {
    path: 'meus', title: 'Meus chamados | SGI SPI', data: { modo: 'meus' },
    loadComponent: () => import('./lista-chamados.component').then((m) => m.ListaChamadosComponent),
  },
  {
    path: 'fila', title: 'Fila de atendimento | SGI SPI', data: { modo: 'fila', papelChamados: 'atender' }, canActivate: [guardaChamados],
    loadComponent: () => import('./lista-chamados.component').then((m) => m.ListaChamadosComponent),
  },
  {
    path: 'parametros', title: 'Parâmetros dos Chamados | SGI SPI', data: { papelChamados: 'administrar' }, canActivate: [guardaChamados],
    loadComponent: () => import('./parametros-chamados.component').then((m) => m.ParametrosChamadosComponent),
  },
  {
    path: 'aprovacoes', title: 'Minhas aprovações | SGI SPI',
    loadComponent: () => import('./aprovacoes-chamados.component').then((m) => m.AprovacoesChamadosComponent),
  },
  {
    path: 'painel', title: 'Painel de chamados | SGI SPI',
    loadComponent: () => import('./painel-chamados.component').then((m) => m.PainelChamadosComponent),
  },
  {
    path: 'relatorios', title: 'Relatórios dos Chamados | SGI SPI', data: { papelChamados: 'atender' }, canActivate: [guardaChamados],
    loadComponent: () => import('./relatorios-chamados.component').then((m) => m.RelatoriosChamadosComponent),
  },
  { path: ':numero', title: 'Chamado | SGI SPI', loadComponent: () => import('./detalhe-chamado.component').then((m) => m.DetalheChamadoComponent) },
];
