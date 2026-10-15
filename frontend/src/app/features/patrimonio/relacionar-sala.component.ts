// Criado por José Eduardo Santana Martins
// Este arquivo serve para relacionar de uma vez todos os bens de uma sala numa lista (inservíveis, extraviados ou baixa), com confirmação.
import { Component, computed, inject, input, output, signal } from '@angular/core';

import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { Bem } from './patrimonio.models';
import { SeletorSalaComponent } from './seletor-sala.component';

/**
 * Escolher a sala abre uma confirmação ("Você deseja relacionar os X ativos da sala Y?") com a lista chapa | série | descrição.
 * Só entram os bens que a lista aceita: nas listas de classificação, ativos e em manutenção sem solicitação pendente; na baixa, os já
 * classificados como inservíveis ou extraviados.
 */
@Component({
  selector: 'app-relacionar-sala',
  imports: [SeletorSalaComponent],
  template: `
    <app-seletor-sala nome="sala-relacionar" rotulo="Relacionar todos os bens de uma sala" placeholder="Relacionar todos os bens de uma sala…" [leitor]="true" [valor]="sala()" (valorChange)="escolher($event)" [soAtivas]="false" />
    @if (aviso()) { <small class="dica" role="status">{{ aviso() }}</small> }
    @if (bens(); as lista) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="cancelar()"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal modal-relacionar" role="dialog" aria-modal="true" aria-labelledby="titulo-relacionar">
        <header>
          <h2 id="titulo-relacionar">Relacionar os bens da sala</h2>
          <button type="button" aria-label="Fechar" (click)="cancelar()">×</button>
        </header>
        <div class="corpo-relacionar">
          <p>Você deseja relacionar os <strong>{{ lista.length }}</strong> ativo(s) da sala <strong>{{ rotuloSala() }}</strong>?</p>
          <div class="tabela-gestao-envoltorio"><table class="tabela-gestao">
            <thead><tr><th>Chapa</th><th>Série</th><th>Descrição</th></tr></thead>
            <tbody>@for (b of lista; track b.id) { <tr><td class="texto-codigo">{{ b.chapa ?? '—' }}</td><td class="texto-codigo">{{ b.numero_serie ?? '—' }}</td><td>{{ b.descricao }}</td></tr> }</tbody>
          </table></div>
        </div>
        <footer class="acoes-formulario">
          <button type="button" class="acao-secundaria" (click)="cancelar()">Cancelar</button>
          <button type="button" class="acao-positiva" (click)="confirmar(lista)">Relacionar {{ lista.length }} bem(ns)</button>
        </footer>
      </section>
    }
  `,
})
export class RelacionarSalaComponent {
  private readonly api = inject(PatrimonioApiService);
  private readonly estado = inject(PatrimonioEstadoService);

  /** `baixa`: só inservíveis e extraviados; `classificacao`: só ativos e em manutenção sem pendência. */
  readonly modo = input<'classificacao' | 'baixa'>('classificacao');
  readonly confirmado = output<Bem[]>();

  protected readonly sala = signal('');
  protected readonly bens = signal<Bem[] | null>(null);
  protected readonly aviso = signal('');
  protected readonly rotuloSala = computed(() => this.estado.rotuloDaSala(this.sala()));

  protected escolher(id: string): void {
    this.sala.set(id);
    this.aviso.set('');
    if (!id) return;
    this.api.bens({ localizacao_id: id, tamanho: 200 }).subscribe({
      next: (r) => {
        const aceitos = r.itens.filter((b) => this.modo() === 'baixa' ? ['inservivel', 'extraviado'].includes(b.situacao) : ['ativo', 'em_manutencao'].includes(b.situacao) && !b.classificacao_pendente);
        if (aceitos.length) this.bens.set(aceitos);
        else { this.aviso.set('Esta sala não tem bens que possam entrar nesta lista.'); this.sala.set(''); }
      },
      error: () => { this.aviso.set('Não foi possível listar os bens da sala.'); this.sala.set(''); },
    });
  }

  protected cancelar(): void {
    this.bens.set(null);
    this.sala.set('');
  }

  protected confirmar(lista: Bem[]): void {
    this.bens.set(null);
    this.sala.set('');
    this.confirmado.emit(lista);
  }
}
