// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API da Reserva de Espaços (/api/reserva-espacos).

import { HttpClient, HttpParams, HttpResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { baixarArquivo } from '../../shared/utilitarios/download';
import {
  Configuracao, Contexto, Espaco, EscopoCancelamento, GravacaoReserva, ListaReservas, Painel, Reserva, ReservaDetalhe, ResultadoSolicitacao, StatusReserva, UsuarioBusca,
} from './reservas.models';

export interface FiltrosReservas {
  status?: StatusReserva | '';
  espaco_id?: number | '';
  inicio?: string;
  fim?: string;
  busca?: string;
}

@Injectable({ providedIn: 'root' })
export class ReservasApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/reserva-espacos';

  contexto(): Observable<Contexto> {
    return this.http.get<Contexto>(`${this.base}/contexto`);
  }

  agenda(inicio: string, fim: string, espacoId?: number | ''): Observable<Reserva[]> {
    let params = new HttpParams().set('inicio', inicio).set('fim', fim);
    if (espacoId) params = params.set('espaco_id', espacoId);
    return this.http.get<Reserva[]>(`${this.base}/agenda`, { params });
  }

  disponibilidade(data: string, horaInicio: string, horaFim: string): Observable<Espaco[]> {
    return this.http.get<Espaco[]>(`${this.base}/disponibilidade`, { params: { data, hora_inicio: horaInicio, hora_fim: horaFim } });
  }

  minhas(status: StatusReserva | '' = ''): Observable<Reserva[]> {
    return this.http.get<Reserva[]>(`${this.base}/minhas`, { params: status ? { status } : {} });
  }

  listar(filtros: FiltrosReservas, pagina = 1, tamanho = 50): Observable<ListaReservas> {
    return this.http.get<ListaReservas>(`${this.base}/reservas`, { params: this.parametros(filtros).set('pagina', pagina).set('tamanho', tamanho) });
  }

  exportar(filtros: FiltrosReservas): Observable<HttpResponse<Blob>> {
    return baixarArquivo(this.http, `${this.base}/exportar?${this.parametros(filtros).toString()}`, 'reservas-espacos.xlsx');
  }

  fila(): Observable<Reserva[]> {
    return this.http.get<Reserva[]>(`${this.base}/fila`);
  }

  detalhe(id: number): Observable<ReservaDetalhe> {
    return this.http.get<ReservaDetalhe>(`${this.base}/reservas/${id}`);
  }

  solicitar(dados: GravacaoReserva, predefinida: boolean): Observable<ResultadoSolicitacao> {
    return this.http.post<ResultadoSolicitacao>(`${this.base}/reservas${predefinida ? '/predefinida' : ''}`, dados);
  }

  editar(id: number, dados: Pick<GravacaoReserva, 'espaco_id' | 'data' | 'hora_inicio' | 'hora_fim' | 'titulo' | 'observacoes' | 'participantes'>): Observable<Reserva> {
    return this.http.put<Reserva>(`${this.base}/reservas/${id}`, dados);
  }

  analisar(id: number, decisao: 'deferir' | 'indeferir', justificativa = ''): Observable<Reserva[]> {
    return this.http.post<Reserva[]>(`${this.base}/reservas/${id}/analise`, { decisao, justificativa });
  }

  cancelar(id: number, escopo: EscopoCancelamento, motivo: string, de?: string, ate?: string): Observable<Reserva[]> {
    return this.http.post<Reserva[]>(`${this.base}/reservas/${id}/cancelamento`, { escopo, motivo, de: de || null, ate: ate || null });
  }

  usuarios(busca: string): Observable<UsuarioBusca[]> {
    return this.http.get<UsuarioBusca[]>(`${this.base}/usuarios`, { params: { busca } });
  }

  salvarEspaco(dados: Omit<Espaco, 'id'>, id?: number): Observable<Espaco> {
    return id ? this.http.put<Espaco>(`${this.base}/espacos/${id}`, dados) : this.http.post<Espaco>(`${this.base}/espacos`, dados);
  }

  excluirEspaco(id: number): Observable<{ resultado: 'excluido' | 'inativado' }> {
    return this.http.delete<{ resultado: 'excluido' | 'inativado' }>(`${this.base}/espacos/${id}`);
  }

  painel(ano: number, mes: number): Observable<Painel> {
    return this.http.get<Painel>(`${this.base}/painel`, { params: { ano, mes } });
  }

  configuracao(): Observable<Configuracao> {
    return this.http.get<Configuracao>(`${this.base}/configuracao`);
  }

  gravarConfiguracao(dados: Omit<Configuracao, 'fiscais'> & { fiscais_ids: number[] }): Observable<Configuracao> {
    return this.http.put<Configuracao>(`${this.base}/configuracao`, dados);
  }

  private parametros(f: FiltrosReservas): HttpParams {
    let params = new HttpParams();
    for (const [chave, valor] of Object.entries(f)) if (valor !== undefined && valor !== '') params = params.set(chave, String(valor));
    return params;
  }
}
