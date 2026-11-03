// Criado por José Eduardo Santana Martins
// Este arquivo serve para a topologia da rede: a árvore dos equipamentos (núcleo, switches de andar, patch panels), no mesmo desenho do Organograma.

import { NgTemplateOutlet } from '@angular/common';
import { Component, ElementRef, inject, OnInit, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRedeComponent } from './cabecalho-rede.component';
import { RedeApiService } from './rede-api.service';
import { NoTopologia, ROTULOS_FUNCAO_EQUIPAMENTO, ROTULOS_PING, ROTULOS_TIPO_EQUIPAMENTO } from './rede.models';

/** Id do grupo "Sem ligação" (não é um equipamento: junta os que não têm cabo para outro equipamento). */
const SEM_LIGACAO = 'sem-ligacao';

/**
 * Topologia da rede, montada pela API a partir dos cabos cadastrados (nada é desenhado à mão).
 * Começa só com o núcleo e o primeiro nível; cada clique no "+" abre o nível de baixo. Clicar no equipamento abre a face dele.
 * Palco, zoom, arrasto e formato vertical são os do Organograma do RH (mesmas classes globais `organograma-*`).
 */
@Component({
  selector: 'app-topologia-rede',
  imports: [NgTemplateOutlet, FormsModule, CabecalhoRedeComponent, EsqueletoComponent],
  // Faixa da esquerda com a cor do rack (as mesmas cores do desenho do rack)
  styles: [`
    .caixa-org[data-cor] { border-left: 4px solid var(--cor-rack, var(--spi-texto)); }
    .caixa-org[data-cor='cinza'] { --cor-rack: var(--spi-apagado); }
    .caixa-org[data-cor='azul'] { --cor-rack: var(--spi-info); }
    .caixa-org[data-cor='verde'] { --cor-rack: var(--spi-sucesso); }
    .caixa-org[data-cor='amarelo'] { --cor-rack: var(--spi-alerta); }
    .caixa-org[data-cor='laranja'] { --cor-rack: var(--spi-atencao); }
    .caixa-org[data-cor='vermelho'] { --cor-rack: var(--spi-perigo); }
    .caixa-org.pendencia { border-style: dashed; }
    .portas-baixo { color: var(--spi-perigo); }
    /* Função e ping do equipamento, embaixo do nome */
    .selos-org { display: flex; flex-wrap: wrap; justify-content: center; gap: 4px; margin: 2px 0; }
    .nucleo-topologia { display: flex; align-items: center; gap: 8px; padding: 4px 4px 4px 12px; border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-m);
      background: var(--spi-superficie); font-size: var(--spi-texto-legenda); color: var(--spi-apagado);
      select { width: auto; min-width: 160px; } }
  `],
  template: `
    <div class="modulo-chamados">
      <app-cabecalho-rede titulo="Topologia" descricao="A rede montada pelos cabos cadastrados: os cores no topo (o primário primeiro; se ele cair, o secundário assume) e, embaixo, o que se liga a cada equipamento. Clique no + para abrir o nível de baixo." />

      <div [class.organograma-vertical-ativo]="vertical()">
      <div class="organograma-palco" #palco (wheel)="rolar($event)" (pointerdown)="comecarArrasto($event)" (pointermove)="arrastar($event)" (pointerup)="terminarArrasto()" (pointerleave)="terminarArrasto()">
        @if (carregando()) {
          <app-esqueleto tipo="lista" [linhas]="6" />
        } @else if (!raizes().length) {
          <p class="estado-vazio">Nenhum equipamento cadastrado ainda. Cadastre os racks e equipamentos em Rede › Equipamentos e ligue as portas entre eles.</p>
        } @else {
          <div class="organograma-lona" #lona [style.transform]="'translate(' + x() + 'px,' + y() + 'px) scale(' + zoom() + ')'">
            <ul class="organograma">
              @for (n of raizes(); track n.id) { <ng-container [ngTemplateOutlet]="no" [ngTemplateOutletContext]="{ $implicit: n, pai: null }" /> }
            </ul>
          </div>
        }

        <div class="organograma-barra" role="toolbar" aria-label="Topologia">
          <span class="organograma-resumo">{{ total() }} equipamento(s) · {{ semLigacao() }} sem ligação</span>
          @if (candidatosNucleo().length > 1) {
            <label class="nucleo-topologia">Núcleo
              <select aria-label="Equipamento no topo da árvore" [ngModel]="raizEscolhida()" (ngModelChange)="trocarNucleo($event)">
                <option [ngValue]="null">Pela função (padrão)</option>
                @for (c of candidatosNucleo(); track c.id) { <option [ngValue]="c.id">{{ c.nome }}</option> }
              </select></label>
          }
          <div class="chips-filtro" role="group" aria-label="Exibição">
            <button type="button" (click)="abertos.set(raizes().map((r) => r.id)); reajustar()">Recolher</button>
            <button type="button" (click)="abertos.set(todosIds()); reajustar()">Expandir tudo</button>
          </div>
          <div class="chips-filtro" role="group" aria-label="Formato">
            <button type="button" [class.ativo]="!vertical()" (click)="mudarFormato(false)">Árvore</button>
            <button type="button" [class.ativo]="vertical()" (click)="mudarFormato(true)">Vertical</button>
          </div>
          @if (!vertical()) {
          <div class="organograma-zoom" role="group" aria-label="Zoom">
            <button type="button" class="acao-secundaria acao-pequena" aria-label="Diminuir" (click)="ampliar(1 / 1.25)">−</button>
            <button type="button" class="acao-secundaria acao-pequena" title="Voltar a 100%" (click)="definirZoom(1)">{{ (zoom() * 100).toFixed(0) }}%</button>
            <button type="button" class="acao-secundaria acao-pequena" aria-label="Aumentar" (click)="ampliar(1.25)">+</button>
            <button type="button" class="acao-secundaria acao-pequena" title="Mostrar a árvore toda" (click)="ajustar()">Ajustar</button>
          </div>
          }
        </div>
      </div>
      </div>
    </div>

    <ng-template #no let-n let-pai="pai">
      <li class="no-org">
        <div class="caixa-org" [class.pendencia]="n.id === semLigacaoId" [attr.data-cor]="n.rack_cor">
          @if (n.id === semLigacaoId) {
            <button type="button" class="titulo-org" (click)="alternar(n)">
              <span class="tipo-org">Pendência do cadastro</span>
              <strong>Sem ligação</strong>
              <small>Equipamentos sem cabo para outro equipamento. Ligue uma porta deles para entrarem na árvore.</small>
            </button>
          } @else {
            <button type="button" class="titulo-org" [attr.aria-label]="'Abrir a face de ' + n.nome" (click)="abrir(n)">
              <span class="tipo-org">{{ rotulo(n) }}{{ n.rack_nome ? ' · ' + n.rack_nome : '' }}</span>
              <strong>{{ n.nome }}</strong>
              @if (n.funcao || n.ping_situacao) {
                <span class="selos-org">
                  @if (n.funcao) { <span class="selo-status" data-chamado="info">{{ textoFuncao(n) }}</span> }
                  @if (n.ping_situacao) { <span class="selo-status" [attr.data-chamado]="n.ping_situacao === 'no_ar' ? 'sucesso' : 'perigo'">{{ textoPing(n) }}</span> }
                  @if (n.assumiu) { <span class="selo-status" data-chamado="alerta">Assumiu: primário fora do ar</span> }
                </span>
              }
              @if (n.ip_gerencia || n.sala) { <span class="lider-org">@if (n.ip_gerencia) { <span class="texto-codigo">{{ n.ip_gerencia }}</span> }{{ n.ip_gerencia && n.sala ? ' · ' : '' }}{{ n.sala }}</span> }
              @if (pai && n.porta_acima) {
                <small>Porta {{ n.porta_acima }} → {{ pai.nome }} porta {{ n.porta_no_pai }}{{ n.cabos_com_pai > 1 ? ' (+' + (n.cabos_com_pai - 1) + ' cabo)' : '' }}</small>
              }
              <small>{{ n.portas_up }}/{{ n.portas_total }} portas ligadas@if (n.portas_down) { · <span class="portas-baixo">{{ n.portas_down }} desligada(s)</span> }</small>
              @if (n.pontos || n.bens) { <small>{{ n.pontos }} ponto(s) · {{ n.bens }} bem(ns) ligado(s)</small> }
              @if (n.tambem_ligado.length) { <small>Também ligado a {{ n.tambem_ligado.join(', ') }}</small> }
            </button>
          }
          @if (n.filhos.length) {
            <button type="button" class="recolher-org" [attr.aria-expanded]="aberto(n)" [attr.aria-label]="(aberto(n) ? 'Recolher ' : 'Abrir o que se liga a ') + n.nome" (click)="alternar(n)">
              {{ aberto(n) ? '−' : '+' + n.filhos.length }}
            </button>
          }
        </div>
        @if (n.filhos.length && aberto(n)) {
          <ul class="organograma org-filhos">
            @for (f of n.filhos; track f.id) { <ng-container [ngTemplateOutlet]="no" [ngTemplateOutletContext]="{ $implicit: f, pai: n.id === semLigacaoId ? null : n }" /> }
          </ul>
        }
      </li>
    </ng-template>
  `,
})
export class TopologiaRedeComponent implements OnInit {
  private readonly api = inject(RedeApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);

