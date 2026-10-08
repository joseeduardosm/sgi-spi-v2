// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar a regra de repetição de uma tarefa recorrente, com o resumo e as próximas datas calculados pela API.

import { DatePipe } from '@angular/common';
import { Component, effect, inject, input, OnDestroy, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { debounceTime, Subject, Subscription } from 'rxjs';

import { TarefasApiService } from './tarefas-api.service';
import { DIAS_SEMANA_CURTOS, FrequenciaRecorrencia, RegraRecorrencia, regraPadrao } from './tarefas.models';

const UNIDADES: Record<FrequenciaRecorrencia, string> = { diaria: 'dia(s)', semanal: 'semana(s)', mensal: 'mês(es)', anual: 'ano(s)' };

/**
 * Bloco "Repetir": sem regra = não repete. Ao ligar, nasce "toda semana no dia do prazo". O texto e as próximas datas vêm da API
 * (`POST /api/tarefas/recorrencias/previa`), que usa o mesmo cálculo da geração (inclusive dias úteis e feriados).
 */
@Component({
  selector: 'app-seletor-recorrencia',
  imports: [FormsModule, DatePipe],
  template: `
    <div class="bloco-recorrencia" [class.ligado]="!!regra()">
      <label class="linha-caixa"><input type="checkbox" name="repetir" [ngModel]="!!regra()" (ngModelChange)="ligar($event)" [disabled]="desabilitado()" />
        <span><strong>Repetir esta tarefa</strong><small>Cria as próximas automaticamente, no calendário.</small></span></label>
      @if (regra(); as r) {
        <div class="grade-recorrencia">
          <div class="campo-rec"><label for="rec-intervalo">A cada</label>
            <span class="intervalo"><input id="rec-intervalo" name="rec-intervalo" type="number" min="1" max="365" [ngModel]="r.intervalo" (ngModelChange)="mudar({ intervalo: +$event || 1 })" />
              <select name="rec-freq" aria-label="Unidade" [ngModel]="r.frequencia" (ngModelChange)="mudar({ frequencia: $event })">
                @for (f of frequencias; track f) { <option [value]="f">{{ unidades[f] }}</option> }
              </select></span></div>
          <div class="campo-rec"><label for="rec-ante">Criar a tarefa antes do prazo</label>
            <span class="intervalo"><input id="rec-ante" name="rec-ante" type="number" min="0" max="60" [ngModel]="r.antecedencia_dias" (ngModelChange)="mudar({ antecedencia_dias: +$event || 0 })" /> <small>dia(s) antes</small></span></div>
          @if (r.frequencia === 'semanal') {
            <div class="campo-rec largo"><label>Nos dias</label>
              <div class="dias-semana" role="group" aria-label="Dias da semana">
                @for (d of dias; track $index; let i = $index) {
                  <button type="button" [class.ativo]="r.dias_semana.includes(i)" [attr.aria-pressed]="r.dias_semana.includes(i)" (click)="alternarDia(i)">{{ d }}</button>
                }
              </div></div>
          }
          <div class="campo-rec largo"><label>Termina</label>
            <div class="termino" role="radiogroup" aria-label="Quando a repetição termina">
              <label class="opcao-termino" [class.escolhida]="termino() === 'nunca'"><input type="radio" name="rec-termino" [checked]="termino() === 'nunca'" (change)="definirTermino('nunca')" /> <span>Nunca</span></label>
              <label class="opcao-termino" [class.escolhida]="termino() === 'data'"><input type="radio" name="rec-termino" [checked]="termino() === 'data'" (change)="definirTermino('data')" /> <span>Em</span>
                <input type="date" name="rec-fim" aria-label="Data final" [disabled]="termino() !== 'data'" [ngModel]="r.fim" (ngModelChange)="mudar({ fim: $event || null })" /></label>
              <label class="opcao-termino" [class.escolhida]="termino() === 'vezes'"><input type="radio" name="rec-termino" [checked]="termino() === 'vezes'" (change)="definirTermino('vezes')" /> <span>Após</span>
                <input type="number" name="rec-max" aria-label="Número de repetições" min="1" max="366" [disabled]="termino() !== 'vezes'" [ngModel]="r.max_ocorrencias" (ngModelChange)="mudar({ max_ocorrencias: +$event || null })" /> <span>vez(es)</span></label>
            </div></div>
          <div class="campo-rec largo"><label class="linha-caixa simples"><input type="checkbox" name="rec-uteis" [ngModel]="r.somente_dias_uteis" (ngModelChange)="mudar({ somente_dias_uteis: $event })" />
            <span>Só em dias úteis <small>(fim de semana e feriado passam para o próximo dia útil)</small></span></label></div>
        </div>
        @if (erro()) { <p class="aviso-formulario">{{ erro() }}</p> }
        @else if (resumo()) {
          <p class="resumo-recorrencia"><strong>{{ resumo() }}</strong>
            @if (proximas().length) { <br /><small>Próximas: @for (d of proximas(); track d; let ultimo = $last) { {{ d + 'T12:00:00' | date: 'dd/MM/yyyy (EEE)' }}{{ ultimo ? '' : ' · ' }} }</small> }
            @else { <br /><small>Esta é a única ocorrência dentro do limite escolhido.</small> }</p>
        }
      }
    </div>
  `,
})
export class SeletorRecorrenciaComponent implements OnDestroy {
  /** Prazo da primeira tarefa (ISO ou valor do campo datetime-local): define a data inicial e o horário. */
  readonly prazo = input.required<string>();
  readonly regra = input<RegraRecorrencia | null>(null);
  readonly regraChange = output<RegraRecorrencia | null>();
  readonly desabilitado = input(false);

  private readonly api = inject(TarefasApiService);
  protected readonly frequencias: FrequenciaRecorrencia[] = ['diaria', 'semanal', 'mensal', 'anual'];
  protected readonly unidades = UNIDADES;
  protected readonly dias = DIAS_SEMANA_CURTOS;
  protected readonly resumo = signal('');
  protected readonly proximas = signal<string[]>([]);
  protected readonly erro = signal('');
  private readonly pedidos = new Subject<void>();
  private readonly assinatura: Subscription = this.pedidos.pipe(debounceTime(250)).subscribe(() => this.atualizarPrevia());

  constructor() {
    // Qualquer mudança da regra ou do prazo recalcula a prévia
    effect(() => {
      this.regra();
      this.prazo();
      this.pedidos.next();
    });
  }

  ngOnDestroy(): void {
    this.assinatura.unsubscribe();
  }

  protected termino(): 'nunca' | 'data' | 'vezes' {
    const r = this.regra();
    return r?.fim ? 'data' : r?.max_ocorrencias ? 'vezes' : 'nunca';
  }

  protected ligar(ligado: boolean): void {
    if (!ligado) return this.regraChange.emit(null);
    const dia = new Date(this.prazo()).getDay();
    this.regraChange.emit(regraPadrao(dia === 0 ? 6 : dia - 1));
  }

  protected mudar(parcial: Partial<RegraRecorrencia>): void {
    const r = this.regra();
    if (!r) return;
    const nova = { ...r, ...parcial };
    // Ao escolher semanal sem dias marcados, usa o dia da semana do prazo
    if (nova.frequencia === 'semanal' && !nova.dias_semana.length) {
      const dia = new Date(this.prazo()).getDay();
      nova.dias_semana = [dia === 0 ? 6 : dia - 1];
    }
    this.regraChange.emit(nova);
  }

  protected alternarDia(dia: number): void {
    const r = this.regra();
    if (!r) return;
    const dias = r.dias_semana.includes(dia) ? r.dias_semana.filter((d) => d !== dia) : [...r.dias_semana, dia].sort();
    this.regraChange.emit({ ...r, dias_semana: dias });
  }

  protected definirTermino(tipo: 'nunca' | 'data' | 'vezes'): void {
    const hoje = new Date(this.prazo());
    hoje.setMonth(hoje.getMonth() + 3);
    const sugestao = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}-${String(hoje.getDate()).padStart(2, '0')}`;
    this.mudar({ fim: tipo === 'data' ? sugestao : null, max_ocorrencias: tipo === 'vezes' ? 10 : null });
  }

  private atualizarPrevia(): void {
    const r = this.regra();
    if (!r || !this.prazo()) { this.resumo.set(''); this.proximas.set([]); this.erro.set(''); return; }
    this.api.previaRecorrencia(new Date(this.prazo()).toISOString(), r).subscribe({
      next: (p) => { this.erro.set(''); this.resumo.set(p.resumo); this.proximas.set(p.proximas); },
      error: (e) => { this.proximas.set([]); this.resumo.set(''); this.erro.set(e?.error?.detalhe ?? 'Regra de repetição inválida.'); },
    });
  }
}
