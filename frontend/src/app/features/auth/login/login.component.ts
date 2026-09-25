// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de login (envio das credenciais e mensagens de erro).

import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, input, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';

/** Tela de login: valida o preenchimento, chama a API e leva o usuário ao destino pedido. */
@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule],
  templateUrl: './login.component.html',
})
export class LoginComponent {
  private readonly autenticacao = inject(AutenticacaoService);
  private readonly roteador = inject(Router);

  /** Parâmetros de consulta preenchidos pelo roteador (withComponentInputBinding). */
  readonly retorno = input<string>();
  readonly sessao = input<string>();

  // Estado da tela: botão desabilitado durante o envio e mensagem de erro exibida
  protected readonly enviando = signal(false);
  protected readonly erro = signal<string | null>(null);

  // Formulário reativo com os dois campos obrigatórios (NonNullable: reset volta a '' em vez de null)
  protected readonly formulario = inject(NonNullableFormBuilder).group({
    login: ['', Validators.required],
    senha: ['', Validators.required],
  });

  /** Envia o formulário; se faltar algum campo, marca os campos e não chama a API. */
  protected enviar(): void {
    if (this.formulario.invalid) {
      this.formulario.markAllAsTouched();
      this.erro.set('Informe usuário e senha.');
      return;
    }
    this.enviando.set(true);
    this.erro.set(null);

    this.autenticacao.entrar(this.formulario.getRawValue()).subscribe({
      next: (usuario) => {
        const destino = this.retorno();
        // Aceita apenas caminhos internos para evitar redirecionamento aberto
        const seguro = destino?.startsWith('/') && !destino.startsWith('//') ? destino : '/';
        // Perfil pendente sempre leva à página "Meu perfil"
        void this.roteador.navigateByUrl(usuario.perfil_restrito ? '/perfil' : seguro);
      },
      error: (erro: unknown) => {
        this.enviando.set(false);
        // Por segurança, limpa a senha digitada depois de uma falha
        this.formulario.controls.senha.reset();
        this.erro.set(this.mensagem(erro));
      },
    });
  }

  /** Traduz o erro da API na mensagem mostrada abaixo do formulário. */
  private mensagem(erro: unknown): string {
    if (erro instanceof HttpErrorResponse) {
      if (erro.status === 401) return 'Usuário ou senha inválidos.';
      if (erro.status === 0 || erro.status >= 500) return 'Serviço indisponível. Tente novamente em instantes.';
      if (typeof erro.error?.detalhe === 'string') return erro.error.detalhe;
    }
    return 'Não foi possível entrar. Tente novamente.';
  }
}
