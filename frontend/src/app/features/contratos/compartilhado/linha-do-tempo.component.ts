// Criado por José Eduardo Santana Martins
// Este arquivo serve para desenhar a linha do tempo do contrato (vigências, termos aditivos, reajustes, hoje e máximo).

import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { formatarData } from '../../../shared/utilitarios/formatadores';
import { Marco } from './contratos.models';

/** Marco com a posição calculada no trilho (0 a 100%) e o lugar do rótulo. */
interface MarcoPosicionado extends Marco {
  posicao: number;
  acima: boolean;
  /** Faixa do rótulo (0 = junto ao trilho); rótulos próximos vão para faixas mais afastadas. */
  nivel: number;
}

/** Largura aproximada de um rótulo, em % do trilho: dois marcos mais próximos que isso não dividem a faixa. */
const LARGURA_ROTULO = 10;
// Altura, em pixels, de cada faixa de rótulos
const ALTURA_FAIXA = 30;

/** Linha do tempo da vigência: um traço por mês e os marcos (início, TAs, reajustes, hoje, máximo). */
@Component({
  selector: 'app-linha-do-tempo',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="linha-tempo" role="img" [attr.aria-label]="descricao()"
         [style.padding-top.px]="24 + faixas().acima * ALTURA_FAIXA" [style.padding-bottom.px]="30 + faixas().abaixo * ALTURA_FAIXA">
      <div class="trilho">
        <div class="decorrido" [style.width.%]="posicao(hoje())"></div>
        @for (m of meses(); track m) { <span class="mes" [style.left.%]="m"></span> }
        @for (m of marcosPosicionados(); track $index) {
          <div [class]="'marco ' + m.tipo + (m.acima ? ' acima' : ' abaixo')" [style.left.%]="m.posicao">
            <i></i><span [style.bottom.px]="m.acima ? 18 + m.nivel * ALTURA_FAIXA : null" [style.top.px]="m.acima ? null : 18 + m.nivel * ALTURA_FAIXA">{{ m.rotulo }}<br />{{ data(m.data) }}</span>
          </div>
        }
      </div>
    </div>
  `,
})
export class LinhaDoTempoComponent {
  // Marcos vindos do contrato e a data de hoje (para a parte já decorrida)
  readonly marcos = input.required<Marco[]>();
  readonly hoje = input.required<string>();

  // Primeira e última data da linha, em milissegundos (as posições são relativas a elas)
  private readonly limites = computed(() => {
    const datas = this.marcos().map((m) => this.dia(m.data));
    return { inicio: Math.min(...datas), fim: Math.max(...datas) };
  });

  // Posição de cada virada de mês, para desenhar os traços do trilho
  protected readonly meses = computed(() => {
    const { inicio, fim } = this.limites();
    const posicoes: number[] = [];
    const cursor = new Date(inicio);
    cursor.setUTCDate(1);
    while (cursor.getTime() <= fim) {
      cursor.setUTCMonth(cursor.getUTCMonth() + 1);
      if (cursor.getTime() < fim) posicoes.push(this.posicao(cursor.toISOString().slice(0, 10)));
    }
    return posicoes;
  });

  protected readonly marcosPosicionados = computed<MarcoPosicionado[]>(() => {
    // Acrescenta o marco "Hoje" e descarta os que caem fora da linha
    const todos = [...this.marcos(), { data: this.hoje(), tipo: 'hoje', rotulo: 'Hoje' } as unknown as Marco];
    const ordenados = todos
      .map((m) => ({ ...m, posicao: this.posicao(m.data) }))
      .filter((m) => m.posicao >= 0 && m.posicao <= 100)
      .sort((a, b) => a.posicao - b.posicao);
    // Cada rótulo ocupa a primeira faixa livre, alternando abaixo/acima do trilho e afastando-se dele
    const fimDasFaixas: Record<string, number> = {};
    return ordenados.map((m) => {
      for (let nivel = 0; ; nivel++) {
        for (const acima of [false, true]) {
          const chave = `${acima}-${nivel}`;
          if ((fimDasFaixas[chave] ?? -Infinity) <= m.posicao - LARGURA_ROTULO) {
            fimDasFaixas[chave] = m.posicao;
            return { ...m, acima, nivel };
          }
        }
      }
    });
  });

  /** Quantas faixas extras há acima e abaixo do trilho (define a altura do componente). */
  protected readonly faixas = computed(() => {
    const niveis = (acima: boolean) => Math.max(0, ...this.marcosPosicionados().filter((m) => m.acima === acima).map((m) => m.nivel + 1));
    return { acima: niveis(true), abaixo: niveis(false) };
  });

  // Constante exposta ao template
  protected readonly ALTURA_FAIXA = ALTURA_FAIXA;

  // Texto alternativo para leitores de tela, com todos os marcos e datas
  protected readonly descricao = computed(() => this.marcos().map((m) => `${m.rotulo}: ${formatarData(m.data)}`).join('; '));
  protected readonly data = formatarData;

  /** Data (AAAA-MM-DD) em milissegundos, sempre em UTC para não sofrer com fuso. */
  private dia(texto: string): number {
    return Date.parse(`${texto}T00:00:00Z`);
  }

  /** Posição da data no trilho, em % com uma casa decimal. */
  protected posicao(texto: string): number {
    const { inicio, fim } = this.limites();
    return fim === inicio ? 0 : Math.round(((this.dia(texto) - inicio) / (fim - inicio)) * 1000) / 10;
  }
}
