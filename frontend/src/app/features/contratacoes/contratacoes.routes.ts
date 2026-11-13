/**
 * =============================================================================
 * ARQUIVO: contratacoes.routes.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Definir as rotas do módulo Contratações: a lista de documentos, a tela de
 * um documento (ETP ou TR) e a tela de versões desse documento.
 *
 * RESUMO TÉCNICO:
 * Exporta ROTAS_CONTRATACOES. Todas as rotas usam o guarda guardaAcl com
 * data.acl = 'contratacoes' (a pessoa precisa ter o recurso na ACL, a lista
 * de controle de acesso por módulo). Os componentes são carregados sob
 * demanda com loadComponent + import dinâmico.
 *
 * FINALIDADE DE NEGÓCIO:
 * Dá acesso à elaboração dos documentos da fase de planejamento da compra:
 * ETP (Estudo Técnico Preliminar) e TR (Termo de Referência), com histórico
 * de versões para saber o que mudou e restaurar quando preciso.
 *
 * CONTEXTO NO SISTEMA:
 * Carregado como filho da rota autenticada em app.routes.ts. O papel de cada
 * pessoa dentro de um documento (autor, revisor etc.) é conferido pela API.
 *
 * =============================================================================
 */

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
