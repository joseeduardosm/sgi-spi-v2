// Criado por José Eduardo Santana Martins
// Este arquivo serve para manter os links antigos /tarefas/123 (e-mails e avisos): abre a tarefa na janela sobre "Minhas tarefas".

import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

/**
 * Os avisos e e-mails trazem o link /tarefas/<número>. A tarefa agora abre numa janela sobre o quadro,
 * então esta rota só redireciona para /tarefas?tarefa=<número> (sem deixar rastro no histórico).
 * Se a tarefa não existir ou o usuário não puder vê-la, a própria janela avisa.
 */
@Component({
  selector: 'app-abrir-tarefa',
  template: `<p class="estado-vazio">Abrindo a tarefa…</p>`,
})
export class AbrirTarefaComponent implements OnInit {
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);

  ngOnInit(): void {
    const numero = Number(this.rota.snapshot.paramMap.get('numero'));
    void this.roteador.navigate(['/tarefas'], { queryParams: Number.isInteger(numero) && numero > 0 ? { tarefa: numero } : {}, replaceUrl: true });
  }
}
