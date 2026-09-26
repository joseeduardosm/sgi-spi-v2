// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir a página dedicada "Alertas de risco" do painel, com filtros e cartões por contrato.

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { PainelContratos } from '../compartilhado/contratos.models';
import { ROTULOS_RISCO } from '../compartilhado/rotulos';
import { listaExercicios } from './painel.component';

/** Tela dedicada "Alertas de risco": os riscos agrupados por contrato, cada um num cartão que leva à ação. */
@Component({
  selector: 'app-alertas-de-risco',
  imports: [FormsModule, RouterLink, CabecalhoModuloComponent, ...PIPES_FORMATACAO],
  template: `
    <app-cabecalho-modulo titulo="Alertas de risco" [trilha]="['Painel', 'Alertas de risco']"
                          descricao="Contratos com risco de vencimento, reajuste, empenho, pagamento ou execução atrasada." />

    <div class="barra-fixa">
      <a class="acao-secundaria" routerLink="/contratos/painel" [queryParams]="filtrosUrl()">← Painel</a>
      @if (painel(); as p) {
        <span class="contador-ciencias" [class.completo]="!p.alertas.length">{{ p.alertas.length }} contrato(s) · {{ totalRiscos() }} risco(s) · {{ altos() }} alto(s)</span>
      }
    </div>

    @if (painel(); as p) {
      <form class="filtros-ocorrencias" (ngSubmit)="aplicar()">
        <select name="exercicio" aria-label="Exercício" [(ngModel)]="exercicio" (change)="aplicar()">
          @for (a of exercicios(); track a) { <option [ngValue]="a">Exercício {{ a }}</option> }
        </select>
        <select name="empresa" aria-label="Empresa" [(ngModel)]="empresaId" (change)="aplicar()">
          <option value="">Todas as empresas</option>
          @for (e of p.empresas; track e.id) { <option [value]="e.id">{{ e.rotulo }}</option> }
        </select>
        <select name="contrato" aria-label="Contrato" [(ngModel)]="contratoId" (change)="aplicar()">
          <option value="">Todos os contratos</option>
          @for (c of p.contratos; track c.id) { <option [value]="c.id">{{ c.rotulo }}</option> }
        </select>
        <label class="so-altos"><input type="checkbox" name="so_altos" [(ngModel)]="soAltos" /> Só gravidade alta</label>
      </form>

      @for (c of p.alertas; track c.contrato_id) {
        @if (!soAltos || c.gravidade === 'alta') {
          <section class="grupo-ocorrencias" [attr.aria-label]="'Contrato ' + c.contrato_numero">
            <a class="cabecalho-grupo" [routerLink]="['/contratos', c.contrato_id]">
              <span class="marcador" [class.alta]="c.gravidade === 'alta'"></span>
              <strong>Contrato {{ c.contrato_numero }}{{ c.contrato_apelido ? ' · ' + c.contrato_apelido : '' }}</strong>
              <small>{{ c.empresa }}</small>
              <span class="ir">Abrir contrato →</span>
            </a>
            <div class="cartoes-ocorrencia">
              @for (r of c.riscos; track $index) {
                @if (!soAltos || r.gravidade === 'alta') {
                  <a class="cartao-ocorrencia" [class.alta]="r.gravidade === 'alta'" [routerLink]="r.rota">
                    <span class="selo-ocorrencia">{{ rotulos[r.tipo] ?? r.tipo }} · {{ r.gravidade === 'alta' ? 'alta' : 'média' }}</span>
                    <strong>{{ r.descricao }}</strong>
                    <footer>
                      <span>
                        @if (r.data) { {{ r.data | dataBr }} }
                        @if (r.valor) { · {{ r.valor | moeda }} }
                      </span>
                      <span class="ir">Resolver →</span>
                    </footer>
                  </a>
                }
              }
            </div>
          </section>
        }
      } @empty {
        <p class="estado-vazio">Nenhum contrato em risco com esses filtros.</p>
      }
    } @else {
      <p class="estado-vazio">Carregando…</p>
    }
  `,
})
export class AlertasDeRiscoComponent implements OnInit {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);

  // Estado da tela e os filtros (ligados aos seletores por [(ngModel)])
  protected readonly rotulos = ROTULOS_RISCO;
  protected readonly painel = signal<PainelContratos | null>(null);
  protected readonly anoAtual = new Date().getFullYear();
  protected exercicio = this.anoAtual;
  protected empresaId = '';
  protected contratoId = '';
  protected soAltos = false;

  // Contadores exibidos na barra superior
  protected readonly totalRiscos = computed(() => this.painel()?.alertas.reduce((t, c) => t + c.riscos.length, 0) ?? 0);
  protected readonly altos = computed(() => this.painel()?.alertas.reduce((t, c) => t + c.riscos.filter((r) => r.gravidade === 'alta').length, 0) ?? 0);
  // Filtros atuais, repassados ao link "← Painel" para manter a mesma seleção
  // Mesma lista fixa de exercícios do painel
  protected readonly exercicios = computed(() => listaExercicios(this.painel()?.contratos.map((c) => c.rotulo) ?? [], this.exercicio));
  protected readonly filtrosUrl = signal<Record<string, string | number>>({});

  /** Lê os filtros da URL (vindos do painel) e carrega os alertas. */
  ngOnInit(): void {
    const parametros = this.rota.snapshot.queryParamMap;
    this.exercicio = Number(parametros.get('exercicio')) || this.anoAtual;
    this.empresaId = parametros.get('empresa_id') ?? '';
    this.contratoId = parametros.get('contrato_id') ?? '';
    this.carregar();
  }

  /** Aplica os filtros: atualiza a URL (sem criar histórico novo) e recarrega. */
  protected aplicar(): void {
    const filtros = this.filtros();
    void this.roteador.navigate([], { queryParams: filtros, replaceUrl: true });
    this.carregar();
  }

  /** Filtros preenchidos, no formato dos parâmetros da URL. */
  private filtros(): Record<string, string | number> {
    const filtros: Record<string, string | number> = { exercicio: this.exercicio };
    if (this.empresaId) filtros['empresa_id'] = this.empresaId;
    if (this.contratoId) filtros['contrato_id'] = this.contratoId;
    return filtros;
  }

  /** Busca o painel na API com os filtros atuais (os alertas vêm dentro dele). */
  private carregar(): void {
    this.filtrosUrl.set(this.filtros());
    this.api.painel({ exercicio: this.exercicio, empresa_id: this.empresaId, contrato_id: this.contratoId }).subscribe({
      next: (p) => this.painel.set(p),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar os alertas'),
    });
  }
}
