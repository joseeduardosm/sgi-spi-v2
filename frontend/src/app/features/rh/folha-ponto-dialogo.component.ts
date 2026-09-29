// Criado por José Eduardo Santana Martins
// Este arquivo serve para a janela "Folha de ponto": o usuário escolhe a competência e baixa o PDF.

import { Component, inject, model, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { RhApiService } from './rh-api.service';
import { CompetenciaFolha } from './rh.models';

/**
 * Janela aberta pelo menu do usuário (abaixo de "Meu perfil"). Lista os meses disponíveis (12 para trás e 2 para
 * frente, com o atual pré-selecionado) e baixa a folha de ponto em PDF, já com fins de semana, feriados, pontos
 * facultativos e férias/licença-prêmio aprovadas.
 */
@Component({
  selector: 'app-folha-ponto-dialogo',
  imports: [FormsModule],
  host: { '(document:keydown.escape)': 'aberta.set(false)' },
  template: `
    @if (aberta()) {
      <div class="fundo-modal" role="presentation" (click)="aberta.set(false)"></div>
      <section class="modal-portal janela-mensagem" role="dialog" aria-modal="true" aria-labelledby="titulo-folha-ponto">
        <header>
          <div><span class="modal-sobretitulo">Registro de frequência</span><h2 id="titulo-folha-ponto">Folha de ponto</h2></div>
          <button type="button" aria-label="Fechar" (click)="aberta.set(false)">×</button>
        </header>
        <form (ngSubmit)="gerar()">
          <div class="grade-formulario" style="grid-template-columns: 1fr">
            <div>
              <label for="folha-competencia">Competência</label>
              <select id="folha-competencia" name="competencia" [(ngModel)]="competencia" [disabled]="!competencias().length">
                @for (c of competencias(); track c.valor) { <option [value]="c.valor">{{ c.rotulo }}{{ c.atual ? ' (atual)' : '' }}</option> }
              </select>
            </div>
          </div>
          <p class="dica-formulario" style="margin-top: 0">A folha sai com sábados, domingos, feriados, pontos facultativos e as férias ou
            licenças-prêmio aprovadas do mês. Imprima, assine e entregue ao superior imediato.</p>
          <footer>
            <button type="button" class="acao-secundaria" (click)="aberta.set(false)">Cancelar</button>
            <button type="submit" class="acao-primaria" [disabled]="!competencia">Gerar PDF</button>
          </footer>
        </form>
      </section>
    }
  `,
})
export class FolhaPontoDialogoComponent implements OnInit {
  /** Controle de abertura (ligado ao menu do usuário). */
  readonly aberta = model(false);
  private readonly api = inject(RhApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly competencias = signal<CompetenciaFolha[]>([]);
  protected competencia = '';

  ngOnInit(): void {
    this.api.competenciasFolha().subscribe({
      next: (lista) => {
        this.competencias.set(lista);
        this.competencia = lista.find((c) => c.atual)?.valor ?? lista[0]?.valor ?? '';
      },
      error: () => undefined,
    });
  }

  protected gerar(): void {
    if (!this.competencia) return;
    this.dialogos.executar(this.api.folhaPonto(this.competencia), 'Gerando a folha de ponto…').subscribe({
      next: () => this.aberta.set(false),
      error: (e) => {
        // Dados funcionais incompletos ou cadastro aguardando validação: aviso (a CGP já foi avisada por e-mail)
        const corpo = (e as { error?: { codigo?: string; detalhe?: string } })?.error;
        if (corpo?.codigo === 'folha_dados_incompletos' || corpo?.codigo === 'folha_cadastro_pendente') {
          this.aberta.set(false);
          this.dialogos.avisar('Folha de ponto indisponível', corpo.detalhe ?? '');
          return;
        }
        this.dialogos.mostrarErro(e, 'Não foi possível gerar a folha de ponto');
      },
    });
  }
}
