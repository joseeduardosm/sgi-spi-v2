// Criado por José Eduardo Santana Martins
// Este arquivo serve para as abas de inservíveis e de extraviados (a rota define qual): as listas de classificação (rascunhos, pendentes de aprovação e decididas).
import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { classeMarcador } from '../tarefas/marcadores.paleta';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { Classificacao, COR_STATUS, ROTULOS_STATUS } from './patrimonio.models';

@Component({
  selector: 'app-listas-classificacao',
  imports: [RouterLink, DatePipe, CabecalhoPatrimonioComponent],
  template: `
    <app-cabecalho-patrimonio [titulo]="extraviado ? 'Extraviados' : 'Inservíveis'" [descricao]="extraviado ? 'Monte a lista dos bens extraviados, justifique e envie para aprovação do controle total.' : 'Monte a lista dos bens inservíveis, justifique e envie para aprovação do controle total.'" />
    <section class="painel-gestao patrimonio">
      @if (estado.podeOperar()) {
        <div class="pat-barra">
          <button type="button" class="acao-primaria pat-botao-grande" (click)="nova(tipo)">{{ extraviado ? '+ Lista de extraviados' : '+ Lista de inservíveis' }}</button>
        </div>
      }
      <div class="pat-lista-bens">
        @for (c of listas(); track c.id) {
          <a class="pat-cartao-bem" [routerLink]="[base, c.id]">
            <span class="pat-chapa"><b class="texto-codigo">#{{ c.numero }}</b> · {{ extraviado ? 'Extraviados' : 'Inservíveis' }} · {{ c.itens.length }} bem(ns)</span>
            <span class="pat-descricao">{{ c.solicitante_nome }}</span>
            <small class="pat-sala">{{ c.criada_em | date: 'dd/MM/yyyy HH:mm' }}</small>
            <span class="pat-marcadores"><span [class]="marcador(cores[c.status])">{{ rotulos[c.status] }}</span></span>
          </a>
        } @empty { <p class="estado-vazio">Nenhuma lista de {{ extraviado ? 'extraviados' : 'inservíveis' }} ainda.</p> }
      </div>
    </section>
  `,
})
export class ListasClassificacaoComponent implements OnInit {
  private readonly api = inject(PatrimonioApiService);
  private readonly roteador = inject(Router);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(PatrimonioEstadoService);
  private readonly rota = inject(ActivatedRoute);
  /** Tipo da tela (`inserviveis` ou `extraviados`), vindo da rota. */
  protected readonly tipo: 'inservivel' | 'extraviado' = this.rota.snapshot.data['tipo'] === 'extraviado' ? 'extraviado' : 'inservivel';
  protected readonly extraviado = this.tipo === 'extraviado';
  protected readonly base = this.extraviado ? '/patrimonio/extraviados' : '/patrimonio/inserviveis';
  protected readonly listas = signal<Classificacao[]>([]);
  protected readonly marcador = classeMarcador;
  protected readonly cores = COR_STATUS;
  protected readonly rotulos = ROTULOS_STATUS;

  ngOnInit(): void {
    void this.estado.carregar();
    this.api.classificacoes().subscribe({ next: (x) => this.listas.set(x.filter((c) => c.tipo === this.tipo)), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar as listas') });
  }

  protected nova(tipo: 'inservivel' | 'extraviado'): void {
    this.api.criarClassificacao(tipo, crypto.randomUUID()).subscribe({
      next: (c) => void this.roteador.navigate([this.base, c.id]), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar a lista'),
    });
  }
}
