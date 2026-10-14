// Criado por José Eduardo Santana Martins
// Este arquivo serve para a árvore de localizações do Patrimônio (prédio, andar, lado, sala): setor e responsável de cada sala, novas salas e inativação.
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { classeMarcador } from '../tarefas/marcadores.paleta';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { Localizacao } from './patrimonio.models';

interface Linha { no: Localizacao; nivel: number; filhos: number }

/** A árvore sai da lista plana (`pai_id`). Só o controle total cadastra salas e altera setor e responsável de salas que já os têm. */
@Component({
  selector: 'app-localizacoes',
  imports: [FormsModule, CabecalhoPatrimonioComponent, SeletorUsuariosComponent],
  template: `
    <app-cabecalho-patrimonio titulo="Locais" descricao="Prédio SPI › andar › lado › sala. O código da sala junta andar, lado e número (05A03, 00B15, -1A01)." />
    <section class="painel-gestao patrimonio">
      <div class="pat-barra">
        <div class="campo pat-busca"><label for="lc-busca">Pesquisar sala</label>
          <input id="lc-busca" type="search" name="busca" autocomplete="off" placeholder="Código, setor ou responsável" [ngModel]="busca()" (ngModelChange)="busca.set($event)" /></div>
      </div>
      <ul class="pat-arvore">
        @for (l of linhas(); track l.no.id) {
          <li [style.padding-left.px]="l.nivel * 18" [class.inativa]="!l.no.ativo">
            <div class="pat-no">
              @if (l.filhos) { <button type="button" class="pat-alternar" [attr.aria-expanded]="abertos().has(l.no.id)" [attr.aria-label]="'Abrir ' + l.no.nome" (click)="alternar(l.no.id)">{{ abertos().has(l.no.id) ? '▾' : '▸' }}</button> } @else { <span class="pat-alternar"></span> }
              <div class="pat-no-texto"><strong>{{ l.no.tipo === 'sala' ? (l.no.nome !== l.no.codigo ? l.no.codigo + ' — ' + l.no.nome : l.no.codigo) : l.no.nome }}</strong>
                @if (l.no.tipo === 'sala') {
                  <small>{{ l.no.setor_nome ?? 'Sem setor' }} · {{ l.no.responsavel_nome ?? 'sem responsável' }} · {{ l.no.total_bens }} bem(ns)</small>
                  @if (l.no.deposito_inservivel) { <span [class]="marcador(2)">Depósito inservível</span> }
                  @if (!l.no.ativo) { <span [class]="marcador(0)">Inativa</span> }
                }</div>
              <div class="pat-acoes">
                @if (l.no.tipo === 'andar' && estado.podeAdministrar()) { <button type="button" class="acao-secundaria acao-pequena" (click)="novaAreaComum(l.no)" title="Hall dos elevadores, copa, escada...: fora da numeração A/B">+ Área comum</button> }
                @if (l.no.tipo === 'lado' && estado.podeAdministrar()) { <button type="button" class="acao-secundaria acao-pequena" (click)="novaSala(l.no)">+ Sala</button> }
                @if (l.no.tipo === 'sala') {
                  @if (estado.podeOperar()) { <button type="button" class="acao-secundaria acao-pequena" (click)="editar(l.no)">Setor e responsável</button> }
                  @if (estado.podeAdministrar()) {
                    <button type="button" class="acao-secundaria acao-pequena" (click)="inativar(l.no)">{{ l.no.ativo ? 'Inativar' : 'Reativar' }}</button>
                    <button type="button" class="acao-recusar acao-pequena" (click)="excluir(l.no)">Excluir</button>
                  }
                }
              </div>
            </div>
            @if (emEdicao()?.id === l.no.id) {
              <div class="pat-painel-acao">
                <strong>Sala {{ l.no.codigo }}</strong>
                <label for="lc-setor">Setor</label>
                <select id="lc-setor" name="setor" [(ngModel)]="setorId"><option [ngValue]="null">Sem setor</option>@for (s of setores(); track s.id) { <option [ngValue]="s.id">{{ s.nome }}</option> }</select>
                <label>Responsável (os bens da sala passam a ter este responsável)</label>
                <app-seletor-usuarios [fonte]="fonteUsuarios" [multiplo]="false" [(selecionados)]="responsavel" idCampo="lc-responsavel" />
                <div class="pat-acoes"><button type="button" class="acao-secundaria" (click)="emEdicao.set(null)">Cancelar</button><button type="button" class="acao-primaria" (click)="salvar(l.no)">Salvar</button></div>
              </div>
            }
          </li>
        } @empty { <li class="estado-vazio">Nenhuma localização.</li> }
      </ul>
    </section>
  `,
})
export class LocalizacoesComponent implements OnInit {
  private readonly api = inject(PatrimonioApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(PatrimonioEstadoService);
  protected readonly abertos = signal<Set<string>>(new Set());
  protected readonly busca = signal('');
  protected readonly emEdicao = signal<Localizacao | null>(null);
  protected readonly setores = signal<{ id: number; nome: string }[]>([]);
  protected readonly responsavel = signal<OpcaoUsuario[]>([]);
  protected setorId: number | null = null;
  protected readonly marcador = classeMarcador;
  protected readonly fonteUsuarios = (busca: string) => this.api.opcoesUsuarios(busca);

  /** Linhas visíveis em profundidade; com pesquisa, só as salas que casam (já abertas). */
  protected readonly linhas = computed<Linha[]>(() => {
    const todos = this.estado.localizacoes();
    const porPai = new Map<string | null, Localizacao[]>();
    for (const l of todos) porPai.set(l.pai_id, [...(porPai.get(l.pai_id) ?? []), l]);
    const termo = this.busca().trim().toLowerCase();
    if (termo) {
      return todos.filter((l) => l.tipo === 'sala' && `${l.codigo} ${l.setor_nome ?? ''} ${l.responsavel_nome ?? ''}`.toLowerCase().includes(termo)).map((no) => ({ no, nivel: 0, filhos: 0 }));
    }
    const saida: Linha[] = [];
    const visitar = (pai: string | null, nivel: number) => {
      for (const no of porPai.get(pai) ?? []) {
        const filhos = porPai.get(no.id)?.length ?? 0;
        saida.push({ no, nivel, filhos });
        if (filhos && this.abertos().has(no.id)) visitar(no.id, nivel + 1);
      }
    };
    visitar(null, 0);
    return saida;
  });

  ngOnInit(): void {
    void this.estado.carregar().then(() => {
      const raiz = this.estado.localizacoes().find((l) => l.tipo === 'predio');
      if (raiz) this.abertos.set(new Set([raiz.id]));
    });
  }

  protected alternar(id: string): void {
    this.abertos.update((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  protected editar(sala: Localizacao): void {
    this.emEdicao.set(sala);
    this.setorId = sala.setor_id;
    this.responsavel.set(sala.responsavel_id ? [{ id: sala.responsavel_id, login: '', nome_completo: sala.responsavel_nome ?? '', cargo: '', ativo: true }] : []);
    this.api.opcoesSetores().subscribe((s) => this.setores.set(s));
  }

  protected salvar(sala: Localizacao): void {
    this.api.dadosSala(sala.id, this.setorId, this.responsavel()[0]?.id ?? null).subscribe({
      next: () => { this.emEdicao.set(null); void this.estado.carregar(true); }, error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar'),
    });
  }

  protected novaAreaComum(andar: Localizacao): void {
    const nome = window.prompt(`Nome da área comum no ${andar.nome} (ex.: Hall dos elevadores):`, 'Hall dos elevadores')?.trim();
    if (!nome) return;
    const sigla = (window.prompt('Sigla do código (1 a 4 letras; H para hall, ex.: 05H):', 'H') ?? '').trim().toUpperCase();
    if (!/^[A-Z]{1,4}$/.test(sigla)) return;
    this.api.criarAreaComum(andar.id, nome, sigla).subscribe({ next: () => void this.estado.carregar(true), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar a área comum') });
  }

  protected novaSala(lado: Localizacao): void {
    const numero = Number(window.prompt(`Número da nova sala no lado ${lado.lado} do andar ${lado.andar} (1 a 99):`)?.trim());
    if (!Number.isInteger(numero) || numero < 1 || numero > 99) return;
    this.api.criarSala(lado.id, numero).subscribe({ next: () => void this.estado.carregar(true), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar a sala') });
  }

  protected inativar(sala: Localizacao): void {
    this.api.atualizarLocalizacao(sala.id, { ativo: !sala.ativo }).subscribe({ next: () => void this.estado.carregar(true), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível alterar') });
  }

  protected async excluir(sala: Localizacao): Promise<void> {
    if (!(await this.dialogos.confirmar({ titulo: `Excluir a sala ${sala.codigo}?`, mensagem: 'Sala com bens vinculados não pode ser excluída, só inativada.', rotuloConfirmar: 'Excluir', segundos: 3 }))) return;
    this.api.excluirSala(sala.id).subscribe({ next: () => void this.estado.carregar(true), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir') });
  }
}
