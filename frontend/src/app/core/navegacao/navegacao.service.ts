import { computed, inject, Injectable } from '@angular/core';

import { AcessoService } from '../acesso/acesso.service';
import { AutenticacaoService } from '../autenticacao/autenticacao.service';
import { Papel } from '../modelos/usuario.model';
import { NAVEGACAO, NAVEGACAO_RESTRITA } from './navegacao';
import { ItemNavegacao, SecaoNavegacao } from './navegacao.model';

/** Entrega a navegação filtrada pelos papéis e pelos acessos efetivos do usuário autenticado. */
@Injectable({ providedIn: 'root' })
export class NavegacaoService {
  private readonly autenticacao = inject(AutenticacaoService);
  private readonly acesso = inject(AcessoService);

  readonly secoes = computed<SecaoNavegacao[]>(() => {
    const usuario = this.autenticacao.usuario(); // recalcula ao trocar de usuário
    if (usuario?.perfil_restrito) return NAVEGACAO_RESTRITA;
    this.acesso.carregado(); // e quando os acessos efetivos chegam
    return NAVEGACAO.filter((s) => this.permitido(s.papeis))
      .map((s) => ({ ...s, itens: this.filtrarItens(s.itens) }))
      .filter((s) => s.itens.length > 0);
  });

  private filtrarItens(itens: ItemNavegacao[]): ItemNavegacao[] {
    return itens
      .filter((i) => this.permitido(i.papeis) && (!i.acl || this.acesso.pode(i.acl)))
      .map((i) => (i.filhos ? { ...i, filhos: this.filtrarItens(i.filhos) } : i));
  }

  private permitido(papeis?: Papel[]): boolean {
    return !papeis?.length || this.autenticacao.possuiPapel(...papeis);
  }
}
