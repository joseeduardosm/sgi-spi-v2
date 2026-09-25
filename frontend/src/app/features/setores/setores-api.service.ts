import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { OpcaoUsuario } from '../../core/modelos/usuario.model';

/** Contratos de /api/setores (ver docs/endpoints/setores.md). */
export interface Setor {
  id: number;
  nome: string;
  setor_pai_id: number | null;
  setor_pai_nome: string | null;
  lider_id: number | null;
  lider_nome: string | null;
  sistemico: boolean;
  ativo: boolean;
  total_membros: number;
  total_subordinados: number;
  criado_em: string;
  atualizado_em: string;
}

export interface DetalheSetor extends Setor {
  membros: OpcaoUsuario[];
}

export interface GravacaoSetor {
  nome: string;
  setor_pai_id: number | null;
  lider_id: number | null;
  sistemico: boolean;
  ativo: boolean;
  membros_ids: number[];
}

@Injectable({ providedIn: 'root' })
export class SetoresApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/setores`;

  listar(busca = ''): Observable<Setor[]> {
    return this.http.get<Setor[]>(this.base, { params: busca ? { busca } : {} });
  }

  consultar(id: number): Observable<DetalheSetor> {
    return this.http.get<DetalheSetor>(`${this.base}/${id}`);
  }

  criar(dados: GravacaoSetor): Observable<DetalheSetor> {
    return this.http.post<DetalheSetor>(this.base, dados);
  }

  alterar(id: number, dados: GravacaoSetor): Observable<DetalheSetor> {
    return this.http.put<DetalheSetor>(`${this.base}/${id}`, dados);
  }

  excluir(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }
}
