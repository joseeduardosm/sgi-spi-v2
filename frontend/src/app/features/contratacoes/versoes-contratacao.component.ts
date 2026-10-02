// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela de versões do documento: linha do tempo, o que foi retirado e incluído em cada versão, visualizar e restaurar.

import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { ContratacoesApiService } from './contratacoes-api.service';
import { Alteracoes, DocumentoContratacao, ROTULOS_ITEM, Versao, VersaoDetalhe } from './contratacoes.models';
import { HtmlConfiavelPipe } from './html-confiavel.pipe';

type Modo = 'alteracoes' | 'visualizar';

const ROTULOS_MUDANCA = { incluido: 'Incluído', removido: 'Retirado', alterado: 'Alterado', movido: 'Movido' } as const;

/**
 * Versões do documento, no modelo das revisões de página do BookStack, mas por item: cada versão mostra o que foi **incluído**
 * (verde), **retirado** (vermelho, tachado) e **alterado** (diferença por palavra) em relação à anterior, e pode ser visualizada
 * ou restaurada (o estado atual fica guardado numa versão antes).
 */
@Component({
  selector: 'app-versoes-contratacao',
  imports: [FormsModule, DatePipe, RouterLink, TrilhaComponent, HtmlConfiavelPipe],
  template: `
    <div class="cabecalho-pagina">
      <div>
        <app-trilha [itens]="[{ rotulo: 'Contratações', rota: '/contratacoes' }, { rotulo: nome(), rota: ['/contratacoes', id] }, { rotulo: 'Versões' }]" />
        <h1>Versões do documento</h1>
        <small>Cada versão guarda o documento inteiro. Veja o que foi retirado e incluído, visualize ou restaure.</small>
      </div>
      <div class="acoes-cabecalho"><a class="acao-secundaria" [routerLink]="['/contratacoes', id]">Voltar ao documento</a></div>
    </div>

    <section class="painel-gestao contratacoes versoes">
      @if (!versoes().length) {
        <p class="estado-vazio">{{ carregado() ? 'Nenhuma versão ainda.' : 'Carregando…' }}</p>
      } @else {
        <div class="duas-colunas">
          <ol class="linha-do-tempo" aria-label="Versões">
            @for (v of versoes(); track v.numero) {
              <li [class.ativa]="v.numero === atual()?.numero">
                <button type="button" (click)="escolher(v)">
                  <strong>Versão {{ v.numero }}</strong> <span class="tipo-versao">{{ v.tipo_rotulo }}</span>
                  <small>{{ v.criada_em | date: 'dd/MM/yyyy HH:mm' }} · {{ v.autor_nome || '—' }}</small>
                  @if (v.resumo) { <em>{{ v.resumo }}</em> }
                </button>
              </li>
            }
          </ol>

          @if (atual(); as v) {
            <div class="detalhe-versao">
              <header>
                <h2>Versão {{ v.numero }} <small>{{ v.tipo_rotulo }}</small></h2>
                <div class="acoes-item">
                  <button type="button" class="acao-secundaria acao-pequena" [class.ativo]="modo() === 'alteracoes'" (click)="trocarModo('alteracoes')">Alterações</button>
                  <button type="button" class="acao-secundaria acao-pequena" [class.ativo]="modo() === 'visualizar'" (click)="trocarModo('visualizar')">Visualizar</button>
                  @if (podeEditar()) { <button type="button" class="acao-positiva acao-pequena" (click)="restaurar(v)">Restaurar esta versão</button> }
                </div>
              </header>

              @if (modo() === 'alteracoes') {
                <div class="campo curto"><label for="vs-contra">Comparar com</label>
                  <select id="vs-contra" [ngModel]="contra()" (ngModelChange)="comparar($event)">
                    <option [ngValue]="0">a versão anterior</option>
                    @for (o of versoes(); track o.numero) { @if (o.numero !== v.numero) { <option [ngValue]="o.numero">Versão {{ o.numero }}</option> } }
                  </select></div>
                @if (alteracoes(); as a) {
                  <p class="resumo-alteracoes">
                    <span class="incluido">{{ a.resumo['incluido'] }} incluído(s)</span><span class="removido">{{ a.resumo['removido'] }} retirado(s)</span>
                    <span class="alterado">{{ a.resumo['alterado'] }} alterado(s)</span><span class="movido">{{ a.resumo['movido'] }} movido(s)</span>
                  </p>
                  @for (m of a.metadados; track m.campo) {
                    <div class="alteracao movido"><b>{{ m.campo }}</b>: <del>{{ m.antes || '—' }}</del> → <ins>{{ m.depois || '—' }}</ins></div>
                  }
                  @for (s of a.secoes; track s.id) {
                    <div class="alteracao" [class]="'alteracao ' + (s.mudanca === 'removida' ? 'removido' : s.mudanca === 'incluida' ? 'incluido' : 'alterado')">
                      <b>Seção {{ s.mudanca }}:</b> {{ s.titulo }}@if (s.titulo_antes) { <small> (antes: {{ s.titulo_antes }})</small> }</div>
                  }
                  @for (i of a.itens; track i.id) {
                    <div [class]="'alteracao ' + i.mudanca">
                      <header><b>{{ rotuloMudanca[i.mudanca] }}</b> · {{ rotuloItem[i.tipo] }} {{ i.marcador }} <small>{{ i.secao }}</small>
                        @if (i.marcador_antes && i.marcador_antes !== i.marcador) { <small>(era {{ i.marcador_antes }})</small> }</header>
                      @if (i.diferenca) { <div class="diferenca" [innerHTML]="i.diferenca | htmlConfiavel"></div> }
                      @else { <div class="diferenca" [class.tachado]="i.mudanca === 'removido'" [innerHTML]="i.html | htmlConfiavel"></div> }
                    </div>
                  } @empty { @if (!a.secoes.length && !a.metadados.length) { <p class="estado-vazio">Nenhuma diferença de conteúdo nesta comparação.</p> } }
                }
              } @else if (completa(); as c) {
                <div class="foto-versao">
                  @for (s of c.foto.secoes; track s.id) {
                    <h3>{{ s.ordem }}. {{ s.titulo }}</h3>
                    @for (i of itensDaSecao(c, s.id); track i.id) {
                      <div class="conteudo-item" [style.margin-left.px]="i.profundidade * 22" [innerHTML]="(i.conteudo_html || i.conteudo) | htmlConfiavel"></div>
                    }
                  }
                </div>
              }
            </div>
          }
        </div>
      }
    </section>
  `,
})
export class VersoesContratacaoComponent implements OnInit {
  private readonly api = inject(ContratacoesApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);

