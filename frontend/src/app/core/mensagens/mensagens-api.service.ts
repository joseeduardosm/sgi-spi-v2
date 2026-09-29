// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API da mensageria (/api/mensagens).

import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import {
  Destinatarios, EntregaDetalhe, EntregaResumo, EnviadaDetalhe, EnviadaResumo, EnvioMensagem, Pagina, ResumoCaixa,
} from './mensagens.models';

@Injectable({ providedIn: 'root' })
export class MensagensApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/mensagens`;

  resumo(): Observable<ResumoCaixa> {
    return this.http.get<ResumoCaixa>(`${this.base}/resumo`);
  }

  listar(estado: string, busca: string, pagina: number): Observable<Pagina<EntregaResumo>> {
    const params = new HttpParams().set('estado', estado).set('busca', busca).set('pagina', pagina);
    return this.http.get<Pagina<EntregaResumo>>(this.base, { params });
  }

  abrir(id: string): Observable<EntregaDetalhe> {
    return this.http.get<EntregaDetalhe>(`${this.base}/${id}`);
  }

  ciencia(id: string): Observable<EntregaDetalhe> {
    return this.http.post<EntregaDetalhe>(`${this.base}/${id}/ciencia`, {});
  }

  destinatarios(): Observable<Destinatarios> {
    return this.http.get<Destinatarios>(`${this.base}/destinatarios`);
  }

  enviar(dados: EnvioMensagem): Observable<{ mensagem_id: string; destinatarios: number }> {
    return this.http.post<{ mensagem_id: string; destinatarios: number }>(this.base, dados);
  }

  enviadas(pagina: number): Observable<Pagina<EnviadaResumo>> {
    return this.http.get<Pagina<EnviadaResumo>>(`${this.base}/enviadas`, { params: new HttpParams().set('pagina', pagina) });
  }

  enviada(id: string): Observable<EnviadaDetalhe> {
    return this.http.get<EnviadaDetalhe>(`${this.base}/enviadas/${id}`);
  }

  lembrar(id: string): Observable<{ lembrados: number }> {
    return this.http.post<{ lembrados: number }>(`${this.base}/enviadas/${id}/lembrar`, {});
  }
}
