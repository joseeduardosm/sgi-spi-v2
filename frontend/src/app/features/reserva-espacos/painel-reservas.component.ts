// Criado por José Eduardo Santana Martins
// Este arquivo serve para o painel do fiscal: indicadores do mês, deferidas por mês, ocupação dos espaços e ranking de pessoas.

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoReservasComponent } from './cabecalho-reservas.component';
import { ReservasApiService } from './reservas-api.service';
import { MESES, Painel } from './reservas.models';

@Component({
  selector: 'app-painel-reservas',
  imports: [FormsModule, CabecalhoReservasComponent],
  template: `
    <app-cabecalho-reservas titulo="Painel da Reserva de Espaços" descricao="Indicadores do mês, ocupação por espaço e quem mais reserva." />
    <section class="painel-gestao protocolo reservas">
      <div class="barra-protocolo">
        <div class="campo"><label for="pr-mes">Mês</label>
          <select id="pr-mes" [ngModel]="mes()" (ngModelChange)="trocar(ano(), +$event)">
            @for (m of meses; track $index) { <option [ngValue]="$index + 1">{{ m }}</option> }
          </select></div>
        <div class="campo curto"><label for="pr-ano">Ano</label>
          <input id="pr-ano" type="number" min="2000" max="2200" [ngModel]="ano()" (change)="trocar(+$any($event.target).value, mes())" /></div>
      </div>
      @if (p(); as p) {
        <div class="indicadores">
          <div><b>{{ p.total }}</b><small>Reservas no mês</small></div>
          <div class="ok"><b>{{ p.deferidas }}</b><small>Deferidas</small></div>
          <div class="ruim"><b>{{ p.indeferidas }}</b><small>Indeferidas</small></div>
          <div><b>{{ p.aguardando }}</b><small>Aguardando</small></div>
          <div><b>{{ p.canceladas }}</b><small>Canceladas</small></div>
          <div><b>{{ p.media_por_dia }}</b><small>Média por dia útil</small></div>
        </div>
        <div class="cartao-dados">
          <header><div><h2>Deferidas por mês em {{ p.ano }}</h2></div></header>
          <div class="corpo grafico-meses">
            @for (m of p.por_mes; track m.mes) {
              <div class="coluna-mes" [title]="m.total + ' reserva(s)'"><div class="barras"><i class="utilizado" [style.height.%]="altura(m.total)"></i></div><b>{{ m.rotulo }}</b><small>{{ m.total }}</small></div>
            }
          </div>
        </div>
        <div class="grade-painel-reservas">
          <div class="cartao-dados">
            <header><div><h2>Ocupação por espaço</h2><small>Horas deferidas ÷ horas de funcionamento nos dias úteis do mês.</small></div></header>
            <div class="corpo">
              @for (o of p.ocupacao; track o.espaco) {
                <div class="linha-ocupacao"><span><i class="ponto-cor" [style.background]="o.cor"></i>{{ o.espaco }}</span>
                  <span class="trilho"><b [style.width.%]="Math.min(o.ocupacao_percentual, 100)" [style.background]="o.cor"></b></span>
                  <small>{{ o.ocupacao_percentual }}% · {{ o.horas }} h · {{ o.reservas }} reserva(s)</small></div>
              } @empty { <p class="estado-vazio">Sem espaços ativos.</p> }
            </div>
          </div>
          <div class="cartao-dados">
            <header><div><h2>Quem mais reserva</h2><small>No mês, sem contar canceladas.</small></div></header>
            <div class="corpo">
              @for (pessoa of p.pessoas; track pessoa.nome) { <div class="linha-ocupacao"><span>{{ pessoa.nome }}</span><strong>{{ pessoa.total }}</strong></div> }
              @empty { <p class="estado-vazio">Nenhuma reserva no mês.</p> }
            </div>
          </div>
        </div>
      }
    </section>
  `,
})
export class PainelReservasComponent implements OnInit {
  private readonly api = inject(ReservasApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly Math = Math;
  protected readonly meses = MESES;
  protected readonly ano = signal(new Date().getFullYear());
  protected readonly mes = signal(new Date().getMonth() + 1);
  protected readonly p = signal<Painel | null>(null);
  private readonly maximo = computed(() => Math.max(1, ...(this.p()?.por_mes.map((m) => m.total) ?? [0])));

  ngOnInit(): void {
    this.trocar(this.ano(), this.mes());
  }

  protected altura(total: number): number {
    return (total / this.maximo()) * 100;
  }

  protected trocar(ano: number, mes: number): void {
    this.ano.set(ano);
    this.mes.set(mes);
    this.api.painel(ano, mes).subscribe({ next: (p) => this.p.set(p), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o painel') });
  }
}
