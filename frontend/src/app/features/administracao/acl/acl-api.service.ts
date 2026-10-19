// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API de controle de acesso (ACL) e definir seus tipos.

import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { AcessoEfetivo, NiveisTextos, NivelAcl } from '../../../core/acesso/acesso.service';
import { OpcaoUsuario } from '../../../core/modelos/usuario.model';

/** Ação (permissão independente) que um módulo oferece nos perfis. */
export interface AcaoModulo {
  /** `LEITURA`, `MODIFICACAO`, `CONTROLE_TOTAL` ou o código de uma ação própria do módulo (ex.: `LANCAR_OB`). */
  codigo: string;
  rotulo: string;
  descricao: string;
}

/** Contratos de /api/acl (ver docs/endpoints/acl.md). */
export interface RecursoAcl {
  id: number;
  nome: string;
  slug: string;
  descricao: string;
  url_base: string;
  ativo: boolean;
  total_regras: number;
  total_perfis?: number;
  niveis?: NiveisTextos;
  /** Ações (permissões independentes) que o módulo oferece nos perfis. */
  acoes?: AcaoModulo[];
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
  niveis?: NiveisTextos;
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

/** Perfil na lista da administração. */
export interface PerfilAcl {
  id: number;
  nome: string;
  descricao: string;
  ativo: boolean;
  total_usuarios: number;
  total_direitos: number;
  criado_em: string;
  atualizado_em: string;
}

/** Módulo adicionado ao perfil, com as ações marcadas. */
export interface DireitoPerfilModulo {
  recurso_id: number;
  recurso_nome: string;
  recurso_slug: string;
  acoes: string[];
  acoes_disponiveis: AcaoModulo[];
}

/** Usuário que tem o perfil. */
export interface UsuarioDoPerfil {
  id: number;
  login: string;
  nome_completo: string;
  cargo: string | null;
  ativo: boolean;
  padrao: boolean;
}

/** Perfil com a matriz de direitos e os usuários. */
export interface DetalhePerfil extends PerfilAcl {
  direitos: DireitoPerfilModulo[];
  usuarios: UsuarioDoPerfil[];
  /** Setores e grupos sistêmicos que recebem o perfil (os membros passam a tê-lo). */
  setores: { id: number; nome: string; sistemico: boolean; setor_pai_id: number | null }[];
}

/** Perfil atribuído a um usuário. */
export interface PerfilDoUsuario {
  perfil_id: number;
  nome: string;
  ativo: boolean;
  padrao: boolean;
  /** Setores/grupos do usuário que dão este perfil. */
  via_setores: string[];
  /** Atribuído diretamente ao usuário (falso = só recebe pelo setor). */
  direto: boolean;
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
  acessoEfetivo(usuarioId: number, perfilId?: number): Observable<AcessoEfetivo[]> {
    return this.http.get<AcessoEfetivo[]>(`${this.base}/efetivo/${usuarioId}`, { params: perfilId ? { perfil_id: perfilId } : {} });
  }

  // --- Perfis ---
  listarPerfis(): Observable<PerfilAcl[]> {
    return this.http.get<PerfilAcl[]>(`${this.base}/perfis`);
  }

  detalharPerfil(id: number): Observable<DetalhePerfil> {
    return this.http.get<DetalhePerfil>(`${this.base}/perfis/${id}`);
  }

  /** Cria (sem id) ou altera (com id) o cadastro do perfil. */
  gravarPerfil(dados: Pick<PerfilAcl, 'nome' | 'descricao' | 'ativo'>, id?: number): Observable<DetalhePerfil> {
    return id ? this.http.put<DetalhePerfil>(`${this.base}/perfis/${id}`, dados) : this.http.post<DetalhePerfil>(`${this.base}/perfis`, dados);
  }

  excluirPerfil(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/perfis/${id}`);
  }

  /** Adiciona o módulo ao perfil ou troca as ações dele. */
  definirModuloPerfil(id: number, recursoId: number, acoes: string[]): Observable<DetalhePerfil> {
    return this.http.put<DetalhePerfil>(`${this.base}/perfis/${id}/modulos/${recursoId}`, { acoes });
  }

  removerModuloPerfil(id: number, recursoId: number): Observable<DetalhePerfil> {
    return this.http.delete<DetalhePerfil>(`${this.base}/perfis/${id}/modulos/${recursoId}`);
  }

  definirUsuariosPerfil(id: number, usuariosIds: number[]): Observable<DetalhePerfil> {
    return this.http.put<DetalhePerfil>(`${this.base}/perfis/${id}/usuarios`, { usuarios_ids: usuariosIds });
  }

  definirSetoresPerfil(id: number, setoresIds: number[]): Observable<DetalhePerfil> {
    return this.http.put<DetalhePerfil>(`${this.base}/perfis/${id}/setores`, { setores_ids: setoresIds });
  }

  perfisDoUsuario(usuarioId: number): Observable<PerfilDoUsuario[]> {
    return this.http.get<PerfilDoUsuario[]>(`${this.base}/usuarios/${usuarioId}/perfis`);
  }

  definirPerfisDoUsuario(usuarioId: number, perfisIds: number[], padraoId: number | null): Observable<PerfilDoUsuario[]> {
    return this.http.put<PerfilDoUsuario[]>(`${this.base}/usuarios/${usuarioId}/perfis`, { perfis_ids: perfisIds, padrao_id: padraoId });
  }
}
