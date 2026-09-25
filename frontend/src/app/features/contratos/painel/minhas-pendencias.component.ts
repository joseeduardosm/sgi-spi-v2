// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir a página dedicada "Minhas pendências", com busca e filtro por tipo.

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { Pendencia } from '../compartilhado/contratos.models';
import { ROTULOS_PENDENCIA } from '../compartilhado/rotulos';

/** Tela dedicada "Minhas pendências": um cartão por ocorrência, que leva direto à ação. */
@Component({
  selector: 'app-minhas-pendencias',
  imports: [FormsModule, RouterLink, CabecalhoModuloComponent, ...PIPES_FORMATACAO],
  template: `
    <app-cabecalho-modulo titulo="Minhas pendências" [trilha]="['Painel', 'Minhas pendências']"
                          descricao="O que precisa da sua ação nos contratos em que você é criador ou integra a equipe." />

    <div class="barra-fixa">
      <a class="acao-secundaria" routerLink="/contratos/painel">← Painel</a>
      <span class="contador-ciencias" [class.completo]="!pendencias().length">{{ filtradas().length }} de {{ pendencias().length }}</span>
    </div>

    @if (carregando()) {
      <p class="estado-vazio">Carregando…</p>
    } @else if (!pendencias().length) {
      <p class="estado-vazio">Nada pendente com você. 🎉</p>
    } @else {
      <div class="filtros-ocorrencias">
        <input type="search" name="busca" aria-label="Buscar por contrato" placeholder="Buscar por contrato ou descrição" [(ngModel)]="busca" />
        <div class="chips-tipo" role="group" aria-label="Filtrar por tipo">
          <button type="button" [class.ativo]="!tipo()" (click)="tipo.set(null)">Todas <b>{{ pendencias().length }}</b></button>
          @for (t of tipos(); track t.tipo) {
            <button type="button" [class.ativo]="tipo() === t.tipo" (click)="tipo.set(t.tipo)">{{ t.rotulo }} <b>{{ t.quantidade }}</b></button>
          }
        </div>
      </div>

      <div class="cartoes-ocorrencia">
        @for (p of filtradas(); track $index) {
          <a class="cartao-ocorrencia" [class.alta]="p.tipo.startsWith('ciencia')" [routerLink]="p.rota">
            <span class="selo-ocorrencia">{{ rotulos[p.tipo] ?? p.tipo }}</span>
            <strong>{{ p.descricao }}</strong>
            <small>Contrato {{ p.contrato_numero }}{{ p.contrato_apelido ? ' · ' + p.contrato_apelido : '' }}</small>
            <footer>
              <span>@if (p.desde) { Desde {{ p.desde | dataBr }}@if (dias(p.desde) > 0) { · há {{ dias(p.desde) }} dia(s) } }</span>
              <span class="ir">Abrir →</span>
            </footer>
          </a>
        } @empty {
          <p class="estado-vazio">Nenhuma pendência com esse filtro.</p>
        }
      </div>
    }
  `,
})
export class MinhasPendenciasComponent implements OnInit {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);

  // Estado: lista vinda da API, tipo escolhido nos chips e texto da busca
  protected readonly rotulos = ROTULOS_PENDENCIA;
  protected readonly pendencias = signal<Pendencia[]>([]);
  protected readonly carregando = signal(true);
  protected readonly tipo = signal<string | null>(null);
  protected readonly termo = signal('');

  // get/set permitem usar [(ngModel)]="busca" no template guardando o valor num signal
  protected get busca(): string {
    return this.termo();
  }

  protected set busca(valor: string) {
    this.termo.set(valor);
  }

  /** Tipos presentes na lista, com a quantidade de cada um (os chips de filtro). */
  protected readonly tipos = computed(() => {
    const contagem = new Map<string, number>();
    for (const p of this.pendencias()) contagem.set(p.tipo, (contagem.get(p.tipo) ?? 0) + 1);
    return [...contagem].map(([tipo, quantidade]) => ({ tipo, quantidade, rotulo: this.rotulos[tipo] ?? tipo }));
  });

  /** Pendências que passam pelo filtro de tipo e pela busca. */
  protected readonly filtradas = computed(() => {
    const termo = this.termo().trim().toLowerCase();
    return this.pendencias().filter(
      (p) =>
        (!this.tipo() || p.tipo === this.tipo()) &&
        (!termo || `${p.contrato_numero} ${p.contrato_apelido} ${p.descricao}`.toLowerCase().includes(termo)),
    );
  });

  /** Carrega o painel (sem filtros) e usa só as pendências do usuário. */
  ngOnInit(): void {
    this.api.painel({}).subscribe({
      next: (p) => {
        this.pendencias.set(p.minhas_pendencias);
        this.carregando.set(false);
      },
      error: (e) => {
        this.carregando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível carregar as pendências');
      },
    });
  }

  /** Dias desde a data informada (para "há N dia(s)"). */
  protected dias(desde: string): number {
    return Math.floor((Date.now() - Date.parse(`${desde}T00:00:00`)) / 86_400_000);
  }
}
