// Criado por José Eduardo Santana Martins
// Este arquivo serve para oferecer o botão "Importar XLSX" de checklists e formulários de avaliação (contrato e modelos globais).

import { Component, computed, inject, input, output, signal } from '@angular/core';

import { AcessoService } from '../../../core/acesso/acesso.service';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { validarPlanilha } from '../carteira/importacao-xlsx.component';
import { ContratosApiService } from './contratos-api.service';
import { PreviaImportacaoModelo } from './contratos.models';

/**
 * Botão "Importar XLSX" (liberado pela ACL `importacao-modelos`). Sem `contratoId` cria um modelo
 * global; com ele, cria uma versão inativa do checklist/formulário do contrato. Fluxo da janela:
 * baixar o modelo → escolher a planilha → ver a prévia (erros e avisos) → confirmar.
 */
@Component({
  selector: 'app-importacao-modelo-xlsx',
  host: { '(document:keydown.escape)': 'fechar()' },
  template: `
    @if (liberado()) {
      <button type="button" class="acao-secundaria" [class.acao-pequena]="pequeno()" (click)="abrir()">Importar XLSX</button>
    }

    @if (aberta()) {
      <div class="fundo-modal" role="presentation" (click)="fechar()"></div>
      <section class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="titulo-importacao-modelo">
        <header>
          <div>
            <span class="modal-sobretitulo">{{ contratoId() ? 'Contrato' : 'Modelos globais' }}</span>
            <h2 id="titulo-importacao-modelo">Importar {{ tipo() === 'checklist' ? 'checklist' : 'formulário de avaliação' }} por planilha</h2>
          </div>
          <button type="button" aria-label="Fechar" [disabled]="ocupado()" (click)="fechar()">×</button>
        </header>

        <div class="corpo-importacao">
          <p class="dica-formulario" style="margin-top: 0">
            {{ contratoId() ? 'A importação cria uma versão inativa; ative-a depois de conferir.' : 'A importação cria um modelo global.' }}
            <button type="button" class="link-arquivo" (click)="baixarModelo()">Baixar modelo</button>
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
                  <thead><tr><th>Linha</th><th>Documento</th><th>Observação</th><th>Obrigatório</th><th>Com validade</th></tr></thead>
                  <tbody>
                    @for (d of p.documentos; track d.linha) {
                      <tr><td>{{ d.linha }}</td><td>{{ d.nome }}</td><td>{{ d.observacao || '—' }}</td><td>{{ d.obrigatorio ? 'Sim' : 'Não' }}</td><td>{{ d.com_validade ? 'Sim' : 'Não' }}</td></tr>
                    } @empty { <tr><td class="estado-vazio" colspan="5">Nenhum documento na planilha.</td></tr> }
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

  protected readonly liberado = computed(() => this.acesso.pode('importacao-modelos', 'MODIFICACAO') && this.acesso.pode('contratos', 'MODIFICACAO'));
  protected readonly aberta = signal(false);
  protected readonly arquivo = signal<File | null>(null);
  protected readonly erroArquivo = signal<string | null>(null);
  protected readonly previa = signal<PreviaImportacaoModelo | null>(null);
  protected readonly ocupado = signal(false);

  /** Escala da prévia em uma linha (ex.: "0 Ruim · 5 Regular"). */
  protected escala(): string {
    return (this.previa()?.escala ?? []).map((n) => `${n.valor ?? '—'} ${n.legenda}`).join(' · ') || '—';
  }

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

  protected baixarModelo(): void {
    this.api.baixarModeloImportacaoModelo(this.tipo(), this.contratoId()).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar o modelo') });
  }

  /** Ao escolher a planilha: confere extensão e tamanho no navegador e já pede a prévia. */
  protected aoEscolher(campo: HTMLInputElement): void {
    const escolhido = campo.files?.[0] ?? null;
    campo.value = '';
    this.previa.set(null);
    const problema = validarPlanilha(escolhido);
    this.erroArquivo.set(problema);
    this.arquivo.set(problema ? null : escolhido);
    if (!problema && escolhido) this.carregarPrevia(escolhido);
  }

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
