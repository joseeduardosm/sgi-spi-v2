// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as guardas de rota de perfil pendente e de permissão (ACL) nos módulos.

import { inject } from '@angular/core';
import { CanActivateChildFn, CanActivateFn, Router } from '@angular/router';
import { map, of } from 'rxjs';

import { AutenticacaoService } from '../autenticacao/autenticacao.service';
import { AcessoService, NivelAcl } from './acesso.service';

/** Com o perfil pendente, só a página "Meu perfil" fica acessível. */
export const guardaPerfil: CanActivateChildFn = (_rota, estado) => {
  const autenticacao = inject(AutenticacaoService);
  if (autenticacao.usuario()?.perfil_restrito && !estado.url.startsWith('/perfil')) {
    return inject(Router).createUrlTree(['/perfil']);
  }
  return true;
};

/**
 * Exige nível de ACL em `route.data.acl` (slug) e opcionalmente `route.data.nivelAcl`.
 * Ex.: `{ path: 'usuarios', canActivate: [guardaAcl], data: { acl: 'usuarios' } }`
 */
export const guardaAcl: CanActivateFn = (rota) => {
  const acesso = inject(AcessoService);
  const roteador = inject(Router);
  // Slug do recurso e nível mínimo exigido (padrão: leitura)
  const slug = rota.data['acl'] as string;
  const nivel = (rota.data['nivelAcl'] ?? 'LEITURA') as NivelAcl;
  // Sem acesso: volta para o início com ?acesso=negado (a tela inicial mostra o aviso)
  const verificar = () => (acesso.pode(slug, nivel) ? true : roteador.createUrlTree(['/'], { queryParams: { acesso: 'negado' } }));
  // Se os acessos ainda não foram carregados, espera o carregamento antes de decidir
  return acesso.carregado() ? of(verificar()) : acesso.carregar().pipe(map(verificar));
};

/** Painel Executivo: libera só quem a API diz que pode (sem regras na ACL, apenas o SuperRoot). */
export const guardaPainelExecutivo: CanActivateFn = () => {
  const acesso = inject(AcessoService);
  const roteador = inject(Router);
  const verificar = () => (acesso.painelExecutivo() ? true : roteador.createUrlTree(['/'], { queryParams: { acesso: 'negado' } }));
  return acesso.carregado() ? of(verificar()) : acesso.carregar().pipe(map(verificar));
};

/**
 * Chamados: o papel exigido vem de `data.papelChamados` (`abrir`, `atender` ou `administrar`; padrão `abrir`).
 * A API decide quem tem papel (sem regras na ACL, o módulo é fechado: só o SuperRoot).
 */
export const guardaChamados: CanActivateFn = (rota) => {
  const acesso = inject(AcessoService);
  const roteador = inject(Router);
  const papel = (rota.data['papelChamados'] ?? 'abrir') as 'abrir' | 'atender' | 'administrar';
  const verificar = () => (acesso.chamados()?.[papel] ? true : roteador.createUrlTree(['/'], { queryParams: { acesso: 'negado' } }));
  return acesso.carregado() ? of(verificar()) : acesso.carregar().pipe(map(verificar));
};

/** Plano de face da rede: exige o papel da rota (`data.papelRede`: `ver`, `editar` ou `administrar`; padrão `ver`). */
export const guardaRede: CanActivateFn = (rota) => {
  const acesso = inject(AcessoService);
  const roteador = inject(Router);
  const papel = (rota.data['papelRede'] ?? 'ver') as 'ver' | 'editar' | 'administrar';
  const verificar = () => (acesso.rede()?.[papel] ? true : roteador.createUrlTree(['/'], { queryParams: { acesso: 'negado' } }));
  return acesso.carregado() ? of(verificar()) : acesso.carregar().pipe(map(verificar));
};
