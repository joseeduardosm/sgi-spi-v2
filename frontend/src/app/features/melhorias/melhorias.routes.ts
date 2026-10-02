// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas do Módulo Melhorias (minhas sugestões e triagem).

import { Routes } from '@angular/router';

export const ROTAS_MELHORIAS: Routes = [
  { path: '', title: 'Minhas sugestões | SGI SPI', loadComponent: () => import('./minhas-sugestoes.component').then((m) => m.MinhasSugestoesComponent) },
  // A triagem confere o acesso na API (SuperRoot ou CONTROLE_TOTAL em `melhorias`); sem ele, a tela mostra o aviso
  { path: 'triagem', title: 'Triagem de melhorias | SGI SPI', loadComponent: () => import('./triagem.component').then((m) => m.TriagemComponent) },
  { path: 'triagem/:numero', title: 'Sugestão | SGI SPI', loadComponent: () => import('./detalhe-sugestao.component').then((m) => m.DetalheSugestaoComponent) },
];
