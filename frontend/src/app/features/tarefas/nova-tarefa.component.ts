// Criado por José Eduardo Santana Martins
// Este arquivo serve para cadastrar uma tarefa completa: formulário à esquerda e, à direita, a agenda de quem vai recebê-la.

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { SeletorMarcadoresComponent } from './seletor-marcadores.component';
import { SeletorRecorrenciaComponent } from './seletor-recorrencia.component';
import { AgendaPessoaComponent } from './agenda-pessoa.component';
import { CabecalhoTarefasComponent } from './cabecalho-tarefas.component';
import { TarefasApiService } from './tarefas-api.service';
import { Equipe, Marcador, PessoaCarga, PrioridadeTarefa, RegraRecorrencia, ROTULOS_PRIORIDADE } from './tarefas.models';

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
  imports: [FormsModule, RouterLink, SeletorUsuariosComponent, SeletorMarcadoresComponent, SeletorRecorrenciaComponent, CabecalhoTarefasComponent, AgendaPessoaComponent],
  template: `
    <app-cabecalho-tarefas titulo="Nova tarefa" [trilha]="[{ rotulo: 'Nova tarefa' }]"
                           descricao="Quem recebe a tarefa é avisado na caixa de mensagens e por e-mail." />

    <div class="nova-tarefa-colunas">
    <form class="cartao-dados formulario-tarefa" (submit)="$event.preventDefault(); salvar()">
      <div class="corpo">
        <!-- 1. O que precisa ser feito -->
        <section class="secao-tarefa">
          <h3><span>1</span> O que precisa ser feito</h3>
          <div class="grade-formulario">
            <div class="ocupa-duas"><label for="nt-titulo">Título *</label>
              <input id="nt-titulo" name="titulo" maxlength="200" required [(ngModel)]="titulo" placeholder="Ex.: Atualizar a política de senhas" /></div>
            <div class="ocupa-duas"><label for="nt-descricao">Descrição</label>
              <textarea id="nt-descricao" name="descricao" maxlength="20000" rows="4" [(ngModel)]="descricao"
                        placeholder="Contexto, entregáveis esperados, links"></textarea></div>
          </div>
        </section>

        <!-- 2. Onde, quando e com que urgência -->
        <section class="secao-tarefa">
          <h3><span>2</span> Equipe, prioridade e prazo</h3>
          <div class="grade-formulario tres-colunas">
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
          </div>
          <app-seletor-recorrencia [prazo]="prazo" [regra]="recorrencia()" (regraChange)="recorrencia.set($event)" />
        </section>

        <!-- 3. Quem faz -->
        <section class="secao-tarefa">
          <h3><span>3</span> Quem vai fazer</h3>
          <div class="grade-formulario">
            <div class="ocupa-duas">
              <label for="nt-responsaveis">Responsáveis</label>
              @if (equipeId()) {
                <!-- Na equipe: lista dos membros com a carga de cada um; marque um ou mais (o primeiro marcado é o principal) -->
                <div class="lista-carga" role="group" aria-label="Responsáveis">
                  @for (p of pessoas(); track p.id) {
                    <label class="opcao-carga" [class.selecionada]="responsaveisIds().includes(p.id)">
                      <input type="checkbox" name="responsavel-{{ p.id }}" [checked]="responsaveisIds().includes(p.id)" (change)="alternarResponsavel(p.id)" />
                      <span class="nome">{{ p.nome }}</span>
                      <span class="faixa-carga" [attr.data-faixa]="p.faixa">{{ p.faixa }}</span>
                      <small>{{ p.a_fazer }} a fazer · {{ p.em_andamento }} em andamento{{ p.atrasadas ? ' · ' + p.atrasadas + ' atrasada(s)' : '' }}</small>
                    </label>
                  }
                </div>
                @for (p of sobrecarregados(); track p.id) {
                  <p class="aviso-formulario">{{ p.nome }} está com sobrecarga crítica. Considere outra pessoa ou um prazo maior.</p>
                }
              } @else {
                <app-seletor-usuarios idCampo="nt-responsaveis" [selecionados]="responsaveis" (selecionadosChange)="aoMudarResponsaveis($event)"
                                      [fonte]="api.opcoesPessoas" textoAjuda="Um ou mais responsáveis, com os mesmos poderes. Vazio: você mesmo" />
              }
            </div>
            @if (equipeId()) {
              <div class="ocupa-duas"><label for="nt-marcadores">Marcadores</label>
                <app-seletor-marcadores [equipeId]="equipeId()" [valor]="marcadores()" [podeGerir]="equipeLiderada()"
                                        (valorChange)="marcadores.set($event)" />
                <small class="dica-formulario">Clique para ver os mais usados ou digite para buscar; se não existir, crie na hora.</small></div>
            }
          </div>
        </section>

        <!-- 4. Anexos -->
        <section class="secao-tarefa">
          <h3><span>4</span> Anexos <small>(opcional, até 5)</small></h3>
          <label class="acao-secundaria botao-arquivo" for="nt-anexos">📎 Anexar documentos
            <input id="nt-anexos" type="file" multiple accept=".pdf,.docx,.xlsx,.pptx,.odt,.ods,.odp,.doc,.xls,.ppt,.png,.jpg,.jpeg,.txt,.csv" (change)="escolherArquivos($event)" /></label>
          @if (arquivos().length) {
            <ul class="arquivos-escolhidos">
              @for (a of arquivos(); track $index) {
                <li>📄 {{ a.name }} <small>{{ tamanhoLegivel(a.size) }}</small>
                  <button type="button" class="link-simples" [attr.aria-label]="'Remover ' + a.name" (click)="removerArquivo($index)">×</button></li>
              }
            </ul>
          }
          <small class="dica-formulario">Ficam na linha do tempo da tarefa, no evento "Tarefa criada". Quem recebe a tarefa já os vê.</small>
        </section>

        <div class="acoes-formulario acoes-fixas">
          <a class="acao-secundaria" routerLink="/tarefas">Cancelar</a>
          <button type="submit" class="acao-primaria" [disabled]="!titulo.trim() || !prazo || salvando()">Criar tarefa</button>
        </div>
      </div>
    </form>

    <!-- Agenda de quem recebe: muda conforme o último responsável escolhido -->
    <aside class="cartao-dados agenda-nova-tarefa">
      <header><h2>Agenda de quem recebe</h2><small>Escolha os responsáveis para ver a carga e as tarefas da pessoa.</small></header>
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
  protected responsaveis: OpcaoUsuario[] = [];
  protected readonly equipes = signal<Equipe[]>([]);
  protected readonly equipeId = signal('');
  protected readonly pessoas = signal<PessoaCarga[]>([]);
  /** Responsáveis marcados na lista da equipe, na ordem da marcação (o primeiro é o principal). */
  protected readonly responsaveisIds = signal<number[]>([]);
  protected readonly marcadores = signal<Marcador[]>([]);
  protected readonly equipeLiderada = computed(() => !!this.equipes().find((e) => e.id === this.equipeId())?.lider);
  protected readonly salvando = signal(false);
  /** Regra de repetição (nula = não repete). */
  protected readonly recorrencia = signal<RegraRecorrencia | null>(null);
  protected readonly arquivos = signal<File[]>([]);
  protected readonly sobrecarregados = computed(() => this.pessoas().filter((p) => this.responsaveisIds().includes(p.id) && p.faixa === 'Sobrecarga crítica'));
  /** Pessoa cuja agenda aparece à direita (último responsável incluído). */
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
    this.pessoas.set([]);
    this.responsaveisIds.set([]);
    this.marcadores.set([]);
    if (!id) return;
    this.api.pessoas(id).subscribe({
      next: (lista) => {
        this.pessoas.set(lista);
        // Padrão: o próprio usuário, se for da equipe
        const eu = this.autenticacao.usuario()?.id;
        this.responsaveisIds.set(lista.some((p) => p.id === eu) ? [eu!] : []);
        this.pessoaAgenda.set(this.responsaveisIds()[0] ?? null);
      },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  /** Marca ou desmarca um responsável na lista da equipe; a agenda mostra o último marcado. */
  protected alternarResponsavel(id: number): void {
    const marcado = this.responsaveisIds().includes(id);
    this.responsaveisIds.update((l) => (marcado ? l.filter((x) => x !== id) : [...l, id]));
    this.pessoaAgenda.set(marcado ? (this.responsaveisIds().at(-1) ?? null) : id);
  }

  /** Responsáveis fora de equipe (seletor de busca): ao incluir alguém, a agenda passa a ser a dele. */
  protected aoMudarResponsaveis(lista: OpcaoUsuario[]): void {
    const novo = lista.find((p) => !this.responsaveis.some((x) => x.id === p.id));
    this.responsaveis = lista;
    this.pessoaAgenda.set(novo ? novo.id : (lista.at(-1)?.id ?? null));
  }

  /** Soma os arquivos escolhidos aos anteriores (máximo 5, como na API). */
  protected escolherArquivos(evento: Event): void {
    const entrada = evento.target as HTMLInputElement;
    const todos = [...this.arquivos(), ...Array.from(entrada.files ?? [])];
    if (todos.length > 5) this.dialogos.avisar('Muitos arquivos', 'Anexe no máximo 5 arquivos.');
    this.arquivos.set(todos.slice(0, 5));
    entrada.value = '';
  }

  protected removerArquivo(indice: number): void {
    this.arquivos.update((l) => l.filter((_, i) => i !== indice));
  }

  protected tamanhoLegivel(bytes: number): string {
    return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  protected salvar(): void {
    const equipe = this.equipeId() || null;
    const responsaveis = equipe ? this.responsaveisIds() : this.responsaveis.map((p) => p.id);
    this.salvando.set(true);
    const dados = {
      titulo: this.titulo.trim(), descricao: this.descricao, prazo: new Date(this.prazo).toISOString(), prioridade: this.prioridade,
      equipe_id: equipe, responsaveis_ids: responsaveis, marcadores_ids: this.marcadores().map((m) => m.id), recorrencia: this.recorrencia(),
    };
    const chamada = this.arquivos().length ? this.api.criarComAnexos(dados, this.arquivos()) : this.api.criar(dados);
    this.dialogos.executar(chamada, this.arquivos().length ? 'Criando a tarefa e enviando os anexos…' : 'Criando a tarefa…').subscribe({
      // Abre a tela da tarefa nova (no lugar do formulário, para o "voltar" não reabrir a criação)
      next: (t) => void this.roteador.navigate(['/tarefas', t.numero], { replaceUrl: true }),
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e); },
    });
  }
}
