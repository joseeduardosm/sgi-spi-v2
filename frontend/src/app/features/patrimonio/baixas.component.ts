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
import { Baixa, Classificacao, COR_STATUS, ROTULOS_STATUS } from './patrimonio.models';

@Component({
  selector: 'app-baixas',
  imports: [RouterLink, DatePipe, CabecalhoPatrimonioComponent],
  template: `
    <app-cabecalho-patrimonio titulo="Baixa de bens" descricao="A baixa nasce de uma lista aprovada de inservíveis ou extraviados, aguarda o aceite da autoridade e conclui com o PDF do de acordo (D.O.E.)." />
    <section class="painel-gestao patrimonio">
      @if (estado.podeOperar()) {
        <div class="pat-barra">
          <select name="lista-origem" aria-label="Lista aprovada de onde a baixa herda os bens" [value]="listaEscolhida()" (change)="listaEscolhida.set($any($event.target).value)">
            <option value="">Escolha a lista aprovada…</option>
            @for (l of listasAprovadas(); track l.id) { <option [value]="l.id">#{{ l.numero }} · {{ l.tipo === 'inservivel' ? 'Inservíveis' : 'Extraviados' }} · {{ l.itens.length }} bem(ns)</option> }
          </select>
          <button type="button" class="acao-primaria pat-botao-grande" [disabled]="!listaEscolhida()" (click)="nova()">+ Dar baixa da lista</button>
        </div>
      }
      <div class="pat-lista-bens">
        @for (b of baixas(); track b.id) {
          <a class="pat-cartao-bem" [routerLink]="['/patrimonio/baixas', b.id]">
            <span class="pat-chapa"><b class="texto-codigo">#{{ b.numero }}</b> · Baixa · {{ b.itens.length }} bem(ns)</span>
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
  /** Listas aprovadas (ou aprovadas em parte) que ainda podem gerar baixa; a API recusa se já houver uma. */
  protected readonly listasAprovadas = signal<Classificacao[]>([]);
  protected readonly listaEscolhida = signal('');
  protected readonly marcador = classeMarcador;
  protected readonly cores = COR_STATUS;
  protected readonly rotulos = ROTULOS_STATUS;

  ngOnInit(): void {
    void this.estado.carregar();
    this.api.classificacoes().subscribe({ next: (l) => this.listasAprovadas.set(l.filter((x) => (x.status === 'aprovada' || x.status === 'parcial') && x.itens.some((i) => i.resultado === 'aprovado'))), error: () => this.listasAprovadas.set([]) });
    this.api.baixas().subscribe({ next: (x) => this.baixas.set(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar as baixas') });
  }

  protected nova(): void {
    this.api.criarBaixa(this.listaEscolhida(), crypto.randomUUID()).subscribe({ next: (b) => void this.roteador.navigate(['/patrimonio/baixas', b.id]), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar a baixa') });
  }
}
