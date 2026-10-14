// Criado por José Eduardo Santana Martins
// Este arquivo serve para escolher uma sala num único campo (combobox): conforme a pessoa digita, a lista de salas vai sendo filtrada.
import { Component, computed, effect, inject, input, model, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { LeitorCodigoComponent } from './leitor-codigo.component';

import { OpcaoSala, PatrimonioEstadoService } from './patrimonio-estado.service';

/**
 * Combobox de sala: **um só campo**. Ao focar ou digitar, abre a lista (agrupada por andar) filtrada pelo texto; clicar numa sala (ou Enter na
 * destacada) escolhe e mostra o nome dela no campo. Setas ↑ ↓ navegam e Esc fecha. Digitar de novo depois de escolher limpa a escolha.
 */
@Component({
  selector: 'app-seletor-sala',
  imports: [FormsModule, LeitorCodigoComponent],
  template: `
    <div class="pat-seletor-sala" role="combobox" [attr.aria-expanded]="aberto()" aria-haspopup="listbox">
      <input type="text" [id]="idCampo()" [name]="nome()" autocomplete="off" [placeholder]="placeholder()" [attr.aria-label]="rotulo()" aria-autocomplete="list"
             [ngModel]="texto()" (ngModelChange)="digitou($event)" (focus)="abrir()" (blur)="fecharDepois()" (keydown)="teclado($event)" />
      @if (valor()) { <button type="button" class="pat-limpar-sala" aria-label="Limpar a sala escolhida" (mousedown)="$event.preventDefault()" (click)="limpar()">×</button> }
      @if (leitor()) {
        <button type="button" class="pat-leitor-sala" aria-label="Ler o código da porta da sala com a câmera" title="Ler o código ou QR da porta da sala" (mousedown)="$event.preventDefault()" (click)="lendo.set(true)">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10" /></svg></button>
      }
      @if (aberto()) {
        <ul class="pat-opcoes-sala" role="listbox">
          @for (g of grupos(); track g.andar) {
            <li class="pat-grupo-sala" role="presentation">{{ g.titulo }}</li>
            @for (s of g.salas; track s.id) {
              <li role="option" [attr.aria-selected]="s.id === valor()" [class.destacada]="s.id === destacada()" [class.escolhida]="s.id === valor()"
                  (mousedown)="$event.preventDefault()" (click)="escolher(s)" (mouseenter)="destacada.set(s.id)">{{ s.rotulo }}{{ s.ativo ? '' : ' (inativa)' }}</li>
            }
          } @empty { <li class="pat-sem-sala" role="presentation">Nenhuma sala encontrada.</li> }
        </ul>
      }
    </div>
    @if (avisoLeitura()) { <small class="dica pat-aviso-leitura" role="alert">{{ avisoLeitura() }}</small> }
    @if (lendo()) { <app-leitor-codigo mensagem="Aponte a câmera para o código ou QR da porta da sala" (lido)="lerPorta($event)" (fechar)="lendo.set(false)" /> }
  `,
})
export class SeletorSalaComponent {
  private readonly estado = inject(PatrimonioEstadoService);
  /** Id da sala escolhida (vazio = nenhuma). */
  readonly valor = model<string>('');
  readonly nome = input('sala');
  /** `id` do campo (para o `<label for>` de quem usa o componente). */
  readonly idCampo = input('');
  readonly rotulo = input('Sala');
  readonly placeholder = input('Digite o código ou escolha a sala');
  /** Só salas do setor "Depósito inservível" (destino dos inservíveis). */
  readonly soDeposito = input(false);
  /** Esconde as salas inativas (cadastro e destino não aceitam sala inativa). */
  readonly soAtivas = input(true);
  /** Mostra o botão da câmera: lê o código ou QR da porta e escolhe a sala. */
  readonly leitor = input(false);
  /** Salas a esconder (a origem, na movimentação). */
  readonly excluir = input<string[]>([]);

  protected readonly lendo = signal(false);
  protected readonly avisoLeitura = signal('');
  protected readonly texto = signal('');
  protected readonly aberto = signal(false);
  protected readonly destacada = signal('');
  /** Texto usado no filtro: vazio logo depois de escolher (para a lista inteira aparecer ao reabrir). */
  private readonly filtro = signal('');

  constructor() {
    // Quando quem usa o componente define o valor (ou as salas terminam de carregar), o campo mostra o nome da sala escolhida
    effect(() => {
      const sala = this.estado.salas().find((s) => s.id === this.valor());
      if (sala) this.texto.set(sala.rotulo);
    });
  }

  protected readonly grupos = computed(() => {
    const termo = this.filtro().trim().toLowerCase();
    const mapa = new Map<number | null, OpcaoSala[]>();
    for (const s of this.estado.salas()) {
      if (this.soAtivas() && !s.ativo && s.id !== this.valor()) continue;
      if (this.soDeposito() && !s.deposito) continue;
      if (this.excluir().includes(s.id)) continue;
      if (termo && !s.rotulo.toLowerCase().includes(termo)) continue;
      mapa.set(s.andar, [...(mapa.get(s.andar) ?? []), s]);
    }
    return [...mapa.entries()].sort((a, b) => (a[0] ?? 99) - (b[0] ?? 99)).map(([andar, salas]) => ({
      andar, salas, titulo: andar === null ? 'Sem andar' : andar === -1 ? 'Subsolo' : andar === 0 ? 'Térreo' : `${andar}º andar`,
    }));
  });

  private visiveis(): OpcaoSala[] {
    return this.grupos().flatMap((g) => g.salas);
  }

  protected abrir(): void {
    this.filtro.set(this.valor() ? '' : this.texto());
    this.aberto.set(true);
    this.destacada.set(this.valor() || this.visiveis()[0]?.id || '');
  }

  /** Fecha depois do clique numa opção ser processado (o `mousedown` das opções já impede o campo de perder o foco). */
  protected fecharDepois(): void {
    this.aberto.set(false);
    const sala = this.estado.salas().find((s) => s.id === this.valor());
    this.texto.set(sala ? sala.rotulo : '');
  }

  protected digitou(texto: string): void {
    this.texto.set(texto);
    this.filtro.set(texto);
    // Digitar depois de ter escolhido desfaz a escolha: o campo volta a ser busca
    if (this.valor()) this.valor.set('');
    this.aberto.set(true);
    this.destacada.set(this.visiveis()[0]?.id ?? '');
  }

  protected escolher(sala: OpcaoSala): void {
    this.valor.set(sala.id);
    this.texto.set(sala.rotulo);
    this.filtro.set('');
    this.aberto.set(false);
  }

  /** Código lido na porta: acha a sala pelo código (05A03, 5a03, 05-A-03...) e a escolhe se a lista deste campo a aceita. */
  protected lerPorta(codigo: string): void {
    this.avisoLeitura.set('');
    const alvo = normalizarCodigoSala(codigo);
    const sala = this.estado.salas().find((s) => s.codigo && normalizarCodigoSala(s.codigo) === alvo);
    if (!sala) { this.avisoLeitura.set(`Nenhuma sala com o código lido (${codigo.trim()}).`); return; }
    if ((this.soAtivas() && !sala.ativo) || (this.soDeposito() && !sala.deposito) || this.excluir().includes(sala.id)) {
      this.avisoLeitura.set(`A sala ${sala.codigo} não pode ser escolhida aqui.`);
      return;
    }
    this.escolher(sala);
    this.lendo.set(false);
  }

  protected limpar(): void {
    this.avisoLeitura.set('');
    this.valor.set('');
    this.texto.set('');
    this.filtro.set('');
  }

  protected teclado(evento: KeyboardEvent): void {
    const lista = this.visiveis();
    const i = lista.findIndex((s) => s.id === this.destacada());
    if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
      evento.preventDefault();
      if (!this.aberto()) { this.abrir(); return; }
      const novo = lista[Math.max(0, Math.min(lista.length - 1, i + (evento.key === 'ArrowDown' ? 1 : -1)))];
      if (novo) this.destacada.set(novo.id);
    } else if (evento.key === 'Enter' && this.aberto()) {
      // Enter escolhe a sala destacada sem enviar o formulário
      evento.preventDefault();
      const sala = lista.find((s) => s.id === this.destacada());
      if (sala) this.escolher(sala);
    } else if (evento.key === 'Escape') {
      this.aberto.set(false);
    }
  }
}

/** Código de sala comparável: sem espaços, hífens ou barras, em maiúsculas, com o andar e o número em dois dígitos (5a3 → 05A03; -1A1 → -1A01). */
export function normalizarCodigoSala(texto: string): string {
  const bruto = texto.trim().toUpperCase();
  const subsolo = bruto.startsWith('-');
  const limpo = bruto.replace(/[\s_/.-]+/g, '');
  const m = /^(\d{1,2})([AB])(\d{1,2})$/.exec(limpo);
  if (!m) return limpo;
  return `${subsolo ? '-' : ''}${subsolo ? m[1] : m[1].padStart(2, '0')}${m[2]}${m[3].padStart(2, '0')}`;
}
