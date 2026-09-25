// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a etapa 4 (consulta ao CADIN), com o histórico de consultas.

import { DatePipe } from '@angular/common';
import { Component, inject, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { DetalheCompetencia } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';

/** Etapa 4: consulta ao CADIN. Com pendência, a etapa continua aberta; "Não" conclui. */
@Component({
  selector: 'app-etapa-cadin',
  imports: [FormsModule, DatePipe, EnvioPdfComponent],
  template: `
    @let d = detalhe();
    <section class="cartao-dados" aria-labelledby="titulo-cadin">
      <header><h2 id="titulo-cadin">4. Consulta ao CADIN</h2></header>
      <div class="corpo">
        @if (editavel()) {
          <fieldset class="linha-caixas">
            <legend class="dica-formulario" style="margin: 0 0 6px; font-size: 12px">Há pendência no CADIN?</legend>
            <label><input type="radio" name="pendencia" [value]="false" [(ngModel)]="possuiPendencia" /> Não</label>
            <label><input type="radio" name="pendencia" [value]="true" [(ngModel)]="possuiPendencia" /> Sim</label>
          </fieldset>
          <div class="acoes-cartao esquerda" style="margin: 0 0 14px"><app-envio-pdf rotulo="Selecionar certidão do CADIN" (selecionado)="certidao = $event" /></div>
          @if (possuiPendencia) {
            <div class="grade-formulario">
              <div class="ocupa-duas"><label for="cadin-pendencia">Qual é a pendência? *</label><textarea id="cadin-pendencia" maxlength="2000" [(ngModel)]="pendencia"></textarea></div>
              <div class="ocupa-duas"><label for="cadin-texto">Texto de notificação</label><textarea id="cadin-texto" maxlength="2500" [(ngModel)]="textoNotificacao"></textarea></div>
            </div>
            <div class="acoes-cartao esquerda" style="margin: 0 0 14px"><app-envio-pdf rotulo="Anexar e-mail de comunicação (PDF)" (selecionado)="email = $event" /></div>
          }
          <div class="acoes-cartao">
            <button type="button" class="acao-primaria" [disabled]="!certidao || (possuiPendencia && (!pendencia.trim() || !email))" (click)="registrar()">
              {{ possuiPendencia ? 'Registrar pendência' : 'Registrar consulta e concluir' }}
            </button>
          </div>
        }
        <p class="secao-formulario">Histórico de consultas</p>
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <thead><tr><th>Data</th><th>Resultado</th><th>Pendência</th><th>Usuário</th><th>Arquivos</th></tr></thead>
            <tbody>
              @for (c of d.consultas_cadin; track c.id) {
                <tr>
                  <td>{{ c.criado_em | date: 'dd/MM/yyyy HH:mm' }}</td>
                  <td><span class="selo-situacao" [class.vermelho]="c.possui_pendencia">{{ c.possui_pendencia ? 'Pendência encontrada' : 'Sem pendência' }}</span></td>
                  <td>{{ c.pendencia || '—' }}@if (c.texto_notificacao) { <small>{{ c.texto_notificacao }}</small> }</td>
                  <td>{{ c.criado_por_nome }}</td>
                  <td>
                    <button type="button" class="link-arquivo" (click)="baixar(c.certidao.anexo_id)">Certidão</button>
                    @if (c.email) { · <button type="button" class="link-arquivo" (click)="baixar(c.email.anexo_id)">E-mail</button> }
                  </td>
                </tr>
              } @empty {
                <tr><td class="estado-vazio" colspan="5">Nenhuma consulta registrada.</td></tr>
              }
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `,
})
export class EtapaCadinComponent {
  readonly detalhe = input.required<DetalheCompetencia>();
  readonly editavel = input(false);
  readonly atualizado = output<DetalheCompetencia>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  // Campos do formulário (ligados por [(ngModel)]) e os PDFs escolhidos
  protected possuiPendencia = false;
  protected pendencia = '';
  protected textoNotificacao = '';
  protected certidao: File | null = null;
  protected email: File | null = null;

  /** Envia a consulta; em seguida, limpa o formulário para uma nova consulta. */
  protected registrar(): void {
    const d = this.detalhe();
    const campos = { possui_pendencia: this.possuiPendencia, certidao: this.certidao, pendencia: this.pendencia.trim(),
                     // O e-mail só vai quando há pendência
                     texto_notificacao: this.textoNotificacao.trim(), email: this.possuiPendencia ? this.email : null };
    this.dialogos.executar(this.api.cadin(d.contrato_id, d.id, campos), 'Registrando a consulta…').subscribe({
      next: (novo) => {
        this.pendencia = this.textoNotificacao = '';
        this.certidao = this.email = null;
        this.atualizado.emit(novo);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível registrar a consulta'),
    });
  }

  /** Baixa a certidão ou o e-mail de uma consulta. */
  protected baixar(anexoId: string): void {
    const d = this.detalhe();
    this.api.baixar(d.contrato_id, d.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
