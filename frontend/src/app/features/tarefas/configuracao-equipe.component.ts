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
import { Equipe, Marcador, Pessoa } from './tarefas.models';

const CORES = ['#c82331', '#e3b341', '#2e8b57', '#2f6fb5', '#6b3f99', '#5a6673', '#d9731a', '#1f9aa8'];

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
        <header><h2>Marcadores</h2><small>Etiquetas da equipe para organizar e filtrar as tarefas (criadas pela liderança).</small></header>
        <div class="corpo">
          <div class="marcadores lista-marcadores">
            @for (m of marcadores(); track m.id) {
              <span class="marcador-tarefa" [style.--cor]="m.cor">{{ m.nome }}
                @if (m.equipe_id) { <button type="button" class="link-simples" [attr.aria-label]="'Excluir ' + m.nome" (click)="excluirMarcador(m)">×</button> }
                @else { <small>(global)</small> }
              </span>
            } @empty { <span class="dica-formulario">Nenhum marcador.</span> }
          </div>
          <form class="novo-marcador" (submit)="$event.preventDefault(); criarMarcador()">
            <input name="marcador" maxlength="60" placeholder="Novo marcador" aria-label="Nome do marcador" [(ngModel)]="novoMarcador" />
            <div class="cores" role="radiogroup" aria-label="Cor">
              @for (c of cores; track c) {
                <button type="button" class="cor" [style.background]="c" [class.ativa]="cor === c" [attr.aria-label]="'Cor ' + c" (click)="cor = c"></button>
              }
            </div>
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
  protected readonly cores = CORES;

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
  protected cor = CORES[3];

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

  protected criarMarcador(): void {
    this.api.criarMarcador(this.id, this.novoMarcador.trim(), this.cor).subscribe({
      next: () => { this.novoMarcador = ''; this.carregarMarcadores(); },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected excluirMarcador(m: Marcador): void {
    this.api.excluirMarcador(m.id).subscribe({ next: () => this.carregarMarcadores(), error: (e) => this.dialogos.mostrarErro(e) });
  }
}
