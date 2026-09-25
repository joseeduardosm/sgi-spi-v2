import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { OpcaoUsuario, Usuario } from '../../core/modelos/usuario.model';
import { AlteracaoUsuario, CriacaoUsuario, DadosPerfil, DetalheUsuario, PaginaUsuarios, PerfilLeitura } from './usuarios.models';

export interface FiltroUsuarios {
  busca?: string;
  situacao?: 'ativos' | 'inativos' | 'todos';
  origem?: string;
  pagina?: number;
  tamanho_pagina?: number;
}

@Injectable({ providedIn: 'root' })
export class UsuariosApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/usuarios`;
  private readonly baseAutenticacao = `${ambiente.urlApi}/autenticacao`;

  listar(filtro: FiltroUsuarios): Observable<PaginaUsuarios> {
    let parametros = new HttpParams();
    for (const [chave, valor] of Object.entries(filtro)) {
      if (valor !== undefined && valor !== null && valor !== '') parametros = parametros.set(chave, String(valor));
    }
    return this.http.get<PaginaUsuarios>(this.base, { params: parametros });
  }

  opcoes = (busca: string): Observable<OpcaoUsuario[]> =>
    this.http.get<OpcaoUsuario[]>(`${this.base}/opcoes`, { params: { busca, limite: 20 } });

  consultar(id: number): Observable<DetalheUsuario> {
    return this.http.get<DetalheUsuario>(`${this.base}/${id}`);
  }

  criar(dados: CriacaoUsuario): Observable<DetalheUsuario> {
    return this.http.post<DetalheUsuario>(this.base, dados);
  }

  alterar(id: number, dados: AlteracaoUsuario): Observable<DetalheUsuario> {
    return this.http.put<DetalheUsuario>(`${this.base}/${id}`, dados);
  }

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

  opcoesGestor = (busca: string): Observable<OpcaoUsuario[]> =>
    this.http.get<OpcaoUsuario[]>(`${this.baseAutenticacao}/perfil/opcoes-gestor`, { params: { busca, limite: 20 } });
}
