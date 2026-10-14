// Criado por José Eduardo Santana Martins
// Este arquivo serve para a aba Baixa: lista das baixas (rascunhos, pendentes de aprovação e decididas) e atalho para começar uma.
import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { classeMarcador } from '../tarefas/marcadores.paleta';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { Baixa, COR_STATUS, ROTULOS_STATUS } from './patrimonio.models';

@Component({
  selector: 'app-baixas',
  imports: [RouterLink, DatePipe, CabecalhoPatrimonioComponent],
  template: `
    <app-cabecalho-patrimonio titulo="Baixa de bens" descricao="Só entram bens já aprovados como inservíveis ou extraviados. A aprovação gera o termo em PDF." />
    <section class="painel-gestao patrimonio">
      @if (estado.podeOperar()) { <div class="pat-barra"><button type="button" class="acao-primaria pat-botao-grande" (click)="nova()">+ Nova baixa</button></div> }
      <div class="pat-lista-bens">
        @for (b of baixas(); track b.id) {
          <a class="pat-cartao-bem" [routerLink]="['/patrimonio/baixas', b.id]">
            <span class="pat-chapa">{{ b.itens.length }} bem(ns)</span>
            <span class="pat-descricao">{{ b.solicitante_nome }}</span>
            <small class="pat-sala">{{ b.criada_em | date: 'dd/MM/yyyy HH:mm' }}</small>
            <span class="pat-marcadores"><span [class]="marcador(cores[b.status])">{{ rotulos[b.status] }}</span>@if (b.tem_termo) { <span [class]="marcador(4)">Termo em PDF</span> }</span>
          </a>
        } @empty { <p class="estado-vazio">Nenhuma baixa ainda.</p> }
      </div>
    </section>
  `,
})
export class BaixasComponent implements OnInit {
  private readonly api = inject(PatrimonioApiService);
  private readonly roteador = inject(Router);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(PatrimonioEstadoService);
  protected readonly baixas = signal<Baixa[]>([]);
  protected readonly marcador = classeMarcador;
  protected readonly cores = COR_STATUS;
  protected readonly rotulos = ROTULOS_STATUS;

  ngOnInit(): void {
    void this.estado.carregar();
    this.api.baixas().subscribe({ next: (x) => this.baixas.set(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar as baixas') });
  }

  protected nova(): void {
    this.api.criarBaixa(crypto.randomUUID()).subscribe({ next: (b) => void this.roteador.navigate(['/patrimonio/baixas', b.id]), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar a baixa') });
  }
}
