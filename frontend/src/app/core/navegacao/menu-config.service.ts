// Criado por José Eduardo Santana Martins
// Este arquivo serve para carregar e gravar a configuração do menu lateral (ordem, grupos, links e itens ocultos).

import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { NoMenu } from './menu-config';

/** Resposta de `GET /api/menu` (`LeituraMenu`). */
export interface ConfiguracaoMenu {
  itens: NoMenu[];
  padrao: boolean;
  atualizado_por_nome: string;
  atualizado_em: string | null;
}

/** Configuração do menu lateral escolhida pelo administrador; vazia = vale o menu padrão do código. */
@Injectable({ providedIn: 'root' })
export class MenuConfigService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/menu`;

  /** Nós configurados; a barra lateral aplica por cima do menu do código. */
  readonly nos = signal<NoMenu[]>([]);

  /** Carrega a configuração; se falhar, o menu padrão do código continua valendo. */
  carregar(): void {
    this.http.get<ConfiguracaoMenu>(this.base).subscribe({ next: (r) => this.nos.set(r.itens), error: () => this.nos.set([]) });
  }

  ler(): Observable<ConfiguracaoMenu> {
    return this.http.get<ConfiguracaoMenu>(this.base);
  }

  gravar(itens: NoMenu[]): Observable<ConfiguracaoMenu> {
    return this.http.put<ConfiguracaoMenu>(this.base, { itens }).pipe(tap((r) => this.nos.set(r.itens)));
  }

  restaurar(): Observable<void> {
    return this.http.delete<void>(this.base).pipe(tap(() => this.nos.set([])));
  }
}
