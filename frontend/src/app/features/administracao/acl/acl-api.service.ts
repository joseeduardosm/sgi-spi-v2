// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API de controle de acesso (ACL) e definir seus tipos.

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

/** Campos editáveis de um recurso. */
export type GravacaoRecurso = Pick<RecursoAcl, 'nome' | 'slug' | 'descricao' | 'url_base' | 'ativo'>;

/** Setor em forma reduzida (para listas de seleção). */
export interface OpcaoSetor {
  id: number;
  nome: string;
  sistemico: boolean;
}

/** Regra de acesso com os nomes já resolvidos. */
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

/** Corpo para criar ou alterar uma regra. */
export interface GravacaoRegra {
  recurso_id: number;
  nivel: NivelAcl;
  usuarios_ids: number[];
  setores_ids: number[];
}

/** Serviço de acesso à API de ACL (usado só pela tela de administração, do SuperRoot). */
@Injectable({ providedIn: 'root' })
export class AclApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/acl`;

  /** Lista todos os recursos cadastrados. */
  listarRecursos(): Observable<RecursoAcl[]> {
    return this.http.get<RecursoAcl[]>(`${this.base}/recursos`);
  }

  /** Cria (sem id) ou altera (com id) um recurso. */
  gravarRecurso(dados: GravacaoRecurso, id?: number): Observable<RecursoAcl> {
    return id
      ? this.http.put<RecursoAcl>(`${this.base}/recursos/${id}`, dados)
      : this.http.post<RecursoAcl>(`${this.base}/recursos`, dados);
  }

  /** Exclui um recurso e suas regras. */
  excluirRecurso(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/recursos/${id}`);
  }

  /** Lista as regras, opcionalmente de um só recurso. */
  listarRegras(recursoId?: number): Observable<RegraAcl[]> {
    return this.http.get<RegraAcl[]>(`${this.base}/regras`, { params: recursoId ? { recurso_id: recursoId } : {} });
  }

  /** Cria (sem id) ou altera (com id) uma regra. */
  gravarRegra(dados: GravacaoRegra, id?: number): Observable<RegraAcl> {
    return id ? this.http.put<RegraAcl>(`${this.base}/regras/${id}`, dados) : this.http.post<RegraAcl>(`${this.base}/regras`, dados);
  }

  /** Exclui uma regra. */
  excluirRegra(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/regras/${id}`);
  }

  /** Nível efetivo de um usuário em cada recurso (consulta do SuperRoot). */
  acessoEfetivo(usuarioId: number): Observable<AcessoEfetivo[]> {
    return this.http.get<AcessoEfetivo[]>(`${this.base}/efetivo/${usuarioId}`);
  }
}
