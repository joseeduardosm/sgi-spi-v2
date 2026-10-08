// Criado por José Eduardo Santana Martins
// Este arquivo serve para criar e configurar uma equipe de tarefas: nome, equipe pai, liderança, membros e marcadores.

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoTarefasComponent } from './cabecalho-tarefas.component';
import { TarefasApiService } from './tarefas-api.service';
import { classeMarcador, PALETA_MARCADORES } from './marcadores.paleta';
import { Equipe, Marcador, Pessoa } from './tarefas.models';


function opcao(p: Pessoa): OpcaoUsuario {
  return { id: p.id, login: p.login, nome_completo: p.nome, cargo: '', ativo: true };
}

@Component({
  selector: 'app-configuracao-equipe',
  imports: [FormsModule, RouterLink, SeletorUsuariosComponent, CabecalhoTarefasComponent],
  template: `
    <app-cabecalho-tarefas [titulo]="nova() ? 'Nova equipe' : 'Configurar ' + nome"
                           [trilha]="[{ rotulo: 'Equipes', rota: '/tarefas/equipes' }, { rotulo: nova() ? 'Nova equipe' : 'Configurar' }]"
                           descricao="Quem cria a equipe é o dono. Dono e líderes validam as entregas; a liderança de uma equipe vale para as equipes abaixo dela." />

    <form class="cartao-dados formulario-tarefa" (submit)="$event.preventDefault(); salvar()">
      <header><h2>Equipe</h2>@if (dono()) { <small>Dono: {{ dono()!.nome }}</small> }</header>
      <div class="corpo">
        <div class="grade-formulario">
          <div><label for="eq-nome">Nome *</label><input id="eq-nome" name="nome" maxlength="150" [(ngModel)]="nome" /></div>
          <div><label for="eq-pai">Dentro de (equipe pai)</label>
            <select id="eq-pai" name="pai" [(ngModel)]="paiId">
              <option value="">Nenhuma (equipe principal)</option>
              @for (e of possiveisPais(); track e.id) { <option [value]="e.id">{{ e.nome }}</option> }
            </select></div>
          <div class="ocupa-duas"><label for="eq-lideres">Líderes</label>
            <app-seletor-usuarios idCampo="eq-lideres" [(selecionados)]="lideres" [fonte]="api.opcoesPessoas" textoAjuda="Quem valida as entregas com o dono" /></div>
          <div class="ocupa-duas"><label for="eq-membros">Membros</label>
            <app-seletor-usuarios idCampo="eq-membros" [(selecionados)]="membros" [fonte]="api.opcoesPessoas" textoAjuda="Quem recebe tarefas da equipe" /></div>
        </div>
        <div class="acoes-formulario">
          @if (!nova()) { <button type="button" class="acao-secundaria botao-excluir" (click)="excluir()">Desativar equipe</button> }
          <a class="acao-secundaria" routerLink="/tarefas/equipes">Cancelar</a>
          <button type="submit" class="acao-primaria" [disabled]="!nome.trim()">{{ nova() ? 'Criar equipe' : 'Salvar' }}</button>
        </div>
      </div>
    </form>

    @if (!nova()) {
      <section class="cartao-dados formulario-tarefa">
        <header><h2>Estágios do quadro</h2><small>As colunas da equipe. Cada estágio pertence a uma situação do pipeline (a validação e os relatórios seguem a situação). A situação "Em validação" e a "Concluída" têm um estágio cada.</small></header>
        <div class="corpo">
          <div class="lista-estagios">
            @for (e of estagiosEdicao(); track $index; let i = $index) {
              <div class="linha-estagio">
                <span class="amostra-estagio" [style.background]="paleta[e.cor_indice].fundo" [style.border-color]="paleta[e.cor_indice].borda" aria-hidden="true"></span>
                <input [name]="'est-nome-' + i" maxlength="80" aria-label="Nome do estágio" [(ngModel)]="e.nome" />
                <select [name]="'est-cat-' + i" aria-label="Situação do estágio" [(ngModel)]="e.categoria">
                  @for (c of categorias; track c[0]) { <option [value]="c[0]">{{ c[1] }}</option> }
                </select>
                <select [name]="'est-cor-' + i" aria-label="Cor do estágio" [(ngModel)]="e.cor_indice">
                  @for (c of paleta; track $index; let k = $index) { <option [ngValue]="k">Cor {{ k + 1 }}</option> }
                </select>
                <button type="button" class="botao-icone" aria-label="Subir" [disabled]="i === 0" (click)="moverEstagio(i, -1)">↑</button>
                <button type="button" class="botao-icone" aria-label="Descer" [disabled]="i === estagiosEdicao().length - 1" (click)="moverEstagio(i, 1)">↓</button>
                <button type="button" class="botao-icone" aria-label="Excluir estágio" (click)="removerEstagio(i)">×</button>
              </div>
            }
          </div>
          <div class="acoes-formulario">
            <button type="button" class="acao-secundaria" (click)="adicionarEstagio()">+ Estágio</button>
            <button type="button" class="acao-primaria" (click)="salvarEstagios()">Salvar estágios</button>
          </div>
        </div>
      </section>

      <section class="cartao-dados formulario-tarefa">
        <header><h2>Marcadores</h2><small>Etiquetas da equipe. Membros e liderança criam na hora, ao marcar uma tarefa; aqui a liderança troca a cor, renomeia e exclui.</small></header>
        <div class="corpo">
          <div class="marcadores lista-marcadores">
            @for (m of marcadores(); track m.id) {
              <button type="button" [class]="classeMarcador(m.cor_indice)" [attr.aria-expanded]="editando()?.id === m.id" (click)="editar(m)">{{ m.nome }}@if (!m.equipe_id) { <small>(global)</small> }</button>
            } @empty { <span class="dica-formulario">Nenhum marcador.</span> }
          </div>
          @if (editando(); as e) {
            <div class="edicao-marcador">
              <div class="cores" role="radiogroup" aria-label="Cor">
                @for (c of paleta; track $index; let i = $index) {
                  <button type="button" class="cor" [class.atual]="i === e.cor_indice" [style.background]="c.fundo" [style.border-color]="c.borda"
                          [attr.aria-label]="'Cor ' + (i + 1)" (click)="trocarCor(e, i)"></button>
                }
              </div>
              @if (e.equipe_id) {
                <div class="renomear">
                  <input name="nome-marcador" maxlength="120" aria-label="Nome do marcador" [(ngModel)]="nomeEditado" />
                  <button type="button" class="acao-secundaria" [disabled]="!nomeEditado.trim() || nomeEditado.trim() === e.nome" (click)="renomear(e)">Renomear</button>
                  <button type="button" class="acao-recusar" (click)="excluirMarcador(e)">Excluir</button>
                </div>
              }
            </div>
          }
          <form class="novo-marcador" (submit)="$event.preventDefault(); criarMarcador()">
            <input name="marcador" maxlength="120" placeholder="Novo marcador" aria-label="Nome do marcador" [(ngModel)]="novoMarcador" />
            <button type="submit" class="acao-secundaria" [disabled]="!novoMarcador.trim()">Incluir</button>
          </form>
        </div>
      </section>
    }
  `,
})
export class ConfiguracaoEquipeComponent implements OnInit {
  protected readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  protected readonly paleta = PALETA_MARCADORES;
  protected readonly categorias: [string, string][] = [['a_fazer', 'A fazer'], ['em_andamento', 'Em andamento'], ['em_validacao', 'Em validação'], ['concluida', 'Concluída']];
  protected readonly estagiosEdicao = signal<{ id: string | null; nome: string; categoria: string; cor_indice: number }[]>([]);
  protected readonly classeMarcador = classeMarcador;
  protected readonly editando = signal<Marcador | null>(null);
  protected nomeEditado = '';

