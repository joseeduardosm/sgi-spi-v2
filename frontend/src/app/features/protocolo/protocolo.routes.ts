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
    // Página dedicada: novo tipo (com a faixa do primeiro exercício) ou novo exercício de um tipo existente
    path: 'administracao/tipos/novo',
    title: 'Novo tipo de documento | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'protocolo', nivelAcl: 'CONTROLE_TOTAL' },
    loadComponent: () => import('./tipo-protocolo.component').then((m) => m.TipoProtocoloComponent),
  },
  {
    path: 'administracao/tipos/:tipoId/exercicio',
    title: 'Novo exercício | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'protocolo', nivelAcl: 'CONTROLE_TOTAL' },
    loadComponent: () => import('./tipo-protocolo.component').then((m) => m.TipoProtocoloComponent),
  },
  {
    // Detalhe do tipo (clique no cartão da administração); `?sequencia=<id>` escolhe o exercício
    path: 'administracao/tipos/:tipoId',
    title: 'Tipo de documento | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'protocolo', nivelAcl: 'CONTROLE_TOTAL' },
    loadComponent: () => import('./detalhe-tipo-protocolo.component').then((m) => m.DetalheTipoProtocoloComponent),
  },
  {
    path: 'administracao',
    title: 'Administração do Protocolo | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'protocolo', nivelAcl: 'CONTROLE_TOTAL' },
    loadComponent: () => import('./administracao-protocolo.component').then((m) => m.AdministracaoProtocoloComponent),
  },
];
