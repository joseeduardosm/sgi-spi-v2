// Criado por José Eduardo Santana Martins
// Este arquivo serve para o organograma do RH: árvore clássica no desktop que vira árvore vertical abaixo de 900px, com unidades recolhíveis e vagas.

import { NgTemplateOutlet } from '@angular/common';
import { Component, ElementRef, inject, OnInit, signal, viewChild } from '@angular/core';

import { AvatarComponent } from '../diretorio/avatar.component';
import { DetalheContatoComponent } from '../diretorio/detalhe-contato.component';
import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { RhCargosApiService } from './rh-cargos-api.service';
import { Cargo, NoOrganograma } from './rh-cargos.models';

/** Organograma da SPI: cada unidade mostra seus cargos (quem ocupa ou "Vago") e as unidades subordinadas. */
@Component({
  selector: 'app-organograma',
  host: { '(document:keydown.escape)': 'contato() ? contato.set(null) : aberta.set(null)' },
  imports: [NgTemplateOutlet, AvatarComponent, DetalheContatoComponent, CabecalhoRhComponent, EsqueletoComponent],
  template: `
    <app-cabecalho-rh titulo="Organograma" [trilha]="['Organograma']" descricao="Estrutura da SPI com cargos e quem os ocupa. Role o mouse para dar zoom e arraste para mover." />

    <div [class.organograma-vertical-ativo]="vertical()">
    <div class="organograma-palco" #palco (wheel)="rolar($event)" (pointerdown)="comecarArrasto($event)" (pointermove)="arrastar($event)" (pointerup)="terminarArrasto()" (pointerleave)="terminarArrasto()">
      @if (carregando()) {
        <app-esqueleto tipo="lista" [linhas]="6" />
      } @else {
        <div class="organograma-lona" #lona [style.transform]="'translate(' + x() + 'px,' + y() + 'px) scale(' + zoom() + ')'">
          <ul class="organograma">
            @for (n of raizes(); track n.setor_id) { <ng-container [ngTemplateOutlet]="no" [ngTemplateOutletContext]="{ $implicit: n }" /> }
          </ul>
        </div>
      }

      <div class="organograma-barra" role="toolbar" aria-label="Organograma">
        <span class="organograma-resumo">{{ totalPosicoes() }} posições · {{ totalVagas() }} vaga(s)</span>
        <div class="chips-filtro" role="group" aria-label="Exibição">
          <button type="button" [class.ativo]="mostrarVagas()" (click)="alternarVagas()">Vagas</button>
          <button type="button" (click)="recolhidos.set(todosIds()); reajustar()">Recolher</button>
          <button type="button" (click)="recolhidos.set([]); reajustar()">Expandir</button>
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
          <button type="button" class="acao-secundaria acao-pequena" title="Mostrar o organograma todo" (click)="ajustar()">Ajustar</button>
        </div>
        }
      </div>
    </div>
    </div>

    <ng-template #no let-n>
      <li class="no-org">
        <div class="caixa-org">
          <button type="button" class="titulo-org" aria-haspopup="dialog" (click)="abrir(n)">
            <span class="tipo-org">{{ n.sigla || n.tipo_unidade || 'Unidade' }}</span>
            <strong>{{ n.nome }}</strong>
            @if (n.lider_nome) { <span class="lider-org">{{ n.lider_nome }}</span> }
            <small>{{ n.total_posicoes - n.total_vagas }}/{{ n.total_posicoes }} ocupadas</small>
          </button>
          @if (n.filhos.length) {
            <button type="button" class="recolher-org" [attr.aria-expanded]="!recolhido(n)" [attr.aria-label]="(recolhido(n) ? 'Expandir ' : 'Recolher ') + n.nome" (click)="alternar(n)">
              {{ recolhido(n) ? '+' + n.filhos.length : '−' }}
            </button>
          }
        </div>
        @if (n.filhos.length && !recolhido(n)) {
          <ul class="organograma org-filhos">
            @for (f of n.filhos; track f.setor_id) { <ng-container [ngTemplateOutlet]="no" [ngTemplateOutletContext]="{ $implicit: f }" /> }
          </ul>
        }
      </li>
    </ng-template>

    @if (aberta(); as u) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="aberta.set(null)"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-unidade">
        <header>
          <div><span class="modal-sobretitulo">{{ u.sigla || u.tipo_unidade || 'Unidade' }}</span><h2 id="titulo-unidade">{{ u.nome }}</h2></div>
          <button type="button" aria-label="Fechar" (click)="aberta.set(null)">×</button>
        </header>
        @if (u.lider; as l) {
          <p class="rotulo-lider">Líder da unidade</p>
          <ul class="posicoes-org lider-lista">
            <li>
              <button type="button" class="pessoa-org" [attr.aria-label]="'Abrir o cartão de ' + l.nome" (click)="contato.set(l.usuario_id)">
                <app-avatar [nome]="l.nome" [foto]="l.foto_url" /><span><strong>{{ l.nome }}</strong><small>{{ l.cargo || 'Sem cargo cadastrado' }}</small></span>
              </button>
            </li>
          </ul>
          <p class="rotulo-lider">Cargos da unidade</p>
        }
        <ul class="posicoes-org">
          @for (c of cargosSemLider(u); track c.id) {
            <li [class.vago]="!c.ocupante">
              @if (c.ocupante; as o) {
                <button type="button" class="pessoa-org" [attr.aria-label]="'Abrir o cartão de ' + o.nome" (click)="contato.set(o.usuario_id)">
                  <app-avatar [nome]="o.nome" [foto]="o.foto_url" /><span><strong>{{ o.nome }}</strong><small>{{ c.rotulo }}</small></span>
                </button>
              }
              @else { <span class="avatar-vago" aria-hidden="true">?</span><span><strong>Vago</strong><small>{{ c.rotulo }}</small></span> }
            </li>
          } @empty { <li class="vago"><span><small>Esta unidade não tem cargos cadastrados.</small></span></li> }
        </ul>
      </section>
    }

    @if (contato(); as id) {
      <app-detalhe-contato [contatoId]="id" (fechar)="contato.set(null)" (abrirOutro)="contato.set($event)" />
    }
  `,
})
export class OrganogramaComponent implements OnInit {
  private readonly api = inject(RhCargosApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly raizes = signal<NoOrganograma[]>([]);
  protected readonly carregando = signal(true);
  protected readonly mostrarVagas = signal(true);
  /** Unidades recolhidas (ids dos setores). */
  protected readonly recolhidos = signal<number[]>([]);
  private readonly palco = viewChild<ElementRef<HTMLElement>>('palco');
  private readonly lona = viewChild<ElementRef<HTMLElement>>('lona');
  /** Formato escolhido (lembrado neste navegador): a árvore vertical é a padrão. */
  protected readonly vertical = signal(this.formatoSalvo());
  protected readonly zoom = signal(1);
  protected readonly x = signal(0);
  protected readonly y = signal(0);
  private arrastando: { x: number; y: number; moveu: boolean } | null = null;
  protected readonly contato = signal<number | null>(null);
  protected readonly aberta = signal<NoOrganograma | null>(null);
  protected readonly totalPosicoes = signal(0);
  protected readonly totalVagas = signal(0);

  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    this.carregando.set(true);
    this.api.organograma(this.mostrarVagas()).subscribe({
      next: (r) => {
        this.raizes.set(r);
        let posicoes = 0, vagas = 0;
        const somar = (n: NoOrganograma) => { posicoes += n.posicoes.length; vagas += n.posicoes.filter((c) => !c.ocupante).length; n.filhos.forEach(somar); };
        r.forEach(somar);
        this.totalPosicoes.set(posicoes);
        this.totalVagas.set(vagas);
        this.carregando.set(false);
        this.reajustar();
      },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar o organograma'); },
    });
  }

