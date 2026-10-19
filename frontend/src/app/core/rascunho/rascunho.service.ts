// Criado por José Eduardo Santana Martins
// Este arquivo serve para guardar rascunhos de formulários no navegador, para não perder o que foi digitado se a sessão vencer ou a aba fechar.

import { DestroyRef, inject, Injectable } from '@angular/core';

import { AutenticacaoService } from '../autenticacao/autenticacao.service';

const PREFIXO = 'sgi-spi.rascunho.';
// Rascunho esquecido por mais de 7 dias é descartado
const VALIDADE_MS = 7 * 24 * 60 * 60 * 1000;
// De quanto em quanto tempo o formulário é comparado com o último rascunho gravado
const INTERVALO_MS = 2000;

/** Rascunho lido do navegador. */
export interface RascunhoGuardado<T> {
  dados: T;
  /** Quando foi gravado (ISO). */
  salvoEm: string;
}

/**
 * Rascunhos de formulários, guardados no `localStorage` **por usuário** (a chave inclui o id de quem está logado, então outra pessoa no mesmo
 * computador não vê o rascunho). Só campos de texto e números: arquivos anexados não são guardados.
 *
 * Uso: `vigiar(destroyRef, chave, () => estado | null)` grava sozinho a cada alteração (devolver `null` apaga o rascunho: formulário vazio);
 * `ler(chave)` restaura ao abrir a tela; `limpar(chave)` apaga depois de salvar de verdade ou ao descartar.
 */
@Injectable({ providedIn: 'root' })
export class RascunhoService {
  private readonly autenticacao = inject(AutenticacaoService);

  private chaveCompleta(chave: string): string {
    return `${PREFIXO}${this.autenticacao.usuario()?.id ?? 'anonimo'}.${chave}`;
  }

  /** Rascunho gravado (ou `null` se não há, venceu ou o navegador não permite ler). */
  ler<T>(chave: string): RascunhoGuardado<T> | null {
    try {
      const bruto = localStorage.getItem(this.chaveCompleta(chave));
      if (!bruto) return null;
      const lido = JSON.parse(bruto) as RascunhoGuardado<T>;
      if (!lido?.salvoEm || Date.now() - new Date(lido.salvoEm).getTime() > VALIDADE_MS) {
        this.limpar(chave);
        return null;
      }
      return lido;
    } catch {
      return null;
    }
  }

  /** Apaga o rascunho. */
  limpar(chave: string): void {
    try {
      localStorage.removeItem(this.chaveCompleta(chave));
    } catch {
      // armazenamento indisponível: nada a apagar
    }
  }

  /**
   * Grava o rascunho sempre que `obter()` devolver algo diferente do último gravado; `null` apaga o rascunho. O formulário não precisa
   * usar signals: a comparação é periódica e termina junto com o componente (`destruir`).
   */
  vigiar<T>(destruir: DestroyRef, chave: string, obter: () => T | null): void {
    let ultimo = '';
    const temporizador = setInterval(() => {
      try {
        const dados = obter();
        const texto = dados === null ? '' : JSON.stringify(dados);
        if (texto === ultimo) return;
        ultimo = texto;
        if (dados === null) this.limpar(chave);
        else localStorage.setItem(this.chaveCompleta(chave), JSON.stringify({ dados, salvoEm: new Date().toISOString() } satisfies RascunhoGuardado<T>));
      } catch {
        // armazenamento cheio ou bloqueado: o formulário continua funcionando sem rascunho
      }
    }, INTERVALO_MS);
    destruir.onDestroy(() => clearInterval(temporizador));
  }
}
