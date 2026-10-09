// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API da portaria de designação do contrato e das autoridades signatárias.

import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { baixarArquivo } from '../../../shared/utilitarios/download';
import { AutoridadePortaria, GravacaoAutoridade, PainelPortarias } from './contratos.models';

/** Portarias do contrato e autoridades (docs/endpoints/contratos-portarias.md). */
@Injectable({ providedIn: 'root' })
export class PortariasApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/contratos`;
  private readonly baseAutoridades = `${ambiente.urlApi}/portarias/autoridades`;

  painel(contratoId: string): Observable<PainelPortarias> {
    return this.http.get<PainelPortarias>(`${this.base}/${contratoId}/portarias`);
  }

  solicitar(contratoId: string, autoridadeId: string): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias`, { autoridade_id: autoridadeId });
  }

  reenviar(contratoId: string, portariaId: string): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/reenviar`, {});
  }

  aceitar(contratoId: string, portariaId: string): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/aceite`, {});
  }

  devolver(contratoId: string, portariaId: string, motivo: string): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/devolucao`, { motivo });
  }

  cancelar(contratoId: string, portariaId: string, motivo: string): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/cancelamento`, { motivo });
  }

  publicar(contratoId: string, portariaId: string, arquivo: File): Observable<PainelPortarias> {
    const dados = new FormData();
    dados.append('arquivo', arquivo);
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/publicacao`, dados);
  }

  /** Baixa a minuta com marca d'água "MINUTA". */
  baixarMinuta(contratoId: string, portariaId: string, formato: 'docx' | 'pdf') {
    return baixarArquivo(this.http, `${this.base}/${contratoId}/portarias/${portariaId}/minuta?formato=${formato}`, `minuta.${formato}`);
  }

  autoridades(): Observable<AutoridadePortaria[]> {
    return this.http.get<AutoridadePortaria[]>(this.baseAutoridades);
  }

  criarAutoridade(dados: GravacaoAutoridade): Observable<AutoridadePortaria[]> {
    return this.http.post<AutoridadePortaria[]>(this.baseAutoridades, dados);
  }

  alterarAutoridade(id: string, dados: GravacaoAutoridade): Observable<AutoridadePortaria[]> {
    return this.http.put<AutoridadePortaria[]>(`${this.baseAutoridades}/${id}`, dados);
  }

  excluirAutoridade(id: string): Observable<AutoridadePortaria[]> {
    return this.http.delete<AutoridadePortaria[]>(`${this.baseAutoridades}/${id}`);
  }
}