  protected alternarVagas(): void {
    this.mostrarVagas.update((v) => !v);
    this.carregar();
  }

  protected recolhido(n: NoOrganograma): boolean {
    return this.recolhidos().includes(n.setor_id);
  }

  protected alternar(n: NoOrganograma): void {
    this.recolhidos.update((l) => (l.includes(n.setor_id) ? l.filter((i) => i !== n.setor_id) : [...l, n.setor_id]));
  }

  protected todosIds(): number[] {
    const ids: number[] = [];
    const visitar = (n: NoOrganograma) => { if (n.filhos.length) ids.push(n.setor_id); n.filhos.forEach(visitar); };
    this.raizes().forEach(visitar);
    return ids;
  }

  /** O líder já aparece na própria seção; não se repete na lista de cargos. */
  protected cargosSemLider(u: NoOrganograma): Cargo[] {
    return u.lider ? u.posicoes.filter((c) => c.ocupante?.usuario_id !== u.lider!.usuario_id) : u.posicoes;
  }

  protected abrir(n: NoOrganograma): void {
    // Um arrasto que termina sobre o cartão não conta como clique
    if (!this.arrastando?.moveu) this.aberta.set(n);
  }

  /** Mostra o organograma inteiro no palco, centralizado (no celular a lista vertical dispensa zoom). */
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

  /** Espera o Angular desenhar a árvore antes de medir. */
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
    // Mantém o ponto sob o cursor parado enquanto aproxima ou afasta
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
    if (this.semZoom() || (e.target as HTMLElement).closest('button, .organograma-barra')) return;
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
    // O clique que vem logo depois do arrasto ainda consulta `moveu`; zera no próximo ciclo
    setTimeout(() => (this.arrastando = null), 0);
  }

  /** Sem zoom nem arrasto: formato vertical ou tela estreita (a árvore vertical já cabe). */
  private semZoom(): boolean {
    return this.vertical() || window.innerWidth <= 900;
  }

  private formatoSalvo(): boolean {
    try {
      return localStorage.getItem('organograma-formato') !== 'arvore';
    } catch {
      return true;
    }
  }

  protected mudarFormato(vertical: boolean): void {
    this.vertical.set(vertical);
    try {
      localStorage.setItem('organograma-formato', vertical ? 'vertical' : 'arvore');
    } catch {
      // sem armazenamento local o formato só vale nesta visita
    }
    this.reajustar();
  }
}
