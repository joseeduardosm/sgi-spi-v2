// Criado por José Eduardo Santana Martins
// Este arquivo serve para saber se o usuário já viu a novidade mais recente do Changelog (a bolinha vermelha no menu).

import { computed, inject, Injectable, signal } from '@angular/core';

import { AcessoService } from '../acesso/acesso.service';
import { AutenticacaoService } from '../autenticacao/autenticacao.service';
import { moduloVisivel } from './visibilidade-novidades';
import { ULTIMA_NOVIDADE } from './ultima-novidade';

/** Prefixo da chave no navegador; a chave leva o id do usuário (duas pessoas no mesmo computador não se misturam). */
const PREFIXO = 'sgi-spi.changelog-visto.';

/**
 * Bolinha do item "Changelog" da barra lateral: acesa até a pessoa abrir a tela depois da última novidade.
 *
 * A data vista fica no navegador (`localStorage`): é só uma conveniência visual. Se o navegador não guardar
 * (aba anônima, dados limpos), a bolinha volta a aparecer, o que é inofensivo.
 */
@Injectable({ providedIn: 'root' })
export class NovidadesVistasService {
  private readonly autenticacao = inject(AutenticacaoService);
  private readonly acesso = inject(AcessoService);
  /**
   * Dias do Changelog (data e módulos de cada novidade), carregados em segundo plano: o arquivo de notícias não entra no carregamento
   * inicial do menu. Enquanto não chega, não há bolinha.
   */
  private readonly dias = signal<{ data: string; novidades: { modulo: string }[] }[] | null>(null);

  constructor() {
    void import('../../features/changelog/novidades').then((m) => this.dias.set(m.NOVIDADES)).catch(() => undefined);
  }
  // Muda a cada `marcarVistas`, para o `computed` recalcular (o localStorage não avisa ninguém)
  private readonly versao = signal(0);

  /**
   * Há novidade mais nova do que a última vista por este usuário, **num módulo que ele usa** (decisão do usuário: cada pessoa só vê as
   * atualizações dos módulos a que tem acesso)?
   */
  readonly temNova = computed(() => {
    this.versao();
    const usuario = this.autenticacao.usuario();
    const dias = this.dias();
    if (!usuario || !dias) return false;
    const ultimaVisivel = dias.find((d) => d.novidades.some((n) => moduloVisivel(n.modulo, this.acesso, this.autenticacao)))?.data;
    return !!ultimaVisivel && (this.ler(usuario.id) ?? '') < ultimaVisivel;
  });

  /** Chamado ao abrir a tela do Changelog: apaga a bolinha. */
  marcarVistas(): void {
    const usuario = this.autenticacao.usuario();
    if (!usuario) return;
    try {
      localStorage.setItem(PREFIXO + usuario.id, ULTIMA_NOVIDADE);
    } catch {
      // Navegador sem armazenamento: a bolinha continua, sem erro
    }
    this.versao.update((v) => v + 1);
  }

  private ler(id: number): string | null {
    try {
      return localStorage.getItem(PREFIXO + id);
    } catch {
      return null;
    }
  }
}
