// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o Painel Executivo em carrossel (contratos, RH e tarefas), na página própria e na home do portal.

import { Component, DestroyRef, ElementRef, inject, input, OnInit, signal, viewChild } from '@angular/core';
import { forkJoin } from 'rxjs';

import { CarrosselComponent } from '../../shared/componentes/carrossel/carrossel.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { PainelExecutivoApiService } from './painel-executivo-api.service';
import { IdSlide, ORDEM_SLIDES, ROTULOS_SLIDE, SlideContratos, SlideRh, SlideTarefas } from './painel-executivo.models';
import { SlideContratosComponent, SlideRhComponent, SlideTarefasComponent } from './slides';

interface Dados { contratos: SlideContratos; rh: SlideRh; tarefas: SlideTarefas }

/**
 * Carrossel dos painéis. Com `compacto` (home) mostra menos altura e esconde o título;
 * na página própria permite pausar, abrir em tela cheia (TV) e baixar o painel em PDF.
 */
@Component({
  selector: 'app-painel-executivo',
  imports: [CarrosselComponent, SlideContratosComponent, SlideRhComponent, SlideTarefasComponent],
  template: `
    @if (dados(); as d) {
      <section #quadro class="painel-executivo" [class.compacto]="compacto()" [class.tela-cheia]="telaCheia()" aria-label="Painel Executivo">
        <header class="barra-painel">
          <div><h2>{{ compacto() ? 'Painel Executivo' : 'Painel Executivo · ' + rotulos[ordem[atual()]] }}</h2>
            <small>Atualizado às {{ hora(d.contratos.gerado_em) }}</small></div>
          <div class="acoes-painel">
            <button type="button" class="acao-secundaria" (click)="pausado.set(!pausado())" [attr.aria-pressed]="pausado()">{{ pausado() ? '▶ Retomar' : '⏸ Pausar' }}</button>
            <button type="button" class="acao-secundaria" (click)="baixar()" [disabled]="baixando()">{{ baixando() ? 'Gerando…' : 'PDF deste painel' }}</button>
            <button type="button" class="acao-secundaria" (click)="alternarTelaCheia()">{{ telaCheia() ? 'Sair da tela cheia' : 'Tela cheia' }}</button>
          </div>
        </header>
        <app-carrossel [total]="3" [rotulos]="nomes" descricao="Painéis executivos" [segundos]="compacto() ? 15 : 20" [pausado]="pausado()" [(atual)]="atual">
          <div class="slide-painel"><app-slide-contratos [dados]="d.contratos" [compacto]="compacto() && !telaCheia()" /></div>
          <div class="slide-painel"><app-slide-rh [dados]="d.rh" [compacto]="compacto() && !telaCheia()" /></div>
          <div class="slide-painel"><app-slide-tarefas [dados]="d.tarefas" [compacto]="compacto() && !telaCheia()" /></div>
        </app-carrossel>
      </section>
    } @else if (erro()) {
      <p class="estado-vazio">Não foi possível carregar o Painel Executivo agora.</p>
    } @else if (!compacto()) {
      <p class="estado-vazio">Carregando…</p>
    }
  `,
})
export class PainelExecutivoComponent implements OnInit {
  readonly compacto = input(false);
  private readonly api = inject(PainelExecutivoApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly quadro = viewChild<ElementRef<HTMLElement>>('quadro');
  protected readonly ordem = ORDEM_SLIDES;
  protected readonly rotulos = ROTULOS_SLIDE;
  protected readonly nomes = ORDEM_SLIDES.map((s) => ROTULOS_SLIDE[s]);
  protected readonly dados = signal<Dados | null>(null);
  protected readonly erro = signal(false);
  protected readonly atual = signal(0);
  protected readonly pausado = signal(false);
  protected readonly telaCheia = signal(false);
  protected readonly baixando = signal(false);

  constructor() {
    // O usuário pode sair da tela cheia com Esc: o estado acompanha o navegador
    const aoMudar = () => this.telaCheia.set(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', aoMudar);
    inject(DestroyRef).onDestroy(() => {
      document.removeEventListener('fullscreenchange', aoMudar);
      if (document.fullscreenElement) void document.exitFullscreen();
    });
  }

  ngOnInit(): void {
    forkJoin({ contratos: this.api.contratos(), rh: this.api.rh(), tarefas: this.api.tarefas() }).subscribe({
      next: (d) => this.dados.set(d),
      error: () => this.erro.set(true),
    });
  }

  protected hora(iso: string): string {
    return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  }

  protected alternarTelaCheia(): void {
    const el = this.quadro()?.nativeElement;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void el.requestFullscreen?.().catch(() => undefined);
  }

  protected baixar(): void {
    const slide: IdSlide = ORDEM_SLIDES[this.atual()];
    this.baixando.set(true);
    this.api.baixarPdf(slide).subscribe({
      next: () => this.baixando.set(false),
      error: (e) => { this.baixando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível gerar o PDF'); },
    });
  }
}
