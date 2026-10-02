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
      <form class="parametros-rh" (ngSubmit)="salvar(x)">
        <section class="cartao-dados" aria-labelledby="titulo-regras">
          <header><div><h2 id="titulo-regras">Regras de agendamento</h2><small>Valem para os próximos pedidos e alterações.</small></div></header>
          <div class="corpo">
            <div class="grade-parametros">
              <div class="campo"><label for="p-min-f">Mínimo de dias seguidos (férias)</label><input id="p-min-f" name="minimo_dias_ferias" type="number" min="1" max="90" [(ngModel)]="x.minimo_dias_ferias" /></div>
              <div class="campo"><label for="p-min-lp">Mínimo de dias seguidos (licença-prêmio)</label><input id="p-min-lp" name="minimo_dias_lp" type="number" min="1" max="180" [(ngModel)]="x.minimo_dias_lp" /></div>
              <div class="campo"><label for="p-antecedencia">Antecedência mínima para agendar (dias)</label><input id="p-antecedencia" name="antecedencia" type="number" min="0" max="365" [(ngModel)]="x.antecedencia_minima_dias" /></div>
              <div class="campo"><label for="p-prazo">Alterar ou cancelar até (dias antes do início)</label><input id="p-prazo" name="prazo" type="number" min="0" max="365" [(ngModel)]="x.prazo_cancelamento_dias" /></div>
              <div class="campo"><label for="p-alerta">Alerta de setor (pessoas afastadas juntas)</label><input id="p-alerta" name="alerta" type="number" min="0" max="500" [(ngModel)]="x.limite_alerta_setor" />
                <small class="ajuda">0 desliga o alerta.</small></div>
            </div>

            <h3 class="subtitulo-parametros">Dias da semana em que o período não pode começar</h3>
            <div class="grade-parametros duas">
              <div class="campo"><span class="rotulo">Férias</span>
                <div class="dias-semana-parametros">@for (d of dias; track $index) {
                  <label class="dia" [class.marcado]="x.inicio_vedado_ferias.includes($index)"><input type="checkbox" [checked]="x.inicio_vedado_ferias.includes($index)" (change)="alternar(x.inicio_vedado_ferias, $index)" />{{ d }}</label> }</div></div>
              <div class="campo"><span class="rotulo">Licença-prêmio</span>
                <div class="dias-semana-parametros">@for (d of dias; track $index) {
                  <label class="dia" [class.marcado]="x.inicio_vedado_lp.includes($index)"><input type="checkbox" [checked]="x.inicio_vedado_lp.includes($index)" (change)="alternar(x.inicio_vedado_lp, $index)" />{{ d }}</label> }</div></div>
            </div>

            <h3 class="subtitulo-parametros">Outras regras</h3>
            <div class="opcoes-parametros">
              <label class="opcao"><input type="checkbox" name="permite_emenda" [(ngModel)]="x.permite_emenda" />
                <span><strong>Permitir emendar férias e licença-prêmio</strong><small>Um período pode começar logo depois do outro.</small></span></label>
              <label class="opcao"><input type="checkbox" name="inicio_vedado_feriado" [(ngModel)]="x.inicio_vedado_feriado" />
                <span><strong>Não começar em feriado ou ponto facultativo</strong><small>Usa o cadastro em Feriados.</small></span></label>
            </div>
          </div>
        </section>

        <section class="cartao-dados" aria-labelledby="titulo-exercicio">
          <header><div><h2 id="titulo-exercicio">Férias por exercício</h2>
            <small>Cada exercício é uma janela de 12 meses: os dias entram no início dela, podem ser agendados e usufruídos dentro dela, e o que sobra expira no fim.</small></div></header>
          <div class="corpo">
            <div class="grade-parametros">
              <div class="campo"><label for="p-dias-periodo">Dias de férias por exercício</label><input id="p-dias-periodo" name="dias_periodo" type="number" min="1" max="60" [(ngModel)]="x.dias_ferias_por_periodo" /></div>
              <div class="campo"><label for="p-abertura">Abertura do agendamento do próximo exercício</label><input id="p-abertura" name="abertura" type="date" [(ngModel)]="x.abertura_agendamento_ferias" />
                <small class="ajuda">Em branco: sem a regra.</small></div>
              <div class="campo"><label for="p-folga">Folga do aviso de expiração (dias)</label><input id="p-folga" name="folga" type="number" min="0" max="180" [(ngModel)]="x.folga_aviso_ferias_dias" /></div>
            </div>
            <div class="opcoes-parametros">
              <label class="opcao"><input type="checkbox" name="aviso_ferias_ativo" [(ngModel)]="x.aviso_ferias_ativo" />
                <span><strong>Enviar avisos de férias a vencer</strong><small>E-mail oficial para a pessoa, o autorizador (ou substituto) e a CGP.</small></span></label>
            </div>

            <div class="explicacoes-parametros">
              <div class="nota-explicativa">
                <strong>Agendamento do próximo exercício</strong>
                <p>Com a data definida (ex.: 15/10/2026), os dias do exercício seguinte só podem ser agendados a partir dela.
                  Depois, qualquer servidor agenda até {{ x.dias_ferias_por_periodo }} dias, mesmo antes de o saldo ser implantado.
                  Quando o exercício começa, esses dias já estão abatidos do saldo.</p>
              </div>
              <div class="nota-explicativa">
                <strong>Avisos de férias a vencer</strong>
                <p>O 1º aviso sai <b>saldo não agendado + {{ x.antecedencia_minima_dias }} + {{ x.folga_aviso_ferias_dias }}</b> dias antes do fim do exercício
                  (ex.: 20 dias de saldo → {{ 20 + x.antecedencia_minima_dias + x.folga_aviso_ferias_dias }} dias antes). Depois vêm um lembrete 7 dias antes da data-limite para pedir e
                  um último aviso nessa data.</p>
              </div>
            </div>
          </div>
        </section>

        <footer class="rodape-parametros">
          <span class="atualizacao">@if (x.atualizado_por_nome) { Atualizado por <b>{{ x.atualizado_por_nome }}</b> em {{ x.atualizado_em | date: 'dd/MM/yyyy HH:mm' }} } @else { Parâmetros ainda não alterados }</span>
          <button type="submit" class="acao-primaria">Salvar parâmetros</button>
        </footer>
      </form>
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
    dados.abertura_agendamento_ferias = dados.abertura_agendamento_ferias || null;
    this.dialogos.executar(this.api.salvarParametros(dados), 'Salvando…').subscribe({
      next: (novo) => {
        this.p.set(novo);
        this.dialogos.avisar('Parâmetros salvos', 'As regras valem para os próximos pedidos e alterações.');
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar (somente a CGP altera os parâmetros)'),
    });
  }
}
