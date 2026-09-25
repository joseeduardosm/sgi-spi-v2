import { DatePipe } from '@angular/common';
import { Component, DestroyRef, inject, OnInit, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { EstadoMigracaoSgi } from '../compartilhado/contratos.models';

const ETAPAS: Record<string, string> = {
  iniciando: 'Iniciando',
  extraindo: 'Extraindo os dados do SGI (somente leitura)',
  carregando: 'Carregando e conferindo os dados neste servidor',
  concluida: 'Concluída',
};

const ROTULOS_RESULTADO: Record<string, string> = {
  empresas: 'Empresas', contratos: 'Contratos', itens: 'Itens', equipe: 'Designações de equipe', documentos: 'Documentos importantes',
  prorrogacoes: 'Prorrogações', notas_empenho: 'Notas de Empenho', competencias: 'Competências', avaliacoes: 'Avaliações',
  reajustes: 'Reajustes', anexos: 'Anexos (PDFs)', auditoria: 'Eventos de auditoria',
};

/**
 * Botão "Importar do SGI" (somente SuperRoot): pede a senha da origem (SGI) e a deste servidor, inicia a
 * importação em segundo plano e acompanha o andamento. A carga substitui os dados do módulo.
 */
@Component({
  selector: 'app-importacao-sgi',
  imports: [FormsModule, DatePipe],
  host: { '(document:keydown.escape)': 'fecharSePossivel()' },
  template: `
    <button type="button" class="acao-secundaria" (click)="abrir()">Importar do SGI</button>

    @if (aberta()) {
      <div class="fundo-modal" role="presentation" (click)="fecharSePossivel()"></div>
      <section class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-importacao-sgi">
        <header>
          <div><span class="modal-sobretitulo">SuperRoot</span><h2 id="titulo-importacao-sgi">Importar contratos do SGI</h2></div>
          <button type="button" aria-label="Fechar" [disabled]="executando()" (click)="fecharSePossivel()">×</button>
        </header>

        @if (estado(); as e) {
          @if (e.situacao === 'executando' || e.situacao === 'concluida' || e.situacao === 'erro') {
            <div class="corpo-importacao">
              @if (e.situacao === 'executando') {
                <p class="aviso-bloco informativo"><strong>{{ etapas[e.etapa ?? ''] ?? e.etapa }}…</strong> Isso leva alguns minutos; pode fechar a janela, a importação continua.</p>
              } @else if (e.situacao === 'concluida') {
                <p class="aviso-bloco informativo"><strong>Importação concluída</strong> em {{ e.concluida_em | date: 'dd/MM/yyyy HH:mm' }}.</p>
                @if (e.resultado) {
                  <ul class="resultado-importacao">
                    @for (r of resultado(e); track r.chave) { <li><span>{{ r.rotulo }}</span><b>{{ r.valor }}</b></li> }
                  </ul>
                }
                @for (a of e.avisos; track $index) { <p class="aviso-bloco">{{ a }}</p> }
              } @else {
                <p class="aviso-bloco erro"><strong>A importação falhou.</strong> {{ e.mensagem }} Os dados deste servidor não foram alterados pela etapa que falhou.</p>
              }
              <details [open]="e.situacao === 'erro'">
                <summary>Registro da execução</summary>
                <pre class="registro-importacao">{{ e.log.join('\\n') }}</pre>
              </details>
            </div>
            <footer>
              @if (e.situacao !== 'executando') { <button type="button" class="acao-secundaria" (click)="novaImportacao()">Nova importação</button> }
              <button type="button" class="acao-primaria" (click)="fecharSePossivel(true)">Fechar</button>
            </footer>
          } @else {
            <form (ngSubmit)="iniciar(e)" autocomplete="off">
              <p class="aviso-bloco erro" style="margin-top: 0">A importação <strong>substitui</strong> todos os contratos, empresas e anexos deste servidor pelos do SGI. O SGI não é alterado (leitura apenas).</p>
              <div class="grade-formulario">
                <div class="ocupa-duas">
                  <label for="senha-origem">Senha de <b>{{ e.origem }}</b> (origem: SGI) *</label>
                  <input id="senha-origem" name="senha_origem" type="password" required autocomplete="off" [(ngModel)]="senhaOrigem" />
                  <small class="dica-formulario">Também usada no sudo do SGI, para ler o banco.</small>
                </div>
                <div class="ocupa-duas">
                  <label for="senha-destino">Senha de <b>{{ e.destino }}</b> (destino: este servidor) *</label>
                  <input id="senha-destino" name="senha_destino" type="password" required autocomplete="off" [(ngModel)]="senhaDestino" />
                </div>
              </div>
              <p class="dica-formulario">As senhas são conferidas por SSH antes de começar e não são gravadas.</p>
              @if (ultima(); as u) {
                <p class="dica-formulario">
                  Última importação: {{ u.concluida_em | date: 'dd/MM/yyyy HH:mm' }}{{ u.iniciada_por ? ' por ' + u.iniciada_por : '' }} —
                  {{ u.situacao === 'concluida' ? (u.resultado?.['contratos'] ?? 0) + ' contrato(s) importado(s)' : 'falhou: ' + u.mensagem }}
                </p>
              }
              <footer>
                <button type="button" class="acao-secundaria" (click)="fecharSePossivel()">Cancelar</button>
                <button type="submit" class="acao-primaria" [disabled]="!senhaOrigem || !senhaDestino || enviando()">
                  {{ enviando() ? 'Conferindo as senhas…' : 'Importar' }}
                </button>
              </footer>
            </form>
          }
        } @else {
          <p class="estado-vazio">Carregando…</p>
        }
      </section>
    }
  `,
})
export class ImportacaoSgiComponent implements OnInit {
  /** Emitido quando uma importação termina com sucesso (a carteira recarrega). */
  readonly concluida = output<void>();

  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly destruir = inject(DestroyRef);

  protected readonly aberta = signal(false);
  protected readonly estado = signal<EstadoMigracaoSgi | null>(null);
  protected readonly enviando = signal(false);
  /** Última importação terminada, resumida no formulário. */
  protected readonly ultima = signal<EstadoMigracaoSgi | null>(null);
  protected readonly executando = () => this.estado()?.situacao === 'executando';
  protected readonly etapas = ETAPAS;
  protected senhaOrigem = '';
  protected senhaDestino = '';
  /** Mostra o formulário mesmo havendo resultado anterior. */
  private formulario = false;
  private temporizador: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    this.destruir.onDestroy(() => this.pararAcompanhamento());
  }

  ngOnInit(): void {
    // Importação em andamento (ex.: página recarregada): reabre o acompanhamento
    this.api.estadoMigracaoSgi().subscribe({
      next: (e) => {
        if (e.situacao === 'executando') {
          this.estado.set(e);
          this.aberta.set(true);
          this.acompanhar();
        }
      },
      error: () => undefined,
    });
  }

  /** Abre direto no formulário de senhas; só uma importação em andamento mostra o acompanhamento. */
  protected abrir(): void {
    this.aberta.set(true);
    this.formulario = true;
    this.consultar();
  }

  protected novaImportacao(): void {
    this.formulario = true;
    this.estado.update((e) => (e ? { ...e, situacao: 'ociosa' } : e));
  }

  /** Esc, fundo e "×" não fecham durante a execução; o botão "Fechar" fecha (a importação continua no servidor). */
  protected fecharSePossivel(forcar = false): void {
    if (this.enviando() || (this.executando() && !forcar)) return;
    this.aberta.set(false);
    this.senhaOrigem = this.senhaDestino = '';
  }

  protected async iniciar(e: EstadoMigracaoSgi): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Substituir os contratos deste servidor?',
      mensagem: `Todos os contratos, empresas e anexos deste servidor serão apagados e substituídos pelos do SGI (${e.origem}). O que foi lançado apenas aqui será perdido.`,
      rotuloConfirmar: 'Importar e substituir',
      segundos: 5,
    });
    if (!ok) return;
    this.enviando.set(true);
    this.api.iniciarMigracaoSgi(this.senhaOrigem, this.senhaDestino).subscribe({
      next: (novo) => {
        this.enviando.set(false);
        this.senhaOrigem = this.senhaDestino = '';
        this.formulario = false;
        this.estado.set(novo);
        this.acompanhar();
      },
      error: (erro) => {
        this.enviando.set(false);
        this.dialogos.mostrarErro(erro, 'Não foi possível iniciar a importação');
      },
    });
  }

  protected resultado(e: EstadoMigracaoSgi): { chave: string; rotulo: string; valor: number }[] {
    return Object.entries(e.resultado ?? {})
      .filter(([chave]) => chave in ROTULOS_RESULTADO)
      .map(([chave, valor]) => ({ chave, rotulo: ROTULOS_RESULTADO[chave], valor }));
  }

  private consultar(): void {
    this.api.estadoMigracaoSgi().subscribe({
      next: (e) => {
        this.ultima.set(e.situacao === 'concluida' || e.situacao === 'erro' ? e : null);
        this.estado.set(this.formulario && e.situacao !== 'executando' ? { ...e, situacao: 'ociosa' } : e);
        if (e.situacao === 'executando') this.acompanhar();
      },
      error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível consultar a importação'),
    });
  }

  private acompanhar(): void {
    this.pararAcompanhamento();
    this.temporizador = setTimeout(() => {
      this.api.estadoMigracaoSgi().subscribe({
        next: (e) => {
          this.estado.set(e);
          if (e.situacao === 'executando') this.acompanhar();
          else if (e.situacao === 'concluida') this.concluida.emit();
        },
        error: () => this.acompanhar(),
      });
    }, 3000);
  }

  private pararAcompanhamento(): void {
    if (this.temporizador) clearTimeout(this.temporizador);
    this.temporizador = null;
  }
}
