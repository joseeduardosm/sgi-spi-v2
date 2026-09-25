import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, ElementRef, inject, input, signal } from '@angular/core';

import { AlteracaoCampo } from './contratos.models';

/** Ícone ⟲ ao lado do rótulo: mostra "quem alterou, quando, de → para" do campo. */
@Component({
  selector: 'app-historico-campo',
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
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
  readonly campo = input.required<string>();
  readonly rotulo = input('campo');
  readonly historico = input<AlteracaoCampo[]>([]);
  /** Tradução opcional de valores (ex.: id da empresa → razão social). */
  readonly traduzir = input<(valor: unknown) => string>();

  protected readonly aberto = signal(false);
  protected readonly registros = computed(() => this.historico().filter((h) => h.campo === this.campo()));
  private readonly elemento = inject(ElementRef<HTMLElement>);

  protected texto(valor: unknown): string {
    const traduzido = this.traduzir()?.(valor);
    if (traduzido) return traduzido;
    if (valor === null || valor === undefined || valor === '') return '(vazio)';
    const data = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(valor));
    return data ? `${data[3]}/${data[2]}/${data[1]}` : String(valor);
  }

  protected aoClicarFora(evento: Event): void {
    if (this.aberto() && !this.elemento.nativeElement.contains(evento.target as Node)) this.aberto.set(false);
  }
}
