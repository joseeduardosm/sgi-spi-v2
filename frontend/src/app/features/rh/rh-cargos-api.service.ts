// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API de cargos, ocupações, organograma e histórico funcional do Módulo RH (/api/rh).

import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { baixarArquivo } from '../../shared/utilitarios/download';
import { Cargo, GravacaoCargo, HistoricoUsuario, MotivoFim, NoOrganograma, PendenciaCargo, TipoCargo } from './rh-cargos.models';

/** Filtros da lista de cargos. */
export interface FiltrosCargos { setor_id?: number | null; tipo_id?: number | null; situacao?: 'vago' | 'ocupado' | ''; busca?: string; incluir_inativos?: boolean }

/** Filtros do histórico funcional. */
export interface FiltrosHistorico { tipos?: string[]; de?: string; ate?: string }

@Injectable({ providedIn: 'root' })
export class RhCargosApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/rh`;

  tipos(): Observable<TipoCargo[]> {
    return this.http.get<TipoCargo[]>(`${this.base}/tipos-cargo`);
  }

  cargos(filtros: FiltrosCargos = {}): Observable<Cargo[]> {
    let params = new HttpParams();
    if (filtros.setor_id) params = params.set('setor_id', filtros.setor_id);
    if (filtros.tipo_id) params = params.set('tipo_id', filtros.tipo_id);
    if (filtros.situacao) params = params.set('situacao', filtros.situacao);
    if (filtros.busca) params = params.set('busca', filtros.busca);
    if (filtros.incluir_inativos) params = params.set('incluir_inativos', true);
    return this.http.get<Cargo[]>(`${this.base}/cargos`, { params });
  }

  criar(dados: GravacaoCargo): Observable<Cargo[]> {
    return this.http.post<Cargo[]>(`${this.base}/cargos`, dados);
  }

  alterar(id: number, dados: GravacaoCargo): Observable<Cargo> {
    return this.http.put<Cargo>(`${this.base}/cargos/${id}`, dados);
  }

  excluir(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/cargos/${id}`);
  }

  ocupar(id: number, usuarioId: number, inicio: string | null, ato: string): Observable<Cargo> {
    return this.http.post<Cargo>(`${this.base}/cargos/${id}/ocupacao`, { usuario_id: usuarioId, inicio: inicio || null, ato });
  }

  vagar(id: number, fim: string | null, motivo: MotivoFim, ato: string): Observable<Cargo> {
    return this.http.post<Cargo>(`${this.base}/cargos/${id}/vacancia`, { fim: fim || null, motivo, ato });
  }

  aReconciliar(): Observable<PendenciaCargo[]> {
    return this.http.get<PendenciaCargo[]>(`${this.base}/cargos-a-reconciliar`);
  }

  vincular(usuarioId: number, setorId: number | null, cargoId: number | null): Observable<Cargo> {
    return this.http.post<Cargo>(`${this.base}/cargos-a-reconciliar/${usuarioId}`, { setor_id: setorId, cargo_id: cargoId });
  }

  organograma(incluirVagas = true): Observable<NoOrganograma[]> {
    return this.http.get<NoOrganograma[]>(`${this.base}/organograma`, { params: { incluir_vagas: incluirVagas } });
  }

  historico(usuarioId: number, filtros: FiltrosHistorico = {}): Observable<HistoricoUsuario> {
    return this.http.get<HistoricoUsuario>(`${this.base}/usuarios/${usuarioId}/historico`, { params: this.parametros(filtros) });
  }

  baixarHistoricoPdf(usuarioId: number, login: string, filtros: FiltrosHistorico = {}) {
    const consulta = this.parametros(filtros).toString();
    return baixarArquivo(this.http, `${this.base}/usuarios/${usuarioId}/historico.pdf${consulta ? '?' + consulta : ''}`, `historico-${login}.pdf`);
  }

  private parametros(filtros: FiltrosHistorico): HttpParams {
    let params = new HttpParams();
    for (const t of filtros.tipos ?? []) params = params.append('tipos', t);
    if (filtros.de) params = params.set('de', filtros.de);
    if (filtros.ate) params = params.set('ate', filtros.ate);
    return params;
  }
}
