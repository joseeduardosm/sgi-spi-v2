import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { AcessoEfetivo, NivelAcl } from '../../../core/acesso/acesso.service';
import { OpcaoUsuario } from '../../../core/modelos/usuario.model';

/** Contratos de /api/acl (ver docs/endpoints/acl.md). */
export interface RecursoAcl {
  id: number;
  nome: string;
  slug: string;
  descricao: string;
  url_base: string;
  ativo: boolean;
  total_regras: number;
  criado_em: string;
  atualizado_em: string;
}

export type GravacaoRecurso = Pick<RecursoAcl, 'nome' | 'slug' | 'descricao' | 'url_base' | 'ativo'>;

export interface OpcaoSetor {
  id: number;
  nome: string;
  sistemico: boolean;
}

export interface RegraAcl {
  id: number;
  recurso_id: number;
  recurso_nome: string;
  recurso_slug: string;
  nivel: NivelAcl;
  usuarios: OpcaoUsuario[];
  setores: OpcaoSetor[];
  criado_em: string;
  atualizado_em: string;
}

export interface GravacaoRegra {
  recurso_id: number;
  nivel: NivelAcl;
  usuarios_ids: number[];
  setores_ids: number[];
}

@Injectable({ providedIn: 'root' })
export class AclApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/acl`;

  listarRecursos(): Observable<RecursoAcl[]> {
    return this.http.get<RecursoAcl[]>(`${this.base}/recursos`);
  }

  gravarRecurso(dados: GravacaoRecurso, id?: number): Observable<RecursoAcl> {
    return id
      ? this.http.put<RecursoAcl>(`${this.base}/recursos/${id}`, dados)
      : this.http.post<RecursoAcl>(`${this.base}/recursos`, dados);
  }

  excluirRecurso(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/recursos/${id}`);
  }

  listarRegras(recursoId?: number): Observable<RegraAcl[]> {
    return this.http.get<RegraAcl[]>(`${this.base}/regras`, { params: recursoId ? { recurso_id: recursoId } : {} });
  }

  gravarRegra(dados: GravacaoRegra, id?: number): Observable<RegraAcl> {
    return id ? this.http.put<RegraAcl>(`${this.base}/regras/${id}`, dados) : this.http.post<RegraAcl>(`${this.base}/regras`, dados);
  }

  excluirRegra(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/regras/${id}`);
  }

  acessoEfetivo(usuarioId: number): Observable<AcessoEfetivo[]> {
    return this.http.get<AcessoEfetivo[]>(`${this.base}/efetivo/${usuarioId}`);
  }
}
