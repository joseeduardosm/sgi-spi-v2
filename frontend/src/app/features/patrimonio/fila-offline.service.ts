// Criado por José Eduardo Santana Martins
// Este arquivo serve para guardar no aparelho (IndexedDB) o que foi feito sem sinal e enviar quando a conexão voltar.
import { HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { DadosBem } from './patrimonio.models';
import { PatrimonioApiService } from './patrimonio-api.service';

/** Referência a uma lista: o id do servidor ou, se ela ainda foi criada só no aparelho, o `id_cliente` dela. */
export interface ReferenciaLista { id?: string; id_cliente?: string }

/** O que pode esperar na fila. Cada item leva o `id_cliente`, por isso o reenvio nunca duplica o registro no servidor. */
export type AcaoOffline =
  | { tipo: 'cadastro_bem'; corpo: DadosBem }
  | { tipo: 'solicitar_movimentacao'; corpo: { id_cliente: string; bens_ids?: string[]; chapas?: string[]; destino_id: string; motivo: string } }
  | { tipo: 'criar_classificacao'; corpo: { id_cliente: string; tipo: 'inservivel' | 'extraviado' } }
  | { tipo: 'criar_baixa'; corpo: { id_cliente: string } }
  | { tipo: 'incluir_classificacao'; corpo: { lista: ReferenciaLista; chapa: string } }
  | { tipo: 'incluir_baixa'; corpo: { lista: ReferenciaLista; chapa: string } };

/** `ordem` é um número crescente (milissegundos e um contador): dois itens criados no mesmo instante nunca trocam de lugar na fila. */
export interface ItemFila { id: string; acao: AcaoOffline; criado_em: string; ordem: number; tentativas: number; erro: string | null; descricao: string }

const BANCO = 'sgi-spi-patrimonio';
const LOJA_FILA = 'fila';
const LOJA_MAPA = 'mapa';

/** Resposta de erro da API que não adianta repetir (a regra recusou): o item fica na fila marcado com o motivo. */
function erroDefinitivo(e: unknown): boolean {
  return e instanceof HttpErrorResponse && e.status >= 400 && e.status < 500 && ![401, 408, 429].includes(e.status);
}

/**
 * Fila offline do Patrimônio. As ações feitas sem sinal (cadastro de bem, solicitação de movimentação e leitura de chapas em listas) ficam no aparelho
 * e são enviadas, **em ordem**, quando a conexão volta. O servidor usa o `id_cliente` de cada item para não duplicar.
 */
@Injectable({ providedIn: 'root' })
export class FilaOfflineService {
  private readonly api = inject(PatrimonioApiService);
  private banco: Promise<IDBDatabase> | null = null;
  private sincronizando = false;
  private contador = 0;

  /** Há conexão agora (o navegador avisa quando ela cai ou volta). */
  readonly online = signal(typeof navigator === 'undefined' ? true : navigator.onLine);
  /** Itens aguardando envio ou parados por erro (indicador na tela). */
  readonly itens = signal<ItemFila[]>([]);

  constructor() {
    if (typeof window === 'undefined') return;
    window.addEventListener('online', () => { this.online.set(true); void this.sincronizar(); });
    window.addEventListener('offline', () => this.online.set(false));
    void this.atualizar().then(() => { if (navigator.onLine) void this.sincronizar(); });
  }

  private abrir(): Promise<IDBDatabase> {
    this.banco ??= new Promise((resolver, rejeitar) => {
      const pedido = indexedDB.open(BANCO, 1);
      pedido.onupgradeneeded = () => {
        pedido.result.createObjectStore(LOJA_FILA, { keyPath: 'id' });
        pedido.result.createObjectStore(LOJA_MAPA, { keyPath: 'id_cliente' });
      };
      pedido.onsuccess = () => resolver(pedido.result);
      pedido.onerror = () => rejeitar(pedido.error);
    });
    return this.banco;
  }

  private async transacao<T>(loja: string, modo: IDBTransactionMode, operacao: (l: IDBObjectStore) => IDBRequest<T>): Promise<T> {
    const banco = await this.abrir();
    return new Promise<T>((resolver, rejeitar) => {
      const pedido = operacao(banco.transaction(loja, modo).objectStore(loja));
      pedido.onsuccess = () => resolver(pedido.result);
      pedido.onerror = () => rejeitar(pedido.error);
    });
  }

  async atualizar(): Promise<void> {
    try {
      const todos = await this.transacao<ItemFila[]>(LOJA_FILA, 'readonly', (l) => l.getAll());
      this.itens.set(todos.sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0)));
    } catch { /* sem IndexedDB (modo privativo): a fila fica vazia e o envio é direto */ }
  }

  /** Coloca a ação na fila e, se houver sinal, já tenta enviar. */
  async enfileirar(acao: AcaoOffline, descricao: string): Promise<void> {
    const item: ItemFila = { id: crypto.randomUUID(), acao, criado_em: new Date().toISOString(), ordem: Date.now() * 1000 + (this.contador++ % 1000), tentativas: 0, erro: null, descricao };
    await this.transacao(LOJA_FILA, 'readwrite', (l) => l.put(item));
    await this.atualizar();
    if (navigator.onLine) void this.sincronizar();
  }

  async descartar(id: string): Promise<void> {
    await this.transacao(LOJA_FILA, 'readwrite', (l) => l.delete(id));
    await this.atualizar();
  }

  /** Reenvia o item parado por erro (depois de o usuário corrigir a causa, como uma sala sem responsável). */
  async tentarDeNovo(id: string): Promise<void> {
    const item = this.itens().find((i) => i.id === id);
    if (!item) return;
    await this.transacao(LOJA_FILA, 'readwrite', (l) => l.put({ ...item, erro: null }));
    await this.atualizar();
    await this.sincronizar();
  }

  private async idDoServidor(ref: ReferenciaLista): Promise<string | null> {
    if (ref.id) return ref.id;
    const registro = await this.transacao<{ id_cliente: string; id: string } | undefined>(LOJA_MAPA, 'readonly', (l) => l.get(ref.id_cliente ?? ''));
    return registro?.id ?? null;
  }

  private async lembrar(idCliente: string, id: string): Promise<void> {
    await this.transacao(LOJA_MAPA, 'readwrite', (l) => l.put({ id_cliente: idCliente, id }));
  }

  private async enviar(acao: AcaoOffline): Promise<void> {
    switch (acao.tipo) {
      case 'cadastro_bem': await firstValueFrom(this.api.cadastrarBem(acao.corpo, 'offline')); return;
      case 'solicitar_movimentacao': await firstValueFrom(this.api.solicitarMovimentacao(acao.corpo, 'offline')); return;
      case 'criar_classificacao': {
        const lista = await firstValueFrom(this.api.criarClassificacao(acao.corpo.tipo, acao.corpo.id_cliente));
        await this.lembrar(acao.corpo.id_cliente, lista.id);
        return;
      }
      case 'criar_baixa': {
        const baixa = await firstValueFrom(this.api.criarBaixa(acao.corpo.id_cliente));
        await this.lembrar(acao.corpo.id_cliente, baixa.id);
        return;
      }
      case 'incluir_classificacao':
      case 'incluir_baixa': {
        const id = await this.idDoServidor(acao.corpo.lista);
        if (!id) throw new Error('A lista ainda não foi criada no servidor.');
        if (acao.tipo === 'incluir_classificacao') await firstValueFrom(this.api.incluirNaClassificacao(id, { chapa: acao.corpo.chapa }));
        else await firstValueFrom(this.api.incluirNaBaixa(id, { chapa: acao.corpo.chapa }));
      }
    }
  }

  /** Envia a fila em ordem. Para no primeiro problema de conexão; o item recusado pela regra fica marcado e a fila segue. */
  async sincronizar(): Promise<void> {
    if (this.sincronizando || !navigator.onLine) return;
    this.sincronizando = true;
    try {
      for (const item of [...this.itens()]) {
        if (item.erro) continue;
        try {
          await this.enviar(item.acao);
          await this.transacao(LOJA_FILA, 'readwrite', (l) => l.delete(item.id));
        } catch (e) {
          if (e instanceof HttpErrorResponse && e.status === 0) break;
          const motivo = e instanceof HttpErrorResponse ? (e.error?.detalhe ?? e.message) : (e as Error).message;
          if (e instanceof HttpErrorResponse && !erroDefinitivo(e)) break;
          await this.transacao(LOJA_FILA, 'readwrite', (l) => l.put({ ...item, tentativas: item.tentativas + 1, erro: String(motivo) }));
        }
      }
    } finally {
      this.sincronizando = false;
      await this.atualizar();
    }
  }
}
