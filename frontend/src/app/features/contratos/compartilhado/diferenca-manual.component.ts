/**
 * =============================================================================
 * ARQUIVO: diferenca-manual.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Perguntar e registrar a diferença retroativa informada manualmente, isto é,
 * o valor de meses que foram pagos fora do sistema, no reajuste e na
 * repactuação de contratos.
 *
 * RESUMO TÉCNICO:
 * Componente standalone (OnPush) com template embutido. Recebe por input() os
 * meses sem medição e a diferença já gravada; guarda em signal() a resposta à
 * pergunta e os campos do formulário; valida valor, justificativa e PDF e
 * emite os outputs salvar, remover e baixar. Não chama a API diretamente.
 *
 * FINALIDADE DE NEGÓCIO:
 * O cálculo automático só considera meses com medição concluída no SGI. Para
 * meses pagos antes da implantação ou fora do sistema, o gestor informa o
 * valor total da diferença (negativo = crédito da SPI), justifica e anexa a
 * memória de cálculo, garantindo rastreabilidade do valor.
 *
 * CONTEXTO NO SISTEMA:
 * Usado pelas telas de reajuste e de repactuação, que fazem a chamada à API.
 * Tipos em contratos.models.ts; conversão de números em rotulos.ts; envio do
 * arquivo pelo componente compartilhado app-envio-pdf.
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
 * Diferença retroativa informada manualmente (reajuste e repactuação).
 *
 * O cálculo automático só enxerga meses com medição concluída no SGI. Quando há meses encerrados sem medição (pagos fora do
 * sistema), a tela pergunta: "Identifiquei que X meses do período de … a … não possuem medições finalizadas. Deseja inserir o
 * valor da diferença manualmente?". No "Sim", o gestor marca os meses, informa o valor total (negativo = crédito da SPI), a
 * justificativa e o PDF da memória feita fora do sistema. Quem usa o componente faz a chamada à API (`salvar`/`remover`).
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
    @if (atual) {
      <!-- Já informada: o resumo com a observação que sai nos documentos -->
      <p class="secao-formulario">Diferença informada manualmente <span class="selo-situacao">Valor manual</span></p>
      <dl class="resumo-reajuste">
        <div><dt>Meses pagos fora do sistema</dt><dd class="texto-codigo">{{ rotulos(atual.meses) }}</dd></div>
        <div><dt>Valor informado</dt><dd>{{ atual.valor | moeda }} <small class="dica-formulario">{{ +atual.valor < 0 ? '(crédito da SPI, vai para o fundo do contrato)' : '(competência complementar a pagar)' }}</small></dd></div>
      </dl>
      <p class="aviso-bloco informativo">{{ atual.observacao }}</p>
      <div class="acoes-cartao esquerda">
        <button type="button" class="acao-secundaria acao-pequena" [title]="atual.arquivo.nome" (click)="baixar.emit(atual.arquivo.anexo_id)">Baixar memória externa</button>
        @if (podeEditar()) {
          <button type="button" class="acao-secundaria acao-pequena" (click)="editar(atual)">Alterar</button>
          <button type="button" class="acao-perigo acao-pequena" [class.carregando]="ocupado()" [disabled]="ocupado()" (click)="remover.emit()">Remover diferença manual</button>
        }
      </div>
    }
    @if (meses().length && podeEditar() && (!atual || editando())) {
      @if (!atual && resposta() === null) {
        <!-- A pergunta, com Sim (verde) e Não (vermelho) separados -->
        <p class="aviso-bloco informativo">
          Identifiquei que {{ meses().length }} {{ meses().length === 1 ? 'mês' : 'meses' }} do período de
          <span class="texto-codigo">{{ meses()[0].periodo_inicio | dataBr }}</span> a <span class="texto-codigo">{{ meses()[meses().length - 1].periodo_fim | dataBr }}</span>
          {{ meses().length === 1 ? 'não possui medição finalizada' : 'não possuem medições finalizadas' }}. Deseja inserir o valor da diferença manualmente?
        </p>
        <div class="acoes-cartao esquerda">
          <button type="button" class="acao-positiva" (click)="resposta.set(true)">Sim, inserir manualmente</button>
          <button type="button" class="acao-recusar" (click)="resposta.set(false)">Não</button>
        </div>
      } @else if (!atual && resposta() === false) {
        <p class="dica-formulario">
          Sem diferença manual: {{ meses().length === 1 ? 'o mês sem medição recebe' : 'os meses sem medição recebem' }} o preço novo e
          {{ meses().length === 1 ? 'entra' : 'entram' }} na medição normalmente.
          @if (podeEditar()) { <button type="button" class="acao-secundaria acao-pequena" (click)="resposta.set(null)">Rever</button> }
        </p>
      } @else {
        <!-- Formulário: meses pagos fora do sistema, valor total, justificativa e PDF -->
        <p class="secao-formulario">Diferença informada manualmente</p>
        <p class="dica-formulario">Marque os meses pagos fora do sistema. Eles ficam no preço de antes (o que foi pago de fato) e saem do cálculo automático.</p>
        <div class="linha-caixas">
          @for (m of meses(); track m.competencia_id) {
            <label>
              <input type="checkbox" [checked]="marcados()[m.competencia_id]" (change)="marcar(m.competencia_id, $any($event.target).checked)" />
              <span class="texto-codigo">{{ m.rotulo }}</span>
              @if (m.coberta_por_outra) { <small class="dica-formulario">(já tem diferença manual de outro procedimento)</small> }
            </label>
          }
        </div>
        <div class="grade-formulario">
          <div>
            <label for="diferenca-manual-valor">Valor total da diferença (R$) *</label>
            <input id="diferenca-manual-valor" type="text" inputmode="decimal" [(ngModel)]="valor" [attr.aria-invalid]="valor && !valorValido()" />
            <small class="dica-formulario">Negativo = crédito da SPI (vai para o fundo do contrato).</small>
          </div>
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
          <button type="button" class="acao-primaria" [class.carregando]="ocupado()" [disabled]="!pronto() || ocupado()" (click)="enviar()">Salvar diferença manual</button>
          <button type="button" class="acao-secundaria" (click)="cancelarEdicao()">Cancelar</button>
        </div>
      }
    }
  `,
})
export class DiferencaManualComponent {
  /** Meses encerrados sem medição concluída (candidatos), vindos da API. */
  // `transform`: aceita a resposta de uma API ainda sem esses campos (vazio/nulo), sem quebrar a tela
  readonly meses = input<MesSemMedicao[], MesSemMedicao[] | null | undefined>([], { transform: (v) => v ?? [] });
  /** Diferença já informada, se houver. */
  readonly diferenca = input<DiferencaManual | null, DiferencaManual | null | undefined>(null, { transform: (v) => v ?? null });
  /** Se o usuário pode alterar (permissão calculada pela tela pai); sem ela, só a leitura aparece. */
  readonly podeEditar = input(false);
  /** Chamada em andamento (o pai liga e desliga). */
  readonly ocupado = input(false);
  /** Emitido com os dados validados (valor no formato da API, meses marcados, justificativa e PDF). */
  readonly salvar = output<GravacaoDiferencaManual>();
  /** Emitido quando o usuário pede para apagar a diferença manual já gravada. */
  readonly remover = output<void>();
  /** Emitido com o id do anexo da memória externa, para o pai fazer o download. */
  readonly baixar = output<string>();

  // Resposta à pergunta (null = ainda não respondeu) e edição de uma diferença já gravada
  protected readonly resposta = signal<boolean | null>(null);
  protected readonly editando = signal(false);
  // Campos do formulário
  protected readonly marcados = signal<Record<string, boolean>>({});
  protected valor = '';
  protected justificativa = '';
  protected readonly arquivo = signal<File | null>(null);

  /** Quantos meses estão marcados; o formulário só libera o salvar com pelo menos um. */
  protected readonly quantidadeMarcada = computed(() => Object.values(this.marcados()).filter(Boolean).length);

  /** Junta os rótulos dos meses (ex.: "01/2026, 02/2026") para o resumo. */
  protected rotulos(meses: MesSemMedicao[]): string {
    return meses.map((m) => m.rotulo).join(', ');
  }

  /**
   * Marca ou desmarca um mês. Cria um objeto novo (em vez de alterar o atual) para o signal perceber a mudança.
   * @param id Id da competência (mês) clicada.
   * @param marcado Estado novo da caixa.
   */
  protected marcar(id: string, marcado: boolean): void {
    this.marcados.update((atual) => ({ ...atual, [id]: marcado }));
  }

  /** Valor preenchido, numérico e diferente de zero. */
  protected valorValido(): boolean {
    // Converte "1.234,56" (tela) para "1234.56" (API) antes de validar; zero não faz sentido como diferença
    const texto = paraDecimalApi(this.valor.trim());
    return VALOR.test(texto) && Number(texto) !== 0;
  }

  /** Formulário completo: ao menos um mês, valor válido, justificativa e PDF (todos obrigatórios). */
  protected pronto(): boolean {
    return this.quantidadeMarcada() > 0 && this.valorValido() && !!this.justificativa.trim() && !!this.arquivo();
  }

  /** Abre o formulário com o que já está gravado (o PDF precisa ser enviado de novo). */
  protected editar(atual: DiferencaManual): void {
    this.marcados.set(Object.fromEntries(atual.meses.map((m) => [m.competencia_id, true])));
    this.valor = paraDecimalTela(atual.valor);
    this.justificativa = atual.justificativa;
    this.arquivo.set(null);
    this.editando.set(true);
  }

  /** Fecha o formulário e volta à pergunta inicial (ou ao resumo, se já houver diferença gravada). */
  protected cancelarEdicao(): void {
    this.editando.set(false);
    this.resposta.set(null);
  }

  /**
   * Emite `salvar` com os dados prontos para a API. A gravação em si é feita pelo componente pai;
   * aqui só se fecha o modo de edição.
   */
  protected enviar(): void {
    const arquivo = this.arquivo();
    if (!this.pronto() || !arquivo) return;
    this.salvar.emit({
      valor: paraDecimalApi(this.valor.trim()),
      competencias_ids: this.meses().filter((m) => this.marcados()[m.competencia_id]).map((m) => m.competencia_id),
      justificativa: this.justificativa.trim(),
      arquivo,
    });
    this.editando.set(false);
  }
}
