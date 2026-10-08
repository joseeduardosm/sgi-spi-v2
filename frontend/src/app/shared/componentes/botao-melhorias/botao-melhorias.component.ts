// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o botão flutuante "Sugerir melhoria" (arrastável e que pode ser fechado na aba) e a janela de envio.

import { Component, computed, effect, inject, OnDestroy, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { MelhoriasApiService } from '../../../features/melhorias/melhorias-api.service';
import { MAXIMO_PRINTS, MAXIMO_TEXTO, moduloDaTela, ROTULOS_MODULO } from '../../../features/melhorias/melhorias.models';
import { LayoutService } from '../../layout/layout.service';
import { DialogosService } from '../../servicos/dialogos.service';
import { MelhoriasJanelaService } from './melhorias-janela.service';

/** Posição guardada por aba: distância da borda direita e da inferior (acompanha o redimensionamento da janela). */
interface EstadoBotao {
  direita: number;
  inferior: number;
  fechado: boolean;
}

// `sessionStorage` é por aba: fechar o botão ou arrastá-lo vale só nesta aba; uma aba nova volta ao canto inferior direito
const CHAVE = 'sgi-melhorias-botao';
const PADRAO: EstadoBotao = { direita: 20, inferior: 20, fechado: false };
const MARGEM = 8;
// Deslocamento mínimo (px) para o gesto contar como arrasto, e não como clique
const LIMIAR_ARRASTO = 6;

interface PrintEscolhido {
  arquivo: File;
  previa: string;
}

@Component({
  selector: 'app-botao-melhorias',
  imports: [FormsModule, RouterLink],
  template: `
    @if (!estado().fechado && !layout.menuCelularAberto()) {
      <div class="botao-melhorias" [style.right.px]="estado().direita" [style.bottom.px]="estado().inferior" [class.arrastando]="arrastando()">
        <button type="button" class="botao-melhorias-principal" title="Sugerir melhoria (arraste para mudar de lugar)" aria-label="Sugerir melhoria"
                (pointerdown)="iniciarArrasto($event)" (click)="aoClicar()">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15a4 4 0 0 1-4 4H8l-5 3v-7a4 4 0 0 1-1-2.7V7a4 4 0 0 1 4-4h11a4 4 0 0 1 4 4Z"/><path d="M8 8h8M8 12h5"/></svg>
          <span>Sugerir melhoria</span>
        </button>
        <button type="button" class="botao-melhorias-fechar" title="Esconder nesta aba (volta ao abrir uma nova aba)" aria-label="Esconder o botão de melhorias nesta aba"
                (click)="fechar()">×</button>
      </div>
    }
    @if (aviso(); as a) {
      <div class="aviso-melhorias" role="status">{{ a.texto }} <a routerLink="/melhorias" (click)="aviso.set(null)">Minhas sugestões</a></div>
    }

    @if (aberta()) {
      <div class="fundo-modal" role="presentation" (click)="fecharJanela()"></div>
      <section class="modal-portal modal-largo janela-melhorias" role="dialog" aria-modal="true" aria-labelledby="titulo-melhorias"
               (paste)="aoColar($event)">
        <header><div><span class="modal-sobretitulo">Sua opinião importa</span><h2 id="titulo-melhorias">Sugerir uma melhoria</h2></div>
          <button type="button" aria-label="Fechar" (click)="fecharJanela()">×</button></header>
        <form (submit)="$event.preventDefault(); enviar()">
          <div class="corpo-janela-melhorias">
            <p class="dica-formulario">Conte de forma objetiva o que pode melhorar. A equipe responde em <b>Melhorias › Minhas sugestões</b>.</p>
            <p class="tela-melhorias"><span>Tela</span> {{ rotuloModulo() }} · <code>{{ tela() }}</code></p>
            <label for="texto-melhoria">Sugestão *</label>
            <textarea id="texto-melhoria" name="texto" rows="6" [maxlength]="maximoTexto" [(ngModel)]="texto" autofocus
                      placeholder="Ex.: no painel de contratos, lembrar os filtros usados na última visita."></textarea>
            <small class="contador-melhorias">{{ texto.length }} / {{ maximoTexto }}</small>

            <p class="secao-formulario">Prints (opcional)</p>
            <div class="prints-melhorias">
              @for (p of prints(); track p.previa) {
                <figure>
                  <img [src]="p.previa" [alt]="'Print ' + ($index + 1)" />
                  <button type="button" class="link-arquivo" [attr.aria-label]="'Remover print ' + ($index + 1)" (click)="removerPrint($index)">remover</button>
                </figure>
              }
              @if (prints().length < maximoPrints) {
                <input #campoPrint type="file" accept="image/png,image/jpeg,image/webp" multiple hidden (change)="aoEscolher(campoPrint)" />
                <button type="button" class="adicionar-print" (click)="campoPrint.click()">+ Anexar print<small>ou cole com Ctrl+V</small></button>
              }
            </div>
            @if (erro()) { <p class="aviso-formulario erro" role="alert">{{ erro() }}</p> }
          </div>
          <footer><button type="button" class="acao-secundaria" (click)="fecharJanela()">Cancelar</button>
            <button type="submit" class="acao-primaria" [disabled]="enviando() || !texto.trim()">{{ enviando() ? 'Enviando…' : 'Enviar sugestão' }}</button></footer>
        </form>
      </section>
    }
  `,
  host: { '(window:resize)': 'ajustarAoRedimensionar()', '(document:keydown.escape)': 'fecharJanela()' },
})
export class BotaoMelhoriasComponent implements OnDestroy {
  protected readonly layout = inject(LayoutService);
  private readonly api = inject(MelhoriasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  private readonly pedidosExternos = inject(MelhoriasJanelaService);
  private pedidosAtendidos = this.pedidosExternos.pedidos();
  // Pedido de fora (paleta de comandos): abre a janela mesmo com o botão escondido nesta aba
  private readonly abrirAPedido = effect(() => {
    const n = this.pedidosExternos.pedidos();
    if (n === this.pedidosAtendidos) return;
    this.pedidosAtendidos = n;
    untracked(() => this.abrirJanela());
  });

  protected readonly estado = signal<EstadoBotao>(this.ler());
  protected readonly arrastando = signal(false);
  protected readonly aberta = signal(false);
  protected readonly enviando = signal(false);
  protected readonly erro = signal<string | null>(null);
  protected readonly prints = signal<PrintEscolhido[]>([]);
  protected readonly aviso = signal<{ texto: string } | null>(null);
  protected readonly tela = signal('');
  protected readonly rotuloModulo = computed(() => ROTULOS_MODULO[moduloDaTela(this.tela())] ?? 'Geral');
  protected readonly maximoTexto = MAXIMO_TEXTO;
  protected readonly maximoPrints = MAXIMO_PRINTS;
  protected texto = '';
  // O clique que encerra um arrasto não abre a janela
  private arrastou = false;
  private temporizadorAviso: ReturnType<typeof setTimeout> | undefined;

  ngOnDestroy(): void {
    this.limparPrints();
    clearTimeout(this.temporizadorAviso);
  }

  /** Arrasta o botão com o ponteiro (mouse, caneta ou toque), sem sair da janela. */
  protected iniciarArrasto(evento: PointerEvent): void {
    if (evento.button !== 0) return;
    const alvo = evento.currentTarget as HTMLElement;
    const caixa = alvo.parentElement!.getBoundingClientRect();
    const inicioX = evento.clientX, inicioY = evento.clientY;
    const { direita, inferior } = this.estado();
    this.arrastou = false;
    alvo.setPointerCapture(evento.pointerId);
    const mover = (e: PointerEvent) => {
      const dx = e.clientX - inicioX, dy = e.clientY - inicioY;
      if (!this.arrastou && Math.hypot(dx, dy) < LIMIAR_ARRASTO) return;
      this.arrastou = true;
      this.arrastando.set(true);
      this.estado.update((s) => ({ ...s, ...this.limitar(direita - dx, inferior - dy, caixa.width, caixa.height) }));
    };
    const soltar = () => {
      alvo.removeEventListener('pointermove', mover);
      alvo.removeEventListener('pointerup', soltar);
      alvo.removeEventListener('pointercancel', soltar);
      this.arrastando.set(false);
      if (this.arrastou) this.gravar();
    };
    alvo.addEventListener('pointermove', mover);
    alvo.addEventListener('pointerup', soltar);
    alvo.addEventListener('pointercancel', soltar);
  }

  protected aoClicar(): void {
    if (this.arrastou) {
      this.arrastou = false;
      return;
    }
    this.abrirJanela();
  }

  /** Esconde o botão só nesta aba. */
  protected fechar(): void {
    this.estado.update((s) => ({ ...s, fechado: true }));
    this.gravar();
  }

  /** Ao redimensionar a janela, o botão continua visível. */
  protected ajustarAoRedimensionar(): void {
    const s = this.estado();
    this.estado.set({ ...s, ...this.limitar(s.direita, s.inferior, 190, 48) });
  }

  protected abrirJanela(): void {
    this.tela.set(this.roteador.url);
    this.erro.set(null);
    this.aberta.set(true);
  }

  protected fecharJanela(): void {
    this.aberta.set(false);
  }

  protected aoEscolher(campo: HTMLInputElement): void {
    this.incluirPrints(Array.from(campo.files ?? []));
    campo.value = '';
  }

  /** Ctrl+V com uma imagem na área de transferência vira print. */
  protected aoColar(evento: ClipboardEvent): void {
    const imagens = Array.from(evento.clipboardData?.items ?? []).filter((i) => i.kind === 'file' && i.type.startsWith('image/'))
      .map((i) => i.getAsFile()).filter((f): f is File => !!f)
      .map((f, i) => new File([f], `print-colado-${Date.now()}-${i + 1}.png`, { type: f.type }));
    if (!imagens.length) return;
    evento.preventDefault();
    this.incluirPrints(imagens);
  }

  protected removerPrint(indice: number): void {
    const removido = this.prints()[indice];
    if (removido) URL.revokeObjectURL(removido.previa);
    this.prints.update((l) => l.filter((_, i) => i !== indice));
  }

  protected enviar(): void {
    const texto = this.texto.trim();
    if (!texto || this.enviando()) return;
    this.enviando.set(true);
    this.erro.set(null);
    this.api.enviar(texto, this.tela(), this.prints().map((p) => p.arquivo)).subscribe({
      next: (s) => {
        this.enviando.set(false);
        this.texto = '';
        this.limparPrints();
        this.aberta.set(false);
        this.aviso.set({ texto: `Sugestão #${s.numero} enviada. Obrigado pela contribuição!` });
        clearTimeout(this.temporizadorAviso);
        this.temporizadorAviso = setTimeout(() => this.aviso.set(null), 6000);
      },
      error: (e) => {
        this.enviando.set(false);
        this.erro.set(e?.error?.detalhe ?? 'Não foi possível enviar a sugestão.');
        if (!e?.error?.detalhe) this.dialogos.mostrarErro(e, 'Não foi possível enviar a sugestão');
      },
    });
  }

  private incluirPrints(arquivos: File[]): void {
    const aceitos = arquivos.filter((a) => /^image\/(png|jpeg|webp)$/.test(a.type));
    if (aceitos.length < arquivos.length) this.erro.set('Envie prints em PNG, JPG ou WebP.');
    const livres = MAXIMO_PRINTS - this.prints().length;
    if (aceitos.length > livres) this.erro.set(`No máximo ${MAXIMO_PRINTS} prints por sugestão.`);
    this.prints.update((l) => [...l, ...aceitos.slice(0, livres).map((arquivo) => ({ arquivo, previa: URL.createObjectURL(arquivo) }))]);
  }

  private limparPrints(): void {
    for (const p of this.prints()) URL.revokeObjectURL(p.previa);
    this.prints.set([]);
  }

  /** Mantém o botão dentro da janela. */
  private limitar(direita: number, inferior: number, largura: number, altura: number): Pick<EstadoBotao, 'direita' | 'inferior'> {
    const maxDireita = Math.max(MARGEM, window.innerWidth - largura - MARGEM);
    const maxInferior = Math.max(MARGEM, window.innerHeight - altura - MARGEM);
    return { direita: Math.min(Math.max(direita, MARGEM), maxDireita), inferior: Math.min(Math.max(inferior, MARGEM), maxInferior) };
  }

  private ler(): EstadoBotao {
    try {
      const salvo = JSON.parse(sessionStorage.getItem(CHAVE) ?? 'null') as Partial<EstadoBotao> | null;
      if (salvo && Number.isFinite(salvo.direita) && Number.isFinite(salvo.inferior)) return { ...PADRAO, ...salvo };
    } catch {
      // Armazenamento indisponível (janela privada, bloqueio): usa o padrão
    }
    return { ...PADRAO };
  }

  private gravar(): void {
    try {
      sessionStorage.setItem(CHAVE, JSON.stringify(this.estado()));
    } catch {
      // Sem armazenamento, a posição vale só até recarregar
    }
  }
}
