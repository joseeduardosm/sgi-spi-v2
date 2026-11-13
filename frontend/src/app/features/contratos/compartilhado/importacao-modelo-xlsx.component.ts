/**
 * =============================================================================
 * ARQUIVO: importacao-modelo-xlsx.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Oferecer o botão "Importar XLSX" de checklists e formulários de avaliação,
 * tanto do contrato quanto dos modelos globais, com a janela de importação.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template embutido. Mostra o botão só com ACL
 * contratos em MODIFICACAO ou mais. A janela segue o fluxo baixar modelo,
 * escolher planilha (validada no navegador), prévia pela API (erros e avisos)
 * e confirmação, que reenvia o arquivo para gravar e emite "importado".
 *
 * FINALIDADE DE NEGÓCIO:
 * Permite montar checklists de documentos e formulários de avaliação a partir
 * de uma planilha, sem digitar item por item, conferindo os erros antes de
 * gravar. No contrato a importação cria uma versão inativa, que o gestor
 * ativa depois de conferir.
 *
 * CONTEXTO NO SISTEMA:
 * Usado nas abas Checklists e Formulários do contrato e na tela de modelos
 * globais. Chama ContratosApiService; reaproveita validarPlanilha da
 * importação de contratos e a trilha de etapas (trilha-importacao.ts).
 *
 * =============================================================================
 */

import { TrilhaEtapasComponent } from '../../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { trilhaImportacao } from './trilha-importacao';
import { Component, computed, inject, input, output, signal } from '@angular/core';

import { AcessoService } from '../../../core/acesso/acesso.service';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { validarPlanilha } from '../carteira/importacao-xlsx.component';
import { ContratosApiService } from './contratos-api.service';
import { PreviaImportacaoModelo } from './contratos.models';

/**
 * Botão "Importar XLSX" (parte de Editar contratos: ACL `contratos` ≥ MODIFICACAO). Sem `contratoId` cria um modelo
 * global; com ele, cria uma versão inativa do checklist/formulário do contrato. Fluxo da janela:
 * baixar o modelo → escolher a planilha → ver a prévia (erros e avisos) → confirmar.
 *
 * ACL = lista de controle de acesso do SGI: cada módulo tem níveis (Leitura, Modificação, Controle total).
 * O `host` escuta a tecla Esc no documento para fechar a janela.
 */
@Component({
  selector: 'app-importacao-modelo-xlsx',
  imports: [TrilhaEtapasComponent],
  host: { '(document:keydown.escape)': 'fechar()' },
  template: `
    @if (liberado()) {
      <button type="button" class="acao-secundaria" [class.acao-pequena]="pequeno()" (click)="abrir()">Importar XLSX</button>
    }

    @if (aberta()) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="fechar()"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="titulo-importacao-modelo">
        <header>
          <div>
            <span class="modal-sobretitulo">{{ contratoId() ? 'Contrato' : 'Modelos globais' }}</span>
            <h2 id="titulo-importacao-modelo">Importar {{ tipo() === 'checklist' ? 'checklist' : 'formulário de avaliação' }} por planilha</h2>
          </div>
          <button type="button" aria-label="Fechar" [disabled]="ocupado()" (click)="fechar()">×</button>
        </header>

        <div class="corpo-importacao">
          <app-trilha-etapas [etapas]="trilha()" ariaLabel="Etapas da importação" [compacta]="true" />
          <p class="dica-formulario" style="margin-top: 0">
            {{ contratoId() ? 'A importação cria uma versão inativa; ative-a depois de conferir.' : 'A importação cria um modelo global.' }}
            <button type="button" class="acao-secundaria acao-pequena" (click)="baixarModelo()">Baixar modelo</button>
          </p>
          <div class="acoes-cartao esquerda" style="margin: 0 0 14px">
            <input #campo type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" hidden (change)="aoEscolher(campo)" />
            <button type="button" class="acao-secundaria" [disabled]="ocupado()" (click)="campo.click()">Selecionar planilha</button>
            @if (arquivo(); as a) { <span class="dica-formulario">{{ a.name }}</span> }
            @if (erroArquivo()) { <span class="texto-erro" role="alert">{{ erroArquivo() }}</span> }
          </div>

          @if (previa(); as p) {
            @if (p.erros.length) {
              <div class="aviso-bloco erro" role="alert">
                <strong>{{ p.erros.length }} erro(s) na planilha. Corrija e envie de novo:</strong>
                <ul>@for (e of p.erros; track $index) { <li>{{ e.linha ? 'Linha ' + e.linha + ' · ' : '' }}{{ e.campo }}: {{ e.mensagem }}</li> }</ul>
              </div>
            }
            @for (a of p.avisos; track $index) { <p class="aviso-bloco">{{ a }}</p> }

            <p class="secao-formulario">{{ p.nome || 'Sem nome' }}</p>
            @if (p.tipo === 'checklist') {
              <div class="tabela-gestao-envoltorio">
                <table class="tabela-gestao">
                  <thead><tr><th>Linha</th><th>Documento</th><th>Observação</th><th>Obrigatório</th><th>Com validade</th><th>Da empresa</th></tr></thead>
                  <tbody>
                    @for (d of p.documentos; track d.linha) {
                      <tr><td>{{ d.linha }}</td><td>{{ d.nome }}</td><td>{{ d.observacao || '—' }}</td><td>{{ d.obrigatorio ? 'Sim' : 'Não' }}</td><td>{{ d.com_validade ? 'Sim' : 'Não' }}</td><td>{{ d.vale_outros_contratos ? 'Sim' : 'Não' }}</td></tr>
                    } @empty { <tr><td class="estado-vazio" colspan="6">Nenhum documento na planilha.</td></tr> }
                  </tbody>
                </table>
              </div>
            } @else {
              <p class="dica-formulario">Escala: {{ escala() }}</p>
              <ul class="resultado-importacao">
                @for (f of p.faixas; track f.linha) {
                  <li><span>Faixa (linha {{ f.linha }})</span><b>{{ f.minimo ?? '—' }} a {{ f.maximo ?? 'sem teto' }} → {{ f.percentual ?? '—' }}%@if (f.notas_zero) { · {{ f.notas_zero }} nota(s) zero }</b></li>
                }
              </ul>
              @for (g of p.grupos; track g.nome) {
                <p class="secao-formulario">{{ g.nome }}</p>
                <ul class="resultado-importacao">
                  @for (i of g.itens; track i.linha) { <li><span>{{ i.nome }}@if (i.descricao) { — {{ i.descricao }} }</span><b>peso {{ i.peso ?? '—' }}%</b></li> }
                </ul>
              }
            }
          }
        </div>

        <footer>
          <button type="button" class="acao-secundaria" [disabled]="ocupado()" (click)="fechar()">Cancelar</button>
          <button type="button" class="acao-primaria" [disabled]="!previa()?.pode_importar || ocupado()" (click)="importar()">Confirmar importação</button>
        </footer>
      </section>
    }
  `,
})
export class ImportacaoModeloXlsxComponent {
  /** O que está sendo importado: checklist de documentos ou formulário de avaliação. */
  readonly tipo = input.required<'checklist' | 'formulario'>();
  /** Ausente = modelo global (tela de modelos, só SuperRoot). */
  readonly contratoId = input<string>();
  /** Botão compacto, para cabeçalhos de cartão. */
  readonly pequeno = input(false);
  /** Emitido depois de gravar, para a tela recarregar a lista. */
  readonly importado = output<void>();

  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly acesso = inject(AcessoService);

