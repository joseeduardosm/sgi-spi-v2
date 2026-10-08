// Criado por José Eduardo Santana Martins
// Este arquivo serve para a lista "Minhas atividades": as atividades agendadas para o usuário, separadas em atrasadas, de hoje e futuras.

import { DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoTarefasComponent } from './cabecalho-tarefas.component';
import { TarefasApiService } from './tarefas-api.service';
import { Atividade, ICONES_TIPO_ATIVIDADE, ROTULOS_TIPO_ATIVIDADE } from './tarefas.models';

@Component({
  selector: 'app-atividades',
  imports: [FormsModule, DatePipe, RouterLink, CabecalhoTarefasComponent],
  template: `
    <app-cabecalho-tarefas titulo="Minhas atividades" [trilha]="[{ rotulo: 'Atividades' }]" descricao="O que foi agendado para você nas tarefas, por data. Quem agenda e o dia chegam por aviso." />
    <div class="barra-acoes-tarefa">
      <div class="principais">
        <button type="button" class="acao-secundaria" [class.ativo]="!concluidas()" (click)="trocar(false)">Abertas</button>
        <button type="button" class="acao-secundaria" [class.ativo]="concluidas()" (click)="trocar(true)">Concluídas (últimas 50)</button>
      </div>
    </div>
    @for (g of grupos(); track g.titulo) {
      <section class="cartao-dados" style="margin-bottom: 14px">
        <header><div><h2>{{ g.titulo }}</h2><small>{{ g.itens.length }} atividade(s)</small></div></header>
        <div class="corpo">
          <ul class="lista-atividades">
            @for (a of g.itens; track a.id) {
              <li [class.concluida]="a.situacao === 'concluida'">
                <span class="icone-atividade" aria-hidden="true">{{ icones[a.tipo] }}</span>
                <div class="texto-atividade"><strong>{{ a.resumo }}</strong>
                  <small>{{ tipos[a.tipo] }} · <a [routerLink]="['/tarefas', a.tarefa_numero]">#{{ a.tarefa_numero }} {{ a.tarefa_titulo }}</a> ·
                    <span class="prazo-atividade" [attr.data-situacao]="a.situacao">{{ a.prazo + 'T12:00:00' | date: 'dd/MM/yyyy' }}</span>@if (a.criada_por && a.criada_por.id !== a.responsavel?.id) { · agendada por {{ a.criada_por.nome }} }</small>
                  @if (a.nota) { <small>{{ a.nota }}</small> }
                  @if (a.feedback) { <small class="feedback-atividade">“{{ a.feedback }}”</small> }
                  @if (concluindo() === a.id) {
                    <div class="concluir-atividade">
                      <input name="feedback" maxlength="4000" placeholder="O que foi feito ou combinado? (opcional)" aria-label="Feedback" [(ngModel)]="feedback" />
                      <button type="button" class="acao-positiva" (click)="concluir(a)">Concluir</button>
                      <button type="button" class="link-simples" (click)="concluindo.set(null)">Cancelar</button>
                    </div>
                  }
                </div>
                @if (a.pode_mexer && concluindo() !== a.id) { <button type="button" class="acao-secundaria acao-pequena" (click)="abrir(a)">✓ Concluir</button> }
              </li>
            }
          </ul>
        </div>
      </section>
    } @empty { <p class="estado-vazio">{{ carregando() ? 'Carregando…' : 'Nenhuma atividade por aqui.' }}</p> }
  `,
})
export class AtividadesComponent implements OnInit {
  private readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly icones = ICONES_TIPO_ATIVIDADE;
  protected readonly tipos = ROTULOS_TIPO_ATIVIDADE;
  protected readonly lista = signal<Atividade[]>([]);
  protected readonly concluidas = signal(false);
  protected readonly carregando = signal(true);
  protected readonly concluindo = signal<string | null>(null);
  protected feedback = '';

  protected readonly grupos = computed(() => {
    const l = this.lista();
    const por = (s: Atividade['situacao'], titulo: string) => ({ titulo, itens: l.filter((a) => a.situacao === s) });
    return (this.concluidas() ? [por('concluida', 'Concluídas')] : [por('atrasada', 'Atrasadas'), por('hoje', 'Hoje'), por('futura', 'Próximas')]).filter((g) => g.itens.length);
  });

  ngOnInit(): void {
    this.carregar();
  }

  protected trocar(concluidas: boolean): void {
    this.concluidas.set(concluidas);
    this.carregar();
  }

  private carregar(): void {
    this.carregando.set(true);
    this.api.minhasAtividades(this.concluidas()).subscribe({
      next: (l) => { this.lista.set(l); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar as atividades'); },
    });
  }

  protected abrir(a: Atividade): void {
    this.feedback = '';
    this.concluindo.set(a.id);
  }

  protected concluir(a: Atividade): void {
    this.api.concluirAtividade(a.id, this.feedback.trim()).subscribe({
      next: () => { this.concluindo.set(null); this.carregar(); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível concluir a atividade'),
    });
  }
}
