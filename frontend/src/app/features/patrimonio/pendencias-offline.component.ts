// Criado por José Eduardo Santana Martins
// Este arquivo serve para listar o que está na fila do aparelho (aguardando envio ou parado por erro) e permitir reenviar ou descartar.
import { Component, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { FilaOfflineService } from './fila-offline.service';

@Component({
  selector: 'app-pendencias-offline',
  imports: [RouterLink, DatePipe, CabecalhoPatrimonioComponent],
  template: `
    <app-cabecalho-patrimonio titulo="Itens aguardando envio" descricao="O que foi feito sem sinal e ainda não chegou ao servidor." />
    <section class="painel-gestao pat-pagina">
      @for (i of fila.itens(); track i.id) {
        <article class="pat-linha-item">
          <div><strong>{{ i.descricao }}</strong>
            <small>{{ i.criado_em | date: 'dd/MM/yyyy HH:mm' }} · {{ i.erro ? 'Parado: ' + i.erro : 'Aguardando conexão' }}</small></div>
          <div class="pat-acoes">
            @if (i.erro) { <button type="button" class="acao-secundaria acao-pequena" (click)="fila.tentarDeNovo(i.id)">Tentar de novo</button> }
            <button type="button" class="acao-recusar acao-pequena" (click)="descartar(i.id, i.descricao)">Descartar</button>
          </div>
        </article>
      } @empty { <p class="estado-vazio">Nada aguardando envio. <a routerLink="/patrimonio">Voltar aos bens</a></p> }
    </section>
  `,
})
export class PendenciasOfflineComponent {
  protected readonly fila = inject(FilaOfflineService);
  private readonly dialogos = inject(DialogosService);

  protected async descartar(id: string, descricao: string): Promise<void> {
    if (await this.dialogos.confirmar({ titulo: 'Descartar este item?', mensagem: `"${descricao}" será apagado do aparelho e não será enviado.`, rotuloConfirmar: 'Descartar', segundos: 2 })) await this.fila.descartar(id);
  }
}
