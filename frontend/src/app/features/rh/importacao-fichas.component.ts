// Criado por José Eduardo Santana Martins
// Este arquivo serve para a janela de carga em lote das fichas de pré-cadastro por planilha XLSX (RH).

import { Component, computed, inject, model, output, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { TrilhaEtapasComponent } from '../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { trilhaImportacao } from '../contratos/compartilhado/trilha-importacao';
import { RhPreCadastroApiService } from './rh-pre-cadastro-api.service';
import { ResultadoImportacaoFichas } from './rh-pre-cadastro.models';

/**
 * Ficha por planilha: 1) baixar o formulário (uma pessoa, uma aba, protegido) e enviar à pessoa; 2) escolher o arquivo devolvido e conferir a prévia; 3) importar (rascunho).
 */
@Component({
  selector: 'app-importacao-fichas',
  imports: [TrilhaEtapasComponent, RouterLink],
  host: { '(document:keydown.escape)': 'aberta.set(false)' },
  template: `
    @if (aberta()) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="aberta.set(false)"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal modal-importacao-rh" role="dialog" aria-modal="true" aria-labelledby="titulo-importacao-fichas">
        <header>
          <div><span class="modal-sobretitulo">Pré-cadastro</span><h2 id="titulo-importacao-fichas">Ficha por planilha (XLSX)</h2></div>
          <button type="button" aria-label="Fechar" (click)="aberta.set(false)">×</button>
        </header>
        <div class="corpo-importacao-rh">
          <app-trilha-etapas [etapas]="trilha()" ariaLabel="Etapas da importação" [compacta]="true" />
          <ol class="passos-importacao">
            <li>
              <span class="texto-passo">Baixe o <b>formulário</b> (XLSX) e envie à pessoa. Ele traz as instruções, listas de opções e alertas que a orientam a preencher certo; só as células brancas são editáveis.</span>
              <span class="acao-passo"><button type="button" class="acao-secundaria acao-pequena" (click)="baixarModelo()">Baixar formulário (XLSX)</button></span>
            </li>
            <li>
              <span class="texto-passo">Quando a pessoa devolver o arquivo preenchido, escolha-o aqui. Cada arquivo é a ficha de <b>uma</b> pessoa e é conferido na hora. O CPF é obrigatório e único.</span>
              <span class="acao-passo">
                <label class="acao-secundaria acao-pequena seletor-arquivo">Escolher ficha preenchida (.xlsx)
                  <input type="file" accept=".xlsx" (change)="escolher($any($event.target))" /></label>
                @if (arquivo(); as a) { <small>{{ a.name }}</small> }
              </span>
            </li>
            <li>
              <span class="texto-passo">Confira a prévia e importe. A ficha entra como <b>rascunho</b>: depois o RH completa o setor e o cargo pretendidos, o login proposto e o início previsto.</span>
            </li>
          </ol>

          @if (resultado(); as r) {
            <div class="resumo-importacao" [class.com-erro]="r.com_erro">
              <strong>{{ r.gravado ? 'Importação concluída' : 'Prévia' }}:</strong>
              {{ r.com_erro ? 'a ficha tem erro(s) para corrigir na planilha' : r.gravado ? 'ficha criada como rascunho' : 'ficha sem erros, pronta para importar' }}
            </div>
            <div class="tabela-gestao-envoltorio">
              <table class="tabela-gestao">
                <thead><tr><th>Pessoa</th><th>{{ r.com_erro ? 'Erros' : 'Situação' }}</th></tr></thead>
                <tbody>
                  @for (l of r.linhas; track $index) {
                    <tr>
                      <td><strong>{{ l.nome || '—' }}</strong>@if (l.cpf) { <small class="texto-codigo">{{ l.cpf }}</small> }</td>
                      <td>
                        @for (e of l.erros; track $index) { <span class="texto-erro">{{ e }}</span><br /> }
                        @if (!l.erros.length) { <span class="selo-situacao">{{ r.gravado ? 'Ficha criada (rascunho)' : 'Pronta para importar' }}</span> }
                        @if (l.ficha_id) { <a class="acao-secundaria acao-pequena" [routerLink]="['/rh/pre-cadastros', l.ficha_id]" (click)="aberta.set(false)">Abrir a ficha</a> }
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          }
        </div>
        <footer>
          <button type="button" class="acao-secundaria" (click)="aberta.set(false)">{{ resultado()?.gravado ? 'Fechar' : 'Cancelar' }}</button>
          @if (!resultado()?.gravado) {
            <button type="button" class="acao-primaria" [disabled]="!podeImportar()" (click)="importar()">Importar a ficha</button>
          }
        </footer>
      </section>
    }
  `,
})
export class ImportacaoFichasComponent {
  readonly aberta = model(false);
  /** Avisa a tela para recarregar depois de gravar. */
  readonly importado = output<void>();
  private readonly api = inject(RhPreCadastroApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly arquivo = signal<File | null>(null);
  protected readonly resultado = signal<ResultadoImportacaoFichas | null>(null);
  protected readonly trilha = computed(() => trilhaImportacao(!!this.arquivo(), this.resultado() ? { pode_importar: this.resultado()!.com_erro === 0 } : null));
  protected readonly podeImportar = computed(() => {
    const r = this.resultado();
    return !!this.arquivo() && !!r && !r.gravado && r.com_erro === 0 && r.total > 0;
  });

  protected baixarModelo(): void {
    this.dialogos.executar(this.api.modeloImportacao(), 'Gerando o modelo…').subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Ao escolher o arquivo, confere na hora (prévia, sem gravar). */
  protected escolher(campo: HTMLInputElement): void {
    const arquivo = campo.files?.[0] ?? null;
    campo.value = '';
    this.arquivo.set(arquivo);
    this.resultado.set(null);
    if (!arquivo) return;
    this.dialogos.executar(this.api.importar(arquivo, false), 'Conferindo a planilha…').subscribe({
      next: (r) => this.resultado.set(r),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível ler a planilha'),
    });
  }

  protected importar(): void {
    const arquivo = this.arquivo();
    if (!arquivo || !this.podeImportar()) return;
    this.dialogos.executar(this.api.importar(arquivo, true), 'Criando as fichas…').subscribe({
      next: (r) => { this.resultado.set(r); this.importado.emit(); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível importar'),
    });
  }
}
