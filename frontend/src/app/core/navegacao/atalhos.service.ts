// Criado por José Eduardo Santana Martins
// Este arquivo serve para guardar os favoritos (na conta) e as telas recentes (no navegador) do menu lateral.

import { HttpClient } from '@angular/common/http';
import { computed, effect, inject, Injectable, signal, untracked } from '@angular/core';

import { ambiente } from '../../../environments/ambiente';
import { AutenticacaoService } from '../autenticacao/autenticacao.service';

/** Uma tela guardada: rota do Angular (com query string, se houver) e o texto mostrado no menu. */
export interface Atalho {
  rota: string;
  rotulo: string;
}

// Prefixos das chaves do navegador: a chave final leva o id do usuário (`sgi-spi.recentes.12`), para duas pessoas no mesmo computador
// nunca verem as telas uma da outra
const CHAVE_FAVORITOS = 'sgi-spi.favoritos';
const CHAVE_RECENTES = 'sgi-spi.recentes';
const MAXIMO_FAVORITOS = 20;
// Só as últimas 5 telas: a lista nunca cresce
const MAXIMO_RECENTES = 5;
// Telas que não vale guardar como recentes
const IGNORADAS = ['/', '/login'];

/**
 * Favoritos e recentes do menu.
 * - **Favoritos** valem na hora (cópia em `localStorage`, que também aparece antes da API responder) e ficam na conta
 *   (`GET/PUT /api/favoritos`), para acompanhar o usuário em outro navegador. Depois do login, a lista da conta prevalece.
 * - **Recentes** ficam só neste navegador, **por usuário**, e são sempre as **últimas 5 telas** abertas: a mais nova entra no
 *   topo, a repetida sobe e a sexta empurra a mais antiga para fora. Ao sair ou trocar de usuário, a lista some da tela.
 * Sem usuário logado nada é lido nem gravado.
 */
@Injectable({ providedIn: 'root' })
export class AtalhosService {
  private readonly http = inject(HttpClient);
  private readonly autenticacao = inject(AutenticacaoService);

  readonly favoritos = signal<Atalho[]>([]);
  readonly recentes = signal<Atalho[]>([]);
  private readonly usuarioId = computed(() => this.autenticacao.usuario()?.id ?? null);

  constructor() {
    // Remove as chaves antigas, que eram do navegador e não do usuário (duas pessoas no mesmo computador viam as telas uma da outra)
    for (const antiga of [CHAVE_FAVORITOS, CHAVE_RECENTES]) removerChave(antiga);
    // Ao entrar, trocar de usuário ou sair: carrega só as listas desse usuário (ou esvazia) e busca os favoritos da conta
    effect(() => {
      const id = this.usuarioId();
      untracked(() => {
        this.favoritos.set(id ? lerLista(chave(CHAVE_FAVORITOS, id)) : []);
        this.recentes.set(id ? lerLista(chave(CHAVE_RECENTES, id)).slice(0, MAXIMO_RECENTES) : []);
        if (id) this.carregar();
      });
    });
  }

  /** Lê os favoritos da conta e passam a valer (sem a API, ficam os do navegador). */
  carregar(): void {
    this.http.get<{ itens: Atalho[] }>(`${ambiente.urlApi}/favoritos`).subscribe({
      next: (r) => {
        this.favoritos.set(r.itens);
        this.gravar(CHAVE_FAVORITOS, r.itens);
      },
      error: () => undefined,
    });
  }

  /** Grava a lista do usuário logado no navegador (sem usuário, não grava). */
  private gravar(prefixo: string, lista: Atalho[]): void {
    const id = this.usuarioId();
    if (id) gravarLista(chave(prefixo, id), lista);
  }

  /** A rota é um favorito? */
  ehFavorito(rota: string): boolean {
    return this.favoritos().some((f) => f.rota === rota);
  }

  /** Fixa ou solta uma tela: vale na hora e é gravada na conta (erro de rede é ignorado: continua valendo neste navegador). */
  alternar(rota: string, rotulo: string): void {
    const atuais = this.favoritos();
    const novos = this.ehFavorito(rota) ? atuais.filter((f) => f.rota !== rota) : [...atuais, { rota, rotulo }].slice(-MAXIMO_FAVORITOS);
    this.favoritos.set(novos);
    this.gravar(CHAVE_FAVORITOS, novos);
    if (this.usuarioId()) {
      this.http.put(`${ambiente.urlApi}/favoritos`, { itens: novos }).subscribe({ error: () => undefined });
    }
  }

  /** Registra a tela aberta como a mais recente (sem repetir). */
  registrar(rota: string, rotulo: string): void {
    if (!this.usuarioId() || IGNORADAS.includes(rota.split('?')[0])) return;
    const novos = [{ rota, rotulo }, ...this.recentes().filter((r) => r.rota !== rota)].slice(0, MAXIMO_RECENTES);
    this.recentes.set(novos);
    this.gravar(CHAVE_RECENTES, novos);
  }

  /** Troca o texto da tela atual (a mais recente), quando ela só sabe o nome depois de carregar (ex.: "Contrato 004/2025"). */
  rotularAtual(rotulo: string): void {
    const [atual, ...resto] = this.recentes();
    if (!atual) return;
    const novos = [{ ...atual, rotulo }, ...resto];
    this.recentes.set(novos);
    this.gravar(CHAVE_RECENTES, novos);
    // Se a tela já é favorita, o favorito ganha o nome certo também
    if (this.ehFavorito(atual.rota)) {
      const favoritos = this.favoritos().map((f) => (f.rota === atual.rota ? { ...f, rotulo } : f));
      this.favoritos.set(favoritos);
      this.gravar(CHAVE_FAVORITOS, favoritos);
    }
  }
}

/** Chave do navegador de uma lista de um usuário. */
function chave(prefixo: string, usuarioId: number): string {
  return `${prefixo}.${usuarioId}`;
}

function removerChave(nome: string): void {
  try {
    localStorage.removeItem(nome);
  } catch {
    // sem armazenamento: nada a remover
  }
}

/** Lê uma lista do navegador; sem armazenamento ou com dado estragado, vem vazia. */
function lerLista(chave: string): Atalho[] {
  try {
    const bruto = JSON.parse(localStorage.getItem(chave) ?? '[]');
    return Array.isArray(bruto) ? bruto.filter((i) => typeof i?.rota === 'string' && typeof i?.rotulo === 'string') : [];
  } catch {
    return [];
  }
}

function gravarLista(chave: string, lista: Atalho[]): void {
  try {
    localStorage.setItem(chave, JSON.stringify(lista));
  } catch {
    // navegador sem armazenamento (modo privado): vale só nesta sessão da página
  }
}
