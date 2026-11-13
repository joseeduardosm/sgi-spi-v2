/**
 * =============================================================================
 * ARQUIVO: historico-campo.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Mostrar, ao lado do rótulo de um campo, um ícone que abre o histórico de
 * alterações daquele campo: quem alterou, quando e de qual valor para qual.
 *
 * RESUMO TÉCNICO:
 * Componente standalone (OnPush) com template embutido. Recebe por input() o
 * nome do campo e a lista completa de alterações do registro; filtra com
 * computed() só as do campo e abre uma pequena janela ao clicar. Fecha ao
 * clicar fora, escutando document:click pelo "host" do componente.
 *
 * FINALIDADE DE NEGÓCIO:
 * Dá transparência e rastreabilidade às mudanças no cadastro do contrato
 * (ex.: vigência, valor, empresa), útil em auditorias e para a equipe de
 * fiscalização entender por que um dado mudou.
 *
 * CONTEXTO NO SISTEMA:
 * Usado nas telas de contratos (detalhe e formulário); o tipo AlteracaoCampo
 * vem de contratos.models.ts e os dados chegam no histórico do contrato da API.
 *
 * =============================================================================
 */

import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, ElementRef, inject, input, signal } from '@angular/core';

import { AlteracaoCampo } from './contratos.models';

/** Ícone ⟲ ao lado do rótulo: mostra "quem alterou, quando, de → para" do campo. */
@Component({
  selector: 'app-historico-campo',
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  // A classe no elemento hospedeiro e o clique fora (para fechar a janela)
  host: { class: 'historico-campo', '(document:click)': 'aoClicarFora($event)' },
  template: `
    @if (registros().length) {
      <button type="button" [attr.aria-label]="'Histórico de ' + rotulo()" [attr.aria-expanded]="aberto()" (click)="aberto.set(!aberto())">⟲</button>
      @if (aberto()) {
        <div class="janela" role="dialog" [attr.aria-label]="'Histórico de ' + rotulo()">
          @for (r of registros(); track $index) {
            <p>
              {{ texto(r.de) }} → <strong>{{ texto(r.para) }}</strong>
              <small>{{ r.autor }} · {{ r.ocorrido_em | date: 'dd/MM/yyyy HH:mm' }}</small>
            </p>
          }
        </div>
      }
    }
  `,
})
export class HistoricoCampoComponent {
  // Nome do campo no histórico, rótulo para acessibilidade e a lista completa vinda do contrato
  // `input.required` obriga o pai a informar o valor (erro de compilação se faltar)
  readonly campo = input.required<string>();
  readonly rotulo = input('campo');
  readonly historico = input<AlteracaoCampo[]>([]);
  /** Tradução opcional de valores (ex.: id da empresa → razão social). */
  readonly traduzir = input<(valor: unknown) => string>();

  /** Janela de histórico aberta ou fechada (signal: ao mudar, o Angular redesenha só o necessário). */
  protected readonly aberto = signal(false);
  // Só as alterações deste campo; o botão nem aparece se não houver nenhuma
  protected readonly registros = computed(() => this.historico().filter((h) => h.campo === this.campo()));
  // Referência ao próprio elemento do componente no DOM, usada para saber se um clique foi dentro ou fora
  private readonly elemento = inject(ElementRef<HTMLElement>);

  /** Texto exibido para um valor antigo ou novo: traduzido, "(vazio)", data dd/mm/aaaa ou o próprio valor. */
  protected texto(valor: unknown): string {
    const traduzido = this.traduzir()?.(valor);
    if (traduzido) return traduzido;
    if (valor === null || valor === undefined || valor === '') return '(vazio)';
    // Datas chegam da API como aaaa-mm-dd; aqui são reordenadas para o padrão brasileiro
    const data = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(valor));
    return data ? `${data[3]}/${data[2]}/${data[1]}` : String(valor);
  }

  /** Fecha a janela ao clicar fora do componente. */
  protected aoClicarFora(evento: Event): void {
    if (this.aberto() && !this.elemento.nativeElement.contains(evento.target as Node)) this.aberto.set(false);
  }
}
