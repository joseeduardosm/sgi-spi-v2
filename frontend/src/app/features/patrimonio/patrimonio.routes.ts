// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas do módulo Patrimônio (bens, movimentações, inservíveis, extraviados, baixa, locais, painel e parâmetros).
import { Routes } from '@angular/router';

import { guardaAcl } from '../../core/acesso/acesso.guards';

const consulta = { canActivate: [guardaAcl], data: { acl: 'patrimonio' } };
const edicao = { canActivate: [guardaAcl], data: { acl: 'patrimonio', nivelAcl: 'MODIFICACAO' } };
const administracao = { canActivate: [guardaAcl], data: { acl: 'patrimonio', nivelAcl: 'CONTROLE_TOTAL' } };

/** O acesso ao módulo exige o recurso `patrimonio`; cada rota confere o nível e a API confere em toda ação. Rotas fixas antes das de `:id`. */
export const ROTAS_PATRIMONIO: Routes = [
  { path: '', title: 'Patrimônio | SGI SPI', ...consulta, loadComponent: () => import('./bens.component').then((m) => m.BensComponent) },
  { path: 'bens/novo', title: 'Adicionar bem | SGI SPI', ...edicao, loadComponent: () => import('./cadastro-bem.component').then((m) => m.CadastroBemComponent) },
  { path: 'bens/lote', title: 'Cadastro em lote | SGI SPI', ...edicao, loadComponent: () => import('./cadastro-bem.component').then((m) => m.CadastroBemComponent) },
  { path: 'bens/:bemId', title: 'Patrimônio | SGI SPI', ...consulta, loadComponent: () => import('./detalhe-bem.component').then((m) => m.DetalheBemComponent) },
  { path: 'movimentacoes', title: 'Movimentações | SGI SPI', ...consulta, loadComponent: () => import('./movimentacoes.component').then((m) => m.MovimentacoesComponent) },
  { path: 'movimentacoes/nova', title: 'Solicitar movimentação | SGI SPI', ...edicao, loadComponent: () => import('./nova-movimentacao.component').then((m) => m.NovaMovimentacaoComponent) },
  { path: 'movimentacoes/:movimentacaoId', title: 'Movimentação | SGI SPI', ...consulta, loadComponent: () => import('./detalhe-movimentacao.component').then((m) => m.DetalheMovimentacaoComponent) },
  { path: 'inserviveis', title: 'Inservíveis | SGI SPI', data: { acl: 'patrimonio', tipo: 'inservivel' }, canActivate: [guardaAcl], loadComponent: () => import('./listas-classificacao.component').then((m) => m.ListasClassificacaoComponent) },
  { path: 'inserviveis/:classificacaoId', title: 'Lista de inservíveis | SGI SPI', data: { acl: 'patrimonio', tipo: 'inservivel' }, canActivate: [guardaAcl], loadComponent: () => import('./lista-classificacao.component').then((m) => m.ListaClassificacaoComponent) },
  { path: 'extraviados', title: 'Extraviados | SGI SPI', data: { acl: 'patrimonio', tipo: 'extraviado' }, canActivate: [guardaAcl], loadComponent: () => import('./listas-classificacao.component').then((m) => m.ListasClassificacaoComponent) },
  { path: 'extraviados/:classificacaoId', title: 'Lista de extraviados | SGI SPI', data: { acl: 'patrimonio', tipo: 'extraviado' }, canActivate: [guardaAcl], loadComponent: () => import('./lista-classificacao.component').then((m) => m.ListaClassificacaoComponent) },
  { path: 'baixas', title: 'Baixa de bens | SGI SPI', ...consulta, loadComponent: () => import('./baixas.component').then((m) => m.BaixasComponent) },
  { path: 'baixas/:baixaId', title: 'Baixa | SGI SPI', ...consulta, loadComponent: () => import('./lista-baixa.component').then((m) => m.ListaBaixaComponent) },
  { path: 'localizacoes', title: 'Locais | SGI SPI', ...consulta, loadComponent: () => import('./localizacoes.component').then((m) => m.LocalizacoesComponent) },
  { path: 'painel', title: 'Painel do Patrimônio | SGI SPI', ...consulta, loadComponent: () => import('./painel-patrimonio.component').then((m) => m.PainelPatrimonioComponent) },
  { path: 'pendencias', title: 'Aguardando envio | SGI SPI', ...consulta, loadComponent: () => import('./pendencias-offline.component').then((m) => m.PendenciasOfflineComponent) },
  { path: 'parametros', title: 'Parâmetros | SGI SPI', ...administracao, loadComponent: () => import('./parametros.component').then((m) => m.ParametrosPatrimonioComponent) },
];
