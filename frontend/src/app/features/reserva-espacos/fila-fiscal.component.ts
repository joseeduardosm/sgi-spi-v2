// Criado por José Eduardo Santana Martins
// Este arquivo serve para a fila do fiscal: solicitações aguardando análise, com deferimento e indeferimento (justificado) em série.

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoReservasComponent } from './cabecalho-reservas.component';
import { ReservasApiService } from './reservas-api.service';
import { dataBr, horaCurta, Reserva } from './reservas.models';

@Component({
  selector: 'app-fila-fiscal',
  imports: [FormsModule, RouterLink, CabecalhoReservasComponent],
  template: `
    <app-cabecalho-reservas titulo="Fila do fiscal" descricao="Solicitações aguardando análise. Decidir uma reserva de série vale para todas as ocorrências." />
    <section class="painel-gestao protocolo reservas">
      @for (r of itens(); track r.id) {
        <article class="cartao-dados item-fila">
          <header>
            <div>
              <h2><i class="ponto-cor" [style.background]="r.espaco_cor"></i>{{ r.titulo }}</h2>
              <small>{{ r.espaco_nome }} · {{ data(r.data) }}, {{ hora(r.hora_inicio) }}–{{ hora(r.hora_fim) }}
                @if (r.ocorrencias_serie > 1) { · série de {{ r.ocorrencias_serie }} ocorrências }</small>
            </div>
            <div class="acoes-formulario">
              <a class="acao-secundaria acao-pequena" [routerLink]="['/reserva-espacos/reservas', r.id]">Detalhes</a>
              <button type="button" class="acao-aprovar-janela" [disabled]="ocupado()" (click)="deferir(r)">Deferir</button>
              <button type="button" class="acao-recusar" [disabled]="ocupado()" (click)="abrirRecusa(r)">Indeferir</button>
            </div>
          </header>
          <div class="corpo">
            <p>Solicitante: <strong>{{ r.solicitante_nome }}</strong>@if (r.responsavel_nome && r.responsavel_nome !== r.solicitante_nome) { · Responsável: {{ r.responsavel_nome }} }</p>
            @if (r.observacoes) { <p class="obs">{{ r.observacoes }}</p> }
            @if (recusando() === r.id) {
              <div class="recusa">
                <label for="rec-{{ r.id }}">Justificativa do indeferimento</label>
                <textarea id="rec-{{ r.id }}" rows="2" maxlength="4000" [(ngModel)]="justificativa"></textarea>
                <div class="acoes-formulario">
                  <button type="button" class="acao-recusar" [disabled]="!justificativa.trim() || ocupado()" (click)="indeferir(r)">Confirmar indeferimento</button>
                  <button type="button" class="acao-secundaria" (click)="recusando.set(null)">Voltar</button>
                </div>
              </div>
            }
          </div>
        </article>
      } @empty { <p class="estado-vazio">Nenhuma solicitação aguardando análise.</p> }
    </section>
  `,
})
export class FilaFiscalComponent implements OnInit {
  private readonly api = inject(ReservasApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly itens = signal<Reserva[]>([]);
  protected readonly recusando = signal<number | null>(null);
  protected readonly ocupado = signal(false);
  protected justificativa = '';
  protected data = dataBr;
  protected hora = horaCurta;

  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    this.api.fila().subscribe({ next: (r) => this.itens.set(r), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a fila') });
  }

  protected abrirRecusa(r: Reserva): void {
    this.justificativa = '';
    this.recusando.set(r.id);
  }

  private decidir(r: Reserva, decisao: 'deferir' | 'indeferir', justificativa = ''): void {
    this.ocupado.set(true);
    this.api.analisar(r.id, decisao, justificativa).subscribe({
      next: () => { this.ocupado.set(false); this.recusando.set(null); this.carregar(); },
      error: (e) => { this.ocupado.set(false); this.dialogos.mostrarErro(e, 'Não foi possível concluir a análise'); },
    });
  }

  protected async deferir(r: Reserva): Promise<void> {
    const serie = r.ocorrencias_serie > 1 ? ` As ${r.ocorrencias_serie} ocorrências da série serão deferidas juntas.` : '';
    if (await this.dialogos.confirmar({ titulo: 'Deferir reserva?', mensagem: `"${r.titulo}" em ${r.espaco_nome}, ${dataBr(r.data)}.${serie}`, rotuloConfirmar: 'Deferir' })) this.decidir(r, 'deferir');
  }

  protected indeferir(r: Reserva): void {
    this.decidir(r, 'indeferir', this.justificativa.trim());
  }
}
