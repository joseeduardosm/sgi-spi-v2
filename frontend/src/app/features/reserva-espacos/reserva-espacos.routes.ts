// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas da Reserva de Espaços (agenda, reservas, fila do fiscal, espaços, painel e configuração).

import { Routes } from '@angular/router';

/** Todo usuário autenticado acessa; a API confere o papel de fiscal nas telas e ações restritas. */
export const ROTAS_RESERVA_ESPACOS: Routes = [
  { path: '', title: 'Reserva de Espaços | SGI SPI', loadComponent: () => import('./agenda.component').then((m) => m.AgendaReservasComponent) },
  { path: 'nova', title: 'Nova reserva | SGI SPI', loadComponent: () => import('./nova-reserva.component').then((m) => m.NovaReservaComponent) },
  { path: 'minhas', title: 'Minhas reservas | SGI SPI', data: { modo: 'minhas' }, loadComponent: () => import('./lista-reservas.component').then((m) => m.ListaReservasComponent) },
  { path: 'reservas', title: 'Todas as reservas | SGI SPI', data: { modo: 'todas' }, loadComponent: () => import('./lista-reservas.component').then((m) => m.ListaReservasComponent) },
  { path: 'reservas/:id', title: 'Reserva | SGI SPI', loadComponent: () => import('./detalhe-reserva.component').then((m) => m.DetalheReservaComponent) },
  { path: 'reservas/:id/editar', title: 'Alterar reserva | SGI SPI', loadComponent: () => import('./nova-reserva.component').then((m) => m.NovaReservaComponent) },
  { path: 'fila', title: 'Fila do fiscal | SGI SPI', loadComponent: () => import('./fila-fiscal.component').then((m) => m.FilaFiscalComponent) },
  { path: 'espacos', title: 'Espaços | SGI SPI', loadComponent: () => import('./espacos.component').then((m) => m.EspacosReservasComponent) },
  { path: 'painel', title: 'Painel | SGI SPI', loadComponent: () => import('./painel-reservas.component').then((m) => m.PainelReservasComponent) },
  { path: 'configuracao', title: 'Configuração | SGI SPI', loadComponent: () => import('./configuracao-reservas.component').then((m) => m.ConfiguracaoReservasComponent) },
];
