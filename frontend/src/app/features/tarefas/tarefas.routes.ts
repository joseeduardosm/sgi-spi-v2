/**
 * =============================================================================
 * ARQUIVO: tarefas.routes.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Definir as rotas do Módulo Tarefas.
 *
 * RESUMO TÉCNICO:
 * Exporta ROTAS_TAREFAS: uma rota-casca (ModuloTarefasComponent) com rotas
 * filhas carregadas sob demanda (loadComponent). O `data.escopo` diz ao
 * EspacoTarefasComponent se mostra minhas tarefas, de uma equipe, de uma
 * pessoa ou as subtarefas. Rotas fixas vêm antes de ':numero' para não serem
 * confundidas com o número de uma tarefa.
 *
 * FINALIDADE DE NEGÓCIO:
 * Cada tela do módulo tem um endereço próprio (inclusive cada tarefa em
 * /tarefas/123), que é o link usado nos e-mails e avisos. Assim o servidor
 * pode compartilhar e abrir diretamente a tarefa, a RDM ou o quadro da equipe.
 *
 * CONTEXTO NO SISTEMA:
 * Carregado em frontend/src/app/app.routes.ts, sob o layout autenticado e a
 * guarda de ACL do módulo. As permissões finais são conferidas na API.
 *
 * =============================================================================
 */

import { Routes } from '@angular/router';

/**
 * Todas as telas ficam dentro da casca do módulo (navegação lateral própria).
 * Visão e filtros ficam na URL (`?visao=lista&pessoas=3`); cada tarefa tem a própria tela em `/tarefas/123`; as permissões são conferidas na API.
 */
// `loadComponent` com import() faz o carregamento sob demanda (lazy): o
// código da tela só é baixado quando o usuário a abre.
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
        // RDMs (Requisições de Mudança) das tarefas visíveis; antes de ':numero'
        path: 'rdms',
        title: 'RDMs | SGI SPI',
        loadComponent: () => import('./lista-rdms.component').then((m) => m.ListaRdmsComponent),
      },
      {
        path: 'atividades',
        title: 'Minhas atividades | SGI SPI',
        loadComponent: () => import('./atividades.component').then((m) => m.AtividadesComponent),
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
        path: 'equipes/:equipeId/recorrencias',
        title: 'Tarefas recorrentes | SGI SPI',
        loadComponent: () => import('./recorrencias.component').then((m) => m.RecorrenciasComponent),
      },
      {
        path: 'recorrencias',
        title: 'Tarefas recorrentes | SGI SPI',
        loadComponent: () => import('./recorrencias.component').then((m) => m.RecorrenciasComponent),
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
        // RDM da tarefa: formulário, envio e decisão da liderança
        path: ':numero/rdm',
        title: 'RDM | SGI SPI',
        loadComponent: () => import('./rdm-tarefa.component').then((m) => m.RdmTarefaComponent),
      },
      {
        path: ':numero/subtarefas/nova',
        title: 'Nova subtarefa | SGI SPI',
        loadComponent: () => import('./nova-subtarefa.component').then((m) => m.NovaSubtarefaComponent),
      },
      {
        // Quadro só das subtarefas de uma tarefa ("Equipe X - Tarefa #N - Subtarefas"), com andamento independente
        path: ':numero/subtarefas',
        title: 'Subtarefas | SGI SPI',
        data: { escopo: 'subtarefas' },
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
