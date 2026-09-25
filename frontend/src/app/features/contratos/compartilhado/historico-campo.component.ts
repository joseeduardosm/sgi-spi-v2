// Criado por José Eduardo Santana Martins
// Este arquivo serve para mostrar, ao lado de um campo, o histórico de alterações dele (quem, quando, de → para).

import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, ElementRef, inject, input, signal } from '@angular/core';

import { AlteracaoCampo } from './contratos.models';

/** Ícone ⟲ ao lado do rótulo: mostra "quem alterou, quando, de → para" do campo. */
@Component({
  selector: 'app-historico-campo',
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  // A classe no elemento hospedeiro e o clique fora (para fechar a janela)
  host: { class: 'historico-campo', '(document:click)': 'aoClicarFora($event)' },
  template: `
    @if (registros().length) {
      <button type="button" [attr.aria-label]="'Histórico de ' + rotulo()" [attr.aria-expanded]="aberto()" (click)="aberto.set(!aberto())">⟲</button>
      @if (aberto()) {
        <div class="janela" role="dialog" [attr.aria-label]="'Histórico de ' + rotulo()">
          @for (r of registros(); track $index) {
            <p>
              {{ texto(r.de) }} → <strong>{{ texto(r.para) }}</strong>
              <small>{{ r.autor }} · {{ r.ocorrido_em | date: 'dd/MM/yyyy HH:mm' }}</small>
            </p>
          }
        </div>
      }
    }
  `,
})
export class HistoricoCampoComponent {
  // Nome do campo no histórico, rótulo para acessibilidade e a lista completa vinda do contrato
  readonly campo = input.required<string>();
  readonly rotulo = input('campo');
  readonly historico = input<AlteracaoCampo[]>([]);
  /** Tradução opcional de valores (ex.: id da empresa → razão social). */
  readonly traduzir = input<(valor: unknown) => string>();

  protected readonly aberto = signal(false);
  // Só as alterações deste campo; o botão nem aparece se não houver nenhuma
  protected readonly registros = computed(() => this.historico().filter((h) => h.campo === this.campo()));
  private readonly elemento = inject(ElementRef<HTMLElement>);

  /** Texto exibido para um valor antigo ou novo: traduzido, "(vazio)", data dd/mm/aaaa ou o próprio valor. */
  protected texto(valor: unknown): string {
    const traduzido = this.traduzir()?.(valor);
    if (traduzido) return traduzido;
    if (valor === null || valor === undefined || valor === '') return '(vazio)';
    const data = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(valor));
    return data ? `${data[3]}/${data[2]}/${data[1]}` : String(valor);
  }

  /** Fecha a janela ao clicar fora do componente. */
  protected aoClicarFora(evento: Event): void {
    if (this.aberto() && !this.elemento.nativeElement.contains(evento.target as Node)) this.aberto.set(false);
  }
}
