// Criado por José Eduardo Santana Martins
// Este arquivo serve para carregar os atalhos fixos (por categoria) e gerenciá-los na tela de administração.

import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';

/** Atalho fixo (`LeituraAtalho` da API): rota interna do SGI ou endereço externo. */
export interface AtalhoFixo {
  id: number;
  categoria_id: number;
  titulo: string;
  url: string;
  externo: boolean;
  nova_aba: boolean;
  ordem: number;
  ativo: boolean;
}

/** Categoria com seus atalhos (`LeituraCategoriaAtalho` da API). */
export interface CategoriaAtalho {
  id: number;
  nome: string;
  ordem: number;
  ativo: boolean;
  atalhos: AtalhoFixo[];
}

export interface GravacaoCategoria {
  nome: string;
  ordem: number;
  ativo: boolean;
}

export interface GravacaoAtalho {
  categoria_id: number;
  titulo: string;
  url: string;
  nova_aba: boolean | null;
  ordem: number;
  ativo: boolean;
}

/** Atalhos fixos para todos os usuários (internos e externos), organizados em categorias. */
@Injectable({ providedIn: 'root' })
export class AtalhosFixosService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/atalhos`;

  /** Categorias ativas com ao menos um atalho ativo, como a barra lateral exibe. */
  readonly categorias = signal<CategoriaAtalho[]>([]);

  /** Recarrega os atalhos da barra lateral; falha silenciosa (a barra funciona sem eles). */
  carregar(): void {
    this.http.get<{ categorias: CategoriaAtalho[] }>(this.base).subscribe({
      next: (r) => this.categorias.set(r.categorias),
      error: () => this.categorias.set([]),
    });
  }

  /** Lista completa da gestão (inclui inativos e categorias vazias). */
  gestao(): Observable<{ categorias: CategoriaAtalho[] }> {
    return this.http.get<{ categorias: CategoriaAtalho[] }>(`${this.base}/gestao`);
  }

  criarCategoria(dados: GravacaoCategoria): Observable<CategoriaAtalho> {
    return this.http.post<CategoriaAtalho>(`${this.base}/categorias`, dados).pipe(tap(() => this.carregar()));
  }

  alterarCategoria(id: number, dados: GravacaoCategoria): Observable<CategoriaAtalho> {
    return this.http.put<CategoriaAtalho>(`${this.base}/categorias/${id}`, dados).pipe(tap(() => this.carregar()));
  }

  excluirCategoria(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/categorias/${id}`).pipe(tap(() => this.carregar()));
  }

  criarAtalho(dados: GravacaoAtalho): Observable<AtalhoFixo> {
    return this.http.post<AtalhoFixo>(`${this.base}/itens`, dados).pipe(tap(() => this.carregar()));
  }

  alterarAtalho(id: number, dados: GravacaoAtalho): Observable<AtalhoFixo> {
    return this.http.put<AtalhoFixo>(`${this.base}/itens/${id}`, dados).pipe(tap(() => this.carregar()));
  }

  excluirAtalho(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/itens/${id}`).pipe(tap(() => this.carregar()));
  }
}
