// Criado por José Eduardo Santana Martins
// Este arquivo serve para ler os manuais do BookStack pela API do portal (estantes, livros, páginas, busca e imagens).

import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';

export interface ResumoLivro { id: number; nome: string; descricao: string; }
export interface Estante { id: number; nome: string; descricao: string; livros: ResumoLivro[]; }
export interface ListaManuais { estantes: Estante[]; livros_avulsos: ResumoLivro[]; url_origem: string; }

/** Entrada do sumário: capítulo (com `paginas`) ou página. */
export interface ItemSumario { tipo: 'pagina' | 'capitulo'; id: number; nome: string; paginas: ItemSumario[]; }
export interface DetalheLivro {
  id: number; nome: string; descricao: string; sumario: ItemSumario[]; primeira_pagina_id: number | null; url_origem: string;
}

export interface PaginaVizinha { id: number; nome: string; }
export interface DetalhePagina {
  id: number; nome: string; livro_id: number; livro_nome: string; capitulo_id: number | null; capitulo_nome: string | null;
  html: string; atualizado_em: string | null; anterior: PaginaVizinha | null; proxima: PaginaVizinha | null; url_origem: string;
}

export interface ResultadoBuscaManual {
  tipo: 'pagina' | 'capitulo' | 'livro'; id: number; nome: string; livro_id: number | null; livro_nome: string | null; trecho: string; rota: string;
}

/** Manuais do BookStack lidos pelo portal (somente leitura). */
@Injectable({ providedIn: 'root' })
export class ManuaisService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/manuais`;

  listar(): Observable<ListaManuais> {
    return this.http.get<ListaManuais>(this.base);
  }

  livro(id: number): Observable<DetalheLivro> {
    return this.http.get<DetalheLivro>(`${this.base}/livros/${id}`);
  }

  pagina(id: number): Observable<DetalhePagina> {
    return this.http.get<DetalhePagina>(`${this.base}/paginas/${id}`);
  }

  buscar(q: string): Observable<{ itens: ResultadoBuscaManual[] }> {
    return this.http.get<{ itens: ResultadoBuscaManual[] }>(`${this.base}/busca`, { params: { q } });
  }

  /** Imagem do manual (o `<img src>` não leva o token; por isso o portal baixa pela API e usa um endereço local). */
  imagem(caminho: string): Observable<Blob> {
    return this.http.get(`${this.base}/imagem`, { params: { caminho }, responseType: 'blob' });
  }
}
