import { HttpClient, HttpResponse } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

/** Nome do arquivo indicado pela API no cabeçalho Content-Disposition. */
export function nomeDoArquivo(resposta: HttpResponse<Blob>, padrao: string): string {
  const cabecalho = resposta.headers.get('Content-Disposition') ?? '';
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(cabecalho);
  if (utf8) return decodeURIComponent(utf8[1]);
  const simples = /filename="?([^";]+)"?/i.exec(cabecalho);
  return simples ? simples[1] : padrao;
}

/** Salva o conteúdo no computador do usuário (download disparado pelo navegador). */
export function salvarBlob(conteudo: Blob, nome: string): void {
  const url = URL.createObjectURL(conteudo);
  const link = document.createElement('a');
  link.href = url;
  link.download = nome;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Baixa um arquivo da API. Os downloads exigem o token (o interceptador o anexa), por isso não
 * podem ser um simples link <a href>.
 */
export function baixarArquivo(http: HttpClient, url: string, padrao = 'arquivo'): Observable<HttpResponse<Blob>> {
  return http
    .get(url, { observe: 'response', responseType: 'blob' })
    .pipe(tap((resposta) => salvarBlob(resposta.body ?? new Blob(), nomeDoArquivo(resposta, padrao))));
}
