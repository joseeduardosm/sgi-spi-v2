import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { Papel } from '../modelos/usuario.model';
import { AutenticacaoService } from './autenticacao.service';

/** Protege rotas que exigem usuário autenticado. Redireciona para /login preservando o destino. */
export const guardaAutenticacao: CanActivateFn = (_rota, estado) => {
  const autenticacao = inject(AutenticacaoService);
  if (autenticacao.autenticado()) return true;
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
  const papeis = (rota.data['papeis'] ?? []) as Papel[];
  const autenticacao = inject(AutenticacaoService);
  return papeis.length === 0 || autenticacao.possuiPapel(...papeis) ? true : inject(Router).createUrlTree(['/']);
};
