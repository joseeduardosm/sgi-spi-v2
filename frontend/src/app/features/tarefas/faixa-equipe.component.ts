// Criado por José Eduardo Santana Martins
// Este arquivo serve para a faixa da equipe: situação atual (status publicado pela liderança) e marcos com progresso, com a gestão de ambos.

import { DatePipe } from '@angular/common';
import { Component, computed, inject, input, OnInit, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { TarefasApiService } from './tarefas-api.service';
import { AtualizacaoStatus, Marco, ROTULOS_SITUACAO_MARCO, ROTULOS_STATUS_EQUIPE, SituacaoStatusEquipe } from './tarefas.models';

type Janela = 'status' | 'historico' | 'marcos' | null;

@Component({
  selector: 'app-faixa-equipe',
  imports: [FormsModule, DatePipe],
  template: `
    <section class="faixa-equipe" aria-label="Situação e marcos da equipe">
      <div class="situacao-equipe">
        @if (atual(); as s) {
          <span class="ponto-situacao" [attr.data-situacao]="s.situacao" aria-hidden="true"></span>
          <div><strong>{{ rotulosStatus[s.situacao] }}</strong>
            <small>{{ s.autor_nome }} · {{ s.criado_em | date: 'dd/MM/yyyy' }}@if (s.texto) { · {{ s.texto }} }</small></div>
        } @else { <span class="ponto-situacao" data-situacao="nenhuma" aria-hidden="true"></span><div><strong>Sem atualização de status</strong><small>A liderança publica a situação da equipe aqui.</small></div> }
        <span class="espacador"></span>
        @if (historico().length > 1) { <button type="button" class="link-simples" (click)="janela.set('historico')">Histórico</button> }
        @if (lider()) { <button type="button" class="acao-secundaria acao-pequena" (click)="abrirStatus()">Atualizar status</button> }
      </div>
      @if (marcos().length || lider()) {
        <div class="marcos-equipe">
          @for (m of marcos(); track m.id) {
            <button type="button" class="marco" [class.ativo]="marcoAtivo() === m.id" [attr.data-situacao]="m.situacao" (click)="filtrar.emit(marcoAtivo() === m.id ? null : m.id)"
                    [title]="m.descricao || m.nome">
              <b>{{ m.nome }}</b>
              <span class="barra"><i [style.width.%]="m.total ? 100 * m.concluidas / m.total : 0"></i></span>
              <small>{{ m.concluidas }}/{{ m.total }} · {{ m.data_alvo + 'T12:00:00' | date: 'dd/MM' }} · {{ rotulosMarco[m.situacao] }}</small>
            </button>
          }
          @if (lider()) { <button type="button" class="acao-secundaria acao-pequena" (click)="janela.set('marcos')">{{ marcos().length ? 'Gerenciar marcos' : '+ Marco' }}</button> }
        </div>
      }
    </section>

    @if (janela() === 'status') {
      <div class="fundo-modal" role="presentation" (click)="janela.set(null)"></div>
      <section class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-status-equipe">
        <header><div><h2 id="titulo-status-equipe">Atualizar status da equipe</h2><small>Os membros e a liderança são avisados.</small></div><button type="button" aria-label="Fechar" (click)="janela.set(null)">×</button></header>
        <form class="grade-formulario" (submit)="$event.preventDefault(); publicar()">
          <div class="ocupa-duas"><label for="st-situacao">Situação</label>
            <select id="st-situacao" name="situacao" [(ngModel)]="novaSituacao">@for (k of situacoes; track k) { <option [value]="k">{{ rotulosStatus[k] }}</option> }</select></div>
          <div class="ocupa-duas"><label for="st-texto">O que está acontecendo</label><textarea id="st-texto" name="texto" rows="4" maxlength="4000" [(ngModel)]="novoTexto" placeholder="Avanços, riscos e próximos passos"></textarea></div>
          <div class="ocupa-duas acoes-formulario"><button type="submit" class="acao-primaria">Publicar</button><button type="button" class="acao-secundaria" (click)="janela.set(null)">Cancelar</button></div>
        </form>
      </section>
    }

    @if (janela() === 'historico') {
      <div class="fundo-modal" role="presentation" (click)="janela.set(null)"></div>
      <section class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="titulo-historico-status">
        <header><div><h2 id="titulo-historico-status">Histórico de status</h2></div><button type="button" aria-label="Fechar" (click)="janela.set(null)">×</button></header>
        <ul class="historico-status">
          @for (h of historico(); track h.id) {
            <li><span class="ponto-situacao" [attr.data-situacao]="h.situacao" aria-hidden="true"></span>
              <div><strong>{{ rotulosStatus[h.situacao] }}</strong> <small>{{ h.autor_nome }} · {{ h.criado_em | date: 'dd/MM/yyyy HH:mm' }}</small>@if (h.texto) { <p>{{ h.texto }}</p> }</div></li>
          }
        </ul>
      </section>
    }

    @if (janela() === 'marcos') {
      <div class="fundo-modal" role="presentation" (click)="janela.set(null)"></div>
      <section class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="titulo-marcos">
        <header><div><h2 id="titulo-marcos">Marcos da equipe</h2><small>Um marco fica atingido quando todas as tarefas ligadas a ele concluem (ou por decisão da liderança).</small></div>
          <button type="button" aria-label="Fechar" (click)="janela.set(null)">×</button></header>
        <div class="corpo-marcos">
          <ul class="lista-gestao-marcos">
            @for (m of marcos(); track m.id) {
              <li><div><strong>{{ m.nome }}</strong> <small>{{ m.data_alvo + 'T12:00:00' | date: 'dd/MM/yyyy' }} · {{ rotulosMarco[m.situacao] }} · {{ m.concluidas }}/{{ m.total }} tarefas</small></div>
                <div class="acoes-formulario">
                  <button type="button" class="acao-secundaria acao-pequena" (click)="editarMarco(m)">Editar</button>
                  <button type="button" class="acao-secundaria acao-pequena" (click)="atingir(m)">{{ m.situacao === 'atingido' ? 'Reabrir' : 'Marcar atingido' }}</button>
                  <button type="button" class="acao-recusar acao-pequena" (click)="excluirMarco(m)">Excluir</button></div></li>
            } @empty { <li class="dica-formulario">Nenhum marco ainda.</li> }
          </ul>
          <form class="grade-formulario" (submit)="$event.preventDefault(); salvarMarco()">
            <div><label for="mc-nome">{{ editandoMarco() ? 'Editar marco' : 'Novo marco' }}</label><input id="mc-nome" name="nome" maxlength="120" required [(ngModel)]="formMarco.nome" /></div>
            <div><label for="mc-data">Data-alvo</label><input id="mc-data" name="data" type="date" required [(ngModel)]="formMarco.data_alvo" /></div>
            <div class="ocupa-duas"><label for="mc-desc">Descrição (opcional)</label><input id="mc-desc" name="descricao" maxlength="4000" [(ngModel)]="formMarco.descricao" /></div>
            <div class="ocupa-duas acoes-formulario"><button type="submit" class="acao-primaria" [disabled]="!formMarco.nome.trim() || !formMarco.data_alvo">{{ editandoMarco() ? 'Salvar' : 'Incluir' }}</button>
              @if (editandoMarco()) { <button type="button" class="acao-secundaria" (click)="limparForm()">Cancelar edição</button> }</div>
          </form>
        </div>
      </section>
    }
  `,
})
export class FaixaEquipeComponent implements OnInit {
  readonly equipeId = input.required<string>();
  readonly lider = input(false);
  /** Marco usado como filtro do quadro. */
  readonly marcoAtivo = input<string | null>(null);
  readonly filtrar = output<string | null>();
  /** Avisa o espaço que os marcos mudaram (a lista de tarefas pode precisar recarregar). */
  readonly alterado = output<void>();

  private readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly rotulosStatus = ROTULOS_STATUS_EQUIPE;
  protected readonly rotulosMarco = ROTULOS_SITUACAO_MARCO;
  protected readonly situacoes = Object.keys(ROTULOS_STATUS_EQUIPE) as SituacaoStatusEquipe[];
  protected readonly marcos = signal<Marco[]>([]);
  protected readonly historico = signal<AtualizacaoStatus[]>([]);
  protected readonly atual = computed(() => this.historico()[0] ?? null);
  protected readonly janela = signal<Janela>(null);
  protected readonly editandoMarco = signal<Marco | null>(null);
  protected novaSituacao: SituacaoStatusEquipe = 'no_prazo';
  protected novoTexto = '';
  protected formMarco = { nome: '', descricao: '', data_alvo: '' };

  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    this.api.marcos(this.equipeId()).subscribe({ next: (m) => this.marcos.set(m), error: () => undefined });
    this.api.historicoStatus(this.equipeId()).subscribe({ next: (h) => this.historico.set(h), error: () => undefined });
  }

  private falha(titulo: string) {
    return (e: unknown) => this.dialogos.mostrarErro(e, titulo);
  }

  protected abrirStatus(): void {
    this.novaSituacao = this.atual()?.situacao ?? 'no_prazo';
    this.novoTexto = '';
    this.janela.set('status');
  }

  protected publicar(): void {
    this.api.publicarStatus(this.equipeId(), this.novaSituacao, this.novoTexto.trim()).subscribe({
      next: () => { this.janela.set(null); this.carregar(); }, error: this.falha('Não foi possível publicar o status'),
    });
  }

  protected editarMarco(m: Marco): void {
    this.editandoMarco.set(m);
    this.formMarco = { nome: m.nome, descricao: m.descricao, data_alvo: m.data_alvo };
  }

  protected limparForm(): void {
    this.editandoMarco.set(null);
    this.formMarco = { nome: '', descricao: '', data_alvo: '' };
  }

  protected salvarMarco(): void {
    this.api.salvarMarco(this.equipeId(), { ...this.formMarco, nome: this.formMarco.nome.trim() }, this.editandoMarco()?.id).subscribe({
      next: () => { this.limparForm(); this.carregar(); this.alterado.emit(); }, error: this.falha('Não foi possível salvar o marco'),
    });
  }

  protected atingir(m: Marco): void {
    this.api.atingirMarco(m.id, m.situacao !== 'atingido').subscribe({ next: () => this.carregar(), error: this.falha('Não foi possível alterar o marco') });
  }

  protected async excluirMarco(m: Marco): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: 'Excluir este marco?', mensagem: `"${m.nome}" será removido. As tarefas continuam, sem marco.`, rotuloConfirmar: 'Excluir', segundos: 3, perigo: true });
    if (ok) this.api.excluirMarco(m.id).subscribe({ next: () => { this.carregar(); this.alterado.emit(); }, error: this.falha('Não foi possível excluir o marco') });
  }
}
