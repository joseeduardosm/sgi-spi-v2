// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API das Notificações do sistema (e-mail de changelog).

import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { EnvioChangelog, PedidoEnvioChangelog, RascunhoChangelog } from './notificacoes-sistema.models';

/** Serviço da API `/api/notificacoes` (só a conta root). */
@Injectable({ providedIn: 'root' })
export class NotificacoesSistemaApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/notificacoes/changelog`;

  /** Rascunho com as entradas do CHANGELOG ainda não enviadas a todos. */
  rascunho(): Observable<RascunhoChangelog> {
    return this.http.get<RascunhoChangelog>(`${this.base}/rascunho`);
  }

  /** HTML do e-mail no layout oficial (com o brasão embutido). */
  previa(assunto: string, corpo: string): Observable<string> {
    return this.http.post<{ html: string }>(`${this.base}/previa`, { assunto, corpo }).pipe(map((r) => r.html));
  }

  /** Registra o envio (os e-mails saem em segundo plano). */
  enviar(pedido: PedidoEnvioChangelog): Observable<EnvioChangelog> {
    return this.http.post<EnvioChangelog>(`${this.base}/envios`, pedido);
  }

  /** Quantos da seleção receberão o e-mail (todo escolhido ativo e com e-mail). */
  contagem(usuariosIds: number[], setoresIds: number[]): Observable<{ total: number; selecionados: number }> {
    return this.http.post<{ total: number; selecionados: number }>(`${this.base}/contagem`, { usuarios_ids: usuariosIds, setores_ids: setoresIds });
  }

  /** Últimos envios, do mais recente para o mais antigo. */
  historico(): Observable<EnvioChangelog[]> {
    return this.http.get<EnvioChangelog[]>(`${this.base}/envios`);
  }
}
