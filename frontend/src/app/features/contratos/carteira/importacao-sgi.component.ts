// Criado por José Eduardo Santana Martins
// Este arquivo serve para oferecer à conta root o botão "Importar do SGI": pede o número do contrato e abre o cadastro preenchido.

import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ContratosApiService } from '../compartilhado/contratos-api.service';

/**
 * Botão "Importar do SGI" (somente a conta root). A janela pede o número do contrato no SGI e a senha do SSH de lá;
 * a API lê o contrato (somente leitura) e a tela abre "Novo contrato" já preenchido. **Nada é gravado** até o
 * usuário revisar e salvar o formulário.
 */
@Component({
  selector: 'app-importacao-sgi',
  imports: [FormsModule],
  host: { '(document:keydown.escape)': 'fechar()' },
  template: `
    <button type="button" class="acao-secundaria" (click)="abrir()">Importar do SGI</button>

    @if (aberta()) {
      <div class="fundo-modal" role="presentation" (click)="fechar()"></div>
      <section class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-importacao-sgi">
        <header>
          <div><span class="modal-sobretitulo">Conta root</span><h2 id="titulo-importacao-sgi">Importar contrato do SGI</h2></div>
          <button type="button" aria-label="Fechar" [disabled]="lendo()" (click)="fechar()">×</button>
        </header>
        <form (submit)="$event.preventDefault(); ler()">
          <p class="dica-formulario" style="margin-top: 0">
            O contrato é lido no SGI ({{ origem }}) e abre no cadastro de novo contrato, <b>sem salvar</b>. Revise, complete o que faltar e salve.
          </p>
          <div class="grade-formulario uma-coluna">
            <div>
              <label for="sgi-numero">Número do contrato no SGI *</label>
              <input id="sgi-numero" name="numero" placeholder="Ex.: 010/2024" maxlength="9" autocomplete="off" [(ngModel)]="numero" autofocus />
            </div>
            <div>
              <label for="sgi-senha">Senha de {{ origem }} *</label>
              <input id="sgi-senha" name="senha" type="password" autocomplete="off" [(ngModel)]="senha" />
              <small class="dica-formulario">Usada só nesta leitura (também no sudo do SGI); não é gravada.</small>
            </div>
          </div>
          @if (erro()) { <p class="aviso-formulario erro" role="alert">{{ erro() }}</p> }
          <footer>
            <button type="button" class="acao-secundaria" [disabled]="lendo()" (click)="fechar()">Cancelar</button>
            <button type="submit" class="acao-primaria" [disabled]="lendo() || !numeroValido() || !senha">{{ lendo() ? 'Lendo o SGI…' : 'Abrir no cadastro' }}</button>
          </footer>
        </form>
      </section>
    }
  `,
})
export class ImportacaoSgiComponent {
  private readonly api = inject(ContratosApiService);
  private readonly roteador = inject(Router);
  protected readonly origem = 'administrador@10.23.1.220';
  protected readonly aberta = signal(false);
  protected readonly lendo = signal(false);
  protected readonly erro = signal<string | null>(null);
  protected numero = '';
  protected senha = '';

  protected abrir(): void {
    this.numero = '';
    this.senha = '';
    this.erro.set(null);
    this.aberta.set(true);
  }

  protected fechar(): void {
    if (!this.lendo()) this.aberta.set(false);
  }

  protected numeroValido(): boolean {
    return /^\s*\d{1,4}\/\d{4}\s*$/.test(this.numero);
  }

  /** Lê o contrato no SGI e abre o cadastro com o rascunho (passado pelo estado da navegação, sem gravar). */
  protected ler(): void {
    if (!this.numeroValido() || !this.senha) return;
    this.lendo.set(true);
    this.erro.set(null);
    this.api.rascunhoSgi(this.numero.trim(), this.senha).subscribe({
      next: (rascunho) => {
        this.lendo.set(false);
        this.senha = '';
        this.aberta.set(false);
        void this.roteador.navigate(['/contratos/novo'], { state: { rascunhoSgi: rascunho } });
      },
      error: (e) => {
        this.lendo.set(false);
        this.erro.set(e?.error?.detalhe ?? 'Não foi possível ler o contrato no SGI.');
      },
    });
  }
}
