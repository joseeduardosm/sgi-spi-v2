// Criado por José Eduardo Santana Martins
// Este arquivo serve para mostrar o histórico de recusas da nota fiscal (trilha, PDFs e e-mail) nas etapas da nota fiscal e da retenção.

import { DatePipe } from '@angular/common';
import { Component, inject, input, output, signal } from '@angular/core';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { LinkificarPipe } from '../../../shared/utilitarios/linkificar.pipe';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { DetalheCompetencia } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';

/**
 * Histórico das recusas da nota fiscal: justificativa, quem e quando, as notas recusadas (PDF), o PDF da recusa (para juntar a um processo)
 * e o estado do e-mail enviado à equipe e a todos os prepostos, com "Reenviar e-mail".
 */
@Component({
  selector: 'app-historico-recusas',
  imports: [DatePipe, LinkificarPipe, ...PIPES_FORMATACAO],
  template: `
    @let d = detalhe();
    @if (d.recusas.length) {
      <section class="historico-recusas" aria-label="Recusas da nota fiscal">
        <p class="secao-formulario">Recusas da nota fiscal ({{ d.recusas.length }})</p>
        @for (r of d.recusas; track r.id) {
          <article class="recusa-nf">
            <header>
              <strong>Recusa nº {{ r.ordem }}</strong>
              <small>por {{ r.recusada_por_nome }} em {{ r.recusada_em | date: 'dd/MM/yyyy HH:mm' }}</small>
            </header>
            <p class="justificativa-recusa" [innerHTML]="r.justificativa | linkificar"></p>
            <ul class="notas-recusadas">
              @for (n of r.notas; track $index) {
                <li>{{ n.rotulo }}@if (n.valor_bruto) { · {{ n.valor_bruto | moeda }} }
                  @if (n.arquivo) { <button type="button" class="link-arquivo" (click)="baixar(n.arquivo.anexo_id)">PDF da nota</button> }
                </li>
              }
            </ul>
            <div class="acoes-cartao esquerda">
              @if (r.pdf) { <button type="button" class="acao-secundaria acao-pequena" (click)="baixar(r.pdf.anexo_id)">Baixar PDF da recusa</button> }
              @if (d.pode_conferir_retencao && r.email.enviado_em !== null) {
                <button type="button" class="acao-secundaria acao-pequena" [disabled]="reenviando() === r.id" (click)="reenviar(r.id)">
                  {{ reenviando() === r.id ? 'Reenviando…' : 'Reenviar e-mail' }}</button>
              }
            </div>
            @if (r.email.enviado_em === null) {
              <p class="dica-formulario">Enviando o e-mail à equipe e aos prepostos…</p>
            } @else if (r.email.ok) {
              <p class="dica-formulario">E-mail com o PDF enviado em {{ r.email.enviado_em | date: 'dd/MM/yyyy HH:mm' }} a {{ r.email.destinatarios.join(', ') }}.</p>
            } @else {
              <p class="aviso-bloco erro">O e-mail não foi enviado: {{ r.email.erro }}</p>
            }
          </article>
        }
      </section>
    }
  `,
})
export class HistoricoRecusasComponent {
  readonly detalhe = input.required<DetalheCompetencia>();
  readonly atualizado = output<DetalheCompetencia>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly reenviando = signal<string | null>(null);

  protected baixar(anexoId: string): void {
    const d = this.detalhe();
    this.api.baixar(d.contrato_id, d.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected reenviar(recusaId: string): void {
    const d = this.detalhe();
    this.reenviando.set(recusaId);
    this.api.reenviarEmailRecusa(d.contrato_id, d.id, recusaId).subscribe({
      next: (novo) => {
        this.reenviando.set(null);
        this.atualizado.emit(novo);
      },
      error: (e) => {
        this.reenviando.set(null);
        this.dialogos.mostrarErro(e, 'Não foi possível reenviar o e-mail');
      },
    });
  }
}
