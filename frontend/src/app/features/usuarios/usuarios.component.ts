// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de usuários: lista com filtros e paginação, e o cadastro em janela (modal).

import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { debounceTime, Subject } from 'rxjs';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { OpcaoUsuario, ROTULOS_ORIGEM } from '../../core/modelos/usuario.model';
import { CamposPerfilComponent } from './campos-perfil.component';
import { criarFormularioPerfil, dadosDoFormularioPerfil, gestorComoOpcao, preencherFormularioPerfil } from './formulario-perfil';
import { FiltroUsuarios, UsuariosApiService } from './usuarios-api.service';
import { DetalheUsuario } from './usuarios.models';

/** Administração de usuários: consulta para quem tem ACL; criação, edição e exclusão para o SuperRoot. */
@Component({
  selector: 'app-usuarios',
  imports: [FormsModule, ReactiveFormsModule, DatePipe, CamposPerfilComponent],
  templateUrl: './usuarios.component.html',
  // Esc fecha a janela de cadastro
  host: { '(document:keydown.escape)': 'fecharFormulario()' },
})
export class UsuariosComponent implements OnInit {
  protected readonly autenticacao = inject(AutenticacaoService);
  protected readonly api = inject(UsuariosApiService);
  private readonly construtor = inject(NonNullableFormBuilder);

  protected readonly rotulosOrigem = ROTULOS_ORIGEM;
  protected readonly ehAdministrador = computed(() => this.autenticacao.possuiPapel('SuperRoot'));

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

  // Formulário (modal)
  protected readonly formularioAberto = signal(false);
  protected readonly emEdicao = signal<DetalheUsuario | null>(null);
  protected readonly salvando = signal(false);
  protected readonly erroFormulario = signal<string | null>(null);
  protected readonly gestor = signal<OpcaoUsuario[]>([]);
  // Dados da conta; o perfil institucional usa o formulário compartilhado
  protected readonly conta = this.construtor.group({
    login: ['', [Validators.required, Validators.maxLength(150), Validators.pattern(/^[A-Za-z0-9._@-]+$/)]],
    senha: [''],
    ativo: [true],
    superusuario: [false],
  });
  protected readonly perfil = criarFormularioPerfil(this.construtor, false);

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

  /** Abre a janela de cadastro: vazia (novo usuário) ou preenchida (edição). */
  protected abrirFormulario(usuario?: DetalheUsuario): void {
    this.emEdicao.set(usuario ?? null);
    this.erroFormulario.set(null);
    this.conta.reset({ login: usuario?.login ?? '', senha: '', ativo: usuario?.ativo ?? true, superusuario: usuario?.superusuario ?? false });
    // Na edição o login não muda; a senha só é obrigatória na criação
    if (usuario) this.conta.controls.login.disable();
    else this.conta.controls.login.enable();
    this.conta.controls.senha.setValidators(usuario ? [Validators.minLength(8)] : [Validators.required, Validators.minLength(8)]);
    this.conta.controls.senha.updateValueAndValidity();
    preencherFormularioPerfil(this.perfil, usuario?.perfil ?? null);
    this.gestor.set(gestorComoOpcao(usuario?.perfil));
    this.formularioAberto.set(true);
  }

  /** Fecha a janela, a menos que esteja salvando. */
  protected fecharFormulario(): void {
    if (!this.salvando()) this.formularioAberto.set(false);
  }

  /** Valida e envia a criação ou a alteração. */
  protected salvar(): void {
    if (this.conta.invalid || this.perfil.invalid) {
      this.conta.markAllAsTouched();
      this.perfil.markAllAsTouched();
      this.erroFormulario.set(
        this.emEdicao() ? 'Verifique os campos. A nova senha precisa de 8 caracteres.' : 'Informe login e senha (mínimo 8 caracteres) e verifique os campos.',
      );
      return;
    }
    const valores = this.conta.getRawValue();
    const perfil = dadosDoFormularioPerfil(this.perfil, this.gestor()[0]?.id ?? null);
    const atual = this.emEdicao();
    this.salvando.set(true);
    this.erroFormulario.set(null);
    // Mesma tela para criar e alterar: a chamada depende de haver um usuário em edição
    const requisicao = atual
      ? this.api.alterar(atual.id, { senha: valores.senha || null, ativo: valores.ativo, superusuario: valores.superusuario, perfil })
      : this.api.criar({ login: valores.login.trim(), senha: valores.senha, ativo: valores.ativo, superusuario: valores.superusuario, perfil });
    requisicao.subscribe({
      next: (salvo) => {
        this.salvando.set(false);
        this.formularioAberto.set(false);
        this.aviso.set({ texto: `Usuário "${salvo.login}" ${atual ? 'atualizado' : 'criado'}.`, erro: false });
        this.carregar();
      },
      error: (erro) => {
        this.salvando.set(false);
        this.erroFormulario.set(this.mensagem(erro, 'Não foi possível salvar o usuário.'));
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
