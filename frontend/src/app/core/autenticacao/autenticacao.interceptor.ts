import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { AutenticacaoService } from './autenticacao.service';

const URL_LOGIN = `${ambiente.urlApi}/autenticacao/login`;

/**
 * Anexa o JWT às chamadas da API.
 * 401 → encerra a sessão; 403 `revisao_perfil_obrigatoria` → leva à página de perfil.
 */
export const interceptadorAutenticacao: HttpInterceptorFn = (requisicao, proximo) => {
  const autenticacao = inject(AutenticacaoService);
  const roteador = inject(Router);
  const ehApi = requisicao.url.startsWith(ambiente.urlApi);
  const ehLogin = requisicao.url === URL_LOGIN;
  const token = autenticacao.token;

  const comToken =
    ehApi && !ehLogin && token ? requisicao.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : requisicao;

  return proximo(comToken).pipe(
    catchError((erro: unknown) => {
      if (erro instanceof HttpErrorResponse && ehApi && !ehLogin && autenticacao.autenticado()) {
        if (erro.status === 401) {
          autenticacao.sair('expirada');
        } else if (erro.status === 403 && erro.error?.codigo === 'revisao_perfil_obrigatoria') {
          autenticacao.validarSessao().subscribe(() => void roteador.navigate(['/perfil']));
        }
      }
      return throwError(() => erro);
    }),
  );
};
