import { Pipe, PipeTransform } from '@angular/core';

import { formatarCompetencia, formatarData, formatarMoeda, formatarPercentual, formatarQuantidade, formatarTamanho } from './formatadores';

/** Pipes de formatação brasileira para os templates (valores da API chegam como texto). */

@Pipe({ name: 'moeda' })
export class MoedaPipe implements PipeTransform {
  transform(valor: string | number | null | undefined, vazio = 'R$ -'): string {
    return formatarMoeda(valor, vazio);
  }
}

@Pipe({ name: 'quantidade' })
export class QuantidadePipe implements PipeTransform {
  transform(valor: string | number | null | undefined): string {
    return formatarQuantidade(valor);
  }
}

@Pipe({ name: 'percentual' })
export class PercentualPipe implements PipeTransform {
  transform(valor: string | number | null | undefined): string {
    return formatarPercentual(valor);
  }
}

@Pipe({ name: 'dataBr' })
export class DataBrPipe implements PipeTransform {
  transform(valor: string | null | undefined): string {
    return formatarData(valor);
  }
}

@Pipe({ name: 'competencia' })
export class CompetenciaPipe implements PipeTransform {
  transform(valor: string | null | undefined): string {
    return formatarCompetencia(valor);
  }
}

@Pipe({ name: 'tamanho' })
export class TamanhoPipe implements PipeTransform {
  transform(valor: number | null | undefined): string {
    return formatarTamanho(valor);
  }
}

export const PIPES_FORMATACAO = [MoedaPipe, QuantidadePipe, PercentualPipe, DataBrPipe, CompetenciaPipe, TamanhoPipe] as const;
