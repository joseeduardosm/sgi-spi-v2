// Criado por José Eduardo Santana Martins
// Este arquivo serve para mostrar um prazo em dias úteis como barra de progresso (aberto, vencido ou encerrado), com o texto sempre visível.

import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** Situação do prazo: dentro do prazo, vencido sem a entrega ou encerrado pela entrega. */
export type SituacaoPrazo = 'aberto' | 'vencido' | 'encerrado';

/**
 * Barra de prazo em dias úteis. Segue o visual da barra "X de N etapas" da trilha: título, texto de estado e a barra.
 * A cor muda pelo consumo do prazo (sucesso, alerta, perigo), mas o texto diz o mesmo, para não depender só de cor.
 */
@Component({
  selector: 'app-barra-prazo',
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './barra-prazo.component.html',
  styleUrl: './barra-prazo.component.scss',
})
export class BarraPrazoComponent {
  readonly titulo = input('Prazo');
  readonly prazoDias = input.required<number>();
  readonly decorridos = input.required<number>();
  readonly restantes = input.required<number>();
  readonly percentual = input.required<number>();
  readonly situacao = input.required<SituacaoPrazo>();
  /** Fim do último dia útil do prazo (ISO). */
  readonly limite = input.required<string>();
  /** Quando a entrega encerrou o prazo (ISO), só em `encerrado`. */
  readonly encerradaEm = input<string | null>(null);
  /** O que encerra o prazo, para o texto ("nota fiscal anexada"). */
  readonly entrega = input('entrega realizada');

  /** Tom da barra: encerrado = sucesso; vencido ou 80% ou mais = perigo; 50% ou mais = alerta; antes disso, sucesso. */
  protected readonly tom = computed(() => {
    if (this.situacao() === 'encerrado') return 'sucesso';
    if (this.situacao() === 'vencido' || this.percentual() >= 80) return 'perigo';
    return this.percentual() >= 50 ? 'alerta' : 'sucesso';
  });

  protected readonly rotuloRestante = computed(() => {
    const n = this.restantes();
    return n === 1 ? '1 dia útil restante' : `${n} dias úteis restantes`;
  });
}
