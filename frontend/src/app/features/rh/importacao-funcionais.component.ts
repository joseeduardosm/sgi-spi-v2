// Criado por José Eduardo Santana Martins
// Este arquivo serve para a janela de carga em lote dos dados funcionais do RH por planilha (CGP).

import { Component, computed, inject, model, output, signal } from '@angular/core';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { RhApiService } from './rh-api.service';
import { ResultadoImportacaoRh } from './rh.models';

/** Nomes legíveis dos campos que a prévia informa como alterados. */
const ROTULOS: Record<string, string> = {
  autorizador_id: 'autorizador', substituto_id: 'substituto', sem_superior: 'topo da hierarquia',
  inicio_periodo_aquisitivo: 'início do período aquisitivo', exercicio: 'exercício da LP', saldo_lp_dias: 'dias de LP',
  jornada_semanal_horas: 'jornada', regime_plantao: 'plantão', horario_trabalho_inicio: 'horário de trabalho',
  horario_trabalho_fim: 'horário de trabalho', horario_estudante: 'horário de estudante', intervalo_inicio: 'intervalo',
  intervalo_fim: 'intervalo', rg_cin: 'RG/CIN', rs_pv: 'RS/PV',
};

/**
 * Carga dos dados funcionais: 1) baixar o modelo (já com os servidores e os valores atuais); 2) enviar a planilha
 * preenchida e conferir a prévia (o que muda e os erros, por linha); 3) importar, só sem nenhum erro.
 */
@Component({
  selector: 'app-importacao-funcionais',
  host: { '(document:keydown.escape)': 'aberta.set(false)' },
  template: `
    @if (aberta()) {
      <div class="fundo-modal" role="presentation" (click)="aberta.set(false)"></div>
      <section class="modal-portal modal-importacao-rh" role="dialog" aria-modal="true" aria-labelledby="titulo-importacao-rh">
        <header>
          <div><span class="modal-sobretitulo">Dados funcionais</span><h2 id="titulo-importacao-rh">Importar planilha</h2></div>
          <button type="button" aria-label="Fechar" (click)="aberta.set(false)">×</button>
        </header>
        <div class="corpo-importacao-rh">
          <ol class="passos-importacao">
            <li>Baixe o modelo: ele já traz todos os servidores ativos e os valores atuais.
              <button type="button" class="acao-secundaria acao-pequena" (click)="baixarModelo()">Baixar modelo</button></li>
            <li>Preencha as colunas. <b>Célula vazia mantém o valor atual.</b> "Dias disponíveis no período vigente" corrige o saldo de férias de quem já gozou parte do período.</li>
            <li>Envie a planilha e confira a prévia. A importação só grava se não houver nenhum erro.
              <label class="acao-secundaria acao-pequena seletor-arquivo">Escolher planilha (.xlsx)
                <input type="file" accept=".xlsx" (change)="escolher($any($event.target))" /></label>
              @if (arquivo(); as a) { <small>{{ a.name }}</small> }</li>
          </ol>

          @if (resultado(); as r) {
            <div class="resumo-importacao" [class.com-erro]="r.com_erro">
              <strong>{{ r.gravado ? 'Importação concluída' : 'Prévia' }}:</strong>
              {{ r.total }} linha(s) · {{ r.com_mudanca }} com alteração · {{ r.com_erro }} com erro
              @if (r.gravado) { · dados gravados }
            </div>
            <div class="tabela-gestao-envoltorio">
              <table class="tabela-gestao">
                <thead><tr><th class="num">Linha</th><th>Servidor</th><th>{{ r.com_erro ? 'Erros / alterações' : 'Alterações' }}</th></tr></thead>
                <tbody>
                  @for (l of linhasRelevantes(); track l.linha) {
                    <tr>
                      <td class="num">{{ l.linha }}</td>
                      <td><strong>{{ l.nome || l.login }}</strong><small>&#64;{{ l.login }}</small></td>
                      <td>
                        @for (e of l.erros; track $index) { <span class="texto-erro">{{ e }}</span><br /> }
                        @if (!l.erros.length) { {{ rotular(l.mudancas) }} }
                      </td>
                    </tr>
                  } @empty {
                    <tr><td class="estado-vazio" colspan="3">Nenhuma alteração na planilha.</td></tr>
                  }
                </tbody>
              </table>
            </div>
          }
        </div>
        <footer>
          <button type="button" class="acao-secundaria" (click)="aberta.set(false)">{{ resultado()?.gravado ? 'Fechar' : 'Cancelar' }}</button>
          @if (!resultado()?.gravado) {
            <button type="button" class="acao-primaria" [disabled]="!podeImportar()" (click)="importar()">
              Importar {{ resultado()?.com_mudanca ?? 0 }} servidor(es)</button>
          }
        </footer>
      </section>
    }
  `,
})
export class ImportacaoFuncionaisComponent {
  readonly aberta = model(false);
  /** Avisa a tela para recarregar depois de gravar. */
  readonly importado = output<void>();
  private readonly api = inject(RhApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly arquivo = signal<File | null>(null);
  protected readonly resultado = signal<ResultadoImportacaoRh | null>(null);
  protected readonly linhasRelevantes = computed(() => (this.resultado()?.linhas ?? []).filter((l) => l.erros.length || l.mudancas.length));
  protected readonly podeImportar = computed(() => {
    const r = this.resultado();
    return !!this.arquivo() && !!r && !r.gravado && r.com_erro === 0 && r.com_mudanca > 0;
  });

  protected baixarModelo(): void {
    this.dialogos.executar(this.api.modeloFuncionais(), 'Gerando o modelo…').subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Ao escolher o arquivo, confere na hora (prévia, sem gravar). */
  protected escolher(campo: HTMLInputElement): void {
    const arquivo = campo.files?.[0] ?? null;
    campo.value = '';
    this.arquivo.set(arquivo);
    this.resultado.set(null);
    if (!arquivo) return;
    this.dialogos.executar(this.api.importarFuncionais(arquivo, false), 'Conferindo a planilha…').subscribe({
      next: (r) => this.resultado.set(r),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível ler a planilha'),
    });
  }

  protected importar(): void {
    const arquivo = this.arquivo();
    if (!arquivo || !this.podeImportar()) return;
    this.dialogos.executar(this.api.importarFuncionais(arquivo, true), 'Gravando os dados funcionais…').subscribe({
      next: (r) => {
        this.resultado.set(r);
        this.importado.emit();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível importar'),
    });
  }

  protected rotular(campos: string[]): string {
    return [...new Set(campos.map((c) => ROTULOS[c] ?? c))].join(', ');
  }
}
