// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela de cargos do Módulo RH: vagas por setor, quem as ocupa, exoneração e reconciliação dos cadastros antigos.

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { Setor, SetoresApiService } from '../setores/setores-api.service';
import { UsuariosApiService } from '../usuarios/usuarios-api.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { RhApiService } from './rh-api.service';
import { RhCargosApiService } from './rh-cargos-api.service';
import { Cargo, GravacaoCargo, MotivoFim, PendenciaCargo, ROTULOS_MOTIVO_FIM, TipoCargo } from './rh-cargos.models';

type Aba = 'cargos' | 'reconciliar';

/** Formulário de vagas (novo ou edição). */
interface EdicaoCargo { id?: number; setor_id: number; tipo_id: number; grupo: number | null; nivel: number | null; denominacao: string; quantidade: number; ativo: boolean }

/**
 * Cargos do RH. Cada linha é **uma posição (vaga)** de um setor; quem a ocupa passa a fazer parte do setor pelo cargo. O RH cria vagas (em lote), aloca pessoas,
 * registra troca, exoneração ou dispensa e reconcilia quem ainda tem cargo só em texto livre. Tudo vai para o histórico funcional (quem fez e quando).
 */
@Component({
  selector: 'app-cargos',
  imports: [FormsModule, RouterLink, CabecalhoRhComponent, EsqueletoComponent, SeletorUsuariosComponent],
  host: { '(document:keydown.escape)': 'fecharJanelas()' },
  template: `
    <app-cabecalho-rh titulo="Cargos" [trilha]="['Cargos']" descricao="Cada linha é uma vaga de um setor. Quem ocupa o cargo passa a fazer parte do setor por ele." />

    <div class="abas" role="tablist">
      <button type="button" role="tab" [class.ativa]="aba() === 'cargos'" [attr.aria-selected]="aba() === 'cargos'" (click)="aba.set('cargos')">Cargos e vagas <span class="contador-aba">{{ cargos().length }}</span></button>
      <button type="button" role="tab" [class.ativa]="aba() === 'reconciliar'" [attr.aria-selected]="aba() === 'reconciliar'" (click)="aba.set('reconciliar')">
        A reconciliar @if (pendencias().length) { <span class="contador-aba destaque">{{ pendencias().length }}</span> }
      </button>
    </div>

    @if (aba() === 'cargos') {
      <section class="painel-gestao" aria-labelledby="titulo-cargos">
        <div class="barra-ferramentas">
          <div>
            <h2 id="titulo-cargos">Cargos e vagas</h2>
            <p>{{ cargos().length }} posição(ões) · {{ vagas() }} vaga(s) em aberto.</p>
          </div>
          @if (gere()) { <div class="acoes-formulario"><button type="button" class="acao-primaria" (click)="novo()"><span>+</span> Novo cargo</button></div> }
        </div>
        <div class="filtros-gestao">
          <input type="search" aria-label="Buscar" placeholder="Buscar por cargo, setor ou pessoa" [(ngModel)]="busca" (ngModelChange)="carregar()" />
          <select aria-label="Setor" [(ngModel)]="filtroSetor" (ngModelChange)="carregar()">
            <option [ngValue]="0">Todos os setores</option>
            @for (s of setores(); track s.id) { <option [ngValue]="s.id">{{ s.nome }}</option> }
          </select>
          <select aria-label="Tipo" [(ngModel)]="filtroTipo" (ngModelChange)="carregar()">
            <option [ngValue]="0">Todos os tipos</option>
            @for (t of tipos(); track t.id) { <option [ngValue]="t.id">{{ t.codigo }}</option> }
          </select>
        </div>
        <div class="chips-filtro" role="group" aria-label="Situação">
          <button type="button" [class.ativo]="situacao === ''" (click)="filtrarSituacao('')">Todos</button>
          <button type="button" [class.ativo]="situacao === 'vago'" (click)="filtrarSituacao('vago')">Vagos</button>
          <button type="button" [class.ativo]="situacao === 'ocupado'" (click)="filtrarSituacao('ocupado')">Ocupados</button>
        </div>
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <thead><tr><th>Setor</th><th>Cargo</th><th>Ocupante</th><th>Desde</th>@if (gere()) { <th class="coluna-acoes">Ações</th> }</tr></thead>
            <tbody>
              @if (carregando()) {
                <tr><td [attr.colspan]="gere() ? 5 : 4"><app-esqueleto tipo="tabela" [colunas]="4" [linhas]="5" /></td></tr>
              }
              @for (c of cargos(); track c.id) {
                <tr>
                  <td>{{ c.setor_nome }}</td>
                  <td><strong>{{ c.denominacao }}</strong><small><span class="texto-codigo">{{ c.classificacao }}</span></small></td>
                  <td>
                    @if (c.ocupante; as o) { <a [routerLink]="['/rh/historico', o.usuario_id]" title="Histórico funcional">{{ o.nome }}</a><small>&#64;{{ o.login }}</small> }
                    @else { <span class="selo-situacao alerta">Vago</span> }
                  </td>
                  <td>{{ c.ocupante ? dataBr(c.ocupante.inicio) : '—' }}@if (c.ocupante?.ato) { <small>{{ c.ocupante?.ato }}</small> }</td>
                  @if (gere()) {
                    <td class="coluna-acoes"><div class="acoes-linha">
                      @if (c.ocupante) { <button type="button" class="acao-secundaria acao-pequena" (click)="abrirVacancia(c)">Vagar</button> }
                      @else { <button type="button" class="acao-secundaria acao-pequena" (click)="abrirOcupacao(c)">Alocar</button> }
                      <button type="button" class="acao-secundaria acao-pequena" (click)="editar(c)">Editar</button>
                      @if (!c.ocupante) { <button type="button" class="acao-secundaria acao-pequena" (click)="excluir(c)">Excluir</button> }
                    </div></td>
                  }
                </tr>
              } @empty {
                @if (!carregando()) { <tr><td class="estado-vazio" [attr.colspan]="gere() ? 5 : 4">Nenhum cargo encontrado.</td></tr> }
              }
            </tbody>
          </table>
        </div>
      </section>
    } @else {
      <section class="painel-gestao" aria-labelledby="titulo-reconciliar">
        <div class="barra-ferramentas">
          <div>
            <h2 id="titulo-reconciliar">Cargos a reconciliar</h2>
            <p>Pessoas com cargo escrito à mão e ainda sem vínculo com um cargo cadastrado. O sistema interpreta o texto (tipo, grupo, nível e denominação), cria o cargo no setor e aloca a pessoa.</p>
          </div>
        </div>
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <thead><tr><th>Pessoa</th><th>Cargo no cadastro</th><th>Departamento no cadastro</th><th>Será criado</th>@if (gere()) { <th class="coluna-acoes">Ações</th> }</tr></thead>
            <tbody>
              @for (p of pendencias(); track p.usuario_id) {
                <tr>
                  <td><strong>{{ p.nome }}</strong><small>&#64;{{ p.login }}</small></td>
                  <td>{{ p.cargo_texto }}</td>
                  <td>{{ p.departamento_texto || '—' }}</td>
                  <td>{{ p.sugestao }} @if (!p.interpretado) { <small>fora do padrão do quadro: entra como "Outros"</small> }</td>
                  @if (gere()) {
                    <td class="coluna-acoes">
                      @if (p.setor_id) { <button type="button" class="acao-secundaria acao-pequena" (click)="vincular(p, p.setor_id)">Criar cargo e vincular</button> }
                      @else {
                        <select [attr.aria-label]="'Setor de ' + p.nome" (change)="vincular(p, +$any($event.target).value)">
                          <option value="">Escolher o setor…</option>
                          @for (s of setores(); track s.id) { <option [value]="s.id">{{ s.nome }}</option> }
                        </select>
                      }
                    </td>
                  }
                </tr>
              } @empty {
                <tr><td class="estado-vazio" [attr.colspan]="gere() ? 5 : 4">Todos os cadastros com cargo já estão vinculados.</td></tr>
              }
            </tbody>
          </table>
        </div>
      </section>
    }

    @if (edicao(); as e) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="edicao.set(null)"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-janela-cargo">
        <header>
          <div><span class="modal-sobretitulo">Cargos</span><h2 id="titulo-janela-cargo">{{ e.id ? 'Editar cargo' : 'Novo cargo (vagas)' }}</h2></div>
          <button type="button" aria-label="Fechar" (click)="edicao.set(null)">×</button>
        </header>
        <form (ngSubmit)="salvar(e)">
          <div class="grade-formulario">
            <div class="ocupa-duas"><label for="cargo-setor">Setor *</label>
              <select id="cargo-setor" name="setor" [(ngModel)]="e.setor_id" [disabled]="!!e.id && !!cargoAberto()?.ocupante">
                <option [ngValue]="0">Escolher…</option>
                @for (s of setores(); track s.id) { <option [ngValue]="s.id">{{ s.nome }}</option> }
              </select></div>
            <div><label for="cargo-tipo">Tipo *</label>
              <select id="cargo-tipo" name="tipo" [(ngModel)]="e.tipo_id">
                @for (t of tipos(); track t.id) { <option [ngValue]="t.id">{{ t.nome }}</option> }
              </select></div>
            <div><label for="cargo-grupo">Grupo</label>
              <select id="cargo-grupo" name="grupo" [(ngModel)]="e.grupo">
                <option [ngValue]="null">—</option><option [ngValue]="1">1 (direção e chefia)</option><option [ngValue]="2">2 (assessoria)</option>
              </select></div>
            <div><label for="cargo-nivel">Nível</label>
              <input id="cargo-nivel" name="nivel" type="number" min="1" max="18" inputmode="numeric" placeholder="Ex.: 16" [(ngModel)]="e.nivel" /></div>
            @if (!e.id) { <div><label for="cargo-quantidade">Quantidade de vagas</label><input id="cargo-quantidade" name="quantidade" type="number" min="1" max="50" [(ngModel)]="e.quantidade" /></div> }
            <div class="ocupa-duas"><label for="cargo-denominacao">Denominação *</label>
              <input id="cargo-denominacao" name="denominacao" maxlength="200" placeholder="Ex.: Assessor Especial IV" [(ngModel)]="e.denominacao" /></div>
          </div>
          @if (e.id) { <div class="linha-caixas"><label><input type="checkbox" name="ativo" [(ngModel)]="e.ativo" /> Ativo</label></div> }
          <p class="dica-formulario">CCESP e FCESP precisam de grupo e nível (ex.: grupo 2, nível 16 = "FCESP 2.16"). Cargos do tipo Outros ficam sem classificação.</p>
          <footer>
            <button type="button" class="acao-secundaria" (click)="edicao.set(null)">Cancelar</button>
            <button type="submit" class="acao-primaria" [disabled]="!e.setor_id || !e.denominacao.trim()">Salvar</button>
          </footer>
        </form>
      </section>
    }

    @if (ocupando(); as c) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="ocupando.set(null)"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-janela-ocupar">
        <header>
          <div><span class="modal-sobretitulo">{{ c.setor_nome }}</span><h2 id="titulo-janela-ocupar">Alocar pessoa em {{ c.rotulo }}</h2></div>
          <button type="button" aria-label="Fechar" (click)="ocupando.set(null)">×</button>
        </header>
        <form (ngSubmit)="alocar(c)">
          <div class="grade-formulario">
            <div class="ocupa-duas"><label for="ocupar-pessoa">Pessoa *</label>
              <app-seletor-usuarios idCampo="ocupar-pessoa" [multiplo]="false" [(selecionados)]="pessoa" [fonte]="usuarios.opcoes" textoAjuda="Pesquisar pessoa" /></div>
            <div><label for="ocupar-inicio">Data da posse</label><input id="ocupar-inicio" name="inicio" type="date" [(ngModel)]="inicio" /></div>
            <div><label for="ocupar-ato">Ato (resolução, portaria...)</label><input id="ocupar-ato" name="ato" maxlength="200" placeholder="Ex.: Resolução SPI 12/2026" [(ngModel)]="ato" /></div>
          </div>
          <p class="dica-formulario">Se a pessoa já ocupa outro cargo, aquele é encerrado como troca. Ela passa a fazer parte do setor do cargo e o fato vai para o histórico dela.</p>
          <footer>
            <button type="button" class="acao-secundaria" (click)="ocupando.set(null)">Cancelar</button>
            <button type="submit" class="acao-primaria" [disabled]="!pessoa().length">Alocar</button>
          </footer>
        </form>
      </section>
    }

    @if (vagando(); as c) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="vagando.set(null)"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-janela-vagar">
        <header>
          <div><span class="modal-sobretitulo">{{ c.setor_nome }}</span><h2 id="titulo-janela-vagar">Vagar {{ c.rotulo }}</h2></div>
          <button type="button" aria-label="Fechar" (click)="vagando.set(null)">×</button>
        </header>
        <form (ngSubmit)="vagar(c)">
          <p>{{ c.ocupante?.nome }} deixa o cargo e sai do setor {{ c.setor_nome }}.</p>
          <div class="grade-formulario">
            <div><label for="vagar-motivo">Motivo *</label>
              <select id="vagar-motivo" name="motivo" [(ngModel)]="motivo">
                @for (m of motivos; track m[0]) { <option [value]="m[0]">{{ m[1] }}</option> }
              </select></div>
            <div><label for="vagar-fim">Data de saída</label><input id="vagar-fim" name="fim" type="date" [(ngModel)]="fim" /></div>
            <div class="ocupa-duas"><label for="vagar-ato">Ato (ex.: exoneração publicada)</label><input id="vagar-ato" name="ato" maxlength="200" [(ngModel)]="atoFim" /></div>
          </div>
          <footer>
            <button type="button" class="acao-secundaria" (click)="vagando.set(null)">Cancelar</button>
            <button type="submit" [class]="motivo === 'exoneracao' ? 'acao-perigo' : 'acao-primaria'">{{ motivo === 'exoneracao' ? 'Registrar exoneração' : 'Vagar o cargo' }}</button>
          </footer>
        </form>
      </section>
    }
  `,
})
export class CargosComponent implements OnInit {
  private readonly api = inject(RhCargosApiService);
  private readonly rh = inject(RhApiService);
  private readonly setoresApi = inject(SetoresApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly usuarios = inject(UsuariosApiService);

  protected readonly motivos = Object.entries(ROTULOS_MOTIVO_FIM);
  protected readonly aba = signal<Aba>('cargos');
  protected readonly cargos = signal<Cargo[]>([]);
  protected readonly pendencias = signal<PendenciaCargo[]>([]);
  protected readonly setores = signal<Setor[]>([]);
  protected readonly tipos = signal<TipoCargo[]>([]);
  protected readonly carregando = signal(true);
  protected readonly gere = signal(false);
  protected readonly vagas = computed(() => this.cargos().filter((c) => !c.ocupante).length);

  protected busca = '';
  protected filtroSetor = 0;
  protected filtroTipo = 0;
  protected situacao: '' | 'vago' | 'ocupado' = '';

  protected readonly edicao = signal<EdicaoCargo | null>(null);
  protected readonly cargoAberto = signal<Cargo | null>(null);
  protected readonly ocupando = signal<Cargo | null>(null);
  protected readonly vagando = signal<Cargo | null>(null);
  protected readonly pessoa = signal<OpcaoUsuario[]>([]);
  protected inicio = '';
  protected ato = '';
  protected motivo: MotivoFim = 'outro';
  protected fim = '';
  protected atoFim = '';

  ngOnInit(): void {
    this.rh.papeis().subscribe({ next: (p) => this.gere.set(p.nivel_rh === 'MODIFICACAO' || p.nivel_rh === 'CONTROLE_TOTAL'), error: () => undefined });
    this.setoresApi.listar().subscribe((s) => this.setores.set(s.filter((x) => !x.sistemico && x.ativo)));
    this.api.tipos().subscribe((t) => this.tipos.set(t.filter((x) => x.ativo)));
    this.carregar();
    this.carregarPendencias();
  }

  protected carregar(): void {
    this.carregando.set(true);
    this.api.cargos({ busca: this.busca.trim(), setor_id: this.filtroSetor || null, tipo_id: this.filtroTipo || null, situacao: this.situacao }).subscribe({
      next: (lista) => { this.cargos.set(lista); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar os cargos'); },
    });
  }

  private carregarPendencias(): void {
    this.api.aReconciliar().subscribe({ next: (p) => this.pendencias.set(p), error: () => undefined });
  }

  protected filtrarSituacao(valor: '' | 'vago' | 'ocupado'): void {
    this.situacao = valor;
    this.carregar();
  }

  protected dataBr(iso: string): string {
    return iso ? iso.split('-').reverse().join('/') : '';
  }

  // --- Cargos ---
  protected novo(): void {
    const tipo = this.tipos().find((t) => t.codigo === 'FCESP') ?? this.tipos()[0];
    this.cargoAberto.set(null);
    this.edicao.set({ setor_id: this.filtroSetor || 0, tipo_id: tipo?.id ?? 0, grupo: null, nivel: null, denominacao: '', quantidade: 1, ativo: true });
  }

  protected editar(c: Cargo): void {
    this.cargoAberto.set(c);
    this.edicao.set({ id: c.id, setor_id: c.setor_id, tipo_id: c.tipo_id, grupo: c.grupo, nivel: c.nivel, denominacao: c.denominacao, quantidade: 1, ativo: c.ativo });
  }

  protected salvar(e: EdicaoCargo): void {
    const dados: GravacaoCargo = {
      setor_id: e.setor_id, tipo_id: e.tipo_id, grupo: (e.grupo as 1 | 2 | null) ?? null, nivel: e.nivel ? Number(e.nivel) : null, denominacao: e.denominacao.trim(),
      quantidade: Number(e.quantidade) || 1, ativo: e.ativo,
    };
    const chamada = e.id ? this.api.alterar(e.id, dados) : this.api.criar(dados);
    (chamada as unknown as { subscribe: (o: object) => void }).subscribe({
      next: () => { this.edicao.set(null); this.carregar(); },
      error: (erro: unknown) => this.dialogos.mostrarErro(erro, 'Não foi possível salvar o cargo'),
    });
  }

  protected async excluir(c: Cargo): Promise<void> {
    if (!(await this.dialogos.confirmar({ titulo: `Excluir a vaga "${c.rotulo}"?`, mensagem: 'Só vagas que nunca tiveram ocupante podem ser excluídas.', rotuloConfirmar: 'Excluir' }))) return;
    this.api.excluir(c.id).subscribe({ next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir o cargo') });
  }

  // --- Ocupação ---
  protected abrirOcupacao(c: Cargo): void {
    this.pessoa.set([]);
    this.inicio = '';
    this.ato = '';
    this.ocupando.set(c);
  }

  protected alocar(c: Cargo): void {
    const escolhida = this.pessoa()[0];
    if (!escolhida) return;
    this.api.ocupar(c.id, escolhida.id, this.inicio, this.ato.trim()).subscribe({
      next: () => { this.ocupando.set(null); this.carregar(); this.carregarPendencias(); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível alocar a pessoa'),
    });
  }

  protected abrirVacancia(c: Cargo): void {
    this.motivo = 'outro';
    this.fim = '';
    this.atoFim = '';
    this.vagando.set(c);
  }

  protected vagar(c: Cargo): void {
    this.api.vagar(c.id, this.fim, this.motivo, this.atoFim.trim()).subscribe({
      next: () => { this.vagando.set(null); this.carregar(); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível vagar o cargo'),
    });
  }

  // --- Reconciliar ---
  protected vincular(p: PendenciaCargo, setorId: number): void {
    if (!setorId) return;
    this.api.vincular(p.usuario_id, setorId, null).subscribe({
      next: () => { this.carregarPendencias(); this.carregar(); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível vincular a pessoa ao cargo'),
    });
  }

  protected fecharJanelas(): void {
    this.edicao.set(null);
    this.ocupando.set(null);
    this.vagando.set(null);
  }
}