  protected readonly nova = signal(true);
  private id = '';
  protected nome = '';
  protected paiId = '';
  protected lideres: OpcaoUsuario[] = [];
  protected membros: OpcaoUsuario[] = [];
  protected readonly dono = signal<Pessoa | null>(null);
  protected readonly possiveisPais = signal<Equipe[]>([]);
  protected readonly marcadores = signal<Marcador[]>([]);
  protected novoMarcador = '';

  ngOnInit(): void {
    this.id = this.rota.snapshot.paramMap.get('equipeId') ?? 'nova';
    this.nova.set(this.id === 'nova');
    this.api.equipes().subscribe({
      next: (lista) => {
        // A equipe não pode ficar dentro dela mesma nem de uma subequipe sua
        const abaixo = new Set<string>([this.id]);
        let mudou = true;
        while (mudou) {
          mudou = false;
          for (const e of lista) if (e.equipe_pai_id && abaixo.has(e.equipe_pai_id) && !abaixo.has(e.id)) { abaixo.add(e.id); mudou = true; }
        }
        this.possiveisPais.set(lista.filter((e) => !abaixo.has(e.id)).sort((a, b) => a.nome.localeCompare(b.nome)));
        if (this.nova()) return;
        const e = lista.find((x) => x.id === this.id);
        if (!e) { this.dialogos.avisar('Equipe não encontrada', 'A equipe não existe ou você não tem acesso a ela.'); return; }
        this.nome = e.nome;
        this.paiId = e.equipe_pai_id ?? '';
        this.dono.set(e.dono);
        this.lideres = e.lideres.map(opcao);
        this.membros = e.membros.map(opcao);
        this.carregarMarcadores();
        this.carregarEstagios();
      },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected salvar(): void {
    const dados = { nome: this.nome.trim(), equipe_pai_id: this.paiId || null, lideres_ids: this.lideres.map((p) => p.id), membros_ids: this.membros.map((p) => p.id) };
    this.dialogos.executar(this.api.salvarEquipe(dados, this.nova() ? undefined : this.id)).subscribe({
      next: (e) => void this.roteador.navigate(this.nova() ? ['/tarefas/equipes', e.id, 'configurar'] : ['/tarefas/equipes']),
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected async excluir(): Promise<void> {
    if (!(await this.dialogos.confirmar({ titulo: 'Desativar equipe', mensagem: `A equipe "${this.nome}" deixa de aparecer. Só é possível sem tarefas em aberto.`, rotuloConfirmar: 'Desativar', segundos: 3 }))) return;
    this.dialogos.executar(this.api.excluirEquipe(this.id)).subscribe({
      next: () => void this.roteador.navigate(['/tarefas/equipes']),
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  private carregarMarcadores(): void {
    this.api.marcadores(this.id).subscribe({ next: (m) => this.marcadores.set(m), error: (e) => this.dialogos.mostrarErro(e) });
  }

  private carregarEstagios(): void {
    this.api.estagios(this.id).subscribe({
      next: (l) => this.estagiosEdicao.set(l.map((e) => ({ id: e.id, nome: e.nome, categoria: e.categoria, cor_indice: e.cor_indice }))),
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected adicionarEstagio(): void {
    // Novo estágio entra antes da validação, como "Em andamento" (a liderança escolhe a situação)
    const lista = [...this.estagiosEdicao()];
    const posicao = lista.findIndex((e) => e.categoria === 'em_validacao');
    lista.splice(posicao < 0 ? lista.length : posicao, 0, { id: null, nome: '', categoria: 'em_andamento', cor_indice: 3 });
    this.estagiosEdicao.set(lista);
  }

  protected moverEstagio(i: number, delta: number): void {
    const lista = [...this.estagiosEdicao()];
    [lista[i], lista[i + delta]] = [lista[i + delta], lista[i]];
    this.estagiosEdicao.set(lista);
  }

  protected removerEstagio(i: number): void {
    this.estagiosEdicao.update((l) => l.filter((_, k) => k !== i));
  }

  protected salvarEstagios(): void {
    this.api.gravarEstagios(this.id, this.estagiosEdicao()).subscribe({
      next: (l) => { this.estagiosEdicao.set(l.map((e) => ({ id: e.id, nome: e.nome, categoria: e.categoria, cor_indice: e.cor_indice }))); this.dialogos.avisar('Estágios salvos', 'As colunas do quadro da equipe foram atualizadas.'); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar os estágios'),
    });
  }

  protected criarMarcador(): void {
    this.api.criarMarcador(this.id, this.novoMarcador.trim()).subscribe({
      next: () => { this.novoMarcador = ''; this.carregarMarcadores(); },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  /** Abre (ou fecha) a edição de cor e nome do marcador clicado. */
  protected editar(m: Marcador): void {
    this.nomeEditado = m.nome;
    this.editando.set(this.editando()?.id === m.id ? null : m);
  }

  protected trocarCor(m: Marcador, indice: number): void {
    this.api.alterarMarcador(this.id, m.id, m.nome, indice).subscribe({
      next: (n) => { this.editando.set(n); this.carregarMarcadores(); }, error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected renomear(m: Marcador): void {
    this.api.alterarMarcador(this.id, m.id, this.nomeEditado.trim(), m.cor_indice).subscribe({
      next: (n) => { this.editando.set(n); this.carregarMarcadores(); }, error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected excluirMarcador(m: Marcador): void {
    this.api.excluirMarcador(m.id).subscribe({
      next: () => { this.editando.set(null); this.carregarMarcadores(); }, error: (e) => this.dialogos.mostrarErro(e),
    });
  }
}
