// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela Administração › SLA de prazos (prazos de resposta e de resolução em dias úteis, por módulo e prioridade).

import { HttpClient } from '@angular/common/http';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ambiente } from '../../../../environments/ambiente';
import { AcessoService } from '../../../core/acesso/acesso.service';
import { TrilhaComponent } from '../../../shared/componentes/trilha/trilha.component';
import { erroExibivel } from '../../../shared/utilitarios/erros-api';
import { PoliticaSla } from '../../sla/sla.models';

const ROTULOS_PRIORIDADE: Record<string, string> = { critica: 'Crítica', alta: 'Alta', normal: 'Normal', baixa: 'Baixa', '': 'Todas (regra única)' };
const ROTULOS_MODULO: Record<string, string> = { tarefas: 'Tarefas', melhorias: 'Melhorias' };

/**
 * Política de SLA: para cada módulo (e, nas tarefas, para cada prioridade), em quantos dias úteis o item deve receber o primeiro atendimento e ser
 * resolvido. A contagem começa no dia da criação e pula fins de semana e feriados cadastrados no RH. Linha desativada volta ao prazo padrão.
 */
@Component({
  selector: 'app-gestao-sla',
  imports: [FormsModule, TrilhaComponent],
  template: `
    <div class="cabecalho-pagina">
      <div>
        <app-trilha [itens]="[{ rotulo: 'Administração' }, { rotulo: 'SLA de prazos' }]" />
        <h1>SLA de prazos</h1>
        <small>Prazo de resposta (primeiro atendimento) e de resolução, em dias úteis a partir da criação. Vale para Tarefas (por prioridade) e Melhorias.
          Tarefas geradas por outros módulos, como Contratos, ficam de fora.</small>
      </div>
    </div>

    @if (aviso(); as a) { <p class="aviso-admin" [class.erro]="a.erro" role="status">{{ a.texto }}</p> }

    <section class="painel-gestao" aria-labelledby="titulo-politica">
      <div class="barra-ferramentas"><div><h2 id="titulo-politica">Política</h2></div></div>
      <div class="tabela-gestao-envoltorio">
        <table class="tabela-gestao">
          <thead><tr><th>Módulo</th><th>Prioridade</th><th class="num">Resposta (dias úteis)</th><th class="num">Resolução (dias úteis)</th><th>Em uso</th></tr></thead>
          <tbody>
            @for (l of linhas(); track l.modulo + l.prioridade) {
              <tr>
                <td>{{ modulo[l.modulo] }}</td><td>{{ prioridade[l.prioridade] }}</td>
                <td class="num"><input type="number" min="0" max="365" class="campo-tabela" [name]="'r' + l.modulo + l.prioridade" [attr.aria-label]="'Resposta: ' + modulo[l.modulo] + ' ' + prioridade[l.prioridade]" [disabled]="!podeGravar()" [(ngModel)]="l.dias_uteis_resposta" /></td>
                <td class="num"><input type="number" min="0" max="365" class="campo-tabela" [name]="'s' + l.modulo + l.prioridade" [attr.aria-label]="'Resolução: ' + modulo[l.modulo] + ' ' + prioridade[l.prioridade]" [disabled]="!podeGravar()" [(ngModel)]="l.dias_uteis_resolucao" /></td>
                <td><input type="checkbox" [name]="'a' + l.modulo + l.prioridade" [attr.aria-label]="'Usar esta linha'" [disabled]="!podeGravar()" [(ngModel)]="l.ativo" /></td>
              </tr>
            } @empty { <tr><td colspan="5" class="estado-vazio">Carregando…</td></tr> }
          </tbody>
        </table>
      </div>
      @if (podeGravar()) {
        <div class="acoes-formulario" style="margin-top: 12px"><button type="button" class="acao-primaria" [disabled]="salvando() || !valida()" (click)="salvar()">{{ salvando() ? 'Salvando…' : 'Salvar política' }}</button></div>
        @if (!valida()) { <p class="aviso-bloco erro">Em cada linha, o prazo de resolução não pode ser menor que o de resposta.</p> }
      } @else {
        <p class="dica-formulario">Você só pode consultar a política (gravar exige permissão de modificação no recurso SLA).</p>
      }
    </section>
  `,
})
export class GestaoSlaComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly acesso = inject(AcessoService);

  protected readonly modulo = ROTULOS_MODULO;
  protected readonly prioridade = ROTULOS_PRIORIDADE;
  protected readonly linhas = signal<PoliticaSla[]>([]);
  protected readonly salvando = signal(false);
  protected readonly aviso = signal<{ texto: string; erro: boolean } | null>(null);
  protected readonly podeGravar = computed(() => this.acesso.pode('sla', 'MODIFICACAO'));

  ngOnInit(): void {
    this.http.get<PoliticaSla[]>(`${ambiente.urlApi}/sla/politicas`).subscribe({
      next: (l) => this.linhas.set(l),
      error: (e) => this.aviso.set({ texto: erroExibivel(e).mensagem, erro: true }),
    });
  }

  protected valida(): boolean {
    return this.linhas().every((l) => Number.isInteger(+l.dias_uteis_resposta) && Number.isInteger(+l.dias_uteis_resolucao) && +l.dias_uteis_resolucao >= +l.dias_uteis_resposta);
  }

  protected salvar(): void {
    this.salvando.set(true);
    this.http.put<PoliticaSla[]>(`${ambiente.urlApi}/sla/politicas`, { politicas: this.linhas().map((l) => ({ ...l, dias_uteis_resposta: +l.dias_uteis_resposta, dias_uteis_resolucao: +l.dias_uteis_resolucao })) }).subscribe({
      next: (l) => {
        this.linhas.set(l);
        this.salvando.set(false);
        this.aviso.set({ texto: 'Política de SLA salva.', erro: false });
      },
      error: (e) => {
        this.salvando.set(false);
        this.aviso.set({ texto: erroExibivel(e).mensagem, erro: true });
      },
    });
  }
}
