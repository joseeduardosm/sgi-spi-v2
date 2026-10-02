// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas do Módulo Protocolo (numeração, painel e administração).

import { Routes } from '@angular/router';

import { guardaAcl } from '../../core/acesso/acesso.guards';

/** O acesso ao módulo exige o recurso `protocolo`; a administração exige CONTROLE_TOTAL (a API confere em toda ação). */
export const ROTAS_PROTOCOLO: Routes = [
  {
    path: '',
    title: 'Protocolo | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'protocolo' },
    loadComponent: () => import('./numeracao.component').then((m) => m.NumeracaoComponent),
  },
  {
    path: 'painel',
    title: 'Painel do Protocolo | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'protocolo' },
    loadComponent: () => import('./painel-protocolo.component').then((m) => m.PainelProtocoloComponent),
  },
  {
    path: 'administracao',
    title: 'Administração do Protocolo | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'protocolo', nivelAcl: 'CONTROLE_TOTAL' },
    loadComponent: () => import('./administracao-protocolo.component').then((m) => m.AdministracaoProtocoloComponent),
  },
];
