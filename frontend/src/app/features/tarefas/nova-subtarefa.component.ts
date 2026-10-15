// Criado por José Eduardo Santana Martins
// Este arquivo serve para cadastrar uma subtarefa em tela dedicada: campos padrão da tarefa e as dependências (uma ou várias).

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { EditorRicoComponent } from '../contratacoes/editor-rico.component';
import { CabecalhoTarefasComponent } from './cabecalho-tarefas.component';
import { paraCampo } from './nova-tarefa.component';
import { TarefasApiService } from './tarefas-api.service';
import { PessoaCarga, PrioridadeTarefa, ROTULOS_PRIORIDADE, ROTULOS_STATUS, TarefaDetalhe, TarefaResumo } from './tarefas.models';

/** Tarefa que pode bloquear a nova subtarefa. */
interface Candidata { numero: number; titulo: string; status: TarefaResumo['status']; irma: boolean }

/**
 * Tela "Nova subtarefa" (`/tarefas/:numero/subtarefas/nova`): herda equipe e marcadores da mãe; título, descrição, prioridade, prazo (não passa do da
 * mãe), responsáveis e dependências. Nas dependências digita-se `#número` ou parte do título e escolhe-se uma ou várias tarefas da equipe.
 */
@Component({
  selector: 'app-nova-subtarefa',
  imports: [EsqueletoComponent, FormsModule, RouterLink, EditorRicoComponent, CabecalhoTarefasComponent],
  template: `
    @if (mae(); as m) {
      <app-cabecalho-tarefas titulo="Nova subtarefa"
        [trilha]="[{ rotulo: 'Tarefas', rota: '/tarefas' }, { rotulo: '#' + m.numero + ' ' + m.titulo, rota: ['/tarefas', m.numero] }, { rotulo: 'Nova subtarefa' }]"
        descricao="A subtarefa herda a equipe e os marcadores da tarefa mãe e tem andamento próprio." />

      <form class="cartao-dados formulario-tarefa" (submit)="$event.preventDefault(); salvar()">
        <div class="corpo">
          <section class="secao-tarefa">
            <h3><span>1</span> O que precisa ser feito</h3>
            <div class="grade-formulario">
              <div class="ocupa-duas"><label for="ns-titulo">Título *</label>
                <input id="ns-titulo" name="titulo" maxlength="200" required [(ngModel)]="titulo" placeholder="Ex.: Levantar as contas de serviço" /></div>
              <div class="ocupa-duas"><label for="ns-descricao">Descrição</label>
                @defer (on idle) { <app-editor-rico [(html)]="descricao" [colarFormatado]="true" rotulo="Descrição da subtarefa" /> } @placeholder { <app-esqueleto tipo="formulario" [linhas]="3" /> }</div>
            </div>
          </section>

          <section class="secao-tarefa">
            <h3><span>2</span> Prioridade e prazo</h3>
            <div class="grade-formulario">
              <div><label for="ns-prioridade">Prioridade</label>
                <select id="ns-prioridade" name="prioridade" [(ngModel)]="prioridade">
                  @for (p of prioridades; track p) { <option [value]="p">{{ rotulosPrioridade[p] }}</option> }
                </select></div>
              <div><label for="ns-prazo">Prazo *</label>
                <input id="ns-prazo" name="prazo" type="datetime-local" required [max]="prazoMaximo" [(ngModel)]="prazo" />
                <small class="dica-formulario">Não pode passar do prazo da tarefa mãe ({{ prazoMaeTexto }}).</small></div>
            </div>
          </section>

          <section class="secao-tarefa">
            <h3><span>3</span> Quem vai fazer</h3>
            <div class="lista-carga" role="group" aria-label="Responsáveis">
              @for (p of pessoas(); track p.id) {
                <label class="opcao-carga" [class.selecionada]="responsaveisIds().includes(p.id)">
                  <input type="checkbox" [name]="'responsavel-' + p.id" [checked]="responsaveisIds().includes(p.id)" [disabled]="herdado(p.id)" (change)="alternarResponsavel(p.id)" />
                  <span class="nome">{{ p.nome }}@if (herdado(p.id)) { <small> · herdado da mãe</small> }</span>
                  <span class="faixa-carga" [attr.data-faixa]="p.faixa">{{ p.faixa }}</span>
                  <small>{{ p.a_fazer }} a fazer · {{ p.em_andamento }} em andamento{{ p.atrasadas ? ' · ' + p.atrasadas + ' atrasada(s)' : '' }}</small>
                </label>
              }
            </div>
            <small class="dica-formulario">A subtarefa sempre tem os responsáveis da tarefa mãe (mudando lá, muda aqui). Marque outras pessoas para acrescentar.</small>
          </section>

          <section class="secao-tarefa">
            <h3><span>4</span> Depende de <small>(opcional, uma ou várias)</small></h3>
            <div class="dependencias-escolhidas">
              @for (n of escolhidas(); track n) {
                <span class="chip-dependencia"><b>#{{ n }}</b> {{ tituloDe(n) }}
                  <button type="button" [attr.aria-label]="'Remover dependência de #' + n" (click)="remover(n)">×</button></span>
              }
            </div>
            <div class="busca-dependencia-nova">
              <label for="ns-dependencia" class="rotulo-oculto">Buscar tarefa por # ou título</label>
              <input id="ns-dependencia" name="dependencia" autocomplete="off" placeholder="Digite # e o número, ou parte do título (ex.: #535 ou levantamento)"
                     [ngModel]="busca()" (ngModelChange)="busca.set($event)" (keydown.enter)="$event.preventDefault(); escolherPrimeira()" />
              @if (busca().trim() && sugestoes().length) {
                <ul class="sugestoes-dependencia" role="listbox" aria-label="Tarefas que podem bloquear">
                  @for (c of sugestoes(); track c.numero) {
                    <li><button type="button" role="option" (click)="escolher(c.numero)">
                      <b>#{{ c.numero }}</b> {{ c.titulo }}
                      <small>{{ c.irma ? 'subtarefa da mesma mãe · ' : '' }}{{ rotulosStatus[c.status] }}</small></button></li>
                  }
                </ul>
              } @else if (busca().trim()) {
                <p class="dica-formulario">Nenhuma tarefa aberta da equipe encontrada.</p>
              }
            </div>
            <small class="dica-formulario">A subtarefa só pode ser iniciada depois que todas as escolhidas forem concluídas. Aparecem as tarefas abertas da equipe e as outras subtarefas desta mãe.</small>
          </section>

          <div class="acoes-formulario acoes-fixas">
            <a class="acao-secundaria" [routerLink]="['/tarefas', m.numero]">Cancelar</a>
            <button [class.carregando]="salvando()" type="submit" class="acao-primaria" [disabled]="!titulo.trim() || !prazo || salvando()">Criar subtarefa</button>
          </div>
        </div>
      </form>
    } @else {
      <app-esqueleto tipo="formulario" [linhas]="6" />
    }
  `,
  styles: `
    .dependencias-escolhidas { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
    .chip-dependencia { display: inline-flex; align-items: center; gap: 6px; padding: 4px 6px 4px 12px; border: 1px solid var(--spi-borda-campo); border-radius: var(--spi-raio-pilula); background: var(--spi-superficie-alt); font-size: var(--spi-texto-compacto); }
    .chip-dependencia button { width: 22px; height: 22px; border: 0; border-radius: 50%; background: transparent; color: var(--spi-apagado); cursor: pointer; }
    .chip-dependencia button:hover { background: var(--spi-vermelho-suave); color: var(--spi-vermelho); }
    .busca-dependencia-nova { position: relative; }
    .rotulo-oculto { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
    .sugestoes-dependencia { position: absolute; z-index: 20; left: 0; right: 0; max-height: 280px; margin: 4px 0 0; padding: 4px; overflow-y: auto; list-style: none;
      border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-g); background: var(--spi-superficie); box-shadow: var(--spi-sombra-flutuante); }
    .sugestoes-dependencia button { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px; width: 100%; padding: 8px 10px; border: 0; border-radius: var(--spi-raio-m); background: transparent; color: var(--spi-texto); font-size: var(--spi-texto-compacto); text-align: left; cursor: pointer; }
    .sugestoes-dependencia button:hover, .sugestoes-dependencia button:focus-visible { background: var(--spi-superficie-ativa); outline: none; }
    .sugestoes-dependencia small { margin-left: auto; color: var(--spi-apagado); }
  `,
})
export class NovaSubtarefaComponent implements OnInit {
  private readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  private readonly rota = inject(ActivatedRoute);
  private readonly autenticacao = inject(AutenticacaoService);

