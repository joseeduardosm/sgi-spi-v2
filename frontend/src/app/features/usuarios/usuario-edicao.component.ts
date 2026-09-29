// Criado por José Eduardo Santana Martins
// Este arquivo serve para a página de cadastro e edição de um usuário (conta, perfil institucional e dados funcionais do RH).

import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { AcessoService } from '../../core/acesso/acesso.service';
import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { OpcaoUsuario, ROTULOS_ORIGEM } from '../../core/modelos/usuario.model';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { DadosFuncionaisComponent } from '../rh/dados-funcionais.component';
import { CamposPerfilComponent } from './campos-perfil.component';
import { criarFormularioPerfil, dadosDoFormularioPerfil, gestorComoOpcao, preencherFormularioPerfil } from './formulario-perfil';
import { UsuariosApiService } from './usuarios-api.service';
import { DetalheUsuario } from './usuarios.models';

/**
 * Página do usuário (`/usuarios/novo` e `/usuarios/:id`): conta, perfil institucional e, na edição, os dados
 * funcionais do RH (só CGP e SuperRoot). Grava quem é SuperRoot ou tem CONTROLE_TOTAL na ACL `usuarios`; quem não é
 * SuperRoot não concede o papel SuperRoot, não define senha de outra pessoa e não altera contas SuperRoot.
 */
@Component({
  selector: 'app-usuario-edicao',
  imports: [ReactiveFormsModule, CamposPerfilComponent, DadosFuncionaisComponent, TrilhaComponent],
  templateUrl: './usuario-edicao.component.html',
})
export class UsuarioEdicaoComponent implements OnInit {
  /** Parâmetro da rota (`novo` ou o id). */
  readonly id = input<string>();

  protected readonly api = inject(UsuariosApiService);
  private readonly autenticacao = inject(AutenticacaoService);
  private readonly acesso = inject(AcessoService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  private readonly construtor = inject(NonNullableFormBuilder);

  protected readonly rotulosOrigem = ROTULOS_ORIGEM;
  protected readonly ehSuperRoot = computed(() => this.autenticacao.possuiPapel('SuperRoot'));
  protected readonly podeGerir = computed(() => this.acesso.pode('usuarios', 'CONTROLE_TOTAL'));
  protected readonly usuario = signal<DetalheUsuario | null>(null);
  protected readonly carregando = signal(true);
  protected readonly salvando = signal(false);
  protected readonly erro = signal<string | null>(null);
  protected readonly gestor = signal<OpcaoUsuario[]>([]);
  /** Conta SuperRoot vista por quem não é SuperRoot: só leitura. */
  protected readonly somenteLeitura = computed(() => !this.podeGerir() || (!this.ehSuperRoot() && !!this.usuario()?.superusuario));

  protected readonly conta = this.construtor.group({
    login: ['', [Validators.required, Validators.maxLength(150), Validators.pattern(/^[A-Za-z0-9._@-]+$/)]],
    senha: [''],
    ativo: [true],
    superusuario: [false],
  });
  protected readonly perfil = criarFormularioPerfil(this.construtor, false);

  protected get novo(): boolean {
    return !this.id() || this.id() === 'novo';
  }

  ngOnInit(): void {
    if (this.novo) {
      this.preparar(null);
      return;
    }
    this.api.consultar(Number(this.id())).subscribe({
      next: (u) => this.preparar(u),
      error: (e) => {
        this.carregando.set(false);
        this.erro.set(this.mensagem(e, 'Não foi possível carregar o usuário.'));
      },
    });
  }

  private preparar(u: DetalheUsuario | null): void {
    this.usuario.set(u);
    this.conta.reset({ login: u?.login ?? '', senha: '', ativo: u?.ativo ?? true, superusuario: u?.superusuario ?? false });
    // Na edição o login não muda; a senha só é obrigatória na criação
    if (u) this.conta.controls.login.disable();
    this.conta.controls.senha.setValidators(u ? [Validators.minLength(8)] : [Validators.required, Validators.minLength(8)]);
    // Papel SuperRoot e senha de outra pessoa: só o SuperRoot mexe
    if (!this.ehSuperRoot()) {
      this.conta.controls.superusuario.disable();
      if (u) this.conta.controls.senha.disable();
    }
    if (this.somenteLeitura()) {
      this.conta.disable();
      this.perfil.disable();
    }
    preencherFormularioPerfil(this.perfil, u?.perfil ?? null);
    this.gestor.set(gestorComoOpcao(u?.perfil));
    this.carregando.set(false);
  }

  protected salvar(): void {
    if (this.somenteLeitura()) return;
    if (this.conta.invalid || this.perfil.invalid) {
      this.conta.markAllAsTouched();
      this.perfil.markAllAsTouched();
      this.erro.set(this.novo ? 'Informe login e senha (mínimo 8 caracteres) e verifique os campos.' : 'Verifique os campos. A nova senha precisa de 8 caracteres.');
      return;
    }
    const valores = this.conta.getRawValue();
    const perfil = dadosDoFormularioPerfil(this.perfil, this.gestor()[0]?.id ?? null);
    const atual = this.usuario();
    this.salvando.set(true);
    this.erro.set(null);
    const requisicao = atual
      ? this.api.alterar(atual.id, { senha: valores.senha || null, ativo: valores.ativo, superusuario: valores.superusuario, perfil })
      : this.api.criar({ login: valores.login.trim(), senha: valores.senha, ativo: valores.ativo, superusuario: valores.superusuario, perfil });
    requisicao.subscribe({
      next: (salvo) => {
        this.salvando.set(false);
        this.dialogos.avisar(atual ? 'Usuário atualizado' : 'Conta criada', `"${salvo.perfil.nome_completo || salvo.login}" foi ${atual ? 'atualizado' : 'criada'}.`);
        if (atual) {
          this.preparar(salvo);
        } else {
          void this.roteador.navigate(['/usuarios', salvo.id], { replaceUrl: true });
        }
      },
      error: (e) => {
        this.salvando.set(false);
        this.erro.set(this.mensagem(e, 'Não foi possível salvar o usuário.'));
      },
    });
  }

  protected async excluir(): Promise<void> {
    const u = this.usuario();
    if (!u) return;
    const ok = await this.dialogos.confirmar({
      titulo: 'Excluir este usuário?',
      mensagem: `"${u.perfil.nome_completo || u.login}" será excluído. Esta ação não pode ser desfeita.`,
      rotuloConfirmar: 'Excluir',
      segundos: 3,
    });
    if (!ok) return;
    this.dialogos.executar(this.api.excluir(u.id), 'Excluindo…').subscribe({
      next: () => void this.roteador.navigate(['/usuarios']),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir o usuário'),
    });
  }

  protected voltar(): void {
    void this.roteador.navigate(['/usuarios']);
  }

  private mensagem(erro: unknown, padrao: string): string {
    if (erro instanceof HttpErrorResponse) {
      if (typeof erro.error?.detalhe === 'string') return erro.error.detalhe;
      if (erro.status === 0 || erro.status >= 502) return 'Serviço indisponível. Tente novamente em instantes.';
    }
    return padrao;
  }
}
