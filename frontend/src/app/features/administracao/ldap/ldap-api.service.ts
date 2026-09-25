import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { DiretorioLdap, GravacaoDiretorio, ResultadoSincronizacao, ResultadoTeste } from './ldap.models';

@Injectable({ providedIn: 'root' })
export class LdapApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/ldap/diretorios`;

  listar(): Observable<DiretorioLdap[]> {
    return this.http.get<DiretorioLdap[]>(this.base);
  }

  criar(dados: GravacaoDiretorio): Observable<DiretorioLdap> {
    return this.http.post<DiretorioLdap>(this.base, dados);
  }

  alterar(id: string, dados: GravacaoDiretorio): Observable<DiretorioLdap> {
    return this.http.put<DiretorioLdap>(`${this.base}/${id}`, dados);
  }

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

  sincronizar(id: string): Observable<ResultadoSincronizacao> {
    return this.http.post<ResultadoSincronizacao>(`${this.base}/${id}/sincronizar`, null);
  }
}
