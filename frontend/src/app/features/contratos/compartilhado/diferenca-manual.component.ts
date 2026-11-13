/**
 * =============================================================================
 * ARQUIVO: diferenca-manual.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Registrar a diferença retroativa do cálculo manual, mês a mês, no reajuste e
 * na repactuação de contratos.
 *
 * RESUMO TÉCNICO:
 * Componente standalone (OnPush) com template embutido. Recebe por input() os
 * meses que podem ser informados (da data de efeito até o mês em andamento) e a
 * diferença já gravada; guarda em signal() o valor digitado em cada mês, a
 * justificativa e o PDF; soma o total na tela e emite os outputs salvar,
 * remover e baixar. Não chama a API diretamente.
 *
 * FINALIDADE DE NEGÓCIO:
 * Quando o gestor escolhe o cálculo manual, o sistema não calcula nada sozinho
 * (nem a diferença dos meses medidos no SGI): vale só a diferença informada em
 * cada mês (negativa = crédito da SPI), com justificativa e a memória feita
 * fora do sistema, garantindo rastreabilidade do valor.
 *
 * CONTEXTO NO SISTEMA:
 * Usado pelas telas de reajuste e de repactuação (passo da memória de cálculo,
 * depois da pergunta "Cálculo manual ou automático?"), que fazem a chamada à
 * API. Tipos em contratos.models.ts; conversão de números em rotulos.ts; envio
 * do arquivo pelo componente compartilhado app-envio-pdf.
 *
 * =============================================================================
 */

import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { DiferencaManual, GravacaoDiferencaManual, MesSemMedicao } from './contratos.models';
import { paraDecimalApi, paraDecimalTela } from './rotulos';

/**
 * Valor em reais aceito: com sinal, até 2 casas (vírgula ou ponto).
 * A expressão é testada já convertida para o formato da API (ponto decimal).
 */
const VALOR = /^-?\d+(\.\d{1,2})?$/;

/**
 * Diferença retroativa do cálculo manual (reajuste e repactuação), informada mês a mês.
 *
 * A tela pai já perguntou "Cálculo manual ou automático?" e só mostra este componente no manual. Aqui o gestor vê os meses da
 * data de efeito até o mês em andamento (com o selo "Medido no SGI" ou "Em andamento"), digita a diferença dos meses que quiser
 * (mês em branco = sem diferença), e a tela soma o total. Justificativa e PDF são obrigatórios.
 *
 * Recursos do Angular usados aqui: `input()` declara uma entrada vinda do componente pai (lida como função,
 * ex.: `meses()`); `output()` declara um evento que o pai escuta; `signal()` guarda um estado que, ao mudar,
 * atualiza a tela; `computed()` é um valor derivado de outros signals, recalculado sozinho.
 */
