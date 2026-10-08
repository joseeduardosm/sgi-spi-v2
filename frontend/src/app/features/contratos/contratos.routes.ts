// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas (telas) do módulo de contratos.

import { Routes } from '@angular/router';

import { guardaAcl } from '../../core/acesso/acesso.guards';
import { guardaPapel } from '../../core/autenticacao/autenticacao.guards';

/** Rotas do módulo de contratos (filhas de `/contratos`, que já exige ACL `contratos` ≥ LEITURA). */
// Rotas que alteram dados exigem ACL MODIFICACAO; o spread (...edicao) aplica esta configuração em cada uma
const edicao = { canActivate: [guardaAcl], data: { acl: 'contratos', nivelAcl: 'MODIFICACAO' } };

export const ROTAS_CONTRATOS: Routes = [
  // Carteira (lista de contratos), painel e as páginas dedicadas do painel
  {
    path: '',
    title: 'Carteira de contratos | SGI SPI',
    loadComponent: () => import('./carteira/carteira.component').then((m) => m.CarteiraComponent),
  },
  {
    path: 'painel',
    title: 'Painel de contratos | SGI SPI',
    loadComponent: () => import('./painel/painel.component').then((m) => m.PainelComponent),
  },
  {
    // Painel de vigências: uma linha do tempo de vigência por contrato vigente
    path: 'vigencias',
    title: 'Vigências | SGI SPI',
    loadComponent: () => import('./painel/vigencias.component').then((m) => m.VigenciasComponent),
  },
  {
    // Verificação de autenticidade dos PDFs gerados pelo sistema (fica antes de `:id`)
    path: 'verificar',
    title: 'Verificar documento | SGI SPI',
    loadComponent: () => import('./painel/verificar-documento.component').then((m) => m.VerificarDocumentoComponent),
  },
  {
    // Calendário de vencimentos (fica antes de `:id`)
    path: 'calendario',
    title: 'Calendário de vencimentos | SGI SPI',
    loadComponent: () => import('./painel/calendario-vencimentos.component').then((m) => m.CalendarioVencimentosComponent),
  },
  {
    path: 'minhas-pendencias',
    title: 'Minhas pendências | SGI SPI',
    loadComponent: () => import('./painel/minhas-pendencias.component').then((m) => m.MinhasPendenciasComponent),
  },
  {
    path: 'alertas-de-risco',
    title: 'Alertas de risco | SGI SPI',
    loadComponent: () => import('./painel/alertas-de-risco.component').then((m) => m.AlertasDeRiscoComponent),
  },
  {
    // Empresas contratadas e prepostos
    path: 'empresas',
    title: 'Empresas contratadas | SGI SPI',
    loadComponent: () => import('./empresas/empresas.component').then((m) => m.EmpresasComponent),
  },
  {
    path: 'empresas/nova',
    title: 'Cadastrar empresa | SGI SPI',
    ...edicao,
    loadComponent: () => import('./empresas/empresa-detalhe.component').then((m) => m.EmpresaDetalheComponent),
  },
  {
    path: 'empresas/:empresaId',
    title: 'Empresa | SGI SPI',
    loadComponent: () => import('./empresas/empresa-detalhe.component').then((m) => m.EmpresaDetalheComponent),
  },
  {
    // Modelos globais de checklist e formulário (só SuperRoot)
    path: 'modelos',
    title: 'Modelos globais | SGI SPI',
    canActivate: [guardaPapel],
    data: { papeis: ['SuperRoot'] },
    loadComponent: () => import('./modelos/modelos.component').then((m) => m.ModelosComponent),
  },
  {
    // Cadastro de contrato; "novo" precisa vir antes de ":id" para não ser lido como um id
    path: 'novo',
    title: 'Novo contrato | SGI SPI',
    ...edicao,
    loadComponent: () => import('./formulario/formulario-contrato.component').then((m) => m.FormularioContratoComponent),
  },
  {
    // Detalhe do contrato (com as abas) e a edição
    path: ':id',
    title: 'Contrato | SGI SPI',
    loadComponent: () => import('./detalhe/detalhe-contrato.component').then((m) => m.DetalheContratoComponent),
  },
  {
    path: ':id/editar',
    title: 'Editar contrato | SGI SPI',
    ...edicao,
    loadComponent: () => import('./formulario/formulario-contrato.component').then((m) => m.FormularioContratoComponent),
  },
  {
    // Execução de uma competência (ex.: /contratos/<id>/execucao/2026-03)
    path: ':id/execucao/:competencia',
    title: 'Execução da competência | SGI SPI',
    loadComponent: () => import('./execucao/competencia.component').then((m) => m.CompetenciaComponent),
  },
  {
    // Atos do contrato: prorrogação, reajuste, aditamento e supressão (os dois últimos usam a mesma tela)
    path: ':id/prorrogacao',
    title: 'Prorrogação | SGI SPI',
    loadComponent: () => import('./prorrogacao/prorrogacao.component').then((m) => m.ProrrogacaoComponent),
  },
  {
    path: ':id/reajuste',
    title: 'Reajuste | SGI SPI',
    loadComponent: () => import('./reajuste/reajuste.component').then((m) => m.ReajusteComponent),
  },
  {
    path: ':id/aditamento',
    title: 'Aditamento | SGI SPI',
    data: { tipo: 'aditamento' },
    loadComponent: () => import('./alteracao/alteracao.component').then((m) => m.AlteracaoComponent),
  },
  {
    path: ':id/supressao',
    title: 'Supressão | SGI SPI',
    data: { tipo: 'supressao' },
    loadComponent: () => import('./alteracao/alteracao.component').then((m) => m.AlteracaoComponent),
  },
];
