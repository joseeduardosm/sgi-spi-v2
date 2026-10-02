// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API da assinatura de e-mail (/api/assinatura-email).

import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { catchError, from, Observable, switchMap, tap, throwError } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { nomeDoArquivo, salvarBlob } from '../../shared/utilitarios/download';

/** Dados da assinatura: valem só para gerar a imagem (nada é gravado no perfil). */
export interface DadosAssinatura {
  nome_completo: string;
  cargo: string;
  departamento: string;
  email: string;
  ramal: string;
  celular: string;
  andar: string;
  lado: string;
  incluir_celular: boolean;
  incluir_andar_lado: boolean;
}

export interface LeituraDadosAssinatura extends DadosAssinatura {
  /** Campos obrigatórios que o perfil ainda não tem (nome, cargo, e-mail). */
  faltando: string[];
  /** Prefixo do telefone da SPI; o ramal vem depois dele. */
  telefone_prefixo: string;
}

export interface PreviaAssinatura {
  png_base64: string;
  html: string;
  avisos: string[];
}

@Injectable({ providedIn: 'root' })
export class AssinaturaApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/assinatura-email`;

  dados(): Observable<LeituraDadosAssinatura> {
    return this.http.get<LeituraDadosAssinatura>(`${this.base}/dados`);
  }

  previa(dados: DadosAssinatura): Observable<PreviaAssinatura> {
    return this.http.post<PreviaAssinatura>(`${this.base}/previa`, dados);
  }

  /** Baixa a assinatura em PNG (1692×471, usar a 564 px de largura). */
  baixarPng(dados: DadosAssinatura): Observable<unknown> {
    return this.baixar('png', dados, 'assinatura-email.png');
  }

  /** Baixa a assinatura em HTML (para importar no Outlook ou no webmail). */
  baixarHtml(dados: DadosAssinatura): Observable<unknown> {
    return this.baixar('html', dados, 'assinatura-email.html');
  }

  /** Download por POST: o corpo com os dados vai junto, então não dá para usar um simples link. */
  private baixar(formato: 'png' | 'html', dados: DadosAssinatura, padrao: string): Observable<unknown> {
    return this.http.post(`${this.base}/${formato}`, dados, { observe: 'response', responseType: 'blob' }).pipe(
      tap((resposta) => salvarBlob(resposta.body ?? new Blob(), nomeDoArquivo(resposta, padrao))),
      // Com `responseType: 'blob'` o erro da API também chega como Blob: volta a ser JSON
      catchError((erro: unknown) => {
        if (!(erro instanceof HttpErrorResponse) || !(erro.error instanceof Blob)) return throwError(() => erro);
        return from(erro.error.text()).pipe(
          switchMap((texto) => {
            let corpo: unknown = texto;
            try {
              corpo = JSON.parse(texto);
            } catch {
              // Corpo que não é JSON: mantém o texto
            }
            return throwError(() => new HttpErrorResponse({ error: corpo, headers: erro.headers, status: erro.status, statusText: erro.statusText, url: erro.url ?? undefined }));
          }),
        );
      }),
    );
  }
}
