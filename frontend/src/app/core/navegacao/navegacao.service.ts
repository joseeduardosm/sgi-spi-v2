// Criado por José Eduardo Santana Martins
// Este arquivo serve para filtrar a barra lateral conforme os papéis e os acessos do usuário logado.

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

  // Lista de seções já filtrada; `computed` recalcula quando o usuário ou os acessos mudam
  readonly secoes = computed<SecaoNavegacao[]>(() => {
    const usuario = this.autenticacao.usuario(); // recalcula ao trocar de usuário
    if (usuario?.perfil_restrito) return NAVEGACAO_RESTRITA;
    this.acesso.carregado(); // e quando os acessos efetivos chegam
    // Remove seções sem permissão, filtra os itens de cada uma e descarta as que ficaram vazias
    return NAVEGACAO.filter((s) => this.permitido(s.papeis))
      .map((s) => ({ ...s, itens: this.filtrarItens(s.itens) }))
      .filter((s) => s.itens.length > 0);
  });

  /** Mantém só os itens permitidos (papel e ACL), aplicando o mesmo filtro aos submenus. */
  private filtrarItens(itens: ItemNavegacao[]): ItemNavegacao[] {
    return itens
      .filter((i) => this.permitido(i.papeis) && (!i.acl || this.acesso.pode(i.acl)))
      .map((i) => (i.filhos ? { ...i, filhos: this.filtrarItens(i.filhos) } : i));
  }

  /** Sem papéis exigidos, qualquer um vê; senão, é preciso ter pelo menos um deles. */
  private permitido(papeis?: Papel[]): boolean {
    return !papeis?.length || this.autenticacao.possuiPapel(...papeis);
  }
}