  protected readonly rotulos = ROTULOS_TIPO_EQUIPAMENTO;
  protected readonly semLigacaoId = SEM_LIGACAO;
  /** As árvores (uma por grupo ligado) e, por último, o grupo "Sem ligação" quando houver. */
  protected readonly raizes = signal<NoTopologia[]>([]);
  protected readonly carregando = signal(true);
  /** Equipamentos abertos (mostram os filhos). Começa só com as raízes: cada clique abre um nível. */
  protected readonly abertos = signal<string[]>([]);
  protected readonly raizEscolhida = signal<string | null>(this.lerLocal('topologia-raiz'));
  protected readonly total = signal(0);
  protected readonly semLigacao = signal(0);
  /** Switches e roteadores ligados: os que podem ficar no topo. */
  protected readonly candidatosNucleo = signal<{ id: string; nome: string }[]>([]);
  private readonly palco = viewChild<ElementRef<HTMLElement>>('palco');
  private readonly lona = viewChild<ElementRef<HTMLElement>>('lona');
  protected readonly vertical = signal(this.lerLocal('topologia-formato') === 'vertical');
  protected readonly zoom = signal(1);
  protected readonly x = signal(0);
  protected readonly y = signal(0);
  private arrastando: { x: number; y: number; moveu: boolean } | null = null;

  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    this.carregando.set(true);
    this.api.topologia(this.raizEscolhida()).subscribe({
      next: (t) => {
        let total = t.sem_ligacao.length;
        const candidatos: { id: string; nome: string }[] = [];
        const visitar = (n: NoTopologia) => {
          total++;
          if (n.tipo !== 'patch_panel') candidatos.push({ id: n.id, nome: n.nome });
          n.filhos.forEach(visitar);
        };
        t.raizes.forEach(visitar);
        this.total.set(total);
        this.semLigacao.set(t.sem_ligacao.length);
        this.candidatosNucleo.set(candidatos.sort((a, b) => a.nome.localeCompare(b.nome)));
        const grupoSolto: NoTopologia[] = t.sem_ligacao.length ? [{
          id: SEM_LIGACAO, nome: 'Sem ligação', tipo: 'outro', funcao: null, ping_situacao: null, assumiu: false, rack_nome: '', rack_cor: null, sala: '', ip_gerencia: '', portas_total: 0, portas_up: 0, portas_down: 0,
          pontos: 0, bens: 0, porta_acima: '', porta_no_pai: '', cabos_com_pai: 0, tambem_ligado: [], filhos: t.sem_ligacao,
        }] : [];
        this.raizes.set([...t.raizes, ...grupoSolto]);
        this.abertos.set(t.raizes.map((r) => r.id));
        this.carregando.set(false);
        this.reajustar();
      },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível montar a topologia'); },
    });
  }

  protected trocarNucleo(id: string | null): void {
    this.raizEscolhida.set(id);
    this.gravarLocal('topologia-raiz', id ?? '');
    this.carregar();
  }

  protected aberto(n: NoTopologia): boolean {
    return this.abertos().includes(n.id);
  }

  protected alternar(n: NoTopologia): void {
    // Um arrasto que termina sobre o botão não conta como clique
    if (this.arrastando?.moveu) return;
    this.abertos.update((l) => (l.includes(n.id) ? l.filter((i) => i !== n.id) : [...l, n.id]));
  }

  protected textoFuncao(n: NoTopologia): string {
    return n.funcao ? ROTULOS_FUNCAO_EQUIPAMENTO[n.funcao] : '';
  }

  protected textoPing(n: NoTopologia): string {
    return n.ping_situacao ? ROTULOS_PING[n.ping_situacao] : '';
  }

  protected rotulo(n: NoTopologia): string {
    return this.rotulos[n.tipo];
  }

  protected todosIds(): string[] {
    const ids: string[] = [];
    const visitar = (n: NoTopologia) => { if (n.filhos.length) ids.push(n.id); n.filhos.forEach(visitar); };
    this.raizes().forEach(visitar);
    return ids;
  }

  protected abrir(n: NoTopologia): void {
    if (!this.arrastando?.moveu) this.roteador.navigate(['/rede/equipamentos', n.id]);
  }

  // Palco: zoom, arrasto e "Ajustar" iguais aos do Organograma

  protected ajustar(): void {
    const palco = this.palco()?.nativeElement;
    const lona = this.lona()?.nativeElement;
    if (!palco || !lona || this.semZoom()) return;
    const margem = 24;
    const escala = Math.min((palco.clientWidth - margem * 2) / lona.scrollWidth, (palco.clientHeight - margem * 2 - 56) / lona.scrollHeight, 1);
    this.zoom.set(escala);
    this.x.set((palco.clientWidth - lona.scrollWidth * escala) / 2);
    this.y.set(margem + 56);
  }

  protected reajustar(): void {
    setTimeout(() => this.ajustar(), 50);
  }

  protected definirZoom(novo: number, cx?: number, cy?: number): void {
    const palco = this.palco()?.nativeElement;
    if (!palco) return;
    const alvo = Math.min(2.5, Math.max(0.1, novo));
    const px = cx ?? palco.clientWidth / 2;
    const py = cy ?? palco.clientHeight / 2;
    const razao = alvo / this.zoom();
    this.x.set(px - (px - this.x()) * razao);
    this.y.set(py - (py - this.y()) * razao);
    this.zoom.set(alvo);
  }

  protected ampliar(fator: number): void {
    this.definirZoom(this.zoom() * fator);
  }

  protected rolar(e: WheelEvent): void {
    if (this.semZoom()) return;
    e.preventDefault();
    const caixa = this.palco()!.nativeElement.getBoundingClientRect();
    this.definirZoom(this.zoom() * (e.deltaY < 0 ? 1.1 : 1 / 1.1), e.clientX - caixa.left, e.clientY - caixa.top);
  }

  protected comecarArrasto(e: PointerEvent): void {
    if (this.semZoom() || (e.target as HTMLElement).closest('button, select, .organograma-barra')) return;
    this.arrastando = { x: e.clientX, y: e.clientY, moveu: false };
  }

  protected arrastar(e: PointerEvent): void {
    const a = this.arrastando;
    if (!a || !(e.buttons & 1)) return;
    const dx = e.clientX - a.x;
    const dy = e.clientY - a.y;
    if (!a.moveu && Math.hypot(dx, dy) < 4) return;
    a.moveu = true;
    this.x.update((v) => v + dx);
    this.y.update((v) => v + dy);
    a.x = e.clientX;
    a.y = e.clientY;
  }

  protected terminarArrasto(): void {
    setTimeout(() => (this.arrastando = null), 0);
  }

  private semZoom(): boolean {
    return this.vertical() || window.innerWidth <= 900;
  }

  protected mudarFormato(vertical: boolean): void {
    this.vertical.set(vertical);
    this.gravarLocal('topologia-formato', vertical ? 'vertical' : 'arvore');
    this.reajustar();
  }

  private lerLocal(chave: string): string | null {
    try {
      return localStorage.getItem(chave) || null;
    } catch {
      return null;
    }
  }

  private gravarLocal(chave: string, valor: string): void {
    try {
      localStorage.setItem(chave, valor);
    } catch {
      // sem armazenamento local a escolha só vale nesta visita
    }
  }
}
