// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas do Módulo Tarefas.

import { Routes } from '@angular/router';

/**
 * Todas as telas ficam dentro da casca do módulo (navegação lateral própria).
 * Visão e filtros ficam na URL (`?visao=lista&pessoas=3`); cada tarefa tem a própria tela em `/tarefas/123`; as permissões são conferidas na API.
 */
export const ROTAS_TAREFAS: Routes = [
  {
    path: '',
    loadComponent: () => import('./modulo-tarefas.component').then((m) => m.ModuloTarefasComponent),
    children: [
      {
        path: '',
        title: 'Minhas tarefas | SGI SPI',
        data: { escopo: 'minhas' },
        loadComponent: () => import('./espaco-tarefas.component').then((m) => m.EspacoTarefasComponent),
      },
      {
        path: 'nova',
        title: 'Nova tarefa | SGI SPI',
        loadComponent: () => import('./nova-tarefa.component').then((m) => m.NovaTarefaComponent),
      },
      {
        path: 'equipes',
        title: 'Equipes | SGI SPI',
        loadComponent: () => import('./equipes.component').then((m) => m.EquipesComponent),
      },
      {
        // Configuração: `nova` ou o id da equipe (dono ou SuperRoot; a API confere)
        path: 'equipes/:equipeId/configurar',
        title: 'Configurar equipe | SGI SPI',
        loadComponent: () => import('./configuracao-equipe.component').then((m) => m.ConfiguracaoEquipeComponent),
      },
      {
        path: 'equipes/:equipeId',
        title: 'Quadro da equipe | SGI SPI',
        data: { escopo: 'equipe' },
        loadComponent: () => import('./espaco-tarefas.component').then((m) => m.EspacoTarefasComponent),
      },
      {
        path: 'pessoas/:login',
        title: 'Tarefas da pessoa | SGI SPI',
        data: { escopo: 'pessoa' },
        loadComponent: () => import('./espaco-tarefas.component').then((m) => m.EspacoTarefasComponent),
      },
      {
        // Tela própria da tarefa (também é o link dos e-mails e avisos)
        path: ':numero',
        title: 'Tarefa | SGI SPI',
        loadComponent: () => import('./pagina-tarefa.component').then((m) => m.PaginaTarefaComponent),
      },
    ],
  },
];
