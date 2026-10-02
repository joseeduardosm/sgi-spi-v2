// Criado por José Eduardo Santana Martins
// Este arquivo serve para as janelas de ação da tarefa: alterar prazo, transferir, entregar e devolver ou reabrir com motivo.

import { Component, computed, effect, inject, input, model, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { AgendaPessoaComponent } from './agenda-pessoa.component';
import { paraCampo } from './nova-tarefa.component';
import { TarefasApiService } from './tarefas-api.service';
import { AcaoPipeline, PessoaCarga, TarefaDetalhe, TarefaResumo } from './tarefas.models';

export type ModoJanela = 'prazo' | 'transferir' | AcaoPipeline;

/** Tarefa mínima que a janela precisa (serve o resumo da lista ou o detalhe). */
type TarefaJanela = Pick<TarefaResumo, 'numero' | 'titulo' | 'prazo' | 'equipe' | 'responsavel'> & { versao?: number };

const TEXTOS: Partial<Record<ModoJanela, { titulo: string; rotulo: string; botao: string; obrigatorio: boolean; classe: string }>> = {
  prazo: { titulo: 'Alterar prazo', rotulo: 'Justificativa *', botao: 'Alterar prazo', obrigatorio: true, classe: 'acao-primaria' },
  transferir: { titulo: 'Transferir tarefa', rotulo: 'Justificativa *', botao: 'Transferir', obrigatorio: true, classe: 'acao-primaria' },
  entregar: { titulo: 'Entregar para validação', rotulo: 'Comentário da entrega (opcional)', botao: 'Entregar', obrigatorio: false, classe: 'acao-positiva' },
  devolver: { titulo: 'Devolver a entrega', rotulo: 'O que precisa ser ajustado? *', botao: 'Devolver', obrigatorio: true, classe: 'acao-recusar' },
  reabrir: { titulo: 'Reabrir tarefa', rotulo: 'Motivo da reabertura *', botao: 'Reabrir', obrigatorio: true, classe: 'acao-primaria' },
};

/** Janela modal de uma ação da tarefa; emite a tarefa atualizada. */
@Component({
  selector: 'app-janela-tarefa',
  imports: [FormsModule, AgendaPessoaComponent],
  host: { '(document:keydown.escape)': 'fechar()' },
  template: `
    @if (modo(); as m) {
      <!-- "sobre-janela": fica acima da janela da tarefa quando aberta a partir dela -->
      <div class="fundo-modal sobre-janela" role="presentation" (click)="fechar()"></div>
      <section class="modal-portal sobre-janela" role="dialog" aria-modal="true" aria-labelledby="titulo-janela-tarefa">
        <header>
          <div><span class="modal-sobretitulo">Tarefa #{{ tarefa()?.numero }}</span><h2 id="titulo-janela-tarefa">{{ textos()?.titulo }}</h2></div>
          <button type="button" aria-label="Fechar" (click)="fechar()">×</button>
        </header>
        <form (submit)="$event.preventDefault(); confirmar()">
          <p class="dica-formulario" style="margin-top: 0">{{ tarefa()?.titulo }}</p>
          <div class="grade-formulario">
            @if (m === 'prazo' || m === 'transferir') {
              <div class="ocupa-duas"><label for="jt-prazo">{{ m === 'prazo' ? 'Novo prazo *' : 'Novo prazo (opcional)' }}</label>
                <input id="jt-prazo" name="prazo" type="datetime-local" [(ngModel)]="prazo" [required]="m === 'prazo'" /></div>
            }
            @if (m === 'transferir') {
              <div class="ocupa-duas"><label>Para *</label>
                <div class="lista-carga" role="radiogroup" aria-label="Novo responsável">
                  @for (p of pessoas(); track p.id) {
                    @if (p.id !== tarefa()?.responsavel?.id) {
                      <label class="opcao-carga" [class.selecionada]="paraId() === p.id">
                        <input type="radio" name="para" [checked]="paraId() === p.id" (change)="paraId.set(p.id)" />
                        <span class="nome">{{ p.nome }}</span>
                        <span class="faixa-carga" [attr.data-faixa]="p.faixa">{{ p.faixa }}</span>
                        <small>{{ p.a_fazer }} a fazer · {{ p.em_andamento }} em andamento{{ p.atrasadas ? ' · ' + p.atrasadas + ' atrasada(s)' : '' }}</small>
                      </label>
                    }
                  } @empty { <p class="dica-formulario">Carregando a equipe…</p> }
                </div>
                @if (!tarefa()?.equipe) {
                  <input name="busca" placeholder="Pesquisar pessoa (nome ou login)" [ngModel]="busca()" (ngModelChange)="pesquisar($event)" />
                }
                <!-- Agenda de quem vai receber: carga e tarefas, em lista ou linha do tempo -->
                <app-agenda-pessoa [pessoaId]="paraId()" />
              </div>
            }
            <div class="ocupa-duas"><label for="jt-texto">{{ textos()?.rotulo }}</label>
              <textarea id="jt-texto" name="texto" rows="4" maxlength="4000" [(ngModel)]="texto"></textarea></div>
          </div>
          <footer>
            <button type="button" class="acao-secundaria" (click)="fechar()">Cancelar</button>
            <button type="submit" [class]="textos()?.classe" [disabled]="!podeConfirmar()">{{ textos()?.botao }}</button>
          </footer>
        </form>
      </section>
    }
  `,
})
export class JanelaTarefaComponent {
  readonly modo = model<ModoJanela | null>(null);
  readonly tarefa = input<TarefaJanela | null>(null);
  /** Novo prazo já preenchido ao abrir "Alterar prazo" (ex.: tarefa arrastada para outro dia no calendário). */
  readonly prazoSugerido = input<Date | null>(null);
  readonly concluido = output<TarefaDetalhe>();
  /** A ação foi recusada (403) ou deu conflito (409): a tela de quem chamou deve se atualizar. */
  readonly falhou = output<void>();
  private readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);

  protected texto = '';
  protected prazo = '';
  protected readonly pessoas = signal<PessoaCarga[]>([]);
  protected readonly paraId = signal<number | null>(null);
  protected readonly busca = signal('');
  protected readonly textos = computed(() => (this.modo() ? TEXTOS[this.modo()!] : null));

  constructor() {
    // Ao abrir: limpa os campos e, na transferência, carrega a equipe com a carga de cada pessoa
    effect(() => {
      const m = this.modo();
      const t = this.tarefa();
      if (!m || !t) return;
      this.texto = '';
      this.paraId.set(null);
      this.pessoas.set([]);
      this.prazo = m === 'prazo' ? paraCampo(this.prazoSugerido() ?? new Date(t.prazo)) : '';
      if (m === 'transferir' && t.equipe) this.api.pessoas(t.equipe.id).subscribe({ next: (l) => this.pessoas.set(l), error: (e) => this.dialogos.mostrarErro(e) });
    });
  }

  protected pesquisar(termo: string): void {
    this.busca.set(termo);
    if (termo.trim().length < 2) return;
    this.api.pessoas(null, termo.trim()).subscribe({ next: (l) => this.pessoas.set(l), error: () => undefined });
  }

  protected podeConfirmar(): boolean {
    const m = this.modo();
    if (this.textos()?.obrigatorio && !this.texto.trim()) return false;
    if (m === 'prazo' && !this.prazo) return false;
    if (m === 'transferir' && !this.paraId()) return false;
    return true;
  }

  protected fechar(): void {
    this.modo.set(null);
  }

  protected confirmar(): void {
    const m = this.modo();
    const t = this.tarefa();
    if (!m || !t || !this.podeConfirmar()) return;
    const texto = this.texto.trim();
    let operacao: Observable<TarefaDetalhe>;
    if (m === 'prazo') operacao = this.api.prazo(t.numero, new Date(this.prazo).toISOString(), texto, t.versao!);
    else if (m === 'transferir') operacao = this.api.transferir(t.numero, this.paraId()!, texto, this.prazo ? new Date(this.prazo).toISOString() : null, t.versao!);
    else operacao = this.api.mover(t.numero, m, texto, t.versao);
    this.dialogos.executar(operacao).subscribe({
      next: (atualizada) => { this.modo.set(null); this.concluido.emit(atualizada); },
      error: (e) => {
        this.dialogos.mostrarErro(e);
        if (e?.status === 403 || e?.status === 409) {
          this.modo.set(null);
          this.falhou.emit();
        }
      },
    });
  }
}
