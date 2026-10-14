// Criado por José Eduardo Santana Martins
// Este arquivo serve para ler e gravar, na conta do usuário, as colunas que ele escolheu mostrar em cada listagem.
import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';

/** Resposta de `GET /api/preferencias/colunas/{tela}`: `colunas` (visão pessoal) nulo = a pessoa nunca escolheu; `padrao_global` é a visão de todos que não têm a pessoal. */
export interface PreferenciaColunas { tela: string; colunas: string[] | null; padrao_global: string[] | null }
export type VisaoColunas = 'pessoal' | 'global';

/** Colunas das listagens por usuário e tela (`/api/preferencias/colunas/{tela}`): a escolha acompanha a conta em qualquer navegador. */
@Injectable({ providedIn: 'root' })
export class PreferenciasColunasService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/preferencias/colunas`;

  ler(tela: string): Observable<PreferenciaColunas> { return this.http.get<PreferenciaColunas>(`${this.base}/${tela}`); }
  salvar(tela: string, colunas: string[], visao: VisaoColunas = 'pessoal'): Observable<PreferenciaColunas> { return this.http.put<PreferenciaColunas>(`${this.base}/${tela}`, { colunas }, { params: { visao } }); }
  restaurar(tela: string, visao: VisaoColunas = 'pessoal'): Observable<void> { return this.http.delete<void>(`${this.base}/${tela}`, { params: { visao } }); }
}
