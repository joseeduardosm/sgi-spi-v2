// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas do módulo Contratações (lista, documento e versões).

import { Routes } from '@angular/router';

import { guardaAcl } from '../../core/acesso/acesso.guards';

/** O acesso ao módulo exige o recurso `contratacoes`; o papel em cada documento é conferido pela API. */
export const ROTAS_CONTRATACOES: Routes = [
  {
    path: '',
    title: 'Contratações | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'contratacoes' },
    loadComponent: () => import('./lista-contratacoes.component').then((m) => m.ListaContratacoesComponent),
  },
  {
    path: ':id',
    title: 'Documento | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'contratacoes' },
    loadComponent: () => import('./documento-contratacao.component').then((m) => m.DocumentoContratacaoComponent),
  },
  {
    path: ':id/versoes',
    title: 'Versões do documento | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'contratacoes' },
    loadComponent: () => import('./versoes-contratacao.component').then((m) => m.VersoesContratacaoComponent),
  },
];
