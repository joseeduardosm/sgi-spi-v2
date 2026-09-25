// Criado por José Eduardo Santana Martins
// Este arquivo serve para desenhar na tela os diálogos globais (confirmação, erro e "Executando a solicitação").

import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { DialogosService } from '../../servicos/dialogos.service';

/** Desenha os diálogos globais do `DialogosService`. Incluído uma vez no layout autenticado. */
@Component({
  selector: 'app-dialogos',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './dialogos.component.html',
  styleUrl: './dialogos.component.scss',
  // `host`: escuta a tecla Esc no documento inteiro, mesmo sem o foco no diálogo
  host: { '(document:keydown.escape)': 'aoPressionarEsc()' },
})
export class DialogosComponent {
  // `protected`: acessível no template (HTML), mas não por outras classes
  protected readonly dialogos = inject(DialogosService);

  /** Esc fecha o erro aberto ou, se não houver, cancela a confirmação. */
  protected aoPressionarEsc(): void {
    if (this.dialogos.erro()) this.dialogos.fecharErro();
    else this.dialogos.responderConfirmacao(false);
  }
}
