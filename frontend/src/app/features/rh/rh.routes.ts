// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as rotas do Módulo RH.

import { Routes } from '@angular/router';

import { guardaAcl } from '../../core/acesso/acesso.guards';

/** Telas do RH. As de CGP e autorizador conferem o papel na API (403 para quem não tem). */
export const ROTAS_RH: Routes = [
  {
    path: '',
    pathMatch: 'full',
    title: 'RH | SGI SPI',
    loadComponent: () => import('./inicio-rh.component').then((m) => m.InicioRhComponent),
  },
  {
    path: 'ferias',
    title: 'Férias e licença-prêmio | SGI SPI',
    loadComponent: () => import('./ferias.component').then((m) => m.FeriasComponent),
  },
  {
    path: 'painel-afastamentos',
    title: 'Painel de afastamentos | SGI SPI',
    // Quem não é do RH nem autorizador recebe 403 da API (e não vê o item no menu)
    loadComponent: () => import('./painel-afastamentos.component').then((m) => m.PainelAfastamentosComponent),
  },
  {
    path: 'validacoes',
    title: 'Validações de cadastro | SGI SPI',
    loadComponent: () => import('./validacoes.component').then((m) => m.ValidacoesComponent),
  },
  {
    // Feriados e pontos facultativos: todos veem; só a CGP cadastra
    path: 'feriados',
    title: 'Feriados e pontos facultativos | SGI SPI',
    loadComponent: () => import('./feriados.component').then((m) => m.FeriadosComponent),
  },
  {
    // Setores são do RH: a mesma tela de setores, agora dentro do módulo
    path: 'setores',
    canActivate: [guardaAcl],
    data: { acl: 'rh' },
    title: 'Setores | SGI SPI',
    loadComponent: () => import('../setores/setores.component').then((m) => m.SetoresComponent),
  },
  {
    path: 'cargos',
    canActivate: [guardaAcl],
    data: { acl: 'rh' },
    title: 'Cargos | SGI SPI',
    loadComponent: () => import('./cargos.component').then((m) => m.CargosComponent),
  },
  {
    // Aberto a todos: as vagas só aparecem para o RH e para a liderança do setor (e a cadeia acima)
    path: 'organograma',
    title: 'Organograma | SGI SPI',
    loadComponent: () => import('./organograma.component').then((m) => m.OrganogramaComponent),
  },
  {
    // Histórico funcional da pessoa (o RH vê de qualquer um; cada pessoa vê o seu)
    path: 'historico/:id',
    title: 'Histórico funcional | SGI SPI',
    loadComponent: () => import('./historico-usuario.component').then((m) => m.HistoricoUsuarioComponent),
  },
  {
    path: 'pre-cadastros',
    title: 'Pré-cadastro | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'rh' },
    loadComponent: () => import('./pre-cadastros.component').then((m) => m.PreCadastrosComponent),
  },
  {
    path: 'pre-cadastros/nova',
    title: 'Nova ficha | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'rh' },
    loadComponent: () => import('./ficha-pre-cadastro.component').then((m) => m.FichaPreCadastroComponent),
  },
  {
    path: 'pre-cadastros/:id',
    title: 'Ficha de pré-cadastro | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'rh' },
    loadComponent: () => import('./ficha-pre-cadastro.component').then((m) => m.FichaPreCadastroComponent),
  },
  {
    path: 'admissoes',
    title: 'Admissões | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'rh' },
    loadComponent: () => import('./admissoes.component').then((m) => m.AdmissoesComponent),
  },
  {
    path: 'admissoes/:id',
    title: 'Admissão | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'rh' },
    loadComponent: () => import('./admissao.component').then((m) => m.AdmissaoComponent),
  },
  {
    path: 'modelos',
    title: 'Modelos do RH | SGI SPI',
    canActivate: [guardaAcl],
    data: { acl: 'rh' },
    loadComponent: () => import('./modelos.component').then((m) => m.ModelosRhComponent),
  },
  {
    // Cadastro funcional da própria pessoa (bio e ficha): qualquer usuário autenticado
    path: 'meu-cadastro',
    title: 'Meu cadastro funcional | SGI SPI',
    loadComponent: () => import('./meu-cadastro.component').then((m) => m.MeuCadastroComponent),
  },
  {
    path: 'parametros',
    title: 'Parâmetros do RH | SGI SPI',
    loadComponent: () => import('./parametros.component').then((m) => m.ParametrosComponent),
  },
];
