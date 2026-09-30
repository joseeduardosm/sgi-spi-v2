// Criado por José Eduardo Santana Martins
// Este arquivo serve para cadastrar uma tarefa completa: formulário à esquerda e, à direita, a agenda de quem vai recebê-la.

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { AgendaPessoaComponent } from './agenda-pessoa.component';
import { CabecalhoTarefasComponent } from './cabecalho-tarefas.component';
import { TarefasApiService } from './tarefas-api.service';
import { Equipe, Marcador, PessoaCarga, PrioridadeTarefa, ROTULOS_PRIORIDADE } from './tarefas.models';

/** Valor inicial do prazo: daqui a 7 dias, 18:00 (formato do campo datetime-local). */
function prazoPadrao(): string {
  const d = new Date();
  d.setDate(d.getDate() + 7);
  d.setHours(18, 0, 0, 0);
  return paraCampo(d);
}

/** Date → "aaaa-mm-ddThh:mm" no horário local. */
export function paraCampo(d: Date): string {
  const z = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}`;
}

@Component({
  selector: 'app-nova-tarefa',
  imports: [FormsModule, RouterLink, SeletorUsuariosComponent, CabecalhoTarefasComponent, AgendaPessoaComponent],
  template: `
    <app-cabecalho-tarefas titulo="Nova tarefa" [trilha]="[{ rotulo: 'Nova tarefa' }]"
                           descricao="Quem recebe a tarefa é avisado na caixa de mensagens e por e-mail." />

    <div class="nova-tarefa-colunas">
    <form class="cartao-dados formulario-tarefa" (submit)="$event.preventDefault(); salvar()">
      <div class="corpo">
        <div class="grade-formulario">
          <div class="ocupa-duas"><label for="nt-titulo">Título *</label>
            <input id="nt-titulo" name="titulo" maxlength="200" required [(ngModel)]="titulo" placeholder="O que precisa ser feito" /></div>
          <div class="ocupa-duas"><label for="nt-descricao">Descrição</label>
            <textarea id="nt-descricao" name="descricao" maxlength="20000" rows="5" [(ngModel)]="descricao"
                      placeholder="Contexto, entregáveis esperados, links"></textarea></div>
          <div><label for="nt-equipe">Equipe</label>
            <select id="nt-equipe" name="equipe" [ngModel]="equipeId()" (ngModelChange)="trocarEquipe($event)">
              <option value="">Sem equipe (tarefa pessoal, sem validação)</option>
              @for (e of equipes(); track e.id) { <option [value]="e.id">{{ e.nome }}</option> }
            </select></div>
          <div><label for="nt-prioridade">Prioridade</label>
            <select id="nt-prioridade" name="prioridade" [(ngModel)]="prioridade">
              @for (p of prioridades; track p) { <option [value]="p">{{ rotulosPrioridade[p] }}</option> }
            </select></div>
          <div><label for="nt-prazo">Prazo *</label>
            <input id="nt-prazo" name="prazo" type="datetime-local" required [(ngModel)]="prazo" /></div>
          <div></div>

          <div class="ocupa-duas">
            <label for="nt-responsavel">Responsável</label>
            @if (equipeId()) {
              <!-- Na equipe: lista dos membros com a carga de cada um -->
              <div class="lista-carga" role="radiogroup" aria-label="Responsável">
                @for (p of pessoas(); track p.id) {
                  <label class="opcao-carga" [class.selecionada]="responsavelId() === p.id">
                    <input type="radio" name="responsavel" [value]="p.id" [checked]="responsavelId() === p.id" (change)="responsavelId.set(p.id); pessoaAgenda.set(p.id)" />
                    <span class="nome">{{ p.nome }}</span>
                    <span class="faixa-carga" [attr.data-faixa]="p.faixa">{{ p.faixa }}</span>
                    <small>{{ p.a_fazer }} a fazer · {{ p.em_andamento }} em andamento{{ p.atrasadas ? ' · ' + p.atrasadas + ' atrasada(s)' : '' }}</small>
                  </label>
                }
              </div>
              @if (escolhido()?.faixa === 'Sobrecarga crítica') {
                <p class="aviso-formulario">{{ escolhido()!.nome }} está com sobrecarga crítica. Considere outra pessoa ou um prazo maior.</p>
              }
            } @else {
              <app-seletor-usuarios idCampo="nt-responsavel" [multiplo]="false" [selecionados]="responsavel" (selecionadosChange)="aoEscolherResponsavel($event)"
                                    [fonte]="api.opcoesPessoas" textoAjuda="Vazio: você mesmo" />
            }
          </div>
          <div class="ocupa-duas"><label for="nt-participantes">Participantes</label>
            <app-seletor-usuarios idCampo="nt-participantes" [selecionados]="participantes" (selecionadosChange)="aoMudarParticipantes($event)"
                                  [fonte]="api.opcoesPessoas" textoAjuda="Quem mais trabalha na tarefa (a carga conta para cada um)" /></div>
          @if (marcadores().length) {
            <div class="ocupa-duas"><label>Marcadores</label>
              <div class="linha-caixas">
                @for (m of marcadores(); track m.id) {
                  <label><input type="checkbox" [checked]="marcadoresIds().includes(m.id)" (change)="alternarMarcador(m.id)" />
                    <span class="marcador-tarefa" [style.--cor]="m.cor">{{ m.nome }}</span></label>
                }
              </div></div>
          }
        </div>
        <div class="acoes-formulario">
          <a class="acao-secundaria" routerLink="/tarefas">Cancelar</a>
          <button type="submit" class="acao-primaria" [disabled]="!titulo.trim() || !prazo || salvando()">Criar tarefa</button>
        </div>
      </div>
    </form>

    <!-- Agenda de quem recebe: muda conforme o responsável ou o último participante escolhido -->
    <aside class="cartao-dados agenda-nova-tarefa">
      <header><h2>Agenda de quem recebe</h2><small>Escolha o responsável ou um participante para ver a carga e as tarefas da pessoa.</small></header>
      <div class="corpo">
        @if (pessoaAgenda()) { <app-agenda-pessoa [pessoaId]="pessoaAgenda()" /> }
        @else { <p class="dica-formulario">Ninguém escolhido ainda. Sem responsável, a tarefa fica com você.</p> }
      </div>
    </aside>
    </div>
  `,
})
export class NovaTarefaComponent implements OnInit {
  protected readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  private readonly rota = inject(ActivatedRoute);
  private readonly autenticacao = inject(AutenticacaoService);
  protected readonly prioridades: PrioridadeTarefa[] = ['baixa', 'normal', 'alta', 'critica'];
  protected readonly rotulosPrioridade = ROTULOS_PRIORIDADE;

  protected titulo = '';
  protected descricao = '';
  protected prioridade: PrioridadeTarefa = 'normal';
  protected prazo = prazoPadrao();
  protected responsavel: OpcaoUsuario[] = [];
  protected participantes: OpcaoUsuario[] = [];
  protected readonly equipes = signal<Equipe[]>([]);
  protected readonly equipeId = signal('');
  protected readonly pessoas = signal<PessoaCarga[]>([]);
  protected readonly responsavelId = signal<number | null>(null);
  protected readonly marcadores = signal<Marcador[]>([]);
  protected readonly marcadoresIds = signal<string[]>([]);
  protected readonly salvando = signal(false);
  protected readonly escolhido = computed(() => this.pessoas().find((p) => p.id === this.responsavelId()) ?? null);
  /** Pessoa cuja agenda aparece à direita (responsável escolhido ou último participante incluído). */
  protected readonly pessoaAgenda = signal<number | null>(null);

  ngOnInit(): void {
    this.api.equipes().subscribe({
      next: (lista) => {
        this.equipes.set(lista);
        // ?equipe=<id> (vindo da tela da equipe) já escolhe a equipe
        const pedida = this.rota.snapshot.queryParamMap.get('equipe');
        if (pedida && lista.some((e) => e.id === pedida)) this.trocarEquipe(pedida);
      },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected trocarEquipe(id: string): void {
    this.equipeId.set(id);
    this.marcadoresIds.set([]);
    this.pessoas.set([]);
    this.marcadores.set([]);
    if (!id) return;
    this.api.pessoas(id).subscribe({
      next: (lista) => {
        this.pessoas.set(lista);
        // Padrão: o próprio usuário, se for da equipe
        const eu = this.autenticacao.usuario()?.id;
        this.responsavelId.set(lista.some((p) => p.id === eu) ? eu! : null);
        this.pessoaAgenda.set(this.responsavelId());
      },
      error: (e) => this.dialogos.mostrarErro(e),
    });
    this.api.marcadores(id).subscribe({ next: (m) => this.marcadores.set(m), error: () => undefined });
  }

  /** Responsável fora de equipe (seletor de busca): mostra a agenda da pessoa escolhida. */
  protected aoEscolherResponsavel(lista: OpcaoUsuario[]): void {
    this.responsavel = lista;
    this.pessoaAgenda.set(lista[0]?.id ?? null);
  }

  /** Ao incluir um participante, a agenda passa a ser a dele. */
  protected aoMudarParticipantes(lista: OpcaoUsuario[]): void {
    const novo = lista.find((p) => !this.participantes.some((x) => x.id === p.id));
    this.participantes = lista;
    if (novo) this.pessoaAgenda.set(novo.id);
  }

  protected alternarMarcador(id: string): void {
    this.marcadoresIds.update((l) => (l.includes(id) ? l.filter((x) => x !== id) : [...l, id]));
  }

  protected salvar(): void {
    const equipe = this.equipeId() || null;
    const responsavel = equipe ? this.responsavelId() : (this.responsavel[0]?.id ?? null);
    this.salvando.set(true);
    this.dialogos.executar(this.api.criar({
      titulo: this.titulo.trim(), descricao: this.descricao, prazo: new Date(this.prazo).toISOString(), prioridade: this.prioridade,
      equipe_id: equipe, responsavel_id: responsavel, participantes_ids: this.participantes.map((p) => p.id), marcadores_ids: this.marcadoresIds(),
    }), 'Criando a tarefa…').subscribe({
      // Volta ao quadro (da equipe ou Minhas tarefas) com a tarefa nova aberta na janela
      next: (t) => void this.roteador.navigate(equipe ? ['/tarefas/equipes', equipe] : ['/tarefas'], { queryParams: { tarefa: t.numero } }),
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e); },
    });
  }
}
