// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir avatares de pessoas (iniciais em círculo colorido), empilhados como nos apps de gestão de equipes.

import { Component, computed, input } from '@angular/core';

import { corAvatar, iniciais, Pessoa } from './tarefas.models';

/**
 * Avatares sobrepostos: mostra até `maximo` pessoas e, se houver mais, um círculo "+N".
 * O nome completo aparece no `title` (dica ao passar o mouse) e no texto para leitores de tela.
 */
@Component({
  selector: 'app-avatares',
  template: `
    <span class="avatares" [class.grande]="tamanho() === 'grande'" [class.pequeno]="tamanho() === 'pequeno'">
      @for (p of visiveis(); track p.id) {
        <span class="avatar" [style.background]="cor(p.id)" [title]="p.nome" role="img" [attr.aria-label]="p.nome">{{ sigla(p.nome) }}</span>
      }
      @if (restantes()) {
        <span class="avatar mais" [title]="nomesRestantes()" role="img" [attr.aria-label]="'mais ' + restantes() + ' pessoas'">+{{ restantes() }}</span>
      }
    </span>
  `,
})
export class AvataresComponent {
  /** Pessoas a mostrar (a primeira fica na frente). */
  readonly pessoas = input<Pessoa[]>([]);
  /** Quantos avatares aparecem antes do "+N". */
  readonly maximo = input(3);
  readonly tamanho = input<'pequeno' | 'normal' | 'grande'>('normal');

  protected readonly visiveis = computed(() => this.pessoas().slice(0, this.maximo()));
  protected readonly restantes = computed(() => Math.max(0, this.pessoas().length - this.maximo()));
  protected readonly nomesRestantes = computed(() => this.pessoas().slice(this.maximo()).map((p) => p.nome).join(', '));

  // Funções puras expostas ao template
  protected readonly cor = corAvatar;
  protected readonly sigla = iniciais;
}
