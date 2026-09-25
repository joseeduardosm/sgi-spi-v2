// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API de diretórios LDAP.

import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { DiretorioLdap, GravacaoDiretorio, ResultadoSincronizacao, ResultadoTeste } from './ldap.models';

/** Serviço de acesso à API de diretórios LDAP (SuperRoot). */
@Injectable({ providedIn: 'root' })
export class LdapApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/ldap/diretorios`;

  /** Lista os diretórios cadastrados. */
  listar(): Observable<DiretorioLdap[]> {
    return this.http.get<DiretorioLdap[]>(this.base);
  }

  /** Cadastra um diretório. */
  criar(dados: GravacaoDiretorio): Observable<DiretorioLdap> {
    return this.http.post<DiretorioLdap>(this.base, dados);
  }

  /** Altera um diretório (senha vazia mantém a atual). */
  alterar(id: string, dados: GravacaoDiretorio): Observable<DiretorioLdap> {
    return this.http.put<DiretorioLdap>(`${this.base}/${id}`, dados);
  }

  /** Exclui um diretório. */
  excluir(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }

  /** Testa uma configuração ainda não salva (senha obrigatória). */
  testarSemSalvar(dados: GravacaoDiretorio): Observable<ResultadoTeste> {
    return this.http.post<ResultadoTeste>(`${this.base}/testar`, dados);
  }

  /** Testa a configuração salva; `senhaBind` substitui a senha salva só neste teste. */
  testar(id: string, senhaBind?: string): Observable<ResultadoTeste> {
    return this.http.post<ResultadoTeste>(`${this.base}/${id}/testar`, { senha_bind: senhaBind || null });
  }

  /** Sincroniza os usuários do diretório com o portal. */
  sincronizar(id: string): Observable<ResultadoSincronizacao> {
    return this.http.post<ResultadoSincronizacao>(`${this.base}/${id}/sincronizar`, null);
  }
}
