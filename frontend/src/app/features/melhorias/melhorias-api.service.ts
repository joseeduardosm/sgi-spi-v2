// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API do Módulo Melhorias (envio, minhas sugestões, triagem e relatórios).

import { HttpClient, HttpParams, HttpResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { baixarArquivo } from '../../shared/utilitarios/download';
import { ConversaoTarefa, FiltrosTriagem, Pagina, PaginaTriagem, SugestaoAutor, SugestaoTriagem, Tratamento } from './melhorias.models';

@Injectable({ providedIn: 'root' })
export class MelhoriasApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/melhorias';

  /** Envio em multipart: `dados` (texto e tela) e até 3 prints em `arquivos`. */
  enviar(texto: string, tela: string, prints: File[]): Observable<SugestaoAutor> {
    const corpo = new FormData();
    corpo.append('dados', JSON.stringify({ texto, tela }));
    for (const p of prints) corpo.append('arquivos', p, p.name);
    return this.http.post<SugestaoAutor>(`${this.base}/sugestoes`, corpo);
  }

  acesso(): Observable<{ triagem: boolean }> {
    return this.http.get<{ triagem: boolean }>(`${this.base}/acesso`);
  }

  minhas(pagina = 1, tamanho = 20): Observable<Pagina<SugestaoAutor>> {
    return this.http.get<Pagina<SugestaoAutor>>(`${this.base}/minhas`, { params: { pagina, tamanho } });
  }

  listar(filtros: FiltrosTriagem, pagina = 1, tamanho = 20): Observable<PaginaTriagem> {
    return this.http.get<PaginaTriagem>(`${this.base}/sugestoes`, { params: this.parametros(filtros).set('pagina', pagina).set('tamanho', tamanho) });
  }

  detalhe(numero: number): Observable<SugestaoTriagem> {
    return this.http.get<SugestaoTriagem>(`${this.base}/sugestoes/${numero}`);
  }

  tratar(numero: number, dados: Tratamento): Observable<SugestaoTriagem> {
    return this.http.put<SugestaoTriagem>(`${this.base}/sugestoes/${numero}`, dados);
  }

  converterEmTarefa(numero: number, dados: ConversaoTarefa): Observable<SugestaoTriagem> {
    return this.http.post<SugestaoTriagem>(`${this.base}/sugestoes/${numero}/tarefa`, dados);
  }

  exportar(filtros: FiltrosTriagem): Observable<HttpResponse<Blob>> {
    return baixarArquivo(this.http, `${this.base}/sugestoes/exportar?${this.parametros(filtros).toString()}`, 'melhorias.xlsx');
  }

  relatorio(filtros: FiltrosTriagem): Observable<HttpResponse<Blob>> {
    return baixarArquivo(this.http, `${this.base}/sugestoes/relatorio?${this.parametros(filtros).toString()}`, 'relatorio_melhorias.pdf');
  }

  baixarPrint(url: string, nome: string): Observable<HttpResponse<Blob>> {
    return baixarArquivo(this.http, url, nome);
  }

  /** Só os filtros preenchidos vão na URL. */
  private parametros(f: FiltrosTriagem): HttpParams {
    let p = new HttpParams();
    for (const [chave, valor] of Object.entries(f)) if (valor) p = p.set(chave, String(valor).trim());
    return p;
  }
}
