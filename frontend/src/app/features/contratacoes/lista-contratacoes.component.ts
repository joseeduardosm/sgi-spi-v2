// Criado por José Eduardo Santana Martins
// Este arquivo serve para a lista de ETP e TR: painel de andamento, filtros, novo documento e importação de Word com prévia.

import { DatePipe } from '@angular/common';
import { Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { debounceTime, Subject } from 'rxjs';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { ContratacoesApiService } from './contratacoes-api.service';
import { DocumentoResumo, ListaDocumentos, PainelContratacoes, PreviaImportacao, ROTULOS_PAPEL, ROTULOS_SITUACAO, ROTULOS_TIPO, TipoDocumento } from './contratacoes.models';

type Janela = null | 'novo' | 'importar';

/** Lista os ETP e TR que o usuário enxerga (criador, membro ou administração) e cria ou importa novos. */
@Component({
  selector: 'app-lista-contratacoes',
  imports: [FormsModule, DatePipe, RouterLink, TrilhaComponent],
  template: `
    <div class="cabecalho-pagina">
      <div>
        <app-trilha [itens]="[{ rotulo: 'Contratações', rota: '/contratacoes' }]" />
        <h1>Contratações</h1>
        <small>Estudos Técnicos Preliminares (ETP) e Termos de Referência (TR), com revisão e histórico de versões.</small>
      </div>
      @if (lista()?.pode_criar) {
        <div class="acoes-cabecalho">
          <button type="button" class="acao-secundaria" (click)="abrir('importar')">Importar Word</button>
          <button type="button" class="acao-primaria" (click)="abrir('novo')">Novo documento</button>
        </div>
      }
    </div>

    <section class="painel-gestao contratacoes">
      @if (painel(); as p) {
        <div class="resumo-contratacoes">
          <div><strong>{{ p.total }}</strong><span>documentos</span></div>
          <div><strong>{{ p.por_situacao['rascunho'] }}</strong><span>em rascunho</span></div>
          <div><strong>{{ p.por_situacao['em_revisao'] }}</strong><span>em revisão</span></div>
          <div><strong>{{ p.por_situacao['concluido'] }}</strong><span>concluídos</span></div>
          <div><strong>{{ p.revisoes_abertas }}</strong><span>revisões abertas</span></div>
          <div><strong>{{ p.sem_vinculo }}</strong><span>concluídos sem contrato</span></div>
        </div>
      }
      <div class="barra-contratacoes">
        <div class="campo"><label for="ct-busca">Buscar</label>
          <input id="ct-busca" placeholder="Nome ou número do processo" [ngModel]="busca" (ngModelChange)="digitar($event)" /></div>
        <div class="campo curto"><label for="ct-tipo">Tipo</label>
          <select id="ct-tipo" [(ngModel)]="tipo" (ngModelChange)="carregar()"><option value="">Todos</option><option value="etp">ETP</option><option value="tr">TR</option></select></div>
        <div class="campo curto"><label for="ct-sit">Situação</label>
          <select id="ct-sit" [(ngModel)]="situacao" (ngModelChange)="carregar()">
            <option value="">Todas</option>
            @for (s of situacoes; track s[0]) { <option [value]="s[0]">{{ s[1] }}</option> }
          </select></div>
      </div>

      @if (!lista()) {
        <p class="estado-vazio">Carregando…</p>
      } @else if (!lista()!.itens.length) {
        <p class="estado-vazio">Nenhum documento encontrado.</p>
      } @else {
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <thead><tr><th>Tipo</th><th>Nome</th><th>Processo SEI</th><th>Situação</th><th>Contrato</th><th>Responsável</th><th>Atualizado</th></tr></thead>
            <tbody>
              @for (d of lista()!.itens; track d.id) {
                <tr>
                  <td><span [class]="'selo-tipo ' + d.tipo">{{ rotuloTipo[d.tipo] }}</span></td>
                  <td><a [routerLink]="['/contratacoes', d.id]"><strong>{{ d.nome }}</strong></a>
                    <small class="papel">{{ papeis[d.meu_papel] }}@if (d.revisoes_abertas) { · {{ d.revisoes_abertas }} revisão(ões) aberta(s) }</small></td>
                  <td>{{ d.processo || '—' }}</td>
                  <td><span [class]="'situacao ' + d.situacao">{{ rotuloSituacao[d.situacao] }}</span></td>
                  <td>{{ d.contrato_numero || '—' }}</td>
                  <td>{{ d.criador_nome }}</td>
                  <td>{{ d.atualizado_em | date: 'dd/MM/yyyy HH:mm' }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      }
    </section>

    @if (janela() === 'novo') {
      <div class="fundo-modal" role="presentation" (click)="fechar()"></div>
      <section class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-novo">
        <header><div><span class="modal-sobretitulo">Contratações</span><h2 id="titulo-novo">Novo documento</h2></div><button type="button" aria-label="Fechar" (click)="fechar()">×</button></header>
        <form (ngSubmit)="criar()" class="form-contratacoes">
          <div class="grade-formulario uma-coluna">
            <div><label for="nv-tipo">Tipo *</label>
              <select id="nv-tipo" name="tipo" [(ngModel)]="novoTipo"><option value="etp">ETP: Estudo Técnico Preliminar</option><option value="tr">TR: Termo de Referência</option></select></div>
            <div><label for="nv-nome">Nome *</label><input id="nv-nome" name="nome" maxlength="300" [(ngModel)]="novoNome" /></div>
            <div><label for="nv-proc">Processo SEI</label><input id="nv-proc" name="processo" maxlength="100" [(ngModel)]="novoProcesso" /></div>
          </div>
          <footer><button type="button" class="acao-secundaria" (click)="fechar()">Cancelar</button>
            <button type="submit" class="acao-positiva" [disabled]="!novoNome.trim() || ocupado()">Criar</button></footer>
        </form>
      </section>
    }

    @if (janela() === 'importar') {
      <div class="fundo-modal" role="presentation" (click)="fechar()"></div>
      <section class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="titulo-imp">
        <header><div><span class="modal-sobretitulo">Contratações</span><h2 id="titulo-imp">Importar um Word</h2></div><button type="button" aria-label="Fechar" (click)="fechar()">×</button></header>
        <div class="form-contratacoes">
          <div class="grade-formulario">
            <div><label for="im-tipo">Tipo *</label>
              <select id="im-tipo" [(ngModel)]="novoTipo"><option value="etp">ETP</option><option value="tr">TR</option></select></div>
            <div><label for="im-arq">Arquivo .docx (até 10 MB) *</label>
              <input id="im-arq" type="file" accept=".docx" (change)="escolherArquivo($event)" /></div>
            <div><label for="im-nome">Nome (opcional)</label><input id="im-nome" maxlength="300" [(ngModel)]="novoNome" /></div>
            <div><label for="im-proc">Processo SEI (opcional)</label><input id="im-proc" maxlength="100" [(ngModel)]="novoProcesso" /></div>
          </div>
          @if (previa(); as p) {
            <div class="previa-importacao">
              <p><strong>{{ p.totais.secoes }}</strong> seção(ões), <strong>{{ p.totais.itens }}</strong> item(ns), <strong>{{ p.totais.tabelas }}</strong> tabela(s),
                <strong>{{ p.totais.para_revisar }}</strong> para revisar e <strong>{{ p.totais.comentarios }}</strong> comentário(s) do Word.</p>
              @for (s of p.secoes; track s.id_cliente) {
                <details><summary>{{ s.titulo }} ({{ s.itens.length }})</summary>
                  <ul>@for (i of s.itens.slice(0, 40); track i.id_cliente) { <li [class.revisar]="i.precisa_revisao">{{ i.conteudo.slice(0, 140) }}</li> }</ul></details>
              }
              @if (p.avisos.length) { <div class="avisos-importacao"><strong>Atenção</strong><ul>@for (a of p.avisos; track a) { <li>{{ a }}</li> }</ul></div> }
            </div>
          }
          <footer>
            <button type="button" class="acao-secundaria" (click)="fechar()">Cancelar</button>
            <button type="button" class="acao-secundaria" [disabled]="!arquivo || ocupado()" (click)="importar(false)">Ver prévia</button>
            <button type="button" class="acao-positiva" [disabled]="!previa() || ocupado()" (click)="importar(true)">Confirmar importação</button>
          </footer>
        </div>
      </section>
    }
  `,
})
export class ListaContratacoesComponent implements OnInit {
  private readonly api = inject(ContratacoesApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly router = inject(Router);
  private readonly digitacao = new Subject<string>();

  protected readonly lista = signal<ListaDocumentos | null>(null);
  protected readonly painel = signal<PainelContratacoes | null>(null);
  protected readonly janela = signal<Janela>(null);
  protected readonly ocupado = signal(false);
  protected readonly previa = signal<PreviaImportacao | null>(null);
  protected readonly rotuloTipo = ROTULOS_TIPO;
  protected readonly rotuloSituacao = ROTULOS_SITUACAO;
  protected readonly papeis = ROTULOS_PAPEL;
  protected readonly situacoes = Object.entries(ROTULOS_SITUACAO);

  protected busca = '';
  protected tipo = '';
  protected situacao = '';
  protected novoTipo: TipoDocumento = 'etp';
  protected novoNome = '';
  protected novoProcesso = '';
  protected arquivo: File | null = null;

  constructor() {
    this.digitacao.pipe(debounceTime(300), takeUntilDestroyed(inject(DestroyRef))).subscribe(() => this.carregar());
  }

  ngOnInit(): void {
    this.carregar();
    this.api.painel().subscribe({ next: (p) => this.painel.set(p), error: () => this.painel.set(null) });
  }

  protected digitar(valor: string): void {
    this.busca = valor;
    this.digitacao.next(valor);
  }

  protected carregar(): void {
    this.api.listar({ tipo: this.tipo, situacao: this.situacao, busca: this.busca.trim() }).subscribe({
      next: (l) => this.lista.set(l),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar os documentos'),
    });
  }

  protected abrir(janela: Janela): void {
    this.novoNome = '';
    this.novoProcesso = '';
    this.arquivo = null;
    this.previa.set(null);
    this.janela.set(janela);
  }

  protected fechar(): void {
    this.janela.set(null);
  }

  protected criar(): void {
    if (!this.novoNome.trim()) return;
    this.ocupado.set(true);
    this.api.criar({ tipo: this.novoTipo, nome: this.novoNome.trim(), processo: this.novoProcesso.trim(), link_sei: null }).subscribe({
      next: (d: DocumentoResumo) => { this.ocupado.set(false); void this.router.navigate(['/contratacoes', d.id]); },
      error: (e) => { this.ocupado.set(false); this.dialogos.mostrarErro(e, 'Não foi possível criar o documento'); },
    });
  }

  protected escolherArquivo(evento: Event): void {
    this.arquivo = (evento.target as HTMLInputElement).files?.[0] ?? null;
    this.previa.set(null);
  }

  protected importar(confirmar: boolean): void {
    if (!this.arquivo) return;
    this.ocupado.set(true);
    this.api.importarWord(this.arquivo, { tipo: this.novoTipo, nome: this.novoNome.trim(), processo: this.novoProcesso.trim(), confirmar }).subscribe({
      next: (p) => {
        this.ocupado.set(false);
        if (confirmar && p.documento_id) void this.router.navigate(['/contratacoes', p.documento_id]);
        else this.previa.set(p);
      },
      error: (e) => { this.ocupado.set(false); this.dialogos.mostrarErro(e, 'Não foi possível ler o arquivo'); },
    });
  }
}
