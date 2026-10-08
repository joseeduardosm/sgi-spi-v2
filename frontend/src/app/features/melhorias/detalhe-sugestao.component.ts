// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela própria da sugestão de melhoria (/melhorias/triagem/:numero): tratamento, resposta ao autor e conversão em tarefa.

import { DatePipe, Location } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { ImagemAutenticadaDirective } from '../noticias/gestao/imagem-autenticada.directive';
import { TarefasApiService } from '../tarefas/tarefas-api.service';
import { textoSla } from '../sla/sla.models';
import { Equipe, PessoaCarga } from '../tarefas/tarefas.models';
import { CabecalhoMelhoriasComponent } from './cabecalho-melhorias.component';
import { MelhoriasApiService } from './melhorias-api.service';
import { ConversaoTarefa, PrintSugestao, ROTULOS_MODULO, ROTULOS_SITUACAO, SituacaoSugestao, SugestaoTriagem, Tratamento } from './melhorias.models';
import { LinkificarPipe } from '../../shared/utilitarios/linkificar.pipe';

const SITUACOES = Object.keys(ROTULOS_SITUACAO) as SituacaoSugestao[];

/** Cada sugestão tem a própria tela (`/melhorias/triagem/12`), a mesma dos links de avisos; só quem faz a triagem acessa (a API confere). */
@Component({
  selector: 'app-detalhe-sugestao',
  imports: [LinkificarPipe, FormsModule, DatePipe, RouterLink, CabecalhoMelhoriasComponent, ImagemAutenticadaDirective],
  template: `
    <app-cabecalho-melhorias [titulo]="'Sugestão #' + numero" descricao="Analise, responda ao autor e, se fizer sentido, transforme em tarefa." />
    <p><a class="link-arquivo" routerLink="/melhorias/triagem">‹ Voltar à triagem</a></p>
    @if (semAcesso()) {
      <div class="aviso-admin erro">A triagem de melhorias é do SuperRoot e de quem tem CONTROLE TOTAL no recurso "Melhorias" da ACL.</div>
    } @else if (naoEncontrada()) {
      <div class="aviso-admin erro">Sugestão não encontrada.</div>
    } @else if (aberta(); as s) {
      <section class="painel-gestao janela-melhorias">
    <div class="corpo-janela-melhorias">
      <dl class="dados-sugestao">
        <div><dt>Autor</dt><dd>{{ s.autor_nome }} — &#64;{{ s.autor_login }}</dd></div>
        <div><dt>Enviada em</dt><dd>{{ s.criado_em | date: 'dd/MM/yyyy HH:mm' }}</dd></div>
        <div class="inteira"><dt>Tela</dt><dd><code>{{ s.tela || '—' }}</code></dd></div>
        <div class="inteira"><dt>Sugestão</dt><dd class="texto-sugestao" [innerHTML]="s.texto | linkificar"></dd></div>
      </dl>
      @if (s.prints.length) {
        <div class="prints-sugestao grandes">
          @for (p of s.prints; track p.id) {
            <button type="button" [title]="'Baixar ' + p.nome" (click)="baixar(p)"><img [appImagemAutenticada]="p.url" [alt]="p.nome" /></button>
          }
        </div>
      }

      <form (submit)="$event.preventDefault(); salvar()">
        <div class="grade-formulario uma-coluna">
          <div><label for="tr-situacao">Situação</label>
            <select id="tr-situacao" name="situacao" [(ngModel)]="tratamento.situacao">
              @for (x of situacoes; track x) { <option [value]="x">{{ rotulos[x] }}</option> }
            </select></div>
          <div><label for="tr-resposta">Resposta ao autor</label>
            <textarea id="tr-resposta" name="resposta" rows="3" maxlength="4000" [(ngModel)]="tratamento.resposta_publica"
                      placeholder="O autor vê esta resposta em Minhas sugestões e recebe aviso."></textarea></div>
          <div><label for="tr-obs">Observação interna</label>
            <textarea id="tr-obs" name="obs" rows="3" maxlength="12000" [(ngModel)]="tratamento.observacao_interna"
                      placeholder="Só quem faz a triagem vê."></textarea></div>
        </div>
        @if (s.sla; as sla) {
          <p class="dica-formulario"><span class="selo-sla-texto" [attr.data-situacao]="sla.situacao_resposta">{{ textoSla(sla, 'resposta') }}</span> · <span class="selo-sla-texto" [attr.data-situacao]="sla.situacao_resolucao">{{ textoSla(sla, 'resolucao') }}</span></p>
        }
        <div class="acoes-cartao">
          @if (s.tarefa_numero) {
            <a class="link-arquivo" [routerLink]="['/tarefas', s.tarefa_numero]">Tarefa #{{ s.tarefa_numero }} ↗</a>
          } @else {
            <button type="button" class="acao-secundaria" (click)="abrirConversao(s)">Converter em tarefa</button>
          }
          <button type="submit" class="acao-primaria" [disabled]="salvando()">{{ salvando() ? 'Salvando…' : 'Salvar tratamento' }}</button>
        </div>
      </form>

      @if (conversao(); as c) {
        <form class="conversao-tarefa" (submit)="$event.preventDefault(); converter()">
          <p class="secao-formulario">Nova tarefa no Módulo Tarefas</p>
          <div class="grade-formulario">
            <div class="ocupa-duas"><label for="cv-titulo">Título *</label><input id="cv-titulo" name="titulo" maxlength="200" [(ngModel)]="c.titulo" /></div>
            <div><label for="cv-equipe">Equipe</label>
              <select id="cv-equipe" name="equipe" [(ngModel)]="c.equipe_id" (ngModelChange)="aoTrocarEquipe($event)">
                <option [ngValue]="null">Sem equipe (tarefa pessoal)</option>
                @for (e of equipes(); track e.id) { <option [ngValue]="e.id">{{ e.nome }}</option> }
              </select></div>
            <div><label for="cv-resp">Responsável</label>
              <select id="cv-resp" name="resp" [(ngModel)]="c.responsavel_id">
                <option [ngValue]="null">Eu</option>
                @for (p of pessoas(); track p.id) { <option [ngValue]="p.id">{{ p.nome }}</option> }
              </select></div>
            <div><label for="cv-prazo">Prazo *</label><input id="cv-prazo" name="prazo" type="date" [(ngModel)]="prazoData" /></div>
            <div><label for="cv-prio">Prioridade</label>
              <select id="cv-prio" name="prio" [(ngModel)]="c.prioridade">
                <option value="baixa">Baixa</option><option value="normal">Normal</option><option value="alta">Alta</option><option value="critica">Crítica</option>
              </select></div>
          </div>
          <div class="acoes-cartao">
            <small class="dica-formulario">A descrição da tarefa leva o texto, o autor e a tela da sugestão; a sugestão fica Aceita.</small>
            <span>
              <button type="button" class="acao-secundaria" (click)="conversao.set(null)">Cancelar</button>
              <button type="submit" class="acao-positiva" [disabled]="!c.titulo.trim() || !prazoData">Criar tarefa</button>
            </span>
          </div>
        </form>
      }

      @if (s.eventos.length) {
        <p class="secao-formulario">Histórico</p>
        <ul class="historico-sugestao">
          @for (e of s.eventos; track $index) {
            <li><span [innerHTML]="e.descricao | linkificar"></span><small>{{ e.autor_nome }} · {{ e.criado_em | date: 'dd/MM/yyyy HH:mm' }}</small></li>
          }
        </ul>
      }
    </div>
      </section>
    } @else {
      <p class="estado-vazio">Carregando…</p>
    }
  `,
})
export class DetalheSugestaoComponent implements OnInit {
  private readonly api = inject(MelhoriasApiService);
  private readonly tarefas = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  private readonly local = inject(Location);
  protected readonly situacoes = SITUACOES;
  protected readonly rotulos = ROTULOS_SITUACAO;
  protected readonly textoSla = textoSla;
  protected readonly modulos = ROTULOS_MODULO;
  protected readonly numero = Number(this.rota.snapshot.paramMap.get('numero'));
  protected readonly aberta = signal<SugestaoTriagem | null>(null);
  protected readonly semAcesso = signal(false);
  protected readonly naoEncontrada = signal(false);
  protected readonly salvando = signal(false);
  protected readonly conversao = signal<ConversaoTarefa | null>(null);
  protected readonly equipes = signal<Equipe[]>([]);
  protected readonly pessoas = signal<PessoaCarga[]>([]);
  protected tratamento: Tratamento = { situacao: 'nova', resposta_publica: '', observacao_interna: '' };
  protected prazoData = '';

