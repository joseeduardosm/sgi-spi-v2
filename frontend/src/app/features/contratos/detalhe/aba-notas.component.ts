// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a aba "Notas de Empenho": cartões com saldo e extrato e a janela de cadastro.

import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { NotaEmpenho } from '../compartilhado/contratos.models';
import { paraDecimalApi, paraDecimalTela } from '../compartilhado/rotulos';

/** Aba "Notas de Empenho": cartões com saldo, faixa de consumo e extrato. */
@Component({
  selector: 'app-aba-notas',
  imports: [FormsModule, ...PIPES_FORMATACAO],
  // Esc fecha a janela de cadastro
  host: { '(document:keydown.escape)': 'aberto.set(false)' },
  template: `
    <section class="cartao-dados" aria-labelledby="titulo-notas">
      <header>
        <div><h2 id="titulo-notas">Notas de Empenho</h2><small>O débito acontece ao anexar a Ordem Bancária de cada competência, na ordem de NEs escolhida na medição.</small></div>
        @if (podeEditar()) { <button type="button" class="acao-primaria" (click)="abrir()"><span>+</span> Cadastrar NE</button> }
      </header>
      <div class="corpo">
        @for (n of notas(); track n.id) {
          <article class="indicador" style="margin-bottom: 12px">
            <div style="display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap">
              <strong style="font-size: 15px">{{ n.numero }}</strong>
              <span>Valor inicial: {{ n.valor_original | moeda }} · Saldo: <b>{{ n.saldo | moeda }}</b>@if (n.comprometido !== '0.00') { · Comprometido: {{ n.comprometido | moeda }} · Saldo livre: <b>{{ n.saldo_livre | moeda }}</b> }</span>
            </div>
            <div class="barra-consumo" [attr.aria-label]="n.percentual_consumido + '% consumido'"><span [class]="n.faixa" [style.width.%]="n.percentual_consumido"></span></div>
            <small>{{ n.percentual_consumido | percentual }} consumido@if (n.comprometido !== '0.00') { · comprometido = competências já medidas e ainda não pagas }</small>
            @if (n.movimentos.length) {
              <table class="tabela-gestao" style="margin-top: 10px">
                <thead><tr><th>Data</th><th>Tipo</th><th>Execução</th><th class="num">Débito</th><th class="num">Saldo</th></tr></thead>
                <tbody>
                  @for (m of n.movimentos; track m.id) {
                    <tr><td>{{ m.data.slice(0, 10) | dataBr }}</td>
                      <td>{{ m.tipo === 'estorno' ? 'Estorno' : 'Pagamento' }}@if (m.autor) { <small>{{ m.autor }}</small> }@if (m.justificativa) { <small>{{ m.justificativa }}</small> }</td>
                      <td>{{ m.competencia_rotulo ?? (m.competencia | competencia) }}</td>
                      <td class="num">{{ m.debito | moeda }}</td><td class="num">{{ m.saldo_apos | moeda }}</td></tr>
                  }
                </tbody>
              </table>
            } @else {
              <small style="margin-top: 8px">Nenhum débito realizado.</small>
            }
            @if (podeEditar()) {
              <div class="acoes-cartao esquerda">
                <button type="button" class="acao-secundaria acao-pequena" (click)="abrir(n)">Editar</button>
                @if (!n.vinculada) { <button type="button" class="acao-perigo acao-pequena" (click)="excluir(n)">Excluir</button> }
              </div>
            }
          </article>
        } @empty {
          <p class="estado-vazio">Nenhuma Nota de Empenho cadastrada.</p>
        }
      </div>
    </section>

    @if (aberto()) {
      <div class="fundo-modal" role="presentation" (click)="aberto.set(false)"></div>
      <section class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-nota">
        <header>
          <div><span class="modal-sobretitulo">Nota de Empenho</span><h2 id="titulo-nota">{{ emEdicao ? 'Editar NE' : 'Cadastrar NE' }}</h2></div>
          <button type="button" aria-label="Fechar" (click)="aberto.set(false)">×</button>
        </header>
        <form (ngSubmit)="salvar()">
          <div class="grade-formulario">
            <div><label for="nota-numero">Número da NE *</label><input id="nota-numero" name="numero" required maxlength="30" [(ngModel)]="numero" /></div>
            <div><label for="nota-valor">Valor originalmente empenhado (R$) *</label><input id="nota-valor" name="valor" inputmode="decimal" required [(ngModel)]="valor" /></div>
          </div>
          @if (emEdicao) { <p class="dica-formulario">O valor não pode ficar abaixo do já consumido ({{ emEdicao.consumido | moeda }}).</p> }
          <footer>
            <button type="button" class="acao-secundaria" (click)="aberto.set(false)">Cancelar</button>
            <button type="submit" class="acao-primaria" [disabled]="!numero.trim() || !valor">Salvar</button>
          </footer>
        </form>
      </section>
    }
  `,
})
export class AbaNotasComponent implements OnInit {
  readonly contratoId = input.required<string>();
  readonly podeEditar = input(false);

  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  // Estado: lista de NEs e a janela de cadastro/edição
  protected readonly notas = signal<NotaEmpenho[]>([]);
  protected readonly aberto = signal(false);
  protected emEdicao: NotaEmpenho | null = null;
  protected numero = '';
  protected valor = '';

  /** Carrega as NEs ao abrir a aba. */
  ngOnInit(): void {
    this.api.notas(this.contratoId()).subscribe({ next: (n) => this.notas.set(n), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Abre a janela: vazia (nova NE) ou preenchida (edição). */
  protected abrir(nota?: NotaEmpenho): void {
    this.emEdicao = nota ?? null;
    this.numero = nota?.numero ?? '';
    this.valor = nota ? paraDecimalTela(nota.valor_original) : '';
    this.aberto.set(true);
  }

  /** Salva a NE (valor convertido do formato brasileiro para o da API). */
  protected salvar(): void {
    this.api.salvarNota(this.contratoId(), { numero: this.numero.trim(), valor_original: paraDecimalApi(this.valor) }, this.emEdicao?.id).subscribe({
      next: (n) => {
        this.notas.set(n);
        this.aberto.set(false);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar a Nota de Empenho'),
    });
  }

  /** Pede confirmação e exclui a NE. */
  protected async excluir(nota: NotaEmpenho): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir a NE ${nota.numero}?`, mensagem: 'A Nota de Empenho será removida do contrato.', rotuloConfirmar: 'Excluir' });
    if (!ok) return;
    this.api.excluirNota(this.contratoId(), nota.id).subscribe({
      next: () => this.notas.update((l) => l.filter((n) => n.id !== nota.id)),
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }
}
