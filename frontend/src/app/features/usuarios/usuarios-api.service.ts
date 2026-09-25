// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API de usuários e do próprio perfil.

import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { OpcaoUsuario, Usuario } from '../../core/modelos/usuario.model';
import { AlteracaoUsuario, CriacaoUsuario, DadosPerfil, DetalheUsuario, PaginaUsuarios, PerfilLeitura } from './usuarios.models';

/** Filtros aceitos pela listagem de usuários (vão como parâmetros na URL). */
export interface FiltroUsuarios {
  busca?: string;
  situacao?: 'ativos' | 'inativos' | 'todos';
  origem?: string;
  pagina?: number;
  tamanho_pagina?: number;
}

/** Serviço de acesso à API de usuários; as telas nunca chamam o HttpClient diretamente. */
@Injectable({ providedIn: 'root' })
export class UsuariosApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/usuarios`;
  private readonly baseAutenticacao = `${ambiente.urlApi}/autenticacao`;

  /** Lista paginada; envia só os filtros preenchidos. */
  listar(filtro: FiltroUsuarios): Observable<PaginaUsuarios> {
    let parametros = new HttpParams();
    for (const [chave, valor] of Object.entries(filtro)) {
      if (valor !== undefined && valor !== null && valor !== '') parametros = parametros.set(chave, String(valor));
    }
    return this.http.get<PaginaUsuarios>(this.base, { params: parametros });
  }

  /** Busca curta de usuários para seletores (escrita como arrow function para ser passada como `fonte`). */
  opcoes = (busca: string): Observable<OpcaoUsuario[]> =>
    this.http.get<OpcaoUsuario[]>(`${this.base}/opcoes`, { params: { busca, limite: 20 } });

  /** Detalhe de um usuário. */
  consultar(id: number): Observable<DetalheUsuario> {
    return this.http.get<DetalheUsuario>(`${this.base}/${id}`);
  }

  /** Cria uma conta local (SuperRoot). */
  criar(dados: CriacaoUsuario): Observable<DetalheUsuario> {
    return this.http.post<DetalheUsuario>(this.base, dados);
  }

  /** Altera um usuário (SuperRoot). */
  alterar(id: number, dados: AlteracaoUsuario): Observable<DetalheUsuario> {
    return this.http.put<DetalheUsuario>(`${this.base}/${id}`, dados);
  }

  /** Exclui um usuário (SuperRoot). */
  excluir(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }

  // --- Próprio perfil (liberado mesmo com o perfil pendente) ---
  meuPerfil(): Observable<PerfilLeitura> {
    return this.http.get<PerfilLeitura>(`${this.baseAutenticacao}/perfil`);
  }

  revisarMeuPerfil(dados: DadosPerfil): Observable<Usuario> {
    return this.http.put<Usuario>(`${this.baseAutenticacao}/perfil`, dados);
  }

  /** Busca de usuários para o campo "gestor imediato" do próprio perfil. */
  opcoesGestor = (busca: string): Observable<OpcaoUsuario[]> =>
    this.http.get<OpcaoUsuario[]>(`${this.baseAutenticacao}/perfil/opcoes-gestor`, { params: { busca, limite: 20 } });
}
