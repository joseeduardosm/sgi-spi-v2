/**
 * =============================================================================
 * ARQUIVO: chamados.routes.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Definir as rotas filhas do módulo Chamados: abrir chamado, meus chamados,
 * fila de atendimento, parâmetros, aprovações, painel, relatórios e detalhe.
 *
 * RESUMO TÉCNICO:
 * Exporta o vetor ROTAS_CHAMADOS. Cada rota carrega o componente sob demanda
 * (loadComponent + import dinâmico, o chamado "lazy loading"). As telas que
 * exigem papel específico usam o guarda guardaChamados, que lê o campo
 * data.papelChamados ('atender' ou 'administrar'). A rota ':numero' fica por
 * último para não "engolir" os caminhos fixos acima dela.
 *
 * FINALIDADE DE NEGÓCIO:
 * Organiza o atendimento de chamados (pedidos de serviço feitos ao setor
 * responsável): quem pede abre e acompanha; quem atende trabalha na fila e
 * nos relatórios; quem administra configura categorias, SLAs e afins.
 *
 * CONTEXTO NO SISTEMA:
 * Carregado como filho da rota autenticada em app.routes.ts. Usa o guarda de
 * core/acesso/acesso.guards.ts; a API confere de novo o papel em cada chamada.
 *
 * =============================================================================
 */

import { Routes } from '@angular/router';

import { guardaChamados } from '../../core/acesso/acesso.guards';

/**
 * Rotas do módulo Chamados.
 *
 * Cada tela exige o seu papel (`abrir`, `atender` ou `administrar`); a API confere de novo em cada chamada.
 * Rotas sem `canActivate` ficam abertas a qualquer usuário logado (todo mundo pode abrir e acompanhar
 * os próprios chamados). `title` é o texto da aba do navegador.
 */
export const ROTAS_CHAMADOS: Routes = [
  { path: '', title: 'Abrir chamado | SGI SPI', loadComponent: () => import('./novo-chamado.component').then((m) => m.NovoChamadoComponent) },
  // "Meus chamados" e "Fila" usam o mesmo componente de lista; o campo data.modo diz qual visão montar.
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
  // Rota com parâmetro (:numero = número do chamado) fica no fim: o roteador testa na ordem e
  // ela casaria com qualquer palavra, inclusive "fila" ou "painel", se viesse antes.
  { path: ':numero', title: 'Chamado | SGI SPI', loadComponent: () => import('./detalhe-chamado.component').then((m) => m.DetalheChamadoComponent) },
];
