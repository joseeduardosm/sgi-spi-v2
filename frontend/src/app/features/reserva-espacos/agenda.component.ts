// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir a agenda mensal da Reserva de Espaços, com filtro por espaço e lista do dia escolhido.

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoReservasComponent } from './cabecalho-reservas.component';
import { EstadoReservasService } from './estado-reservas.service';
import { ReservasApiService } from './reservas-api.service';
import { dataBr, horaCurta, isoLocal, MESES, Reserva, ROTULOS_STATUS } from './reservas.models';

interface Celula {
  iso: string;
  dia: number;
  doMes: boolean;
  hoje: boolean;
  reservas: Reserva[];
}

@Component({
  selector: 'app-agenda-reservas',
  imports: [FormsModule, RouterLink, CabecalhoReservasComponent],
  template: `
    <app-cabecalho-reservas titulo="Reserva de Espaços" descricao="Veja os espaços ocupados e solicite uma reserva." />
    <section class="painel-gestao protocolo reservas">
      <div class="barra-protocolo">
        <div class="campo curto"><button type="button" class="acao-secundaria" (click)="mudarMes(-1)" aria-label="Mês anterior">‹</button></div>
        <h2 class="mes-agenda">{{ rotuloMes() }}</h2>
        <div class="campo curto"><button type="button" class="acao-secundaria" (click)="mudarMes(1)" aria-label="Próximo mês">›</button></div>
        <button type="button" class="acao-secundaria" (click)="hojeMes()">Hoje</button>
        <div class="campo"><label for="ag-espaco">Espaço</label>
          <select id="ag-espaco" [ngModel]="espacoId()" (ngModelChange)="trocarEspaco($event)">
            <option [ngValue]="''">Todos os espaços</option>
            @for (e of estado.espacos(); track e.id) { <option [ngValue]="e.id">{{ e.nome }}</option> }
          </select></div>
      </div>
      <div class="legenda-espacos">
        @for (e of estado.espacos(); track e.id) { <span><i [style.background]="e.cor"></i>{{ e.nome }}</span> }
        <span><i class="pendente"></i>Aguardando aprovação</span>
      </div>

      <div class="grade-agenda" role="grid" aria-label="Agenda do mês">
        @for (d of diasSemana; track d) { <b class="cab-dia">{{ d }}</b> }
        @for (c of celulas(); track c.iso) {
          <div class="celula" [class.fora]="!c.doMes" [class.hoje]="c.hoje" [class.escolhido]="c.iso === escolhido()" (click)="escolhido.set(c.iso)" role="gridcell" tabindex="0"
               (keydown.enter)="escolhido.set(c.iso)">
            <span class="numero">{{ c.dia }}</span>
            @for (r of c.reservas.slice(0, 3); track r.id) {
              <a class="chip" [class.pendente]="r.status === 'AGUARDANDO_APROVACAO'" [style.--cor]="r.espaco_cor" [routerLink]="['/reserva-espacos/reservas', r.id]"
                 [title]="r.espaco_nome + ' · ' + r.titulo" (click)="$event.stopPropagation()">{{ hora(r.hora_inicio) }} {{ r.titulo }}</a>
            }
            @if (c.reservas.length > 3) { <small class="mais">+{{ c.reservas.length - 3 }}</small> }
          </div>
        }
      </div>

      <div class="cartao-dados dia-escolhido">
        <header>
          <div><h2>{{ data(escolhido()) }}</h2><small>{{ doDia().length }} reserva(s) neste dia</small></div>
          <a class="acao-primaria" routerLink="/reserva-espacos/nova" [queryParams]="{ data: escolhido() }">Reservar neste dia</a>
        </header>
        <div class="corpo">
          @for (r of doDia(); track r.id) {
            <a class="linha-reserva" [routerLink]="['/reserva-espacos/reservas', r.id]">
              <i class="barra-cor" [style.background]="r.espaco_cor"></i>
              <span class="horas">{{ hora(r.hora_inicio) }}–{{ hora(r.hora_fim) }}</span>
              <span><strong>{{ r.titulo }}</strong><small>{{ r.espaco_nome }} · {{ r.responsavel_nome || r.solicitante_nome }}</small></span>
              <span class="selo-reserva" [class]="'selo-reserva ' + r.status">{{ rotulo(r.status) }}</span>
            </a>
          } @empty { <p class="estado-vazio">Nenhuma reserva neste dia.</p> }
        </div>
      </div>
    </section>
  `,
})
export class AgendaReservasComponent implements OnInit {
  private readonly api = inject(ReservasApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(EstadoReservasService);

  protected readonly diasSemana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
  protected readonly mes = signal(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  protected readonly espacoId = signal<number | ''>('');
  protected readonly reservas = signal<Reserva[]>([]);
  protected readonly escolhido = signal(isoLocal(new Date()));

  protected readonly rotuloMes = computed(() => `${MESES[this.mes().getMonth()]} de ${this.mes().getFullYear()}`);
  protected readonly doDia = computed(() => this.reservas().filter((r) => r.data === this.escolhido()));
  protected readonly celulas = computed<Celula[]>(() => {
    const primeiro = this.mes();
    // Semana começa na segunda: getDay() 0 = domingo → 6 dias antes
    const inicio = new Date(primeiro.getFullYear(), primeiro.getMonth(), 1 - ((primeiro.getDay() + 6) % 7));
    const hoje = isoLocal(new Date());
    const porDia = new Map<string, Reserva[]>();
    for (const r of this.reservas()) porDia.set(r.data, [...(porDia.get(r.data) ?? []), r]);
    return Array.from({ length: 42 }, (_, i) => {
      const d = new Date(inicio.getFullYear(), inicio.getMonth(), inicio.getDate() + i);
      const iso = isoLocal(d);
      return { iso, dia: d.getDate(), doMes: d.getMonth() === primeiro.getMonth(), hoje: iso === hoje, reservas: porDia.get(iso) ?? [] };
    });
  });

  protected hora = horaCurta;
  protected data = dataBr;
  protected rotulo = (s: Reserva['status']) => ROTULOS_STATUS[s];

  ngOnInit(): void {
    this.estado.carregar().subscribe();
    this.carregar();
  }

  protected mudarMes(delta: number): void {
    const m = this.mes();
    this.mes.set(new Date(m.getFullYear(), m.getMonth() + delta, 1));
    this.carregar();
  }

  protected hojeMes(): void {
    const h = new Date();
    this.mes.set(new Date(h.getFullYear(), h.getMonth(), 1));
    this.escolhido.set(isoLocal(h));
    this.carregar();
  }

  protected trocarEspaco(id: number | ''): void {
    this.espacoId.set(id);
    this.carregar();
  }

  private carregar(): void {
    const c = this.celulas();
    this.api.agenda(c[0].iso, c[c.length - 1].iso, this.espacoId()).subscribe({
      next: (r) => this.reservas.set(r),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a agenda'),
    });
  }
}
