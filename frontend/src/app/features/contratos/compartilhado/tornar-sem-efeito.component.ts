/**
 * =============================================================================
 * ARQUIVO: tornar-sem-efeito.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Botão "Tornar sem efeito" de um evento concluído do contrato (reajuste,
 * repactuação, aditamento/supressão, prorrogação, vigência retroativa), com o
 * motivo do bloqueio quando não pode e a janela que pede o motivo.
 *
 * RESUMO TÉCNICO:
 * Componente standalone (OnPush). Recebe por input() o contrato, o tipo e o id
 * do registro, se pode e o motivo do bloqueio. Abre um modal (.modal-portal,
 * animate.leave de _movimento.scss) com um textarea de motivo (mínimo de 10
 * caracteres); ao confirmar, chama AlteracoesApiService.tornarSemEfeito e
 * emite `concluido` para a tela recarregar.
 *
 * FINALIDADE DE NEGÓCIO:
 * Decisão do usuário (13/11/2026): a equipe pode tornar sem efeito um evento
 * concluído, desde que nada dependa dele, sempre informando o motivo, que fica
 * no histórico e na auditoria.
 *
 * CONTEXTO NO SISTEMA:
 * Usado no histórico das telas de reajuste, repactuação e aditamento/supressão,
 * no cartão de prorrogações do contrato, na tela de prorrogação (vigência
 * retroativa) e na aba Eventos.
 *
 * =============================================================================
 */

import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { AlteracoesApiService } from './alteracoes-api.service';
import { TipoEventoSemEfeito } from './contratos.models';

/** Tamanho mínimo do motivo (o mesmo da API). */
const MOTIVO_MINIMO = 10;

/**
 * Recursos do Angular usados aqui: `input()` declara uma entrada vinda do componente pai (lida como função, ex.: `pode()`);
 * `output()` declara um evento que o pai escuta; `signal()` guarda um estado que, ao mudar, atualiza a tela.
 */
@Component({
  selector: 'app-tornar-sem-efeito',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="tornar-sem-efeito">
      <button type="button" class="acao-perigo" [class.acao-pequena]="pequeno()" [disabled]="!pode()" [title]="pode() ? '' : motivoBloqueio()"
              (click)="abrir()">Tornar sem efeito</button>
      @if (!pode() && motivoBloqueio()) { <small class="dica-formulario">{{ motivoBloqueio() }}</small> }
    </span>
    @if (aberto()) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="fechar()"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" [attr.aria-labelledby]="idTitulo">
        <header>
          <div><span class="modal-sobretitulo">Tornar sem efeito</span><h2 [id]="idTitulo">{{ titulo() }}</h2></div>
          <button type="button" aria-label="Fechar" (click)="fechar()">×</button>
        </header>
        <form (ngSubmit)="confirmar()">
          <p class="aviso-bloco erro">O que este evento aplicou ao contrato será desfeito. Ele continua no histórico com o selo "Sem efeito", com o seu nome, a data e o motivo.</p>
          <div class="grade-formulario">
            <div class="ocupa-duas">
              <label [for]="idTitulo + '-motivo'">Motivo *</label>
              <textarea [id]="idTitulo + '-motivo'" name="motivo" rows="4" maxlength="4000" required [(ngModel)]="motivo"></textarea>
              <small class="dica-formulario">Pelo menos {{ minimo }} caracteres. Fica no histórico e na auditoria.</small>
            </div>
          </div>
          <footer>
            <button type="button" class="acao-secundaria" (click)="fechar()">Cancelar</button>
            <button type="submit" class="acao-perigo" [class.carregando]="enviando()" [disabled]="motivo.trim().length < minimo || enviando()">Tornar sem efeito</button>
          </footer>
        </form>
      </section>
    }
  `,
  styles: [`
    .tornar-sem-efeito { display: inline-flex; flex-direction: column; align-items: flex-start; gap: var(--spi-espaco-4); }
  `],
})
export class TornarSemEfeitoComponent {
  private static sequencia = 0;
  private readonly api = inject(AlteracoesApiService);
  private readonly dialogos = inject(DialogosService);

  readonly contratoId = input.required<string>();
  readonly tipo = input.required<TipoEventoSemEfeito>();
  readonly registroId = input.required<string>();
  /** Título da janela (ex.: "Tornar o reajuste de 01/2026 sem efeito?"). */
  readonly titulo = input('Tornar este evento sem efeito?');
  /** Se o botão fica ativo (a API já conferiu permissão e dependências). */
  readonly pode = input(false);
  /** Por que não pode (aparece embaixo do botão desativado). */
  readonly motivoBloqueio = input('');
  /** Botão pequeno (em tabelas e listas). */
  readonly pequeno = input(true);
  /** Emitido depois de tornar sem efeito, para a tela recarregar os dados. */
  readonly concluido = output<void>();

  protected readonly idTitulo = `sem-efeito-${++TornarSemEfeitoComponent.sequencia}`;
  protected readonly minimo = MOTIVO_MINIMO;
  protected readonly aberto = signal(false);
  protected readonly enviando = signal(false);
  protected motivo = '';

  protected abrir(): void {
    this.motivo = '';
    this.aberto.set(true);
  }

  protected fechar(): void {
    if (!this.enviando()) this.aberto.set(false);
  }

  /** Envia o motivo; dá certo → fecha e avisa o pai; dá erro (ex.: bloqueio novo) → mostra a mensagem da API. */
  protected confirmar(): void {
    if (this.motivo.trim().length < MOTIVO_MINIMO) return;
    this.enviando.set(true);
    this.api.tornarSemEfeito(this.contratoId(), this.tipo(), this.registroId(), this.motivo.trim()).subscribe({
      next: () => { this.enviando.set(false); this.aberto.set(false); this.concluido.emit(); },
      error: (e) => { this.enviando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível tornar o evento sem efeito'); },
    });
  }
}
