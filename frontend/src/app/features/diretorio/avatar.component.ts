// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir a foto de uma pessoa (que exige token) ou, sem foto, um círculo com as iniciais.

import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { ImagemAutenticadaDirective } from '../noticias/gestao/imagem-autenticada.directive';
import { iniciais } from './diretorio.models';

@Component({
  selector: 'app-avatar',
  imports: [ImagemAutenticadaDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (foto()) { <img [appImagemAutenticada]="foto()" [alt]="nome()" /> } @else { <span aria-hidden="true">{{ siglas() }}</span> }
  `,
  host: { class: 'avatar-diretorio', '[attr.title]': 'nome()' },
})
export class AvatarComponent {
  readonly nome = input.required<string>();
  readonly foto = input<string | null | undefined>(null);
  protected readonly siglas = computed(() => iniciais(this.nome()));
}