  ngOnInit(): void {
    this.api.detalhe(this.numero).subscribe({
      next: (s) => this.carregar(s),
      error: (e) => {
        if (e?.status === 403) this.semAcesso.set(true);
        else if (e?.status === 404) this.naoEncontrada.set(true);
        else this.dialogos.mostrarErro(e, 'Não foi possível carregar a sugestão');
      },
    });
  }

  private carregar(s: SugestaoTriagem): void {
    this.aberta.set(s);
    this.conversao.set(null);
    this.tratamento = { situacao: s.situacao, resposta_publica: s.resposta_publica, observacao_interna: s.observacao_interna };
  }

  protected salvar(): void {
    const s = this.aberta();
    if (!s) return;
    this.salvando.set(true);
    this.api.tratar(s.numero, this.tratamento).subscribe({
      // Salvo o tratamento, volta à triagem (a lista recarrega os totais)
      next: () => { this.salvando.set(false); this.voltar(); },
      error: (e) => {
        this.salvando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível salvar o tratamento');
      },
    });
  }

  private voltar(): void {
    if (this.roteador.navigated) this.local.back();
    else void this.roteador.navigate(['/melhorias/triagem']);
  }

  protected abrirConversao(s: SugestaoTriagem): void {
    const titulo = s.texto.split('\n')[0].slice(0, 120);
    this.conversao.set({ titulo: `Melhoria #${s.numero}: ${titulo}`.slice(0, 200), prazo: '', prioridade: 'normal', equipe_id: null, responsavel_id: null });
    const prazo = new Date();
    prazo.setDate(prazo.getDate() + 14);
    this.prazoData = prazo.toLocaleDateString('sv-SE');
    if (!this.equipes().length) this.tarefas.equipes().subscribe({ next: (l) => this.equipes.set(l), error: () => undefined });
    this.pessoas.set([]);
  }

  protected aoTrocarEquipe(equipeId: string | null): void {
    this.conversao.update((c) => (c ? { ...c, equipe_id: equipeId, responsavel_id: null } : c));
    this.pessoas.set([]);
    if (equipeId) this.tarefas.pessoas(equipeId).subscribe({ next: (l) => this.pessoas.set(l), error: () => undefined });
  }

  protected converter(): void {
    const s = this.aberta(), c = this.conversao();
    if (!s || !c) return;
    // Prazo no fim do expediente do dia escolhido (horário local)
    const prazo = new Date(`${this.prazoData}T18:00:00`).toISOString();
    this.dialogos.executar(this.api.converterEmTarefa(s.numero, { ...c, prazo }), 'Criando a tarefa…').subscribe({
      next: (novo) => {
        this.carregar(novo);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar a tarefa'),
    });
  }

  protected baixar(p: PrintSugestao): void {
    this.api.baixarPrint(p.url, p.nome).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
