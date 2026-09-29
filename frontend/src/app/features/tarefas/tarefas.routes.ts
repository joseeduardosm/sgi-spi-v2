// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas do Módulo Tarefas.

import { Routes } from '@angular/router';

/** Telas de tarefas. Filtros e visão (tabela ou Kanban) ficam na URL; as permissões são conferidas na API. */
export const ROTAS_TAREFAS: Routes = [
  {
    path: '',
    title: 'Minhas tarefas | SGI SPI',
    data: { escopo: 'minhas' },
    loadComponent: () => import('./lista-tarefas.component').then((m) => m.ListaTarefasComponent),
  },
  {
    path: 'nova',
    title: 'Nova tarefa | SGI SPI',
    loadComponent: () => import('./nova-tarefa.component').then((m) => m.NovaTarefaComponent),
  },
  {
    path: 'equipes/:equipeId',
    title: 'Tarefas da equipe | SGI SPI',
    data: { escopo: 'equipe' },
    loadComponent: () => import('./lista-tarefas.component').then((m) => m.ListaTarefasComponent),
  },
  {
    path: 'pessoas/:login',
    title: 'Tarefas da pessoa | SGI SPI',
    data: { escopo: 'pessoa' },
    loadComponent: () => import('./lista-tarefas.component').then((m) => m.ListaTarefasComponent),
  },
  {
    path: ':numero',
    title: 'Tarefa | SGI SPI',
    loadComponent: () => import('./detalhe-tarefa.component').then((m) => m.DetalheTarefaComponent),
  },
];
