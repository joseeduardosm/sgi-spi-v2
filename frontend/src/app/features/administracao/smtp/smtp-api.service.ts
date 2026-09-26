// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API de servidores SMTP.

import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { GravacaoServidorSmtp, ResultadoSmtp, ServidorSmtp } from './smtp.models';

/** Serviço de acesso à API de servidores SMTP (SuperRoot). */
@Injectable({ providedIn: 'root' })
export class SmtpApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/smtp/servidores`;

  /** Lista os servidores cadastrados. */
  listar(): Observable<ServidorSmtp[]> {
    return this.http.get<ServidorSmtp[]>(this.base);
  }

  /** Cadastra um servidor. */
  criar(dados: GravacaoServidorSmtp): Observable<ServidorSmtp> {
    return this.http.post<ServidorSmtp>(this.base, dados);
  }

  /** Altera um servidor (senha vazia mantém a atual). */
  alterar(id: string, dados: GravacaoServidorSmtp): Observable<ServidorSmtp> {
    return this.http.put<ServidorSmtp>(`${this.base}/${id}`, dados);
  }

  /** Exclui um servidor. */
  excluir(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }

  /** Testa uma configuração ainda não salva. */
  testarSemSalvar(dados: GravacaoServidorSmtp): Observable<ResultadoSmtp> {
    return this.http.post<ResultadoSmtp>(`${this.base}/testar`, dados);
  }

  /** Testa a configuração salva; `senha` substitui a salva só neste teste. */
  testar(id: string, senha?: string): Observable<ResultadoSmtp> {
    return this.http.post<ResultadoSmtp>(`${this.base}/${id}/testar`, { senha: senha || null });
  }

  /** Envia um e-mail de teste ao destinatário. */
  enviarTeste(id: string, destinatario: string): Observable<ResultadoSmtp> {
    return this.http.post<ResultadoSmtp>(`${this.base}/${id}/enviar-teste`, { destinatario });
  }
}
