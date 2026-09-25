import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, input, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';

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

  protected readonly enviando = signal(false);
  protected readonly erro = signal<string | null>(null);

  protected readonly formulario = inject(NonNullableFormBuilder).group({
    login: ['', Validators.required],
    senha: ['', Validators.required],
  });

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
        void this.roteador.navigateByUrl(usuario.perfil_restrito ? '/perfil' : seguro);
      },
      error: (erro: unknown) => {
        this.enviando.set(false);
        this.formulario.controls.senha.reset();
        this.erro.set(this.mensagem(erro));
      },
    });
  }

  private mensagem(erro: unknown): string {
    if (erro instanceof HttpErrorResponse) {
      if (erro.status === 401) return 'Usuário ou senha inválidos.';
      if (erro.status === 0 || erro.status >= 500) return 'Serviço indisponível. Tente novamente em instantes.';
      if (typeof erro.error?.detalhe === 'string') return erro.error.detalhe;
    }
    return 'Não foi possível entrar. Tente novamente.';
  }
}
