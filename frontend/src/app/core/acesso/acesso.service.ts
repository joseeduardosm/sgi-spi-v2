import { HttpClient } from '@angular/common/http';
import { effect, inject, Injectable, signal } from '@angular/core';
import { catchError, map, Observable, of, shareReplay, tap } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { AutenticacaoService } from '../autenticacao/autenticacao.service';

export type NivelAcl = 'LEITURA' | 'MODIFICACAO' | 'CONTROLE_TOTAL';

export const NIVEIS_ACL: NivelAcl[] = ['LEITURA', 'MODIFICACAO', 'CONTROLE_TOTAL'];
export const ROTULOS_NIVEL: Record<NivelAcl, string> = {
  LEITURA: 'Leitura',
  MODIFICACAO: 'Modificação',
  CONTROLE_TOTAL: 'Controle total',
};
const POSICAO: Record<NivelAcl, number> = { LEITURA: 1, MODIFICACAO: 2, CONTROLE_TOTAL: 3 };

/** `AcessoEfetivo` da API. */
export interface AcessoEfetivo {
  recurso_id: number;
  nome: string;
  slug: string;
  url_base: string;
  nivel: NivelAcl | null;
}

/**
 * Acessos efetivos do usuário (GET /api/acl/meus-acessos), usados para ocultar módulos.
 * A proteção efetiva continua no backend.
 */
@Injectable({ providedIn: 'root' })
export class AcessoService {
  private readonly http = inject(HttpClient);
  private readonly autenticacao = inject(AutenticacaoService);

  private readonly niveis = signal<ReadonlyMap<string, NivelAcl>>(new Map());
  readonly carregado = signal(false);
  private carregamentoPendente?: Observable<void>;

  constructor() {
    // Recarrega ao entrar, trocar de usuário ou concluir a revalidação do perfil
    effect(() => {
      const usuario = this.autenticacao.usuario();
      if (usuario && !usuario.perfil_restrito) this.carregar().subscribe();
      else this.reiniciar();
    });
  }

  /** Verdadeiro se o usuário tem ao menos `nivelMinimo` no recurso. SuperRoot sempre pode. */
  pode(slug: string, nivelMinimo: NivelAcl = 'LEITURA'): boolean {
    if (this.autenticacao.possuiPapel('SuperRoot')) return true;
    const nivel = this.niveis().get(slug);
    return !!nivel && POSICAO[nivel] >= POSICAO[nivelMinimo];
  }

  carregar(): Observable<void> {
    this.carregamentoPendente ??= this.http.get<AcessoEfetivo[]>(`${ambiente.urlApi}/acl/meus-acessos`).pipe(
      tap((itens) => {
        this.niveis.set(new Map(itens.filter((i) => i.nivel).map((i) => [i.slug, i.nivel!])));
        this.carregado.set(true);
      }),
      map(() => undefined),
      catchError(() => {
        this.carregado.set(true);
        return of(undefined);
      }),
      tap(() => (this.carregamentoPendente = undefined)),
      shareReplay(1),
    );
    return this.carregamentoPendente;
  }

  private reiniciar(): void {
    this.niveis.set(new Map());
    this.carregado.set(false);
  }
}
