// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API do Painel Executivo (slides, PDF e verificação de acesso).

import { HttpClient, HttpResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { baixarArquivo } from '../../shared/utilitarios/download';
import { IdSlide, SlideContratos, SlideRh, SlideTarefas } from './painel-executivo.models';

@Injectable({ providedIn: 'root' })
export class PainelExecutivoApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/painel-executivo';

  acesso(): Observable<{ pode: boolean }> {
    return this.http.get<{ pode: boolean }>(`${this.base}/acesso`);
  }

  contratos(): Observable<SlideContratos> {
    return this.http.get<SlideContratos>(`${this.base}/contratos`);
  }

  rh(): Observable<SlideRh> {
    return this.http.get<SlideRh>(`${this.base}/rh`);
  }

  tarefas(): Observable<SlideTarefas> {
    return this.http.get<SlideTarefas>(`${this.base}/tarefas`);
  }

  baixarPdf(slide: IdSlide): Observable<HttpResponse<Blob>> {
    return baixarArquivo(this.http, `${this.base}/${slide}/pdf`, `painel-executivo-${slide}.pdf`);
  }
}
