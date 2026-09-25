// Criado por José Eduardo Santana Martins
// Este arquivo serve para carregar e consultar os níveis de acesso (ACL) do usuário logado.

import { HttpClient } from '@angular/common/http';
import { effect, inject, Injectable, signal } from '@angular/core';
import { catchError, map, Observable, of, shareReplay, tap } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { AutenticacaoService } from '../autenticacao/autenticacao.service';

/** Níveis de acesso da ACL, do menor para o maior. */
export type NivelAcl = 'LEITURA' | 'MODIFICACAO' | 'CONTROLE_TOTAL';

// Lista em ordem (para seletores) e os textos exibidos na tela
export const NIVEIS_ACL: NivelAcl[] = ['LEITURA', 'MODIFICACAO', 'CONTROLE_TOTAL'];
export const ROTULOS_NIVEL: Record<NivelAcl, string> = {
  LEITURA: 'Leitura',
  MODIFICACAO: 'Modificação',
  CONTROLE_TOTAL: 'Controle total',
};
// Posição numérica de cada nível, para comparar "tem pelo menos"
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

  // Mapa slug → nível do usuário; `carregado` indica se a resposta da API já chegou
  private readonly niveis = signal<ReadonlyMap<string, NivelAcl>>(new Map());
  readonly carregado = signal(false);
  // Requisição em andamento, compartilhada entre chamadas simultâneas (evita pedir duas vezes)
  private carregamentoPendente?: Observable<void>;

  constructor() {
    // Recarrega ao entrar, trocar de usuário ou concluir a revalidação do perfil
    // `effect` roda de novo sempre que um signal lido dentro dele muda (aqui, o usuário da sessão)
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

  /** Busca os acessos na API; chamadas repetidas durante o carregamento reaproveitam a mesma requisição. */
  carregar(): Observable<void> {
    // `??=` só cria a requisição se ainda não houver uma em andamento
    this.carregamentoPendente ??= this.http.get<AcessoEfetivo[]>(`${ambiente.urlApi}/acl/meus-acessos`).pipe(
      tap((itens) => {
        // Guarda só os recursos com algum nível (nulo = sem acesso)
        this.niveis.set(new Map(itens.filter((i) => i.nivel).map((i) => [i.slug, i.nivel!])));
        this.carregado.set(true);
      }),
      map(() => undefined),
      // Erro na API não trava a tela: considera carregado (sem acessos)
      catchError(() => {
        this.carregado.set(true);
        return of(undefined);
      }),
      // Ao terminar, libera para uma próxima carga; `shareReplay` entrega o mesmo resultado a todos os inscritos
      tap(() => (this.carregamentoPendente = undefined)),
      shareReplay(1),
    );
    return this.carregamentoPendente;
  }

  /** Esquece os acessos (logout ou perfil pendente). */
  private reiniciar(): void {
    this.niveis.set(new Map());
    this.carregado.set(false);
  }
}
