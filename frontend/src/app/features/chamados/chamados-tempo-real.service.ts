// Criado por José Eduardo Santana Martins
// Este arquivo serve para receber ao vivo os avisos de chamado novo ou alterado (fila, meus chamados, detalhe e painel de TV).

import { inject, Injectable, signal } from '@angular/core';
import { Observable, share } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { EventoChamado } from './chamados.models';

/** Situação da conexão, mostrada no selo "Ao vivo" / "Reconectando…". `parado` = a API recusou (sem login, TV despareada). */
export type EstadoConexao = 'conectando' | 'ao_vivo' | 'reconectando' | 'parado';

const ESPERA_RECONEXAO_MS = 5000;

/**
 * Lê um fluxo SSE com `fetch`, porque o `EventSource` do navegador não manda o cabeçalho `Authorization`.
 * Reconecta sozinho (a API encerra cada conexão em até 30 min); para de vez em 401/403, avisando por `aoEstado('parado', status)`.
 * Devolve a função que encerra a escuta.
 */
export function ouvirEventos(
  url: string,
  autorizacao: () => string | null,
  aoEvento: (evento: EventoChamado) => void,
  aoEstado: (estado: EstadoConexao, status?: number) => void,
): () => void {
  let ativo = true;
  let controle: AbortController | null = null;
  let espera: ReturnType<typeof setTimeout> | null = null;

  const conectar = async (): Promise<void> => {
    if (!ativo) return;
    controle = new AbortController();
    const valor = autorizacao();
    try {
      const resposta = await fetch(url, { headers: valor ? { Authorization: valor, Accept: 'text/event-stream' } : {}, signal: controle.signal, cache: 'no-store' });
      if (resposta.status === 401 || resposta.status === 403) {
        aoEstado('parado', resposta.status);
        return;
      }
      if (!resposta.ok || !resposta.body) throw new Error(`HTTP ${resposta.status}`);
      aoEstado('ao_vivo');
      const leitor = resposta.body.getReader();
      const decodificador = new TextDecoder();
      let acumulado = '';
      for (;;) {
        const { value, done } = await leitor.read();
        if (done) break;
        acumulado += decodificador.decode(value, { stream: true });
        // Cada mensagem SSE termina com uma linha em branco
        let fim: number;
        while ((fim = acumulado.indexOf('\n\n')) >= 0) {
          const bloco = acumulado.slice(0, fim);
          acumulado = acumulado.slice(fim + 2);
          const evento = interpretar(bloco);
          if (evento) aoEvento(evento);
        }
      }
    } catch {
      // Rede caiu, API reiniciou ou a escuta foi encerrada: tenta de novo abaixo (se ainda estiver ativa)
    }
    if (!ativo) return;
    aoEstado('reconectando');
    espera = setTimeout(() => void conectar(), ESPERA_RECONEXAO_MS);
  };

  aoEstado('conectando');
  void conectar();
  return () => {
    ativo = false;
    controle?.abort();
    if (espera) clearTimeout(espera);
  };
}

/** Uma mensagem SSE (`event:` + `data:`). Comentários (`: ping`) e outros tipos são ignorados. */
export function interpretar(bloco: string): EventoChamado | null {
  let tipo = 'message';
  const dados: string[] = [];
  for (const linha of bloco.split('\n')) {
    if (linha.startsWith('event:')) tipo = linha.slice(6).trim();
    else if (linha.startsWith('data:')) dados.push(linha.slice(5).trim());
  }
  if (tipo !== 'chamado' || !dados.length) return null;
  try {
    const evento = JSON.parse(dados.join('\n')) as EventoChamado;
    return typeof evento.numero === 'number' ? evento : null;
  } catch {
    return null;
  }
}

/** Eventos ao vivo de quem está logado. Uma conexão só, compartilhada pelas telas abertas; fecha quando nenhuma escuta. */
@Injectable({ providedIn: 'root' })
export class ChamadosTempoRealService {
  private readonly autenticacao = inject(AutenticacaoService);
  readonly estado = signal<EstadoConexao>('parado');

  readonly eventos$: Observable<EventoChamado> = new Observable<EventoChamado>((assinante) => {
    const parar = ouvirEventos(
      `${ambiente.urlApi}/chamados/eventos`,
      () => (this.autenticacao.token ? `Bearer ${this.autenticacao.token}` : null),
      (evento) => assinante.next(evento),
      (estado) => this.estado.set(estado),
    );
    return () => {
      parar();
      this.estado.set('parado');
    };
  }).pipe(share());
}
