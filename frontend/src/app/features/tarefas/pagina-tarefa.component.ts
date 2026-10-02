// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela própria da tarefa (/tarefas/:numero), no lugar da janela modal sobre o quadro.

import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { map } from 'rxjs';

import { JanelaDetalheTarefaComponent } from './janela-detalhe-tarefa.component';

/**
 * Cada tarefa tem a própria URL (`/tarefas/123`), a mesma dos links de avisos e e-mails.
 * Ao fechar (×, Esc ou exclusão), volta para a lista de onde o usuário veio, ou para "Minhas tarefas".
 */
@Component({
  selector: 'app-pagina-tarefa',
  imports: [JanelaDetalheTarefaComponent],
  template: `<app-janela-detalhe-tarefa [numeroTarefa]="numero()" [pagina]="true" (fechar)="voltar()" />`,
})
export class PaginaTarefaComponent {
  private readonly roteador = inject(Router);
  private readonly rota = inject(ActivatedRoute);
  protected readonly numero = toSignal(this.rota.paramMap.pipe(map((p) => Number(p.get('numero')) || null)), { initialValue: null });
  /** Havia outra tela do sistema antes desta (o "voltar" do navegador volta a ela). */
  private readonly veioDeOutraTela = this.roteador.navigated;

  protected voltar(): void {
    if (this.veioDeOutraTela) history.back();
    else void this.roteador.navigate(['/tarefas']);
  }
}
