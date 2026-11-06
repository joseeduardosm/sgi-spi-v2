// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas do plano de face da rede (equipamentos, porta e cadastros).

import { Routes } from '@angular/router';

/** Todas exigem ao menos "ver" (guarda na rota-mãe); a API confere de novo o papel de cada ação. */
export const ROTAS_REDE: Routes = [
  { path: '', title: 'Rede | SGI SPI', loadComponent: () => import('./equipamentos-rede.component').then((m) => m.EquipamentosRedeComponent) },
  { path: 'topologia', title: 'Topologia da rede | SGI SPI', loadComponent: () => import('./topologia-rede.component').then((m) => m.TopologiaRedeComponent) },
  { path: 'cadastros', title: 'Pontos, VLANs e modelos | SGI SPI', loadComponent: () => import('./cadastros-rede.component').then((m) => m.CadastrosRedeComponent) },
  { path: 'equipamentos/:id', title: 'Equipamento de rede | SGI SPI', loadComponent: () => import('./equipamento-rede.component').then((m) => m.EquipamentoRedeComponent) },
  { path: 'portas-lista/:filtro', title: 'Portas | Rede | SGI SPI', loadComponent: () => import('./lista-portas-rede.component').then((m) => m.ListaPortasRedeComponent) },
  { path: 'portas/:id', title: 'Porta de rede | SGI SPI', loadComponent: () => import('./porta-rede.component').then((m) => m.PortaRedeComponent) },
];