  protected readonly prioridades: PrioridadeTarefa[] = ['baixa', 'normal', 'alta', 'critica'];
  protected readonly rotulosPrioridade = ROTULOS_PRIORIDADE;
  protected readonly rotulosStatus = ROTULOS_STATUS;

  protected readonly mae = signal<TarefaDetalhe | null>(null);
  protected readonly pessoas = signal<PessoaCarga[]>([]);
  protected readonly responsaveisIds = signal<number[]>([]);
  private readonly candidatas = signal<Candidata[]>([]);
  protected readonly escolhidas = signal<number[]>([]);
  protected readonly busca = signal('');
  protected readonly salvando = signal(false);

  protected titulo = '';
  protected descricao = '';
  protected prioridade: PrioridadeTarefa = 'normal';
  protected prazo = '';
  protected prazoMaximo = '';
  protected prazoMaeTexto = '';

  /** Tarefas abertas que ainda não foram escolhidas e combinam com o que foi digitado (`#12`, `12` ou parte do título). */
  protected readonly sugestoes = computed(() => {
    const texto = this.busca().trim().toLowerCase();
    if (!texto) return [];
    const numero = /^#?(\d+)$/.exec(texto)?.[1];
    const termo = texto.replace(/^#/, '');
    const usadas = new Set(this.escolhidas());
    return this.candidatas()
      .filter((c) => !usadas.has(c.numero) && (numero ? String(c.numero).startsWith(numero) : c.titulo.toLowerCase().includes(termo) || `#${c.numero}`.includes(texto)))
      .slice(0, 8);
  });

  ngOnInit(): void {
    const numero = Number(this.rota.snapshot.paramMap.get('numero'));
    this.api.detalhe(numero).subscribe({
      next: (m) => {
        if (!m.pode_criar_subtarefa || !m.equipe) {
          this.dialogos.avisar('Não é possível criar subtarefa', 'Esta tarefa não aceita subtarefas (é uma subtarefa, está concluída, é de contrato ou você não pode editá-la).');
          void this.roteador.navigate(['/tarefas', numero], { replaceUrl: true });
          return;
        }
        const prazoMae = new Date(m.prazo);
        this.prazoMaximo = paraCampo(prazoMae);
        this.prazo = this.prazoMaximo;
        this.prazoMaeTexto = prazoMae.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
        this.prioridade = m.prioridade;
        this.mae.set(m);
        this.carregarEquipe(m);
      },
      error: (e) => { this.dialogos.mostrarErro(e); void this.roteador.navigate(['/tarefas']); },
    });
  }

  private carregarEquipe(m: TarefaDetalhe): void {
    this.api.pessoas(m.equipe!.id).subscribe({
      next: (lista) => {
        this.pessoas.set(lista);
        // Padrão: os responsáveis da mãe que ainda são da equipe
        const daMae = new Set(m.responsaveis.map((r) => r.id));
        this.responsaveisIds.set(lista.filter((p) => daMae.has(p.id)).map((p) => p.id));
      },
      error: (e) => this.dialogos.mostrarErro(e),
    });
    const vazio = { status: [], prioridade: '' as const, marcador_id: '', responsavel_id: null, busca: '' };
    this.api.listar({ tipo: 'subtarefas', tarefa: m.numero }, vazio).subscribe({
      next: (l) => this.somarCandidatas(l.itens, true),
      error: () => undefined,
    });
    this.api.listar({ tipo: 'equipe', equipeId: m.equipe!.id }, vazio).subscribe({
      next: (l) => this.somarCandidatas(l.itens.filter((t) => t.numero !== m.numero), false),
      error: () => undefined,
    });
  }

  private somarCandidatas(itens: TarefaResumo[], irma: boolean): void {
    const novas = itens.filter((t) => t.status !== 'concluida').map((t) => ({ numero: t.numero, titulo: t.titulo, status: t.status, irma }));
    this.candidatas.update((l) => [...l, ...novas.filter((n) => !l.some((x) => x.numero === n.numero))].sort((a, b) => a.numero - b.numero));
  }

  protected tituloDe(numero: number): string {
    return this.candidatas().find((c) => c.numero === numero)?.titulo ?? '';
  }

  protected escolher(numero: number): void {
    this.escolhidas.update((l) => (l.includes(numero) ? l : [...l, numero]));
    this.busca.set('');
  }

  protected escolherPrimeira(): void {
    const primeira = this.sugestoes()[0];
    if (primeira) this.escolher(primeira.numero);
  }

  protected remover(numero: number): void {
    this.escolhidas.update((l) => l.filter((n) => n !== numero));
  }

  /** Os responsáveis da mãe valem sempre na subtarefa: ficam marcados e não podem ser desmarcados. */
  protected herdado(id: number): boolean {
    return !!this.mae()?.responsaveis.some((r) => r.id === id);
  }

  protected alternarResponsavel(id: number): void {
    if (this.herdado(id)) return;
    this.responsaveisIds.update((l) => (l.includes(id) ? l.filter((x) => x !== id) : [...l, id]));
  }

  protected salvar(): void {
    const m = this.mae();
    if (!m) return;
    const prazo = new Date(this.prazo);
    if (prazo.getTime() > new Date(m.prazo).getTime()) {
      this.dialogos.avisar('Prazo inválido', 'O prazo da subtarefa não pode passar do prazo da tarefa mãe.');
      return;
    }
    this.salvando.set(true);
    const eu = this.autenticacao.usuario()?.id;
    const dados = {
      titulo: this.titulo.trim(), descricao: this.descricao, prazo: prazo.toISOString(), prioridade: this.prioridade,
      responsaveis_ids: this.responsaveisIds().length ? this.responsaveisIds() : eu && !m.responsaveis.length ? [eu] : [],
      bloqueada_por_numeros: this.escolhidas(),
    };
    this.dialogos.executar(this.api.criarSubtarefa(m.numero, dados), 'Criando a subtarefa…').subscribe({
      next: (t) => void this.roteador.navigate(['/tarefas', t.numero], { replaceUrl: true }),
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e); },
    });
  }
}
