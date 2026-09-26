// Criado por José Eduardo Santana Martins
// Este arquivo serve para oferecer o botão "Importar XLSX", que cadastra um contrato a partir da planilha modelo.

import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { PreviaImportacao } from '../compartilhado/contratos.models';
import { MESES, PERIODICIDADES, ROTULOS_TIPO_ITEM, formatarCnpj, formatarCpf } from '../compartilhado/rotulos';

/** Mesmo limite da API: a planilha modelo tem poucos KB. */
const TAMANHO_MAXIMO_MB = 5;

/**
 * Botão "Importar XLSX" da carteira (liberado pela ACL `importacao-contratos`). Fluxo da janela:
 * baixar o modelo → escolher a planilha → ver a prévia (erros e avisos) → confirmar a importação.
 * A equipe não vem da planilha: depois de importar, o usuário a cadastra editando o contrato.
 */
@Component({
  selector: 'app-importacao-xlsx',
  imports: [...PIPES_FORMATACAO],
  host: { '(document:keydown.escape)': 'fechar()' },
  template: `
    <button type="button" class="acao-secundaria" (click)="abrir()">Importar XLSX</button>

    @if (aberta()) {
      <div class="fundo-modal" role="presentation" (click)="fechar()"></div>
      <section class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="titulo-importacao-xlsx">
        <header>
          <div><span class="modal-sobretitulo">Carteira de contratos</span><h2 id="titulo-importacao-xlsx">Importar contrato por planilha</h2></div>
          <button type="button" aria-label="Fechar" [disabled]="ocupado()" (click)="fechar()">×</button>
        </header>

        <div class="corpo-importacao">
          <p class="dica-formulario" style="margin-top: 0">
            Preencha a planilha "Checklist de Alimentação do Sistema de Contratos" e envie para conferir a prévia.
            A equipe de gestão e fiscalização não é importada: cadastre-a editando o contrato depois.
            <button type="button" class="link-arquivo" (click)="baixarModelo()">Baixar modelo</button>
          </p>
          <div class="acoes-cartao esquerda" style="margin: 0 0 14px">
            <input #campo type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" hidden (change)="aoEscolher(campo)" />
            <button type="button" class="acao-secundaria" [disabled]="ocupado()" (click)="campo.click()">Selecionar planilha</button>
            @if (arquivo(); as a) { <span class="dica-formulario">{{ a.name }} · {{ a.size | tamanho }}</span> }
            @if (erroArquivo()) { <span class="texto-erro" role="alert">{{ erroArquivo() }}</span> }
          </div>

          @if (previa(); as p) {
            <!-- Erros: impedem a importação; cada um aponta a linha da planilha -->
            @if (p.erros.length) {
              <div class="aviso-bloco erro" role="alert">
                <strong>{{ p.erros.length }} erro(s) na planilha. Corrija e envie de novo:</strong>
                <ul>@for (e of p.erros; track $index) { <li>{{ e.linha ? 'Linha ' + e.linha + ' · ' : '' }}{{ e.campo }}: {{ e.mensagem }}</li> }</ul>
              </div>
            }
            @for (a of p.avisos; track $index) { <p class="aviso-bloco">{{ a }}</p> }

            <p class="secao-formulario">Contrato</p>
            <ul class="resultado-importacao">
              <li><span>Número</span><b>{{ p.contrato.numero ?? '—' }}</b></li>
              <li><span>Apelido</span><b>{{ p.contrato.apelido || '—' }}</b></li>
              <li><span>Vigência</span><b>{{ p.contrato.data_inicio | dataBr }} a {{ p.contrato.data_fim | dataBr }}</b></li>
              <li><span>Vigência inicial / máxima</span><b>{{ p.contrato.vigencia_inicial_meses ?? '—' }} / {{ p.contrato.vigencia_maxima_meses ?? '—' }} meses</b></li>
              <li><span>Periodicidade</span><b>{{ periodicidade(p.contrato.periodicidade_meses) }}</b></li>
              <li><span>Mês de reajuste</span><b>{{ p.contrato.mes_reajuste ? meses[p.contrato.mes_reajuste - 1] : '—' }}</b></li>
              <li><span>Processos SEI</span><b>{{ p.contrato.sei_gestao_numero || '—' }} · {{ p.contrato.sei_execucao_numero || '—' }}</b></li>
            </ul>
            <p class="dica-formulario">{{ p.contrato.objeto || 'Objeto não informado.' }}</p>

            <p class="secao-formulario">Empresa e preposto</p>
            <ul class="resultado-importacao">
              @if (p.empresa; as e) {
                <li><span>{{ e.existente ? 'Empresa já cadastrada (mantida como está)' : 'Empresa nova' }}</span><b>{{ cnpj(e.cnpj) }} · {{ e.razao_social }}</b></li>
              } @else { <li><span>Empresa</span><b>não informada</b></li> }
              @if (p.preposto; as pr) {
                <li><span>{{ pr.existente ? 'Preposto já cadastrado' : 'Preposto novo' }}</span><b>{{ pr.nome }} · {{ cpf(pr.cpf) }}</b></li>
              } @else { <li><span>Preposto</span><b>não informado</b></li> }
            </ul>

            <p class="secao-formulario">Itens ({{ p.itens.length }}) · valor global estimado {{ p.valor_global_estimado | moeda }}</p>
            <div class="tabela-gestao-envoltorio">
              <table class="tabela-gestao">
                <thead><tr><th>Linha</th><th>Descrição</th><th>Tipo</th><th>Faturamento</th><th class="num">Qtd. mensal</th><th class="num">Qtd. vigência</th><th class="num">Valor unitário</th></tr></thead>
                <tbody>
                  @for (i of p.itens; track i.linha) {
                    <tr>
                      <td>{{ i.linha }}</td>
                      <td>{{ i.descricao }}@if (i.unidade_fornecimento) { <small>UF: {{ i.unidade_fornecimento }}</small> }<small>{{ i.codigo_classe }} · {{ i.codigo_natureza_despesa }} · {{ i.codigo_siafisico }} · {{ i.codigo_catmat_catser }}</small></td>
                      <td>{{ i.tipo ? tipos[i.tipo] : '—' }}</td>
                      <td>{{ i.calcula_pro_rata === null ? '—' : i.calcula_pro_rata ? 'Pró-rata' : 'Sempre integral' }}</td>
                      <td class="num">{{ i.quantidade_mensal | quantidade }}</td>
                      <td class="num">{{ i.quantidade_total | quantidade }}</td>
                      <td class="num">{{ i.valor_unitario | moeda }}</td>
                    </tr>
                  } @empty {
                    <tr><td class="estado-vazio" colspan="7">Nenhum item na planilha.</td></tr>
                  }
                </tbody>
              </table>
            </div>
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
export class ImportacaoXlsxComponent {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);

  // Estado da janela: planilha escolhida, prévia recebida e chamada em andamento
  protected readonly aberta = signal(false);
  protected readonly arquivo = signal<File | null>(null);
  protected readonly erroArquivo = signal<string | null>(null);
  protected readonly previa = signal<PreviaImportacao | null>(null);
  protected readonly ocupado = signal(false);

  // Textos e formatadores usados no template
  protected readonly meses = MESES;
  protected readonly tipos = ROTULOS_TIPO_ITEM;
  protected readonly cnpj = formatarCnpj;
  protected readonly cpf = formatarCpf;

  /** Abre a janela limpa. */
  protected abrir(): void {
    this.arquivo.set(null);
    this.previa.set(null);
    this.erroArquivo.set(null);
    this.aberta.set(true);
  }

  /** Fecha a janela (Esc, fundo, "×" ou Cancelar), a menos que haja uma chamada em andamento. */
  protected fechar(): void {
    if (!this.ocupado()) this.aberta.set(false);
  }

  /** Texto da periodicidade (Mensal, Bimestral...). */
  protected periodicidade(meses: number | null): string {
    return PERIODICIDADES.find((p) => p.valor === meses)?.rotulo ?? '—';
  }

  /** Baixa a planilha modelo em branco. */
  protected baixarModelo(): void {
    this.api.baixarModeloImportacao().subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar o modelo') });
  }

  /** Ao escolher a planilha: confere extensão e tamanho no navegador e já pede a prévia à API. */
  protected aoEscolher(campo: HTMLInputElement): void {
    const escolhido = campo.files?.[0] ?? null;
    // Permite escolher de novo o mesmo arquivo depois de corrigi-lo
    campo.value = '';
    this.previa.set(null);
    const problema = validarPlanilha(escolhido);
    this.erroArquivo.set(problema);
    this.arquivo.set(problema ? null : escolhido);
    if (!problema && escolhido) this.carregarPrevia(escolhido);
  }

  /** Envia a planilha para a prévia (nada é gravado). */
  private carregarPrevia(arquivo: File): void {
    this.ocupado.set(true);
    this.dialogos.executar(this.api.previaImportacao(arquivo), 'Lendo a planilha…').subscribe({
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

  /** Confirma: envia a mesma planilha para gravar e abre o contrato criado. */
  protected importar(): void {
    const arquivo = this.arquivo();
    if (!arquivo || !this.previa()?.pode_importar) return;
    this.ocupado.set(true);
    this.dialogos.executar(this.api.importarXlsx(arquivo), 'Importando o contrato…').subscribe({
      next: (contrato) => {
        this.ocupado.set(false);
        this.aberta.set(false);
        void this.roteador.navigate(['/contratos', contrato.id]);
        this.dialogos.avisar(
          `Contrato ${contrato.numero} importado`,
          'Cadastre a equipe de gestão e fiscalização editando o contrato (ela não vem da planilha).',
        );
      },
      error: (e) => {
        this.ocupado.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível importar o contrato');
      },
    });
  }
}

/** Validação rápida no navegador; devolve a mensagem de erro ou null se a planilha parece válida. */
export function validarPlanilha(arquivo: File | null): string | null {
  if (!arquivo) return null;
  if (!/\.xlsx$/i.test(arquivo.name)) return 'Selecione uma planilha no formato .xlsx.';
  if (arquivo.size === 0) return 'O arquivo está vazio.';
  if (arquivo.size > TAMANHO_MAXIMO_MB * 1024 * 1024) return `O arquivo excede o limite de ${TAMANHO_MAXIMO_MB} MB.`;
  return null;
}
