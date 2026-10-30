// Criado por José Eduardo Santana Martins
// Este arquivo serve para entregar às telas de contratos os parâmetros do módulo (prazos, cortes e limites), lidos uma vez da API.

import { inject, Injectable, signal } from '@angular/core';

import { ContratosApiService } from './contratos-api.service';
import { ParametrosContratos, ValoresParametrosContratos } from './contratos.models';

/** Valores de fábrica: valem até a leitura chegar (e se ela falhar), os mesmos que a API devolve em `padroes`. */
export const PARAMETROS_DE_FABRICA: ValoresParametrosContratos = {
  corte_alertas_a_partir_de: '2026-09-01',
  corte_marcadores_a_partir_de: '2026-08-01',
  dias_pagamento_vencendo: 5,
  dias_atraso: 30,
  dias_vigencia_a_vencer: 90,
  dias_vigencia_atencao: 180,
  dias_sem_prorrogacao_alto: 60,
  dias_documento_alto: 15,
  dias_documento_medio: 30,
  dias_fim_vigencia_alto: 30,
  dias_fim_vigencia_medio: 60,
  vigencia_maxima_padrao_meses: 60,
  maximo_meses_vigencia_retroativa: 120,
  limite_aditamento_sem_autorizacao: 25,
  limite_acerto_centavos: 1,
  maximo_notas_fiscais: 20,
  prazo_pagamento_padrao_dias: 30,
  prazo_nota_fiscal_horas: 48,
  xml_tamanho_maximo_mb: 5,
  planilha_tamanho_maximo_mb: 5,
  maximo_anexos_ocorrencia: 5,
  anexos_email_maximo_mb: 15,
  ssgc_nome: 'Laercio Paulino Simões',
  ssgc_cpf: '822.684.878-49',
  secretario_nome: 'Rafael Antonio Cren Benini',
  secretario_cpf: '223.011.918-42',
  autoridade_competente_nome: 'Laercio Paulino Simões',
  autoridade_competente_cargo: 'Subsecretário de Gestão Corporativa',
  pncp_dias_uteis_licitacao: 20,
  pncp_dias_uteis_direta: 10,
  aviso_pncp_dias_uteis: 5,
  parecer_referencial_validade_dias: 365,
  parecer_referencial_vigencia_ate: '2027-02-09',
};

/** Parâmetros de Contratos para as telas: `valores()` é um signal, então quem o lê se atualiza quando a leitura chega. */
@Injectable({ providedIn: 'root' })
export class ParametrosContratosService {
  private readonly api = inject(ContratosApiService);
  readonly valores = signal<ValoresParametrosContratos>(PARAMETROS_DE_FABRICA);
  private pedido = false;

  /** Lê da API uma única vez (as chamadas seguintes não fazem nada). */
  carregar(): void {
    if (this.pedido) return;
    this.pedido = true;
    this.api.parametros().subscribe({
      next: (p) => this.valores.set(p),
      error: () => (this.pedido = false), // sem acesso ou API fora: segue com os valores de fábrica e tenta de novo na próxima tela
    });
  }

  /** Depois de salvar na tela de parâmetros, as outras telas já enxergam o valor novo. */
  atualizar(p: ParametrosContratos): void {
    this.valores.set(p);
  }
}
