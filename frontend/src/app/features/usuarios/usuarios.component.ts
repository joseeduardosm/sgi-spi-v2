// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de usuários: lista com filtros e paginação (o cadastro abre em página própria).

import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { debounceTime, Subject } from 'rxjs';

import { AcessoService } from '../../core/acesso/acesso.service';
import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { ROTULOS_ORIGEM } from '../../core/modelos/usuario.model';
import { FiltroUsuarios, UsuariosApiService } from './usuarios-api.service';
import { DetalheUsuario } from './usuarios.models';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';

/** Lista de usuários: consulta para quem tem ACL; criação, edição e exclusão para o SuperRoot ou CONTROLE_TOTAL em `usuarios`. */
@Component({
  selector: 'app-usuarios',
  imports: [FormsModule, DatePipe, RouterLink, TrilhaComponent],
  templateUrl: './usuarios.component.html',
})
export class UsuariosComponent implements OnInit {
  protected readonly autenticacao = inject(AutenticacaoService);
  private readonly acesso = inject(AcessoService);
  protected readonly api = inject(UsuariosApiService);

  protected readonly rotulosOrigem = ROTULOS_ORIGEM;
  protected readonly ehSuperRoot = computed(() => this.autenticacao.possuiPapel('SuperRoot'));
  /** Grava quem é SuperRoot ou tem CONTROLE_TOTAL na ACL `usuarios` (ex.: a CGP). */
  protected readonly podeGerir = computed(() => this.acesso.pode('usuarios', 'CONTROLE_TOTAL'));

  // Filtros da lista e estado da paginação
  protected filtro: Required<Pick<FiltroUsuarios, 'busca' | 'situacao' | 'origem'>> = { busca: '', situacao: 'ativos', origem: '' };
  protected readonly pagina = signal(1);
  protected readonly tamanhoPagina = 25;
  protected readonly itens = signal<DetalheUsuario[]>([]);
  protected readonly total = signal(0);
  protected readonly totalPaginas = computed(() => Math.max(1, Math.ceil(this.total() / this.tamanhoPagina)));
  protected readonly carregando = signal(true);
  protected readonly aviso = signal<{ texto: string; erro: boolean } | null>(null);
  // Dispara a pesquisa com atraso enquanto o usuário digita
  private readonly pesquisa$ = new Subject<void>();

  // Pesquisa só depois de 300 ms sem digitação, sempre voltando para a página 1
  constructor() {
    this.pesquisa$.pipe(debounceTime(300), takeUntilDestroyed()).subscribe(() => this.carregar(1));
  }

  ngOnInit(): void {
    this.carregar(1);
  }

  /** Chamado a cada alteração nos filtros. */
  protected aoPesquisar(): void {
    this.pesquisa$.next();
  }

  /** Busca a página pedida na API com os filtros atuais. */
  protected carregar(pagina = this.pagina()): void {
    this.pagina.set(pagina);
    this.carregando.set(true);
    this.api.listar({ ...this.filtro, pagina, tamanho_pagina: this.tamanhoPagina }).subscribe({
      next: (resposta) => {
        this.itens.set(resposta.itens);
        this.total.set(resposta.total);
        this.carregando.set(false);
      },
      error: (erro) => {
        this.carregando.set(false);
        this.aviso.set({ texto: this.mensagem(erro, 'Não foi possível carregar os usuários.'), erro: true });
      },
    });
  }

  /** Pede confirmação e exclui o usuário. */
  protected excluir(usuario: DetalheUsuario): void {
    if (!confirm(`Excluir o usuário "${usuario.perfil.nome_completo || usuario.login}"? Esta ação não pode ser desfeita.`)) return;
    this.api.excluir(usuario.id).subscribe({
      next: () => {
        this.aviso.set({ texto: `Usuário "${usuario.login}" excluído.`, erro: false });
        this.carregar();
      },
      error: (erro) => this.aviso.set({ texto: this.mensagem(erro, 'Não foi possível excluir o usuário.'), erro: true }),
    });
  }

  /** Mensagem de erro para exibir: a da API, se houver, ou a padrão da operação. */
  private mensagem(erro: unknown, padrao: string): string {
    if (erro instanceof HttpErrorResponse) {
      if (typeof erro.error?.detalhe === 'string') return erro.error.detalhe;
      if (erro.status === 0 || erro.status >= 502) return 'Serviço indisponível. Tente novamente em instantes.';
    }
    return padrao;
  }
}
