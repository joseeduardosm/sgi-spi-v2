// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de diretórios LDAP: cadastro, teste de conexão, sincronização e exclusão.

import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { LdapApiService } from './ldap-api.service';
import { DiretorioLdap, GravacaoDiretorio, ResultadoTeste } from './ldap.models';

/** Administração de diretórios LDAP (restrita ao SuperRoot). */
@Component({
  selector: 'app-diretorios-ldap',
  imports: [ReactiveFormsModule, DatePipe],
  templateUrl: './diretorios-ldap.component.html',
  host: { '(document:keydown.escape)': 'fecharFormulario()' },
})
export class DiretoriosLdapComponent implements OnInit {
  private readonly api = inject(LdapApiService);

  // Lista, carregamento e o diretório com ação em andamento (desabilita os botões daquela linha)
  protected readonly diretorios = signal<DiretorioLdap[]>([]);
  protected readonly carregando = signal(true);
  protected readonly idOcupado = signal<string | null>(null);
  protected readonly aviso = signal<{ texto: string; erro: boolean } | null>(null);

  // Estado da janela de cadastro e o resultado do teste feito dentro dela
  protected readonly formularioAberto = signal(false);
  protected readonly emEdicao = signal<DiretorioLdap | null>(null);
  protected readonly salvando = signal(false);
  protected readonly erroFormulario = signal<string | null>(null);
  protected readonly testeFormulario = signal<ResultadoTeste | null>(null);

  // Campos do diretório; a senha bind é obrigatória só no cadastro (ver abrirFormulario)
  protected readonly formulario = inject(NonNullableFormBuilder).group({
    nome: ['', [Validators.required, Validators.maxLength(100)]],
    servidor: ['', [Validators.required, Validators.maxLength(255)]],
    porta: [389, [Validators.required, Validators.min(1), Validators.max(65535)]],
    usar_ssl: [false],
    base_dn: ['', [Validators.required, Validators.maxLength(500)]],
    bind_dn: ['', [Validators.required, Validators.maxLength(500)]],
    senha_bind: [''],
    ativo: [false],
  });

  ngOnInit(): void {
    this.carregar();
  }

  /** Carrega a lista de diretórios. */
  protected carregar(): void {
    this.carregando.set(true);
    this.api.listar().subscribe({
      next: (itens) => {
        this.diretorios.set(itens);
        this.carregando.set(false);
      },
      error: (erro) => {
        this.carregando.set(false);
        this.mostrarAviso(this.mensagem(erro, 'Não foi possível carregar os diretórios.'), true);
      },
    });
  }

  /** Abre a janela de cadastro; o primeiro diretório já vem marcado como ativo. */
  protected abrirFormulario(diretorio?: DiretorioLdap): void {
    this.emEdicao.set(diretorio ?? null);
    this.erroFormulario.set(null);
    this.testeFormulario.set(null);
    this.formulario.reset({
      nome: diretorio?.nome ?? '',
      servidor: diretorio?.servidor ?? '',
      porta: diretorio?.porta ?? 389,
      usar_ssl: diretorio?.usar_ssl ?? false,
      base_dn: diretorio?.base_dn ?? '',
      bind_dn: diretorio?.bind_dn ?? '',
      senha_bind: '',
      ativo: diretorio?.ativo ?? this.diretorios().length === 0,
    });
    // Senha obrigatória somente no cadastro; na edição, vazia preserva a atual
    this.formulario.controls.senha_bind.setValidators(diretorio ? [] : [Validators.required]);
    this.formulario.controls.senha_bind.updateValueAndValidity();
    this.formularioAberto.set(true);
  }

  /** Fecha a janela, a menos que esteja salvando. */
  protected fecharFormulario(): void {
    if (!this.salvando()) this.formularioAberto.set(false);
  }

  /** Valida e grava o diretório (a API ativa e sincroniza, se marcado como ativo). */
  protected salvar(): void {
    if (this.formulario.invalid) {
      this.formulario.markAllAsTouched();
      this.erroFormulario.set('Preencha nome, servidor, porta, Base DN, usuário bind' + (this.emEdicao() ? '.' : ' e senha bind.'));
      return;
    }
    const dados = this.dadosDoFormulario();
    const atual = this.emEdicao();
    this.salvando.set(true);
    this.erroFormulario.set(null);
    (atual ? this.api.alterar(atual.id, dados) : this.api.criar(dados)).subscribe({
      next: (salvo) => {
        this.salvando.set(false);
        this.formularioAberto.set(false);
        this.mostrarAviso(`Diretório "${salvo.nome}" salvo${salvo.ativo ? ' e ativado' : ''}.`, false);
        this.carregar();
      },
      error: (erro) => {
        this.salvando.set(false);
        this.erroFormulario.set(this.mensagem(erro, 'Não foi possível salvar o diretório.'));
      },
    });
  }

