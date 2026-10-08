// Criado por José Eduardo Santana Martins
// Este arquivo serve para listar as reservas: "Minhas reservas" (todo usuário) e "Todas" (fiscal, com filtros e exportação).

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoReservasComponent } from './cabecalho-reservas.component';
import { EstadoReservasService } from './estado-reservas.service';
import { FiltrosReservas, ReservasApiService } from './reservas-api.service';
import { dataBr, horaCurta, Reserva, ROTULOS_STATUS } from './reservas.models';

@Component({
  selector: 'app-lista-reservas',
  imports: [FormsModule, RouterLink, CabecalhoReservasComponent],
  template: `
    <app-cabecalho-reservas [titulo]="todas ? 'Todas as reservas' : 'Minhas reservas'"
      [descricao]="todas ? 'Consulte, filtre e exporte as reservas de todos os espaços.' : 'Reservas que você solicitou ou em que é responsável.'" />
    <section class="painel-gestao protocolo reservas">
      <div class="barra-protocolo">
        <div class="campo"><label for="lr-status">Situação</label>
          <select id="lr-status" [(ngModel)]="filtros.status" (ngModelChange)="carregar()">
            <option value="">Todas</option>
            @for (s of status; track s[0]) { <option [value]="s[0]">{{ s[1] }}</option> }
          </select></div>
        @if (todas) {
          <div class="campo"><label for="lr-espaco">Espaço</label>
            <select id="lr-espaco" [(ngModel)]="filtros.espaco_id" (ngModelChange)="carregar()">
              <option [ngValue]="''">Todos</option>
              @for (e of estado.espacos(); track e.id) { <option [ngValue]="e.id">{{ e.nome }}</option> }
            </select></div>
          <div class="campo curto"><label for="lr-ini">De</label><input id="lr-ini" type="date" [(ngModel)]="filtros.inicio" (ngModelChange)="carregar()" /></div>
          <div class="campo curto"><label for="lr-fim">Até</label><input id="lr-fim" type="date" [(ngModel)]="filtros.fim" (ngModelChange)="carregar()" /></div>
          <div class="campo"><label for="lr-busca">Busca</label><input id="lr-busca" placeholder="Título ou pessoa" [(ngModel)]="filtros.busca" (keyup.enter)="carregar()" /></div>
          <span class="espacador"></span>
          <span class="resumo-protocolo">{{ total() }} reserva(s)</span>
          <button type="button" class="acao-secundaria" (click)="exportar()">Exportar planilha</button>
        }
      </div>
      <div class="tabela-gestao-envoltorio">
        <table class="tabela-gestao">
          <thead><tr><th>Data</th><th>Horário</th><th>Espaço</th><th>Reserva</th><th>Responsável</th><th>Situação</th></tr></thead>
          <tbody>
            @for (r of itens(); track r.id) {
              <tr>
                <td><a [routerLink]="['/reserva-espacos/reservas', r.id]">{{ data(r.data) }}</a></td>
                <td>{{ hora(r.hora_inicio) }}–{{ hora(r.hora_fim) }}</td>
                <td><i class="ponto-cor" [style.background]="r.espaco_cor"></i>{{ r.espaco_nome }}</td>
                <td><strong>{{ r.titulo }}</strong>@if (r.ocorrencias_serie > 1) { <small> · série de {{ r.ocorrencias_serie }}</small> }</td>
                <td>{{ r.responsavel_nome || r.solicitante_nome }}</td>
                <td><span [class]="'selo-reserva ' + r.status">{{ rotulo(r.status) }}</span></td>
              </tr>
            } @empty { <tr><td colspan="6" class="estado-vazio">Nenhuma reserva encontrada.</td></tr> }
          </tbody>
        </table>
      </div>
    </section>
  `,
})
export class ListaReservasComponent implements OnInit {
  private readonly api = inject(ReservasApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(EstadoReservasService);
  protected readonly todas = inject(ActivatedRoute).snapshot.data['modo'] === 'todas';

  protected readonly itens = signal<Reserva[]>([]);
  protected readonly total = signal(0);
  protected filtros: FiltrosReservas = { status: '', espaco_id: '', inicio: '', fim: '', busca: '' };
  protected readonly status = Object.entries(ROTULOS_STATUS);
  protected data = dataBr;
  protected hora = horaCurta;
  protected rotulo = (s: Reserva['status']) => ROTULOS_STATUS[s];

  ngOnInit(): void {
    this.estado.carregar().subscribe();
    this.carregar();
  }

  protected carregar(): void {
    const falha = (e: unknown) => this.dialogos.mostrarErro(e, 'Não foi possível carregar as reservas');
    if (this.todas) this.api.listar(this.filtros, 1, 200).subscribe({ next: (r) => { this.itens.set(r.itens); this.total.set(r.total); }, error: falha });
    else this.api.minhas(this.filtros.status ?? '').subscribe({ next: (r) => { this.itens.set(r); this.total.set(r.length); }, error: falha });
  }

  protected exportar(): void {
    this.api.exportar(this.filtros).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível exportar') });
  }
}
