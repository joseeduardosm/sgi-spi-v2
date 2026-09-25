import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { DialogosService } from '../../servicos/dialogos.service';

/** Desenha os diálogos globais do `DialogosService`. Incluído uma vez no layout autenticado. */
@Component({
  selector: 'app-dialogos',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './dialogos.component.html',
  styleUrl: './dialogos.component.scss',
  host: { '(document:keydown.escape)': 'aoPressionarEsc()' },
})
export class DialogosComponent {
  protected readonly dialogos = inject(DialogosService);

  protected aoPressionarEsc(): void {
    if (this.dialogos.erro()) this.dialogos.fecharErro();
    else this.dialogos.responderConfirmacao(false);
  }
}
