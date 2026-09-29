// Criado por José Eduardo Santana Martins
// Este arquivo serve para a CGP ajustar as regras de agendamento de férias e licença-prêmio.

import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { RhApiService } from './rh-api.service';
import { DIAS_SEMANA, ParametrosRh } from './rh.models';

/** Parâmetros do RH (só a CGP grava): nenhuma regra fica fixa no código. */
@Component({
  selector: 'app-parametros-rh',
  imports: [FormsModule, DatePipe, CabecalhoRhComponent],
  template: `
    <app-cabecalho-rh titulo="Parâmetros do RH" [trilha]="['Parâmetros']" descricao="Regras de agendamento de férias e licença-prêmio. Valem para os próximos pedidos." />
    @if (p(); as x) {
      @if (x.membros_cgp === 0) {
        <p class="aviso-bloco erro">Ninguém está no setor da CGP (Coordenadoria de Gestão de Pessoas): os avisos destinados à CGP
          (alterações de cadastro, pedidos, folha de ponto bloqueada) não chegam a ninguém. Inclua as pessoas da CGP em Setores.</p>
      }
      <section class="cartao-dados" aria-labelledby="titulo-parametros-rh">
        <header><div><h2 id="titulo-parametros-rh">Regras de agendamento</h2>
          @if (x.atualizado_por_nome) { <small>Atualizado por {{ x.atualizado_por_nome }} em {{ x.atualizado_em | date: 'dd/MM/yyyy HH:mm' }}</small> }</div></header>
        <div class="corpo">
          <div class="grade-formulario">
            <div><label for="p-min-f">Mínimo de dias consecutivos (férias)</label><input id="p-min-f" type="number" min="1" max="90" [(ngModel)]="x.minimo_dias_ferias" /></div>
            <div><label for="p-min-lp">Mínimo de dias consecutivos (licença-prêmio)</label><input id="p-min-lp" type="number" min="1" max="180" [(ngModel)]="x.minimo_dias_lp" /></div>
            <div><label>Dias em que as férias não podem começar</label>
              <div class="linha-caixas dias-semana">@for (d of dias; track $index) {
                <label><input type="checkbox" [checked]="x.inicio_vedado_ferias.includes($index)" (change)="alternar(x.inicio_vedado_ferias, $index)" /> {{ d }}</label> }</div></div>
            <div><label>Dias em que a licença-prêmio não pode começar</label>
              <div class="linha-caixas dias-semana">@for (d of dias; track $index) {
                <label><input type="checkbox" [checked]="x.inicio_vedado_lp.includes($index)" (change)="alternar(x.inicio_vedado_lp, $index)" /> {{ d }}</label> }</div></div>
            <div><label for="p-antecedencia">Antecedência mínima para agendar (dias)</label><input id="p-antecedencia" type="number" min="0" max="365" [(ngModel)]="x.antecedencia_minima_dias" /></div>
            <div><label for="p-prazo">Cancelar ou alterar até N dias antes do início</label><input id="p-prazo" type="number" min="0" max="365" [(ngModel)]="x.prazo_cancelamento_dias" /></div>
            <div><label for="p-alerta">Alerta de setor: pessoas afastadas ao mesmo tempo (0 desliga)</label><input id="p-alerta" type="number" min="0" max="500" [(ngModel)]="x.limite_alerta_setor" /></div>
            <div class="linha-caixas" style="align-self: end"><label><input type="checkbox" [(ngModel)]="x.permite_emenda" /> Permite emendar férias e licença-prêmio em sequência</label></div>
            <div class="linha-caixas" style="align-self: end"><label><input type="checkbox" [(ngModel)]="x.inicio_vedado_feriado" /> Períodos não podem começar em feriado ou ponto facultativo (cadastro em Feriados)</label></div>
          </div>
          <p class="secao-formulario">Férias por período aquisitivo</p>
          <div class="grade-formulario">
            <div><label for="p-dias-periodo">Dias de férias creditados a cada período (12 meses)</label><input id="p-dias-periodo" type="number" min="1" max="60" [(ngModel)]="x.dias_ferias_por_periodo" /></div>
            <div><label for="p-folga">Folga do aviso de expiração (dias)</label><input id="p-folga" type="number" min="0" max="180" [(ngModel)]="x.folga_aviso_ferias_dias" /></div>
            <div class="linha-caixas" style="align-self: end"><label><input type="checkbox" [(ngModel)]="x.aviso_ferias_ativo" /> Enviar avisos de férias a vencer (e-mail oficial)</label></div>
          </div>
          <p class="dica-formulario">O saldo não usado expira no início do período seguinte. O 1º aviso sai quando faltam
            <b>saldo não agendado + antecedência mínima ({{ x.antecedencia_minima_dias }}) + folga ({{ x.folga_aviso_ferias_dias }})</b> dias para o fim do período
            (ex.: 20 dias de saldo → aviso {{ 20 + x.antecedencia_minima_dias + x.folga_aviso_ferias_dias }} dias antes); depois, um lembrete 7 dias antes da data-limite
            para pedir e um último aviso nessa data. Vão para a pessoa, o autorizador (ou substituto) e a CGP.</p>
          <div class="acoes-cartao"><button type="button" class="acao-primaria" (click)="salvar(x)">Salvar parâmetros</button></div>
        </div>
      </section>
    } @else { <p class="estado-vazio">Carregando…</p> }
  `,
})
export class ParametrosComponent implements OnInit {
  private readonly api = inject(RhApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly p = signal<ParametrosRh | null>(null);
  protected readonly dias = DIAS_SEMANA;

  ngOnInit(): void {
    this.api.parametros().subscribe({ next: (x) => this.p.set(x), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected alternar(lista: number[], dia: number): void {
    const i = lista.indexOf(dia);
    if (i >= 0) lista.splice(i, 1);
    else lista.push(dia);
  }

  protected salvar(x: ParametrosRh): void {
    const { atualizado_por_nome: _a, atualizado_em: _b, ...dados } = x;
    this.dialogos.executar(this.api.salvarParametros(dados), 'Salvando…').subscribe({
      next: (novo) => {
        this.p.set(novo);
        this.dialogos.avisar('Parâmetros salvos', 'As regras valem para os próximos pedidos e alterações.');
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar (somente a CGP altera os parâmetros)'),
    });
  }
}
