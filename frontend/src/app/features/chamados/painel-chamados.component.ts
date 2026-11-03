// Criado por José Eduardo Santana Martins
// Este arquivo serve para mostrar o painel dos Chamados: os chamados em que o setor de quem está logado é o responsável, ao vivo.

import { Component, computed, DestroyRef, ElementRef, inject, OnInit, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { debounceTime, Subject } from 'rxjs';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { ChamadosApiService } from './chamados-api.service';
import { ChamadosTempoRealService } from './chamados-tempo-real.service';
import { ColunaPainel, EstadoPainel, EventoChamado, horaPainel, ItemPainel, tempoEspera, textoNivelPainel } from './chamados.models';

/** Por garantia, mesmo sem evento ao vivo, o painel busca de novo a cada 2 min. */
const RECARGA_MS = 120000;
/** Quanto tempo a linha nova fica destacada. */
const DESTAQUE_MS = 8000;
/** Altura de uma linha antes de medir a real (só para a primeira conta do modo automático). */
const LINHA_ESTIMADA_PX = 56;

const ROTULOS_COLUNA: Record<ColunaPainel, string> = {
  abertura: 'Abertura', titulo: 'Título', usuario: 'Usuário', local: 'Local', espera: 'Espera', situacao: 'Situação', responsavel: 'Responsável',
};

@Component({
  selector: 'app-painel-chamados',
  imports: [EsqueletoComponent, RouterLink],
  styleUrl: './painel-chamados.component.scss',
  template: `
    <section #quadro class="painel-tv" [attr.data-tamanho]="estado()?.config?.tamanho || 'normal'" [class.sem-cor-linha]="estado()?.config?.cor_linha === false"
      aria-label="Painel de chamados">
      <header class="painel-tv-topo">
        <div class="painel-tv-titulo">
          <span class="sobretitulo">Chamados</span>
          <h1>{{ estado()?.area || 'Painel' }}</h1>
        </div>
        <div class="painel-tv-lado">
          <span class="painel-tv-relogio texto-codigo" aria-label="Hora atual">{{ relogio() }}</span>
          <span class="selo-situacao" [attr.data-conexao]="tempoReal.estado()" role="status">{{ textoConexao() }}</span>
          <button type="button" class="acao-secundaria" (click)="alternarTelaCheia()">{{ telaCheia() ? 'Sair da tela cheia' : 'Tela cheia' }}</button>
        </div>
      </header>

      @if (erro()) {
        <div class="painel-tv-aviso" role="alert"><strong>{{ erro() }}</strong></div>
      } @else if (estado(); as e) {
        <dl class="painel-tv-indicadores">
          <div><dt>Abertos</dt><dd>{{ e.indicadores.abertos }}</dd></div>
          <div [attr.data-destaque]="e.indicadores.sem_responsavel ? 'atencao' : null"><dt>Sem responsável</dt><dd>{{ e.indicadores.sem_responsavel }}</dd></div>
          <div [attr.data-destaque]="e.indicadores.estourados ? 'perigo' : null"><dt>Prazo estourado</dt><dd>{{ e.indicadores.estourados }}</dd></div>
          <div [attr.data-destaque]="'sucesso'"><dt>Resolvidos hoje</dt><dd>{{ e.indicadores.resolvidos_hoje }}</dd></div>
        </dl>

        <div #area class="painel-tv-area">
          @if (e.itens.length) {
            <table class="painel-tv-tabela">
              <thead><tr>@for (c of colunas(); track c) { <th scope="col">{{ rotulo(c) }}</th> }</tr></thead>
              <tbody>
                @for (item of pagina(); track item.numero) {
                  <tr [attr.data-nivel]="item.nivel" [class.linha-nova]="destacados().has(item.numero)" class="linha-clicavel" (click)="abrir(item.numero)">
                    @for (c of colunas(); track c) {
                      @switch (c) {
                        @case ('abertura') { <td class="texto-codigo">{{ hora(item.aberto_em) }}</td> }
                        @case ('titulo') { <td><a class="painel-tv-link" [routerLink]="['/chamados', item.numero]" (click)="$event.stopPropagation()"><span class="painel-tv-numero texto-codigo">#{{ item.numero }}</span> {{ item.titulo }}</a></td> }
                        @case ('usuario') { <td>{{ item.solicitante }}</td> }
                        @case ('local') { <td>{{ item.local || '—' }}</td> }
                        @case ('espera') { <td class="texto-codigo">{{ espera(item.aberto_em) }}</td> }
                        @case ('situacao') { <td><span class="selo-situacao" [attr.data-painel]="item.nivel">{{ situacao(item) }}</span></td> }
                        @case ('responsavel') { <td>{{ item.responsavel || 'Sem responsável' }}</td> }
                      }
                    }
                  </tr>
                }
              </tbody>
            </table>
            @if (paginas() > 1) {
              <nav class="painel-tv-paginas" aria-label="Páginas do painel">
                <button type="button" class="acao-secundaria acao-pequena" (click)="irPara(-1)" aria-label="Página anterior">‹ Anterior</button>
                <span aria-live="polite">Página {{ (paginaAtual() % paginas()) + 1 }} de {{ paginas() }}</span>
                <button type="button" class="acao-secundaria acao-pequena" (click)="irPara(1)" aria-label="Próxima página">Próxima ›</button>
              </nav>
            }
          } @else {
            <p class="painel-tv-vazio">Nenhum chamado aberto para o seu setor neste momento.</p>
          }
        </div>
      } @else {
        <app-esqueleto tipo="tabela" [linhas]="8" [colunas]="6" rotulo="" />
      }
      <p class="painel-tv-limites">Em ordem pela cor do prazo consumido: vermelho a partir de {{ estado()?.limites?.perigo ?? 90 }}%, laranja a partir de {{ estado()?.limites?.atencao ?? 75 }}%,
        amarelo a partir de {{ estado()?.limites?.alerta ?? 50 }}% e, por último, os que estão no prazo. Clique numa linha para abrir o chamado; ← e → trocam de página.</p>
    </section>
  `,
})
export class PainelChamadosComponent implements OnInit {
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  private readonly api = inject(ChamadosApiService);
  protected readonly tempoReal = inject(ChamadosTempoRealService);
  private readonly destruir = inject(DestroyRef);
  private readonly quadro = viewChild<ElementRef<HTMLElement>>('quadro');
  private readonly area = viewChild<ElementRef<HTMLElement>>('area');

  protected readonly estado = signal<EstadoPainel | null>(null);
  protected readonly erro = signal('');
  protected readonly agora = signal(Date.now());
  protected readonly paginaAtual = signal(0);
  protected readonly destacados = signal<Set<number>>(new Set());
  protected readonly telaCheia = signal(false);
  /** Linhas que cabem na área da tabela (modo automático), recalculadas ao mudar o tamanho da tela. */
  private readonly linhasQueCabem = signal(8);

  protected readonly colunas = computed<ColunaPainel[]>(() => this.estado()?.config.colunas ?? ['abertura', 'titulo', 'usuario', 'local', 'espera', 'situacao']);
  protected readonly linhasPorPagina = computed(() => this.estado()?.config.linhas_por_pagina || this.linhasQueCabem());
  protected readonly paginas = computed(() => Math.max(1, Math.ceil((this.estado()?.itens.length ?? 0) / this.linhasPorPagina())));
  protected readonly pagina = computed(() => {
    const itens = this.estado()?.itens ?? [];
    const inicio = (this.paginaAtual() % this.paginas()) * this.linhasPorPagina();
    return itens.slice(inicio, inicio + this.linhasPorPagina());
  });
  protected readonly relogio = computed(() => new Date(this.agora()).toLocaleTimeString('pt-BR', { timeZone: 'America/Sao_Paulo', hour: '2-digit', minute: '2-digit' }));

  private setorId: number | null = null;
  private conhecidos: Set<number> | null = null;
  /** Os itens da última carga, para falar do chamado que saiu da lista (resolvido). */
  private ultimos = new Map<number, ItemPainel>();
  /** Ações recebidas desde a última carga (número → assumido, resolvido, reaberto ou transferido). */
  private acoesPendentes = new Map<number, NonNullable<EventoChamado['acao']>>();
  private readonly recarregar$ = new Subject<void>();
  private novosPendentes = new Set<number>();
  private rotacao: ReturnType<typeof setInterval> | null = null;
  /** Depois de trocar de página na mão, a troca automática espera um minuto. */
  private pausaAte = 0;
  private segundosRotacao = 0;

  ngOnInit(): void {
    this.setorId = Number(this.rota.snapshot.queryParamMap.get('setor_id')) || null;
    // Vários eventos seguidos viram uma busca só
    this.recarregar$.pipe(debounceTime(400), takeUntilDestroyed(this.destruir)).subscribe(() => this.carregar());
    this.carregar();
    const relogio = setInterval(() => this.agora.set(Date.now()), 30000);
    const recarga = setInterval(() => this.carregar(), RECARGA_MS);
    this.destruir.onDestroy(() => { clearInterval(relogio); clearInterval(recarga); if (this.rotacao) clearInterval(this.rotacao); });
    this.tempoReal.eventos$.pipe(takeUntilDestroyed(this.destruir)).subscribe((e) => this.aoEvento(e));
    const aoMudar = () => { this.telaCheia.set(!!document.fullscreenElement); setTimeout(() => this.medir(), 200); };
    const aoRedimensionar = () => this.medir();
    // Setas do teclado trocam de página (menos quando a pessoa está digitando em algum campo)
    const aoTeclar = (e: KeyboardEvent) => {
      const alvo = e.target as HTMLElement | null;
      if (alvo && ['INPUT', 'TEXTAREA', 'SELECT'].includes(alvo.tagName)) return;
      if (e.key === 'ArrowRight' || e.key === 'PageDown') this.irPara(1);
      else if (e.key === 'ArrowLeft' || e.key === 'PageUp') this.irPara(-1);
    };
    document.addEventListener('fullscreenchange', aoMudar);
    document.addEventListener('keydown', aoTeclar);
    window.addEventListener('resize', aoRedimensionar);
    this.destruir.onDestroy(() => {
      document.removeEventListener('fullscreenchange', aoMudar); document.removeEventListener('keydown', aoTeclar); window.removeEventListener('resize', aoRedimensionar);
    });
  }

  private aoEvento(evento: EventoChamado): void {
    if (evento.tipo === 'novo') this.novosPendentes.add(evento.numero);
    else if (evento.acao) this.acoesPendentes.set(evento.numero, evento.acao);
    this.recarregar$.next();
  }

  private carregar(): void {
    this.api.painel(this.setorId).subscribe({ next: (e) => this.aplicar(e), error: () => this.erro.set('Não foi possível carregar o painel.') });
  }

  /** Modo automático: quantas linhas cabem entre o topo da tabela e o fim da tela (medindo uma linha de verdade). */
  private medir(): void {
    const area = this.area()?.nativeElement;
    if (!area) return;
    const linha = area.querySelector('tbody tr') as HTMLElement | null;
    const cabecalho = area.querySelector('thead') as HTMLElement | null;
    const alturaLinha = linha ? linha.getBoundingClientRect().height + 6 : LINHA_ESTIMADA_PX;
    const fundo = this.telaCheia() ? window.innerHeight : Math.max(window.innerHeight, area.getBoundingClientRect().top + 400);
    const livre = fundo - area.getBoundingClientRect().top - (cabecalho?.getBoundingClientRect().height ?? 30) - 70;
    this.linhasQueCabem.set(Math.max(3, Math.floor(livre / alturaLinha)));
    this.ajustarAteCaber(8);
  }

  /** Ajuste fino: se o quadro ainda passa da tela (legenda e paginação), tira uma linha por vez até caber. */
  private ajustarAteCaber(tentativas: number): void {
    requestAnimationFrame(() => {
      const quadro = this.quadro()?.nativeElement;
      const limite = this.telaCheia() ? window.innerHeight : Number.POSITIVE_INFINITY;
      if (!quadro || tentativas <= 0 || this.linhasQueCabem() <= 3 || this.estado()?.config.linhas_por_pagina) return;
      if (quadro.getBoundingClientRect().top + quadro.scrollHeight > limite + 1) {
        this.linhasQueCabem.update((n) => n - 1);
        this.ajustarAteCaber(tentativas - 1);
      }
    });
  }

  /** Troca de página no tempo dos Parâmetros (refeita só quando o tempo muda). */
  private ajustarRotacao(segundos: number): void {
    if (segundos === this.segundosRotacao) return;
    this.segundosRotacao = segundos;
    if (this.rotacao) clearInterval(this.rotacao);
    this.rotacao = setInterval(() => { if (Date.now() >= this.pausaAte) this.paginaAtual.update((p) => (p + 1) % this.paginas()); }, segundos * 1000);
  }

  /** Mostra o estado novo; os chamados novos (e não vistos antes) ganham destaque e o anúncio por voz. */
  private aplicar(estado: EstadoPainel): void {
    this.erro.set('');
    const anteriores = this.conhecidos;
    const ultimos = this.ultimos;
    this.conhecidos = new Set(estado.itens.map((i) => i.numero));
    this.ultimos = new Map(estado.itens.map((i) => [i.numero, i]));
    this.agora.set(Date.now());
    this.estado.set(estado);
    this.ajustarRotacao(estado.config.segundos_pagina);
    setTimeout(() => this.medir());
    if (!anteriores) {
      this.novosPendentes.clear();
      this.acoesPendentes.clear();
      return;
    }
    const falas = this.falasDasAcoes(estado, anteriores, ultimos);
    this.acoesPendentes.clear();
    const novos = estado.itens.filter((i) => !anteriores.has(i.numero) && this.novosPendentes.has(i.numero));
    this.novosPendentes.clear();
    if (estado.config.voz) falas.forEach((f) => this.falar(f));
    if (!novos.length) return;
    this.destacados.update((d) => new Set([...d, ...novos.map((i) => i.numero)]));
    setTimeout(() => this.destacados.update((d) => new Set([...d].filter((n) => !novos.some((i) => i.numero === n)))), DESTAQUE_MS);
    // A linha nova vai para a página que está na tela
    const indice = estado.itens.findIndex((i) => i.numero === novos[0].numero);
    if (indice >= 0) this.paginaAtual.set(Math.floor(indice / this.linhasPorPagina()));
    if (estado.config.voz) for (const item of novos) this.anunciar(item);
  }

  /**
   * O que falar das ações recebidas: "Chamado 123 assumido por João", "Chamado 123 resolvido", "Chamado 123 reaberto",
   * "Chamado 123 transferido para este painel". O chamado que mudou ganha destaque como o novo. Transferido para fora fica em silêncio
   * (só some da lista); o que está em outro setor (fora deste painel) não fala.
   */
  private falasDasAcoes(estado: EstadoPainel, anteriores: Set<number>, ultimos: Map<number, ItemPainel>): string[] {
    const falas: string[] = [];
    const destacar: number[] = [];
    for (const [numero, acao] of this.acoesPendentes) {
      const agora = estado.itens.find((i) => i.numero === numero);
      const antes = ultimos.get(numero);
      if (acao === 'assumido' && agora) {
        falas.push(agora.responsavel ? `Chamado ${numero} assumido por ${agora.responsavel}` : `Chamado ${numero} assumido`);
        destacar.push(numero);
      } else if (acao === 'resolvido' && antes) {
        falas.push(`Chamado ${numero} resolvido`);
      } else if (acao === 'reaberto' && agora) {
        falas.push(`Chamado ${numero} reaberto`);
        destacar.push(numero);
      } else if (acao === 'transferido' && agora && !anteriores.has(numero)) {
        falas.push(`Chamado ${numero} transferido para este painel`);
        destacar.push(numero);
      }
    }
    if (destacar.length) {
      this.destacados.update((d) => new Set([...d, ...destacar]));
      setTimeout(() => this.destacados.update((d) => new Set([...d].filter((n) => !destacar.includes(n)))), DESTAQUE_MS);
    }
    return falas;
  }

  /** "Novo chamado de Maria Aparecida" pela voz do sistema (Web Speech), em português. */
  private anunciar(item: ItemPainel): void {
    this.falar(item.solicitante ? `Novo chamado de ${item.solicitante}` : 'Novo chamado');
  }

  /** Fala o texto na voz pt-BR do sistema; as falas entram em fila (uma depois da outra). */
  private falar(texto: string): void {
    if (typeof speechSynthesis === 'undefined') return;
    const fala = new SpeechSynthesisUtterance(texto);
    fala.lang = 'pt-BR';
    const voz = speechSynthesis.getVoices().find((v) => v.lang === 'pt-BR') ?? speechSynthesis.getVoices().find((v) => v.lang.startsWith('pt'));
    if (voz) fala.voice = voz;
    speechSynthesis.speak(fala);
  }

  /** Página anterior (-1) ou seguinte (1), dando a volta; pausa a troca automática por um minuto. */
  protected irPara(passo: number): void {
    const total = this.paginas();
    this.paginaAtual.update((p) => (((p % total) + passo) % total + total) % total);
    this.pausaAte = Date.now() + 60000;
  }

  /** A linha inteira abre o chamado. */
  protected abrir(numero: number): void {
    void this.roteador.navigate(['/chamados', numero]);
  }

  protected textoConexao(): string {
    return { conectando: 'Conectando…', ao_vivo: 'Ao vivo', reconectando: 'Reconectando…', parado: 'Desconectado' }[this.tempoReal.estado()];
  }

  protected rotulo(c: ColunaPainel): string {
    return ROTULOS_COLUNA[c];
  }

  protected situacao(item: ItemPainel): string {
    return textoNivelPainel(item);
  }

  protected espera(abertoEm: string): string {
    return tempoEspera(abertoEm, this.agora());
  }

  protected hora(valor: string): string {
    return horaPainel(valor, this.agora());
  }

  protected alternarTelaCheia(): void {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void this.quadro()?.nativeElement.requestFullscreen();
  }
}
