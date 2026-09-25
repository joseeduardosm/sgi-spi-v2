// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as guardas de rota ligadas ao login (autenticado, visitante e papel).
//
// Guarda (CanActivateFn) é uma função que o roteador chama antes de abrir uma rota: devolver true
// libera; devolver uma UrlTree redireciona para outro endereço.

import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { Papel } from '../modelos/usuario.model';
import { AutenticacaoService } from './autenticacao.service';

/** Protege rotas que exigem usuário autenticado. Redireciona para /login preservando o destino. */
export const guardaAutenticacao: CanActivateFn = (_rota, estado) => {
  const autenticacao = inject(AutenticacaoService);
  if (autenticacao.autenticado()) return true;
  // Guarda o endereço pedido em ?retorno= para voltar a ele depois do login
  return inject(Router).createUrlTree(['/login'], { queryParams: { retorno: estado.url } });
};

/** Impede que um usuário já autenticado veja a tela de login. */
export const guardaVisitante: CanActivateFn = () => {
  const autenticacao = inject(AutenticacaoService);
  return autenticacao.autenticado() ? inject(Router).createUrlTree(['/']) : true;
};

/**
 * Exige ao menos um dos papéis em `route.data.papeis`. Usar junto com guardaAutenticacao:
 * `{ path: 'admin', canActivate: [guardaPapel], data: { papeis: ['SuperRoot'] } }`
 */
export const guardaPapel: CanActivateFn = (rota) => {
  // Papéis exigidos pela rota (vazio = qualquer usuário autenticado)
  const papeis = (rota.data['papeis'] ?? []) as Papel[];
  const autenticacao = inject(AutenticacaoService);
  return papeis.length === 0 || autenticacao.possuiPapel(...papeis) ? true : inject(Router).createUrlTree(['/']);
};
