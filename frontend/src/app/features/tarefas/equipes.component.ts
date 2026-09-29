// Criado por José Eduardo Santana Martins
// Este arquivo serve para o acompanhamento das equipes de tarefas (cartões com totais), separado da configuração.

import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoTarefasComponent } from './cabecalho-tarefas.component';
import { TarefasApiService } from './tarefas-api.service';
import { Equipe } from './tarefas.models';

/** Cartões das equipes visíveis (membro, liderança ou SuperRoot), com as subequipes logo abaixo da equipe pai. */
@Component({
  selector: 'app-equipes',
  imports: [RouterLink, DecimalPipe, CabecalhoTarefasComponent],
  template: `
    <app-cabecalho-tarefas titulo="Equipes" [trilha]="[{ rotulo: 'Equipes' }]"
                           descricao="Acompanhe as equipes de que você participa ou lidera. A liderança vê também as equipes abaixo." />
    <div class="barra-acoes-tarefa">
      <div class="principais"></div>
      <div class="secundarias"><a class="acao-secundaria" routerLink="/tarefas/equipes/nova/configurar">+ Nova equipe</a></div>
    </div>

    <div class="grade-equipes">
      @for (e of ordenadas(); track e.id) {
        <article class="cartao-dados cartao-equipe" [class.subequipe]="e.equipe_pai_id">
          <header>
            <div>
              <h2><a [routerLink]="['/tarefas/equipes', e.id]">{{ e.nome }}</a></h2>
              <small>@if (e.equipe_pai_nome) { Dentro de {{ e.equipe_pai_nome }} · } {{ e.membros.length }} membro{{ e.membros.length === 1 ? '' : 's' }}
                · {{ e.lideres.length + (e.dono ? 1 : 0) }} na liderança</small>
            </div>
            @if (e.lider) { <span class="selo-status" data-status="em_validacao">Você lidera</span> }
          </header>
          <div class="corpo">
            <dl class="numeros-equipe">
              <div><dt>Em aberto</dt><dd>{{ e.indicadores.operacionais }}</dd></div>
              <div [class.alerta]="e.indicadores.atrasadas"><dt>Atrasadas</dt><dd>{{ e.indicadores.atrasadas }}</dd></div>
              <div [class.validacao]="e.indicadores.em_validacao"><dt>Em validação</dt><dd>{{ e.indicadores.em_validacao }}</dd></div>
              <div><dt>Concluídas</dt><dd>{{ e.indicadores.concluidas }}</dd></div>
            </dl>
            <p class="carga-equipe">Carga: <strong>{{ e.indicadores.carga | number: '1.0-1' }} pts</strong></p>
            <div class="acoes-formulario">
              @if (e.pode_configurar) { <a class="acao-secundaria" [routerLink]="['/tarefas/equipes', e.id, 'configurar']">Configurar</a> }
              @if (e.lider) { <a class="acao-secundaria" [routerLink]="['/tarefas/equipes', e.id]" [queryParams]="{ visao: 'pessoas' }">Pessoas</a> }
              @if (e.lider && e.indicadores.em_validacao) {
                <a class="acao-positiva botao-link" [routerLink]="['/tarefas/equipes', e.id]" [queryParams]="{ status: 'em_validacao' }">Validar entregas</a>
              }
              <a class="acao-primaria" [routerLink]="['/tarefas/equipes', e.id]">Ver tarefas</a>
            </div>
          </div>
        </article>
      } @empty {
        <p class="estado-vazio">{{ carregando() ? 'Carregando…' : 'Você ainda não participa de nenhuma equipe. Crie uma em "Nova equipe".' }}</p>
      }
    </div>
  `,
})
export class EquipesComponent implements OnInit {
  private readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly equipes = signal<Equipe[]>([]);
  protected readonly carregando = signal(true);

  /** Equipes raiz em ordem de nome, cada uma seguida das subequipes. */
  protected readonly ordenadas = computed(() => {
    const todas = [...this.equipes()].sort((a, b) => a.nome.localeCompare(b.nome));
    const ids = new Set(todas.map((e) => e.id));
    const resultado: Equipe[] = [];
    const incluir = (e: Equipe) => {
      resultado.push(e);
      todas.filter((f) => f.equipe_pai_id === e.id).forEach(incluir);
    };
    todas.filter((e) => !e.equipe_pai_id || !ids.has(e.equipe_pai_id)).forEach(incluir);
    return resultado;
  });

  ngOnInit(): void {
    this.api.equipes().subscribe({
      next: (l) => { this.equipes.set(l); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e); },
    });
  }
}