  protected readonly id = this.rota.snapshot.paramMap.get('id') ?? '';
  protected readonly nome = signal('Documento');
  protected readonly podeEditar = signal(false);
  protected readonly versoes = signal<Versao[]>([]);
  protected readonly carregado = signal(false);
  protected readonly atual = signal<Versao | null>(null);
  protected readonly modo = signal<Modo>('alteracoes');
  protected readonly contra = signal(0);
  protected readonly alteracoes = signal<Alteracoes | null>(null);
  protected readonly completa = signal<VersaoDetalhe | null>(null);
  protected readonly rotuloItem = ROTULOS_ITEM;
  protected readonly rotuloMudanca = ROTULOS_MUDANCA;

  ngOnInit(): void {
    this.api.abrir(this.id).subscribe({ next: (d: DocumentoContratacao) => { this.nome.set(d.nome); this.podeEditar.set(d.pode_editar); }, error: () => undefined });
    this.carregar();
  }

  private carregar(): void {
    this.api.versoes(this.id).subscribe({
      next: (v) => { this.versoes.set(v); this.carregado.set(true); if (v.length) this.escolher(v[0]); },
      error: (e) => { this.carregado.set(true); this.dialogos.mostrarErro(e, 'Não foi possível carregar as versões'); },
    });
  }

  protected escolher(v: Versao): void {
    this.atual.set(v);
    this.contra.set(0);
    this.alteracoes.set(null);
    this.completa.set(null);
    this.modo() === 'alteracoes' ? this.carregarAlteracoes() : this.carregarCompleta();
  }

  protected trocarModo(m: Modo): void {
    this.modo.set(m);
    m === 'alteracoes' ? this.carregarAlteracoes() : this.carregarCompleta();
  }

  protected comparar(numero: number): void {
    this.contra.set(numero);
    this.carregarAlteracoes();
  }

  private carregarAlteracoes(): void {
    const v = this.atual();
    if (!v) return;
    this.api.alteracoes(this.id, v.numero, this.contra() || undefined).subscribe({ next: (a) => this.alteracoes.set(a), error: (e) => this.dialogos.mostrarErro(e) });
  }

  private carregarCompleta(): void {
    const v = this.atual();
    if (!v) return;
    this.api.versao(this.id, v.numero).subscribe({ next: (c) => this.completa.set(c), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Itens da seção em pré-ordem com a profundidade (a foto traz lista plana com `pai_id`). */
  protected itensDaSecao(c: VersaoDetalhe, secaoId: string): { id: string; conteudo: string; conteudo_html: string | null; profundidade: number }[] {
    const itens = c.foto.itens.filter((i) => i.secao_id === secaoId);
    const saida: { id: string; conteudo: string; conteudo_html: string | null; profundidade: number }[] = [];
    const descer = (paiId: string | null, nivel: number): void => {
      for (const i of itens.filter((x) => x.pai_id === paiId).sort((a, b) => a.ordem - b.ordem)) {
        saida.push({ id: i.id, conteudo: i.conteudo, conteudo_html: i.conteudo_html, profundidade: nivel });
        descer(i.id, nivel + 1);
      }
    };
    descer(null, 0);
    return saida;
  }

  protected async restaurar(v: Versao): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Restaurar a versão ${v.numero}?`,
      mensagem: 'O documento volta a ficar como nesta versão. O estado de agora é guardado numa versão antes, então nada se perde.',
      rotuloConfirmar: 'Restaurar',
      segundos: 2,
    });
    if (!ok) return;
    this.api.restaurarVersao(this.id, v.numero).subscribe({ next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível restaurar') });
  }
}
