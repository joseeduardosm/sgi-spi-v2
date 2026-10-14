// Criado por José Eduardo Santana Martins
// Este arquivo serve para contar as requisições HTTP em andamento e alimentar a barra de progresso do topo.

import { HttpEventType, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { finalize, tap } from 'rxjs';

import { ProgressoService } from './progresso.service';

/** Consultas automáticas em segundo plano (sino, avisos) não acendem a barra: ela é para o que a pessoa pediu. */
const EM_SEGUNDO_PLANO = /\/(notificacoes|mensagens)\/resumo(\?|$)/;

export const interceptadorProgresso: HttpInterceptorFn = (requisicao, proximo) => {
  if (EM_SEGUNDO_PLANO.test(requisicao.url)) return proximo(requisicao);
  const progresso = inject(ProgressoService);
  progresso.iniciarRequisicao();
  // Envio e download de arquivo: pede os eventos de progresso e deixa a barra do topo determinada (o chamador continua recebendo só a resposta)
  const envio = typeof FormData !== 'undefined' && requisicao.body instanceof FormData;
  // Download de arquivo (blob): se o servidor informar o tamanho, a barra mostra o percentual; senão segue indeterminada
  const download = requisicao.responseType === 'blob';
  return proximo(envio || download ? requisicao.clone({ reportProgress: true }) : requisicao).pipe(
    tap((evento) => {
      if (envio && evento.type === HttpEventType.UploadProgress) progresso.informarEnvio(evento.loaded, evento.total);
      else if (download && evento.type === HttpEventType.DownloadProgress && evento.total) progresso.informarEnvio(evento.loaded, evento.total);
    }),
    finalize(() => { if (envio || download) progresso.informarEnvio(null); progresso.terminarRequisicao(); }),
  );
};
