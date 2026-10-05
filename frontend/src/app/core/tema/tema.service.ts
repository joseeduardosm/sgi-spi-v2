// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar o tema da interface (claro, escuro ou automático) e guardar a escolha do usuário.

import { HttpClient } from '@angular/common/http';
import { effect, inject, Injectable, signal } from '@angular/core';

import { ambiente } from '../../../environments/ambiente';
import { AutenticacaoService } from '../autenticacao/autenticacao.service';
import { Usuario } from '../modelos/usuario.model';

/** Escolha do usuário: `auto` segue o tema do sistema operacional. */
export type PreferenciaTema = 'claro' | 'escuro' | 'auto';

/** Chave do localStorage; o `index.html` lê a mesma chave para aplicar o tema antes do Angular carregar (sem piscar). */
export const CHAVE_TEMA = 'sgi-spi.tema';

/** Aplica o tema no `<html>`: `data-tema` (estilos do sistema) e `data-bs-theme` (componentes do Bootstrap). */
export function aplicarTema(preferencia: PreferenciaTema, sistemaEscuro: boolean): void {
  const escuro = preferencia === 'escuro' || (preferencia === 'auto' && sistemaEscuro);
  const raiz = document.documentElement;
  raiz.setAttribute('data-tema', escuro ? 'escuro' : 'claro');
  raiz.setAttribute('data-bs-theme', escuro ? 'dark' : 'light');
}

/**
 * Tema da interface. A escolha vale na hora e fica em dois lugares:
 * - no navegador (localStorage): vale também na tela de login e evita o "flash" de tema errado;
 * - na conta do usuário (`PUT /api/autenticacao/tema`): acompanha a pessoa em outros navegadores e aparelhos.
 * Depois do login, o tema da conta prevalece sobre o do navegador.
 */
@Injectable({ providedIn: 'root' })
export class TemaService {
  private readonly http = inject(HttpClient);
  private readonly autenticacao = inject(AutenticacaoService);
  private readonly consulta = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null;

  readonly preferencia = signal<PreferenciaTema>(this.lerArmazenado());

  constructor() {
    // Reaplica sempre que a escolha mudar
    effect(() => aplicarTema(this.preferencia(), this.consulta?.matches ?? false));
    // No modo automático, acompanha a troca do tema do sistema operacional
    this.consulta?.addEventListener('change', () => aplicarTema(this.preferencia(), this.consulta?.matches ?? false));
    // Ao entrar (ou ao carregar a sessão), adota o tema salvo na conta
    effect(() => {
      const tema = this.autenticacao.usuario()?.tema;
      if (tema && tema !== this.preferencia()) this.definirLocal(tema);
    });
  }

  /** Escolha do usuário: aplica na hora e grava no navegador e, se houver sessão, na conta. */
  escolher(tema: PreferenciaTema): void {
    this.definirLocal(tema);
    const usuario = this.autenticacao.usuario();
    if (!usuario) return;
    this.http.put<Usuario>(`${ambiente.urlApi}/autenticacao/tema`, { tema }).subscribe({
      next: (atualizado) => this.autenticacao.definirUsuario({ ...usuario, tema: atualizado.tema }),
      // Sem rede ou API fora: o tema continua valendo neste navegador
      error: () => undefined,
    });
  }

  private definirLocal(tema: PreferenciaTema): void {
    this.preferencia.set(tema);
    try {
      localStorage.setItem(CHAVE_TEMA, tema);
    } catch {
      // navegador sem armazenamento (modo privado): vale só nesta sessão da página
    }
  }

  private lerArmazenado(): PreferenciaTema {
    try {
      const valor = localStorage.getItem(CHAVE_TEMA);
      return valor === 'claro' || valor === 'escuro' ? valor : 'auto';
    } catch {
      return 'auto';
    }
  }
}