@Component({
  selector: 'app-diferenca-manual',
  imports: [FormsModule, EnvioPdfComponent, ...PIPES_FORMATACAO],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @let atual = diferenca();
    @if (atual && !editando()) {
      <!-- Já informada: o resumo mês a mês com a observação que sai nos documentos -->
      <p class="secao-formulario">Diferença informada mês a mês <span class="selo-situacao">Valor manual</span></p>
      <div class="tabela-gestao-envoltorio">
        <table class="tabela-gestao">
          <thead><tr><th scope="col">Mês</th><th scope="col">Situação no SGI</th><th scope="col" class="num">Diferença</th></tr></thead>
          <tbody>
            @for (m of atual.meses; track m.competencia_id) {
              <tr>
                <td class="texto-codigo">{{ m.rotulo }}</td>
                <td><span class="selo-situacao" [class.info]="m.medida" [class.alerta]="m.em_andamento" [class.inativo]="!m.medida && !m.em_andamento">{{ situacao(m) }}</span></td>
                <td class="num">{{ m.valor !== null && m.valor !== undefined ? (m.valor | moeda) : '—' }}</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <dl class="resumo-reajuste">
        <div><dt>Total informado</dt><dd><strong>{{ atual.valor | moeda }}</strong> <small class="dica-formulario">{{ +atual.valor < 0 ? '(crédito da SPI, vai para o fundo do contrato)' : '(competência complementar a pagar)' }}</small></dd></div>
      </dl>
      <p class="aviso-bloco informativo">{{ atual.observacao }}</p>
      <div class="acoes-cartao esquerda">
        <button type="button" class="acao-secundaria acao-pequena" [title]="atual.arquivo.nome" (click)="baixar.emit(atual.arquivo.anexo_id)">Baixar memória externa</button>
        @if (podeEditar()) {
          <button type="button" class="acao-secundaria acao-pequena" (click)="editar(atual)">Alterar</button>
          <button type="button" class="acao-perigo acao-pequena" [class.carregando]="ocupado()" [disabled]="ocupado()" (click)="remover.emit()">Remover diferença manual</button>
        }
      </div>
    } @else if (podeEditar() && meses().length) {
      <!-- Formulário: a diferença de cada mês, o total, a justificativa e o PDF -->
      <p class="secao-formulario">Diferença mês a mês</p>
      <p class="dica-formulario">Informe a diferença de cada mês (deixe em branco o mês sem diferença; negativo = crédito da SPI). Os meses informados ficam
        no preço de antes, inclusive o mês em andamento.</p>
      <div class="tabela-gestao-envoltorio">
        <table class="tabela-gestao">
          <thead><tr><th scope="col">Mês</th><th scope="col">Situação no SGI</th><th scope="col" class="num">Diferença (R$)</th></tr></thead>
          <tbody>
            @for (m of meses(); track m.competencia_id) {
              <tr>
                <td class="texto-codigo">{{ m.rotulo }}
                  @if (m.coberta_por_outra) { <small class="dica-formulario">(já tem diferença manual de outro procedimento)</small> }</td>
                <td><span class="selo-situacao" [class.info]="m.medida" [class.alerta]="m.em_andamento" [class.inativo]="!m.medida && !m.em_andamento">{{ situacao(m) }}</span></td>
                <td class="num">
                  <input type="text" inputmode="decimal" [attr.aria-label]="'Diferença de ' + m.rotulo" [ngModel]="valores()[m.competencia_id] ?? ''"
                         (ngModelChange)="digitar(m.competencia_id, $event)" [attr.aria-invalid]="!valorValido(valores()[m.competencia_id])" />
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <dl class="resumo-reajuste">
        <div><dt>Total ({{ preenchidos().length }} {{ preenchidos().length === 1 ? 'mês' : 'meses' }})</dt><dd><strong>{{ total() | moeda }}</strong>
          <small class="dica-formulario">{{ total() < 0 ? '(crédito da SPI, vai para o fundo do contrato)' : total() > 0 ? '(competência complementar a pagar)' : '' }}</small></dd></div>
      </dl>
      <div class="grade-formulario">
        <div>
          <span class="rotulo-campo">Memória feita fora do sistema (PDF) *</span>
          <app-envio-pdf rotulo="Selecionar PDF" (selecionado)="arquivo.set($event)" />
          @if (atual && !arquivo()) { <small class="dica-formulario">Ao alterar, envie o PDF de novo.</small> }
        </div>
        <div class="ocupa-duas">
          <label for="diferenca-manual-justificativa">Justificativa *</label>
          <textarea id="diferenca-manual-justificativa" rows="3" maxlength="4000" [(ngModel)]="justificativa"></textarea>
        </div>
      </div>
      <div class="acoes-cartao esquerda">
        <button type="button" class="acao-primaria" [class.carregando]="ocupado()" [disabled]="!pronto() || ocupado()" (click)="enviar()">Salvar diferença mês a mês</button>
        @if (atual) { <button type="button" class="acao-secundaria" (click)="editando.set(false)">Cancelar</button> }
      </div>
    } @else if (!atual) {
      <p class="dica-formulario">Não há meses da data de efeito até hoje para informar.</p>
    }
  `,
})
export class DiferencaManualComponent {
  /** Meses que podem ser informados (da data de efeito até o mês em andamento), vindos da API. */
  // `transform`: aceita a resposta de uma API ainda sem esses campos (vazio/nulo), sem quebrar a tela
  readonly meses = input<MesSemMedicao[], MesSemMedicao[] | null | undefined>([], { transform: (v) => v ?? [] });
  /** Diferença já informada, se houver. */
  readonly diferenca = input<DiferencaManual | null, DiferencaManual | null | undefined>(null, { transform: (v) => v ?? null });
  /** Se o usuário pode alterar (permissão calculada pela tela pai); sem ela, só a leitura aparece. */
  readonly podeEditar = input(false);
  /** Chamada em andamento (o pai liga e desliga). */
  readonly ocupado = input(false);
  /** Emitido com os dados validados (meses e valores no formato da API, justificativa e PDF). */
  readonly salvar = output<GravacaoDiferencaManual>();
  /** Emitido quando o usuário pede para apagar a diferença manual já gravada. */
  readonly remover = output<void>();
  /** Emitido com o id do anexo da memória externa, para o pai fazer o download. */
  readonly baixar = output<string>();

  // Edição de uma diferença já gravada (sem gravada, o formulário aparece direto)
  protected readonly editando = signal(false);
  // Valor digitado em cada mês: { id da competência: texto como o usuário digitou }
  protected readonly valores = signal<Record<string, string>>({});
  protected justificativa = '';
  protected readonly arquivo = signal<File | null>(null);

  /** Meses com valor digitado (em branco = sem diferença naquele mês), na ordem da lista. */
  protected readonly preenchidos = computed(() =>
    this.meses().filter((m) => (this.valores()[m.competencia_id] ?? '').trim() !== ''),
  );

  /** Soma dos valores válidos digitados (o texto inválido não entra na soma). */
  protected readonly total = computed(() =>
    this.preenchidos().reduce((soma, m) => {
      const texto = paraDecimalApi((this.valores()[m.competencia_id] ?? '').trim());
      return VALOR.test(texto) ? soma + Number(texto) : soma;
    }, 0),
  );

  /** Texto do selo de situação do mês no SGI. */
  protected situacao(m: MesSemMedicao): string {
    if (m.medida) return 'Medido no SGI';
    if (m.em_andamento) return 'Em andamento';
    return 'Sem medição no SGI';
  }

  /**
   * Guarda o valor digitado num mês. Cria um objeto novo (em vez de alterar o atual) para o signal perceber a mudança.
   * @param id Id da competência (mês).
   * @param texto Texto digitado.
   */
  protected digitar(id: string, texto: string): void {
    this.valores.update((atual) => ({ ...atual, [id]: texto }));
  }

  /** Campo vazio (mês sem diferença) ou número diferente de zero. */
  protected valorValido(texto: string | undefined): boolean {
    const limpo = (texto ?? '').trim();
    if (!limpo) return true;
    // Converte "1.234,56" (tela) para "1234.56" (API) antes de validar; zero não faz sentido como diferença
    const api = paraDecimalApi(limpo);
    return VALOR.test(api) && Number(api) !== 0;
  }

  /** Formulário completo: ao menos um mês, todos os valores válidos, total diferente de zero, justificativa e PDF. */
  protected pronto(): boolean {
    const meses = this.preenchidos();
    return meses.length > 0 && meses.every((m) => this.valorValido(this.valores()[m.competencia_id]))
      && Math.round(this.total() * 100) !== 0 && !!this.justificativa.trim() && !!this.arquivo();
  }

  /** Abre o formulário com o que já está gravado (o PDF precisa ser enviado de novo). */
  protected editar(atual: DiferencaManual): void {
    this.valores.set(Object.fromEntries(atual.meses.filter((m) => m.valor !== null && m.valor !== undefined)
      .map((m) => [m.competencia_id, paraDecimalTela(String(m.valor))])));
    this.justificativa = atual.justificativa;
    this.arquivo.set(null);
    this.editando.set(true);
  }

  /**
   * Emite `salvar` com os dados prontos para a API. A gravação em si é feita pelo componente pai;
   * aqui só se fecha o modo de edição.
   */
  protected enviar(): void {
    const arquivo = this.arquivo();
    if (!this.pronto() || !arquivo) return;
    const meses = this.preenchidos();
    this.salvar.emit({
      competencias_ids: meses.map((m) => m.competencia_id),
      valores: meses.map((m) => paraDecimalApi((this.valores()[m.competencia_id] ?? '').trim())),
      justificativa: this.justificativa.trim(),
      arquivo,
    });
    this.editando.set(false);
  }
}
