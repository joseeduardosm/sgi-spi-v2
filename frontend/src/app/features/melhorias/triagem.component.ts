// Criado por José Eduardo Santana Martins
// Este arquivo serve para a triagem das sugestões de melhoria: filtros, tratamento, conversão em tarefa, planilha e relatório em PDF.

import { DatePipe } from '@angular/common';
import { Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { debounceTime, Subject } from 'rxjs';

import { TarefasApiService } from '../tarefas/tarefas-api.service';
import { Equipe, PessoaCarga } from '../tarefas/tarefas.models';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoMelhoriasComponent } from './cabecalho-melhorias.component';
import { MelhoriasApiService } from './melhorias-api.service';
import {
  ConversaoTarefa, FiltrosTriagem, PaginaTriagem, PrintSugestao, ROTULOS_MODULO, ROTULOS_SITUACAO, SituacaoSugestao, SugestaoTriagem, Tratamento,
} from './melhorias.models';
import { LinkificarPipe } from '../../shared/utilitarios/linkificar.pipe';

const SITUACOES = Object.keys(ROTULOS_SITUACAO) as SituacaoSugestao[];

@Component({
  selector: 'app-triagem-melhorias',
  imports: [LinkificarPipe, FormsModule, DatePipe, CabecalhoMelhoriasComponent],
  template: `
    <app-cabecalho-melhorias titulo="Triagem de melhorias" descricao="Sugestões enviadas pelos usuários: analise, responda ao autor e transforme em tarefa." />
    @if (semAcesso()) {
      <div class="aviso-admin erro">A triagem de melhorias é do SuperRoot e de quem tem CONTROLE TOTAL no recurso "Melhorias" da ACL.</div>
    } @else {
      <!-- Totais por situação (com os demais filtros); o clique filtra -->
      <div class="abas" role="tablist">
        <button type="button" role="tab" [class.ativa]="!filtros.situacao" [attr.aria-selected]="!filtros.situacao" (click)="filtrarSituacao('')">
          Todas <span class="contador-aba">{{ totalGeral() }}</span></button>
        @for (s of situacoes; track s) {
          <button type="button" role="tab" [class.ativa]="filtros.situacao === s" [attr.aria-selected]="filtros.situacao === s" (click)="filtrarSituacao(s)">
            {{ rotulos[s] }} @if (pagina()?.totais?.[s]) { <span class="contador-aba" [class.destaque]="s === 'nova'">{{ pagina()!.totais[s] }}</span> }
          </button>
        }
      </div>
      <section class="painel-gestao">
        <div class="filtros-gestao filtros-melhorias">
          <input type="search" aria-label="Buscar" placeholder="Buscar por texto, autor, tela ou nº" [(ngModel)]="filtros.busca" (ngModelChange)="digitacao.next()" />
          <select aria-label="Módulo" [(ngModel)]="filtros.modulo" (ngModelChange)="carregar(1)">
            <option value="">Todos os módulos</option>
            @for (m of pagina()?.modulos ?? []; track m) { <option [value]="m">{{ modulos[m] ?? m }}</option> }
          </select>
          <label>De <input type="date" [(ngModel)]="filtros.inicio" (ngModelChange)="carregar(1)" /></label>
          <label>até <input type="date" [(ngModel)]="filtros.fim" (ngModelChange)="carregar(1)" /></label>
          <span class="espacador"></span>
          <button type="button" class="acao-secundaria acao-pequena" (click)="exportar()">Exportar planilha</button>
          <button type="button" class="acao-secundaria acao-pequena" (click)="relatorio()">Relatório PDF</button>
        </div>
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao tabela-melhorias">
            <thead><tr><th>Nº</th><th>Sugestão</th><th>Autor</th><th>Módulo</th><th>Situação</th><th>Enviada</th></tr></thead>
            <tbody>
              @for (s of pagina()?.itens ?? []; track s.id) {
                <tr (click)="abrir(s)" (keydown.enter)="abrir(s)" tabindex="0" class="linha-clicavel">
                  <td><strong>#{{ s.numero }}</strong></td>
                  <td><span class="resumo-sugestao" [innerHTML]="s.texto | linkificar"></span>
                    <small>@if (s.prints.length) { {{ s.prints.length }} print(s) · } @if (s.tarefa_numero) { tarefa #{{ s.tarefa_numero }} · } {{ s.tela }}</small></td>
                  <td>{{ s.autor_nome }}<small>&#64;{{ s.autor_login }}</small></td>
                  <td>{{ modulos[s.modulo] ?? s.modulo }}</td>
                  <td><span class="selo-sugestao" [attr.data-situacao]="s.situacao">{{ rotulos[s.situacao] }}</span></td>
                  <td>{{ s.criado_em | date: 'dd/MM/yyyy HH:mm' }}</td>
                </tr>
              } @empty {
                <tr><td class="estado-vazio" colspan="6">{{ carregando() ? 'Carregando…' : 'Nenhuma sugestão com estes filtros.' }}</td></tr>
              }
            </tbody>
          </table>
        </div>
        @if ((pagina()?.total ?? 0) > (pagina()?.tamanho ?? 20)) {
          <div class="paginacao-melhorias">
            <button type="button" class="acao-secundaria acao-pequena" [disabled]="pagina()!.pagina <= 1" (click)="carregar(pagina()!.pagina - 1)">‹ Anterior</button>
            <span>Página {{ pagina()!.pagina }} de {{ totalPaginas() }}</span>
            <button type="button" class="acao-secundaria acao-pequena" [disabled]="pagina()!.pagina >= totalPaginas()" (click)="carregar(pagina()!.pagina + 1)">Próxima ›</button>
          </div>
        }
      </section>
    }
  `,
})
export class TriagemComponent implements OnInit {
  private readonly api = inject(MelhoriasApiService);
  private readonly tarefas = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  private readonly destruir = inject(DestroyRef);
  protected readonly situacoes = SITUACOES;
  protected readonly rotulos = ROTULOS_SITUACAO;
  protected readonly modulos = ROTULOS_MODULO;
  protected readonly pagina = signal<PaginaTriagem | null>(null);
  protected readonly carregando = signal(true);
  protected readonly semAcesso = signal(false);
  protected readonly aberta = signal<SugestaoTriagem | null>(null);
  protected readonly salvando = signal(false);
  protected readonly conversao = signal<ConversaoTarefa | null>(null);
  protected readonly equipes = signal<Equipe[]>([]);
  protected readonly pessoas = signal<PessoaCarga[]>([]);
  protected filtros: FiltrosTriagem = { busca: '', situacao: '', modulo: '', inicio: '', fim: '' };
  protected tratamento: Tratamento = { situacao: 'nova', resposta_publica: '', observacao_interna: '' };
  protected prazoData = '';
  protected readonly digitacao = new Subject<void>();