  // Só quem pode editar contratos vê o botão
  protected readonly liberado = computed(() => this.acesso.pode('contratos', 'MODIFICACAO'));
  protected readonly aberta = signal(false);
  protected readonly arquivo = signal<File | null>(null);
  protected readonly erroArquivo = signal<string | null>(null);
  protected readonly previa = signal<PreviaImportacaoModelo | null>(null);
  protected readonly ocupado = signal(false);
  // Etapas da trilha (modelo, planilha, prévia, confirmação), recalculadas conforme o andamento
  protected readonly trilha = computed(() => trilhaImportacao(!!this.arquivo(), this.previa()));

  /** Escala da prévia em uma linha (ex.: "0 Ruim · 5 Regular"). */
  protected escala(): string {
    return (this.previa()?.escala ?? []).map((n) => `${n.valor ?? '—'} ${n.legenda}`).join(' · ') || '—';
  }

  /** Abre a janela limpa (sem arquivo, prévia ou erro de uma tentativa anterior). */
  protected abrir(): void {
    this.arquivo.set(null);
    this.previa.set(null);
    this.erroArquivo.set(null);
    this.aberta.set(true);
  }

  /** Fecha a janela, a menos que haja uma chamada em andamento. */
  protected fechar(): void {
    if (!this.ocupado()) this.aberta.set(false);
  }

  /** Baixa a planilha-modelo vazia (global ou do contrato) para o usuário preencher. */
  protected baixarModelo(): void {
    this.api.baixarModeloImportacaoModelo(this.tipo(), this.contratoId()).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar o modelo') });
  }

  /** Ao escolher a planilha: confere extensão e tamanho no navegador e já pede a prévia. */
  protected aoEscolher(campo: HTMLInputElement): void {
    const escolhido = campo.files?.[0] ?? null;
    // Limpa o campo para permitir escolher o mesmo arquivo de novo (senão o change não dispara)
    campo.value = '';
    this.previa.set(null);
    const problema = validarPlanilha(escolhido);
    this.erroArquivo.set(problema);
    this.arquivo.set(problema ? null : escolhido);
    if (!problema && escolhido) this.carregarPrevia(escolhido);
  }

  /**
   * Envia a planilha para a API ler e validar, sem gravar nada. `dialogos.executar` mostra o aviso
   * "Lendo a planilha…" enquanto a chamada acontece.
   */
  private carregarPrevia(arquivo: File): void {
    this.ocupado.set(true);
    this.dialogos.executar(this.api.previaImportacaoModelo(this.tipo(), arquivo, this.contratoId()), 'Lendo a planilha…').subscribe({
      next: (p) => {
        this.ocupado.set(false);
        this.previa.set(p);
      },
      error: (e) => {
        this.ocupado.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível ler a planilha');
      },
    });
  }

  /** Confirma: envia a mesma planilha para gravar. */
  protected importar(): void {
    const arquivo = this.arquivo();
    // Segurança extra: sem prévia válida não grava, mesmo que o botão seja acionado de outro jeito
    if (!arquivo || !this.previa()?.pode_importar) return;
    this.ocupado.set(true);
    this.dialogos.executar(this.api.importarModelo(this.tipo(), arquivo, this.contratoId()), 'Importando…').subscribe({
      next: () => {
        this.ocupado.set(false);
        this.aberta.set(false);
        this.importado.emit();
      },
      error: (e) => {
        this.ocupado.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível importar a planilha');
      },
    });
  }
}
