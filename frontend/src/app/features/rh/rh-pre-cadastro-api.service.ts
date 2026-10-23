// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API da ficha de pré-cadastro do RH (/api/rh/pre-cadastros).

import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { baixarArquivo } from '../../shared/utilitarios/download';
import { GravacaoFicha, LeituraFicha, LoginDisponivel, ResultadoImportacaoFichas, ResumoFicha } from './rh-pre-cadastro.models';

@Injectable({ providedIn: 'root' })
export class RhPreCadastroApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/rh/pre-cadastros`;

  listar(busca = '', status = '', pendentesDeValidacao = false): Observable<ResumoFicha[]> {
    let params = new HttpParams();
    if (pendentesDeValidacao) params = params.set('pendentes_de_validacao', true);
    if (busca) params = params.set('busca', busca);
    if (status) params = params.set('status', status);
    return this.http.get<ResumoFicha[]>(this.base, { params });
  }

  obter(id: number): Observable<LeituraFicha> {
    return this.http.get<LeituraFicha>(`${this.base}/${id}`);
  }

  criar(dados: GravacaoFicha): Observable<LeituraFicha> {
    return this.http.post<LeituraFicha>(this.base, dados);
  }

  alterar(id: number, dados: GravacaoFicha): Observable<LeituraFicha> {
    return this.http.put<LeituraFicha>(`${this.base}/${id}`, dados);
  }

  cancelar(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }

  loginDisponivel(login: string, fichaId: number | null): Observable<LoginDisponivel> {
    let params = new HttpParams().set('login', login);
    if (fichaId) params = params.set('ficha_id', fichaId);
    return this.http.get<LoginDisponivel>(`${this.base}/login-disponivel`, { params });
  }

  /** Baixa o modelo XLSX da carga em lote. */
  modeloImportacao() {
    return baixarArquivo(this.http, `${this.base}/importacao/modelo`, 'modelo-fichas-pre-cadastro.xlsx');
  }

  /** Prévia (`gravar = false`, não grava) ou importação (`true`, tudo ou nada). */
  importar(arquivo: File, gravar: boolean): Observable<ResultadoImportacaoFichas> {
    const corpo = new FormData();
    corpo.append('arquivo', arquivo);
    return this.http.post<ResultadoImportacaoFichas>(`${this.base}/importacao${gravar ? '' : '/previa'}`, corpo);
  }
}