  ngOnInit(): void {
    this.digitacao.pipe(debounceTime(300), takeUntilDestroyed(this.destruir)).subscribe(() => this.carregar(1));
    this.carregar(1);
    // Link antigo do aviso (?sugestao=N) segue para a tela própria da sugestão
    const n = Number(this.rota.snapshot.queryParamMap.get('sugestao'));
    if (n) void this.roteador.navigate(['/melhorias/triagem', n], { replaceUrl: true });
  }

  protected totalGeral(): number {
    const t = this.pagina()?.totais;
    return t ? Object.values(t).reduce((a, b) => a + b, 0) : 0;
  }

  protected totalPaginas(): number {
    const p = this.pagina();
    return p ? Math.max(1, Math.ceil(p.total / p.tamanho)) : 1;
  }

  protected filtrarSituacao(s: SituacaoSugestao | ''): void {
    this.filtros.situacao = s;
    this.carregar(1);
  }

  protected carregar(pagina: number): void {
    this.carregando.set(true);
    this.api.listar(this.filtros, pagina).subscribe({
      next: (p) => { this.pagina.set(p); this.carregando.set(false); },
      error: (e) => {
        this.carregando.set(false);
        if (e?.status === 403) this.semAcesso.set(true);
        else this.dialogos.mostrarErro(e, 'Não foi possível carregar as sugestões');
      },
    });
  }

  /** Abre a tela própria da sugestão. */
  protected abrir(s: SugestaoTriagem): void {
    void this.roteador.navigate(['/melhorias/triagem', s.numero]);
  }

  protected exportar(): void {
    this.dialogos.executar(this.api.exportar(this.filtros), 'Gerando a planilha…').subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected relatorio(): void {
    this.dialogos.executar(this.api.relatorio(this.filtros), 'Gerando o relatório…').subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