  /** Testa os dados do formulário. Na edição sem senha nova, testa com a senha salva. */
  protected testarFormulario(): void {
    const atual = this.emEdicao();
    const dados = this.dadosDoFormulario();
    if (!atual && !dados.senha_bind) {
      this.erroFormulario.set('Informe a senha bind para testar.');
      return;
    }
    this.salvando.set(true);
    this.erroFormulario.set(null);
    this.testeFormulario.set(null);
    // Com senha digitada (ou diretório novo), testa os dados do formulário; senão, testa o diretório salvo
    const requisicao = dados.senha_bind || !atual ? this.api.testarSemSalvar(dados) : this.api.testar(atual.id);
    requisicao.subscribe({
      next: (resultado) => {
        this.salvando.set(false);
        this.testeFormulario.set(resultado);
      },
      error: (erro) => {
        this.salvando.set(false);
        this.erroFormulario.set(this.mensagem(erro, 'Não foi possível testar a conexão.'));
      },
    });
  }

  /** Testa a conexão de um diretório salvo, a partir da lista. */
  protected testar(diretorio: DiretorioLdap): void {
    this.idOcupado.set(diretorio.id);
    this.api.testar(diretorio.id).subscribe({
      next: (r) => {
        this.idOcupado.set(null);
        this.mostrarAviso(r.sucesso ? `${diretorio.nome}: conexão saudável em ${r.latencia_ms} ms.` : `${diretorio.nome}: ${r.mensagem}`, !r.sucesso);
        this.carregar();
      },
      error: (erro) => {
        this.idOcupado.set(null);
        this.mostrarAviso(this.mensagem(erro, 'Não foi possível testar a conexão.'), true);
      },
    });
  }

  /** Sincroniza os usuários do diretório e mostra o resumo. */
  protected sincronizar(diretorio: DiretorioLdap): void {
    this.idOcupado.set(diretorio.id);
    this.mostrarAviso(`Sincronizando ${diretorio.nome}…`, false);
    this.api.sincronizar(diretorio.id).subscribe({
      next: (r) => {
        this.idOcupado.set(null);
        this.mostrarAviso(
          `${diretorio.nome}: ${r.encontrados} encontrados, ${r.criados} criados, ${r.atualizados} atualizados, ` +
            `${r.desativados} desativados${r.ignorados ? `, ${r.ignorados} ignorados (conta local homônima)` : ''}.`,
          false,
        );
        this.carregar();
      },
      error: (erro) => {
        this.idOcupado.set(null);
        this.mostrarAviso(this.mensagem(erro, 'Não foi possível sincronizar o diretório.'), true);
        this.carregar();
      },
    });
  }

  /** Pede confirmação e exclui o diretório. */
  protected excluir(diretorio: DiretorioLdap): void {
    if (!confirm(`Excluir o diretório "${diretorio.nome}"? Os usuários importados continuam cadastrados.`)) return;
    this.idOcupado.set(diretorio.id);
    this.api.excluir(diretorio.id).subscribe({
      next: () => {
        this.idOcupado.set(null);
        this.mostrarAviso(`Diretório "${diretorio.nome}" excluído.`, false);
        this.carregar();
      },
      error: (erro) => {
        this.idOcupado.set(null);
        this.mostrarAviso(this.mensagem(erro, 'Não foi possível excluir o diretório.'), true);
      },
    });
  }

  /** Lê o formulário no formato da API: porta como número e senha vazia como null. */
  private dadosDoFormulario(): GravacaoDiretorio {
    const valores = this.formulario.getRawValue();
    return { ...valores, porta: Number(valores.porta), senha_bind: valores.senha_bind || null };
  }

  /** Mostra uma mensagem de sucesso ou de erro no topo da tela. */
  private mostrarAviso(texto: string, erro: boolean): void {
    this.aviso.set({ texto, erro });
  }

  /** Mensagem da API, se houver, ou a padrão da operação. */
  private mensagem(erro: unknown, padrao: string): string {
    if (erro instanceof HttpErrorResponse) {
      if (typeof erro.error?.detalhe === 'string') return erro.error.detalhe;
      if (erro.status === 0 || erro.status >= 502) return 'Serviço indisponível. Tente novamente em instantes.';
    }
    return padrao;
  }
}
