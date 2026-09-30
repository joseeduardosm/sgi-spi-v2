// Criado por José Eduardo Santana Martins
// Este arquivo serve para a triagem das sugestões de melhoria: filtros, tratamento, conversão em tarefa, planilha e relatório em PDF.

import { DatePipe } from '@angular/common';
import { Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { debounceTime, Subject } from 'rxjs';

import { ImagemAutenticadaDirective } from '../noticias/gestao/imagem-autenticada.directive';
import { TarefasApiService } from '../tarefas/tarefas-api.service';
import { Equipe, PessoaCarga } from '../tarefas/tarefas.models';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoMelhoriasComponent } from './cabecalho-melhorias.component';
import { MelhoriasApiService } from './melhorias-api.service';
import {
  ConversaoTarefa, FiltrosTriagem, PaginaTriagem, PrintSugestao, ROTULOS_MODULO, ROTULOS_SITUACAO, SituacaoSugestao, SugestaoTriagem, Tratamento,
} from './melhorias.models';

const SITUACOES = Object.keys(ROTULOS_SITUACAO) as SituacaoSugestao[];

@Component({
  selector: 'app-triagem-melhorias',
  imports: [FormsModule, DatePipe, RouterLink, CabecalhoMelhoriasComponent, ImagemAutenticadaDirective],
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
                <tr (click)="abrir(s)" class="linha-clicavel">
                  <td><strong>#{{ s.numero }}</strong></td>
                  <td><span class="resumo-sugestao">{{ s.texto }}</span>
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

    @if (aberta(); as s) {
      <div class="fundo-modal" role="presentation" (click)="fechar()"></div>
      <section class="modal-portal modal-largo janela-melhorias" role="dialog" aria-modal="true" aria-labelledby="titulo-tratar">
        <header><div><span class="modal-sobretitulo">Sugestão #{{ s.numero }} · {{ modulos[s.modulo] ?? s.modulo }}</span><h2 id="titulo-tratar">Tratar sugestão</h2></div>
          <button type="button" aria-label="Fechar" (click)="fechar()">×</button></header>
        <div class="corpo-janela-melhorias">
          <dl class="dados-sugestao">
            <div><dt>Autor</dt><dd>{{ s.autor_nome }} — &#64;{{ s.autor_login }}</dd></div>
            <div><dt>Enviada em</dt><dd>{{ s.criado_em | date: 'dd/MM/yyyy HH:mm' }}</dd></div>
            <div class="inteira"><dt>Tela</dt><dd><code>{{ s.tela || '—' }}</code></dd></div>
            <div class="inteira"><dt>Sugestão</dt><dd class="texto-sugestao">{{ s.texto }}</dd></div>
          </dl>
          @if (s.prints.length) {
            <div class="prints-sugestao grandes">
              @for (p of s.prints; track p.id) {
                <button type="button" [title]="'Baixar ' + p.nome" (click)="baixar(p)"><img [appImagemAutenticada]="p.url" [alt]="p.nome" /></button>
              }
            </div>
          }

          <form (submit)="$event.preventDefault(); salvar()">
            <div class="grade-formulario uma-coluna">
              <div><label for="tr-situacao">Situação</label>
                <select id="tr-situacao" name="situacao" [(ngModel)]="tratamento.situacao">
                  @for (x of situacoes; track x) { <option [value]="x">{{ rotulos[x] }}</option> }
                </select></div>
              <div><label for="tr-resposta">Resposta ao autor</label>
                <textarea id="tr-resposta" name="resposta" rows="3" maxlength="4000" [(ngModel)]="tratamento.resposta_publica"
                          placeholder="O autor vê esta resposta em Minhas sugestões e recebe aviso."></textarea></div>
              <div><label for="tr-obs">Observação interna</label>
                <textarea id="tr-obs" name="obs" rows="3" maxlength="12000" [(ngModel)]="tratamento.observacao_interna"
                          placeholder="Só quem faz a triagem vê."></textarea></div>
            </div>
            <div class="acoes-cartao">
              @if (s.tarefa_numero) {
                <a class="link-arquivo" [routerLink]="['/tarefas']" [queryParams]="{ tarefa: s.tarefa_numero }">Tarefa #{{ s.tarefa_numero }} ↗</a>
              } @else {
                <button type="button" class="acao-secundaria" (click)="abrirConversao(s)">Converter em tarefa</button>
              }
              <button type="submit" class="acao-primaria" [disabled]="salvando()">{{ salvando() ? 'Salvando…' : 'Salvar tratamento' }}</button>
            </div>
          </form>

          @if (conversao(); as c) {
            <form class="conversao-tarefa" (submit)="$event.preventDefault(); converter()">
              <p class="secao-formulario">Nova tarefa no Módulo Tarefas</p>
              <div class="grade-formulario">
                <div class="ocupa-duas"><label for="cv-titulo">Título *</label><input id="cv-titulo" name="titulo" maxlength="200" [(ngModel)]="c.titulo" /></div>
                <div><label for="cv-equipe">Equipe</label>
                  <select id="cv-equipe" name="equipe" [(ngModel)]="c.equipe_id" (ngModelChange)="aoTrocarEquipe($event)">
                    <option [ngValue]="null">Sem equipe (tarefa pessoal)</option>
                    @for (e of equipes(); track e.id) { <option [ngValue]="e.id">{{ e.nome }}</option> }
                  </select></div>
                <div><label for="cv-resp">Responsável</label>
                  <select id="cv-resp" name="resp" [(ngModel)]="c.responsavel_id">
                    <option [ngValue]="null">Eu</option>
                    @for (p of pessoas(); track p.id) { <option [ngValue]="p.id">{{ p.nome }}</option> }
                  </select></div>
                <div><label for="cv-prazo">Prazo *</label><input id="cv-prazo" name="prazo" type="date" [(ngModel)]="prazoData" /></div>
                <div><label for="cv-prio">Prioridade</label>
                  <select id="cv-prio" name="prio" [(ngModel)]="c.prioridade">
                    <option value="baixa">Baixa</option><option value="normal">Normal</option><option value="alta">Alta</option><option value="critica">Crítica</option>
                  </select></div>
              </div>
              <div class="acoes-cartao">
                <small class="dica-formulario">A descrição da tarefa leva o texto, o autor e a tela da sugestão; a sugestão fica Aceita.</small>
                <span>
                  <button type="button" class="acao-secundaria" (click)="conversao.set(null)">Cancelar</button>
                  <button type="submit" class="acao-positiva" [disabled]="!c.titulo.trim() || !prazoData">Criar tarefa</button>
                </span>
              </div>
            </form>
          }

          @if (s.eventos.length) {
            <p class="secao-formulario">Histórico</p>
            <ul class="historico-sugestao">
              @for (e of s.eventos; track $index) {
                <li><span>{{ e.descricao }}</span><small>{{ e.autor_nome }} · {{ e.criado_em | date: 'dd/MM/yyyy HH:mm' }}</small></li>
              }
            </ul>
          }
        </div>
      </section>
    }
  `,
  // Esc fecha a janela de tratamento, com o foco em qualquer lugar
  host: { '(document:keydown.escape)': 'aberta() && fechar()' },
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
    // Link do aviso (?sugestao=N) abre a sugestão
    const n = Number(this.rota.snapshot.queryParamMap.get('sugestao'));
    if (n) this.api.detalhe(n).subscribe({ next: (s) => this.abrir(s), error: () => undefined });
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

  protected abrir(s: SugestaoTriagem): void {
    this.aberta.set(s);
    this.conversao.set(null);
    this.tratamento = { situacao: s.situacao, resposta_publica: s.resposta_publica, observacao_interna: s.observacao_interna };
  }

  protected fechar(): void {
    this.aberta.set(null);
    this.conversao.set(null);
    if (this.rota.snapshot.queryParamMap.has('sugestao')) void this.roteador.navigate([], { queryParams: { sugestao: null }, queryParamsHandling: 'merge', replaceUrl: true });
  }

  protected salvar(): void {
    const s = this.aberta();
    if (!s) return;
    this.salvando.set(true);
    this.api.tratar(s.numero, this.tratamento).subscribe({
      next: (novo) => {
        this.salvando.set(false);
        this.atualizarNaLista(novo);
        this.aberta.set(null);
      },
      error: (e) => {
        this.salvando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível salvar o tratamento');
      },
    });
  }

  protected abrirConversao(s: SugestaoTriagem): void {
    const titulo = s.texto.split('\n')[0].slice(0, 120);
    this.conversao.set({ titulo: `Melhoria #${s.numero}: ${titulo}`.slice(0, 200), prazo: '', prioridade: 'normal', equipe_id: null, responsavel_id: null });
    const prazo = new Date();
    prazo.setDate(prazo.getDate() + 14);
    this.prazoData = prazo.toLocaleDateString('sv-SE');
    if (!this.equipes().length) this.tarefas.equipes().subscribe({ next: (l) => this.equipes.set(l), error: () => undefined });
    this.pessoas.set([]);
  }

  protected aoTrocarEquipe(equipeId: string | null): void {
    this.conversao.update((c) => (c ? { ...c, equipe_id: equipeId, responsavel_id: null } : c));
    this.pessoas.set([]);
    if (equipeId) this.tarefas.pessoas(equipeId).subscribe({ next: (l) => this.pessoas.set(l), error: () => undefined });
  }

  protected converter(): void {
    const s = this.aberta(), c = this.conversao();
    if (!s || !c) return;
    // Prazo no fim do expediente do dia escolhido (horário local)
    const prazo = new Date(`${this.prazoData}T18:00:00`).toISOString();
    this.dialogos.executar(this.api.converterEmTarefa(s.numero, { ...c, prazo }), 'Criando a tarefa…').subscribe({
      next: (novo) => {
        this.atualizarNaLista(novo);
        this.abrir(novo);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar a tarefa'),
    });
  }

  protected exportar(): void {
    this.dialogos.executar(this.api.exportar(this.filtros), 'Gerando a planilha…').subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected relatorio(): void {
    this.dialogos.executar(this.api.relatorio(this.filtros), 'Gerando o relatório…').subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected baixar(p: PrintSugestao): void {
    this.api.baixarPrint(p.url, p.nome).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Atualiza a linha e recarrega os totais (a situação pode ter mudado). */
  private atualizarNaLista(novo: SugestaoTriagem): void {
    this.pagina.update((p) => (p ? { ...p, itens: p.itens.map((x) => (x.id === novo.id ? novo : x)) } : p));
    this.carregar(this.pagina()?.pagina ?? 1);
  }
}
