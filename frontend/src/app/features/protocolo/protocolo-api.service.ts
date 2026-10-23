// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API do Protocolo (/api/protocolo).

import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { baixarArquivo } from '../../shared/utilitarios/download';
import { ListaNumeros, ListaTipos, NumeroProtocolo, PainelProtocolo, SequenciaProtocolo, TipoProtocolo } from './protocolo.models';

/** Faixa de um exercício; `liberar_a_partir_de` (opcional) reserva ao SAA o início da faixa. */
export interface DadosSequencia { exercicio: number; inicio: number; fim: number; liberar_a_partir_de?: number | null }

@Injectable({ providedIn: 'root' })
export class ProtocoloApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/protocolo`;

  tipos(): Observable<ListaTipos> {
    return this.http.get<ListaTipos>(`${this.base}/tipos`);
  }

  /** Cria o tipo e, com `sequencia`, a faixa do primeiro exercício na mesma chamada. */
  criarTipo(nome: string, sequencia?: DadosSequencia, setorId?: number | null): Observable<TipoProtocolo> {
    return this.http.post<TipoProtocolo>(`${this.base}/tipos`, { nome, ...(sequencia ? { sequencia } : {}), ...(setorId ? { setor_id: setorId } : {}) });
  }

  renomearTipo(id: string, nome: string): Observable<TipoProtocolo> {
    return this.http.put<TipoProtocolo>(`${this.base}/tipos/${id}`, { nome });
  }

  excluirSequencia(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/sequencias/${id}`);
  }

  excluirTipo(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/tipos/${id}`);
  }

  criarSequencia(tipoId: string, dados: DadosSequencia): Observable<SequenciaProtocolo> {
    return this.http.post<SequenciaProtocolo>(`${this.base}/tipos/${tipoId}/sequencias`, dados);
  }

  alterarFaixa(sequenciaId: string, dados: { inicio: number; fim: number; liberar_a_partir_de?: number | null }): Observable<SequenciaProtocolo> {
    return this.http.put<SequenciaProtocolo>(`${this.base}/sequencias/${sequenciaId}/faixa`, dados);
  }

  numeros(sequenciaId: string): Observable<ListaNumeros> {
    return this.http.get<ListaNumeros>(`${this.base}/sequencias/${sequenciaId}/numeros`);
  }

  proximo(sequenciaId: string, dados: { finalidade: string; contrato_id: string | null }): Observable<NumeroProtocolo> {
    return this.http.post<NumeroProtocolo>(`${this.base}/sequencias/${sequenciaId}/proximo`, dados);
  }

  lancar(numeroId: string, dados: { finalidade: string; contrato_id: string | null }): Observable<NumeroProtocolo> {
    return this.http.post<NumeroProtocolo>(`${this.base}/numeros/${numeroId}/reservar`, dados);
  }

  detalhe(numeroId: string): Observable<NumeroProtocolo> {
    return this.http.get<NumeroProtocolo>(`${this.base}/numeros/${numeroId}`);
  }

  liberar(numeroId: string, motivo: string): Observable<NumeroProtocolo> {
    return this.http.post<NumeroProtocolo>(`${this.base}/numeros/${numeroId}/liberar`, { motivo });
  }

  concluirSemDocumento(numeroId: string, motivo: string): Observable<NumeroProtocolo> {
    return this.http.post<NumeroProtocolo>(`${this.base}/numeros/${numeroId}/concluir-sem-documento`, { motivo });
  }

  anular(numeroId: string, motivo: string): Observable<NumeroProtocolo> {
    return this.http.post<NumeroProtocolo>(`${this.base}/numeros/${numeroId}/anular`, { motivo });
  }

  anexar(numeroId: string, arquivo: File): Observable<NumeroProtocolo> {
    const corpo = new FormData();
    corpo.append('arquivo', arquivo);
    return this.http.post<NumeroProtocolo>(`${this.base}/numeros/${numeroId}/anexo`, corpo);
  }

  /** Baixa o documento (exige o token: não dá para ser um link simples). Sigiloso: só o dono e o SuperRoot. */
  baixar(numeroId: string, nome: string) {
    return baixarArquivo(this.http, `${this.base}/numeros/${numeroId}/anexo`, nome);
  }

  sigilo(numeroId: string, sigiloso: boolean): Observable<NumeroProtocolo> {
    return this.http.put<NumeroProtocolo>(`${this.base}/numeros/${numeroId}/sigilo`, { sigiloso });
  }

  contrato(numeroId: string, contratoId: string | null): Observable<NumeroProtocolo> {
    return this.http.put<NumeroProtocolo>(`${this.base}/numeros/${numeroId}/contrato`, { contrato_id: contratoId });
  }

  /** Números do Protocolo vinculados a um contrato (a ficha do contrato mostra essa lista). */
  doContrato(contratoId: string): Observable<NumeroProtocolo[]> {
    return this.http.get<NumeroProtocolo[]>(`${this.base}/contratos/${contratoId}`);
  }

  painel(tipoId: string, ano: number): Observable<PainelProtocolo> {
    return this.http.get<PainelProtocolo>(`${this.base}/painel`, { params: new HttpParams().set('tipo_id', tipoId).set('ano', ano) });
  }

  exportar(formato: 'xlsx' | 'pdf', tipoId: string | null, exercicio: number | null) {
    let params = new HttpParams().set('formato', formato);
    if (tipoId) params = params.set('tipo_id', tipoId);
    if (exercicio) params = params.set('exercicio', exercicio);
    return baixarArquivo(this.http, `${this.base}/exportar?${params.toString()}`, `protocolo.${formato}`);
  }
}
