// Criado por José Eduardo Santana Martins
// Este arquivo serve para anexar o token JWT às chamadas da API e reagir a sessão expirada ou perfil pendente.
//
// Interceptador é uma função pela qual passam todas as requisições do HttpClient, antes de sair e
// na volta da resposta.

import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { AutenticacaoService } from './autenticacao.service';

// A chamada de login não leva token (ainda não existe) e seus 401 são "senha errada", não "sessão expirada"
const URL_LOGIN = `${ambiente.urlApi}/autenticacao/login`;

/**
 * Anexa o JWT às chamadas da API.
 * 401 → encerra a sessão; 403 `revisao_perfil_obrigatoria` → leva à página de perfil.
 */
export const interceptadorAutenticacao: HttpInterceptorFn = (requisicao, proximo) => {
  const autenticacao = inject(AutenticacaoService);
  const roteador = inject(Router);
  // Só mexe nas chamadas da nossa API (outros endereços passam intactos)
  const ehApi = requisicao.url.startsWith(ambiente.urlApi);
  const ehLogin = requisicao.url === URL_LOGIN;
  const token = autenticacao.token;

  // `clone`: requisições são imutáveis; cria-se uma cópia com o cabeçalho Authorization
  const comToken =
    ehApi && !ehLogin && token ? requisicao.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : requisicao;

  // Encaminha a requisição e observa erros na resposta
  return proximo(comToken).pipe(
    catchError((erro: unknown) => {
      if (erro instanceof HttpErrorResponse && ehApi && !ehLogin && autenticacao.autenticado()) {
        if (erro.status === 401) {
          autenticacao.sair('expirada');
        } else if (erro.status === 403 && erro.error?.codigo === 'revisao_perfil_obrigatoria') {
          autenticacao.validarSessao().subscribe(() => void roteador.navigate(['/perfil']));
        }
      }
      // Repassa o erro para quem fez a chamada tratar (mensagem na tela etc.)
      return throwError(() => erro);
    }),
  );
};
