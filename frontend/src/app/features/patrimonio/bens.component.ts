// Criado por José Eduardo Santana Martins
// Este arquivo serve para a lista de bens do Patrimônio: pesquisa, filtros, leitura de código pela câmera e atalhos de cadastro.
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { debounceTime, Subject } from 'rxjs';

import { PIPES_FORMATACAO } from '../../shared/utilitarios/formatadores.pipes';
import { PaginacaoComponent } from '../../shared/componentes/paginacao/paginacao.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { PreferenciasColunasService, VisaoColunas } from '../../shared/servicos/preferencias-colunas.service';
import { classeMarcador } from '../tarefas/marcadores.paleta';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { LeitorCodigoComponent } from './leitor-codigo.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { Bem, COR_SITUACAO, FiltrosBens, ROTULOS_CONSERVACAO, ROTULOS_GARANTIA, ROTULOS_SITUACAO } from './patrimonio.models';
import { SeletorSalaComponent } from './seletor-sala.component';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
const TAMANHO = 24;
const CHAVE_VISAO = 'sgi-spi.patrimonio.visao';
const CHAVE_COLUNAS = 'sgi-spi.patrimonio.colunas';

/**
 * Coluna da visão em lista. `ordenavel` liga o cabeçalho clicável (a ordem é do servidor); `padrao` diz se aparece até a pessoa escolher outras.
 * Qualquer dado do bem pode virar coluna: a pessoa escolhe quais e em que ordem (guardado na conta dela).
 */
interface ColunaBens { id: string; rotulo: string; padrao: boolean; ordenavel: boolean; direita?: boolean }
/** Como no GLPI (ID e Título), a chapa e a descrição ficam sempre no começo e não saem. */
const FIXAS = ['chapa', 'descricao'];
const col = (id: string, rotulo: string, padrao = false, ordenavel = true, direita = false): ColunaBens => ({ id, rotulo, padrao, ordenavel, direita });
const COLUNAS: ColunaBens[] = [
  col('chapa', 'Chapa', true), col('descricao', 'Descrição', true), col('numero_serie', 'Número de série'), col('marca', 'Marca'), col('modelo', 'Modelo'),
  col('sala', 'Sala', true), col('andar', 'Andar', false, false), col('setor', 'Setor da sala', false, false), col('responsavel', 'Responsável'),
  col('situacao', 'Situação', true), col('conservacao', 'Conservação', true), col('origem', 'Origem'), col('grupo', 'Grupo de material'),
  col('valor_aquisicao', 'Valor de aquisição', false, true, true), col('valor_atual', 'Valor atual', true, true, true), col('valor_efetivo', 'Valor efetivo', false, false, true),
  col('data_aquisicao', 'Data de aquisição'), col('garantia_meses', 'Meses de garantia', false, false, true), col('garantia', 'Fim da garantia', true),
  col('uge', 'UGE'), col('ua', 'UA'), col('divisao', 'Divisão'), col('nota_fiscal', 'Nota fiscal'), col('fornecedor', 'Fornecedor'), col('observacoes', 'Observações'),
  col('classificacao_pendente', 'Classificação pendente', false, false), col('em_movimentacao', 'Em movimentação', false, false), col('dados_contabeis_pendentes', 'Dados contábeis pendentes', false, false),
  col('criado_por', 'Cadastrado por', false, false), col('criado_em', 'Cadastrado em'), col('atualizado_em', 'Atualizado em'), col('baixado_em', 'Baixado em'),
];
const PADRAO = COLUNAS.filter((c) => c.padrao).map((c) => c.id);
const TELA_COLUNAS = 'patrimonio.bens';

function lerLocal<T>(chave: string, padrao: T): T {
  try { const v = localStorage.getItem(chave); return v ? (JSON.parse(v) as T) : padrao; } catch { return padrao; }
}
function gravarLocal(chave: string, valor: unknown): void {
  try { localStorage.setItem(chave, JSON.stringify(valor)); } catch { /* sem armazenamento: a escolha vale só nesta tela */ }
}

/** Lista de bens (cartões, pensada para o celular). Leitura de código abre o bem ou, se não existir, o cadastro com a chapa preenchida. */
@Component({
  selector: 'app-bens',
  imports: [EsqueletoComponent, FormsModule, RouterLink, ...PIPES_FORMATACAO, PaginacaoComponent, CabecalhoPatrimonioComponent, LeitorCodigoComponent, SeletorSalaComponent],
  template: `
    <app-cabecalho-patrimonio titulo="Patrimônio" descricao="Bens móveis do prédio SPI: onde estão, por onde passaram e se ainda estão em garantia." />
    <section class="painel-gestao patrimonio">
      <div class="pat-barra">
        <div class="campo pat-busca"><label for="pat-busca">Pesquisar</label>
          <input id="pat-busca" type="search" name="busca" autocomplete="off" placeholder="Chapa, descrição, marca, modelo ou série" [ngModel]="filtros.q" (ngModelChange)="filtros.q = $event; digitou.next()" /></div>
        <button type="button" class="acao-secundaria pat-botao-grande" (click)="lendo.set(true)">Ler código</button>
        @if (estado.podeOperar()) {
          <a class="acao-primaria pat-botao-grande" routerLink="/patrimonio/bens/novo">+ Adicionar bem</a>
          <a class="acao-secundaria pat-botao-grande" routerLink="/patrimonio/bens/lote">Cadastro em lote</a>
        }
        <div class="pat-visoes" role="group" aria-label="Forma de exibição">
          <button type="button" [class.ativa]="visao() === 'cartoes'" (click)="trocarVisao('cartoes')">Cartões</button>
          <button type="button" [class.ativa]="visao() === 'lista'" (click)="trocarVisao('lista')">Lista</button>
        </div>
        @if (visao() === 'lista') { <button type="button" class="acao-secundaria pat-botao-grande" [attr.aria-expanded]="colunasAbertas()" (click)="colunasAbertas.set(!colunasAbertas())">Colunas</button> }
        <button type="button" class="acao-secundaria pat-botao-grande" (click)="filtrosAbertos.set(!filtrosAbertos())">{{ filtrosAbertos() ? 'Esconder filtros' : 'Filtros' }}</button>
      </div>

      @if (filtrosAbertos()) {
        <div class="pat-barra pat-filtros">
          <div class="campo"><label for="pf-situacao">Situação</label>
            <select id="pf-situacao" name="situacao" [(ngModel)]="filtros.situacao" (ngModelChange)="carregar(1)">
              <option value="">Todas (sem baixados)</option>
              @for (s of situacoes; track s[0]) { <option [value]="s[0]">{{ s[1] }}</option> }
            </select></div>
          <div class="campo"><label for="pf-conservacao">Conservação</label>
            <select id="pf-conservacao" name="conservacao" [(ngModel)]="filtros.conservacao" (ngModelChange)="carregar(1)">
              <option value="">Todas</option>
              @for (c of conservacoes; track c[0]) { <option [value]="c[0]">{{ c[0] }} · {{ c[1] }}</option> }
            </select></div>
          <div class="campo"><label for="pf-garantia">Garantia</label>
            <select id="pf-garantia" name="garantia" [(ngModel)]="filtros.garantia" (ngModelChange)="carregar(1)">
              <option value="">Todas</option>
              @for (g of garantias; track g[0]) { <option [value]="g[0]">{{ g[1] }}</option> }
            </select></div>
          <div class="campo"><label for="pf-grupo">Grupo de material</label>
            <select id="pf-grupo" name="grupo" [(ngModel)]="filtros.grupo_id" (ngModelChange)="carregar(1)">
              <option value="">Todos</option>
              @for (g of estado.grupos(); track g.id) { <option [value]="g.id">{{ g.nome }}</option> }
            </select></div>
          <div class="campo pat-campo-sala"><label>Sala</label>
            <app-seletor-sala nome="filtro-sala" rotulo="Filtrar por sala" placeholder="Todas as salas" [soAtivas]="false" [valor]="filtros.localizacao_id ?? ''" (valorChange)="filtros.localizacao_id = $event; carregar(1)" /></div>
          <label class="pat-marca"><input type="checkbox" name="pendentes" [ngModel]="filtros.contabeis_pendentes" (ngModelChange)="filtros.contabeis_pendentes = $event || undefined; carregar(1)" /> Só dados contábeis pendentes</label>
          <div class="pat-acoes">
            <button type="button" class="acao-secundaria acao-pequena" (click)="limpar()">Limpar</button>
            <button type="button" class="acao-secundaria acao-pequena" (click)="exportar('xlsx')">Excel</button>
            <button type="button" class="acao-secundaria acao-pequena" (click)="exportar('pdf')">PDF</button>
          </div>
        </div>
      }

      @if (carregando()) { <app-esqueleto tipo="lista" [linhas]="4" /> }
      @if (visao() === 'lista') {
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao pat-tabela-bens">
            <thead><tr>
              @for (c of colunasMostradas(); track c.id) {
                <th [class.num]="c.direita" [attr.aria-sort]="sentido(c.id)">
                  @if (!c.ordenavel) { {{ c.rotulo }} } @else { <button type="button" class="ordenar-coluna" [class.ativa]="filtros.ordenar_por === c.id" [title]="'Ordenar por ' + c.rotulo.toLowerCase()" (click)="ordenar(c.id)">{{ c.rotulo }}<span aria-hidden="true">{{ filtros.ordenar_por === c.id ? (filtros.direcao === 'asc' ? '▲' : '▼') : '↕' }}</span></button> }
                </th>
              }
            </tr></thead>
            <tbody>
              @for (b of bens(); track b.id) {
                <tr>
                  @for (c of colunasMostradas(); track c.id) {
                    <td [class.num]="c.direita">
                      @switch (c.id) {
                        @case ('chapa') { <a [routerLink]="['/patrimonio/bens', b.id]"><strong class="texto-codigo">{{ b.rotulo }}</strong></a> }
                        @case ('situacao') { <span [class]="marcador(cores[b.situacao])">{{ situacoesMapa[b.situacao] }}</span> }
                        @case ('conservacao') { {{ b.conservacao }} · {{ conservacaoMapa[b.conservacao] }} }
                        @case ('valor_aquisicao') { {{ b.valor_aquisicao ? (b.valor_aquisicao | moeda) : '—' }} }
                        @case ('valor_atual') { {{ b.valor_atual ? (b.valor_atual | moeda) : '—' }} }
                        @case ('garantia') { @if (b.garantia_fim) { <span [class]="marcador(b.situacao_garantia === 'vencida' ? 1 : b.vence_em_90_dias ? 3 : 10)">{{ b.garantia_fim | dataBr }}</span> } @else { <span class="pat-indefinida">Indefinida</span> } }
                        @case ('data_aquisicao') { {{ b.data_aquisicao ? (b.data_aquisicao | dataBr) : '—' }} }
                        @case ('criado_em') { {{ b.criado_em | dataBr }} }
                        @case ('atualizado_em') { {{ b.atualizado_em | dataBr }} }
                        @case ('baixado_em') { {{ b.baixado_em ? (b.baixado_em | dataBr) : '—' }} }
                        @case ('valor_efetivo') { {{ b.valor_efetivo ? (b.valor_efetivo | moeda) : '—' }} }
                        @case ('classificacao_pendente') { {{ b.classificacao_pendente ? 'Sim' : 'Não' }} }
                        @case ('em_movimentacao') { {{ b.em_movimentacao ? 'Sim' : 'Não' }} }
                        @case ('dados_contabeis_pendentes') { {{ b.dados_contabeis_pendentes ? 'Sim' : 'Não' }} }
                        @default { {{ valorTexto(b, c.id) }} }
                      }
                    </td>
                  }
                </tr>
              } @empty { @if (!carregando()) { <tr><td [attr.colspan]="colunasMostradas().length" class="estado-vazio">Nenhum bem encontrado.</td></tr> } }
            </tbody>
          </table>
        </div>
      } @else {
      <div class="pat-lista-bens">
        @for (b of bens(); track b.id) {
          <a class="pat-cartao-bem" [routerLink]="['/patrimonio/bens', b.id]">
            <span class="pat-chapa texto-codigo">{{ b.rotulo }}</span>
            <span class="pat-descricao">{{ b.descricao }}</span>
            <small class="pat-sala">{{ b.sala_rotulo }}</small>
            <span class="pat-marcadores">
              <span [class]="marcador(cores[b.situacao])">{{ situacoesMapa[b.situacao] }}</span>
              <span [class]="marcador(b.conservacao <= 2 ? 1 : b.conservacao === 3 ? 3 : 10)">{{ b.conservacao }} · {{ conservacaoMapa[b.conservacao] }}</span>
              @if (b.situacao_garantia === 'vencida') { <span [class]="marcador(1)">Fora de garantia</span> }
              @if (b.vence_em_90_dias) { <span [class]="marcador(3)">Garantia vence em breve</span> }
              @if (b.dados_contabeis_pendentes) { <span [class]="marcador(0)">Dados contábeis pendentes</span> }
              @if (b.classificacao_pendente) { <span [class]="marcador(3)">Classificação pendente</span> }
              @if (b.em_movimentacao) { <span [class]="marcador(4)">Em movimentação</span> }
            </span>
          </a>
        } @empty { @if (!carregando()) { <p class="estado-vazio">Nenhum bem encontrado.</p> } }
      </div>
      }
      <app-paginacao [pagina]="pagina()" [tamanhoPagina]="tamanho" [total]="total()" (mudar)="carregar($event)" />
    </section>

    @if (colunasAbertas()) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="colunasAbertas.set(false)"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal modal-colunas" role="dialog" aria-modal="true" aria-labelledby="titulo-colunas">
        <header>
          <h2 id="titulo-colunas">Selecione os itens padrões a serem mostrados - Bens</h2>
          <button type="button" aria-label="Fechar" (click)="colunasAbertas.set(false)">×</button>
        </header>
        <div class="corpo-colunas">
          @if (ehSuperRoot) {
            <select name="visao-colunas" aria-label="Visão" [ngModel]="visaoEdicao()" (ngModelChange)="visaoEdicao.set($event)">
              <option value="pessoal">Minha visão pessoal</option>
              <option value="global">Visão global</option>
            </select>
          }
          <p class="aviso-colunas" role="note">
            {{ visaoEdicao() === 'global' ? 'Estas preferências são usadas por todos que não possuem uma visão pessoal configurada.' : 'Esta é a sua visão pessoal: vale só para a sua conta, em qualquer navegador. Sem ela, vale a visão global.' }}
          </p>
          <div class="adicionar-coluna">
            <select name="nova-coluna" aria-label="Coluna a adicionar" [(ngModel)]="novaColuna">
              <option value=""></option>
              @for (c of colunasDisponiveis(); track c.id) { <option [value]="c.id">{{ c.rotulo }}</option> }
            </select>
            <button type="button" class="acao-primaria" [disabled]="!novaColuna" (click)="adicionarColuna()">+ Adicionar</button>
          </div>
          <ul class="lista-colunas">
            @for (c of colunasEditadas(); track c.id; let i = $index) {
              @if (c.fixa) {
                <li class="fixa"><span>{{ c.rotulo }}</span></li>
              } @else {
                <li draggable="true" [class.arrastando]="arrastando() === c.id" (dragstart)="arrastando.set(c.id)" (dragend)="arrastando.set(null)" (dragover)="$event.preventDefault()" (drop)="soltarSobre(c.id)">
                  <span class="alca" aria-hidden="true">⠿</span><span class="nome">{{ c.rotulo }}</span>
                  <button type="button" class="tirar" [attr.aria-label]="'Tirar ' + c.rotulo" (click)="alternarColuna(c.id)">×</button>
                </li>
              }
            }
          </ul>
        </div>
        <footer>
          <button type="button" class="acao-secundaria" (click)="restaurarColunas()">Restaurar o padrão</button>
          <button type="button" class="acao-primaria" (click)="colunasAbertas.set(false)">Fechar</button>
        </footer>
      </section>
    }

    @if (lendo()) { <app-leitor-codigo (lido)="aoLer($event)" (fechar)="lendo.set(false)" /> }
  `,
})
export class BensComponent implements OnInit {
  private readonly api = inject(PatrimonioApiService);
  private readonly roteador = inject(Router);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(PatrimonioEstadoService);

  protected readonly tamanho = TAMANHO;
  protected readonly bens = signal<Bem[]>([]);
  protected readonly total = signal<number | null>(0);
  protected readonly pagina = signal(1);
  protected readonly carregando = signal(false);
  protected readonly lendo = signal(false);
  protected readonly filtrosAbertos = signal(false);
  protected readonly digitou = new Subject<void>();
  protected filtros: FiltrosBens = { q: '', situacao: '', conservacao: '', garantia: '', grupo_id: '', localizacao_id: '', ordenar_por: 'chapa', direcao: 'asc' };
  protected readonly visao = signal<'cartoes' | 'lista'>(lerLocal<'cartoes' | 'lista'>(CHAVE_VISAO, 'cartoes'));
  protected readonly colunasAbertas = signal(false);
  private readonly preferencias = inject(PreferenciasColunasService);
  protected readonly ehSuperRoot = inject(AutenticacaoService).possuiPapel('SuperRoot');
  /** Visão da conta (nulo = nunca escolheu) e visão global (nulo = vale o padrão da tela). A mostrada é a pessoal, senão a global, senão o padrão. */
  private readonly pessoal = signal<string[] | null>(lerLocal<string[] | null>(CHAVE_COLUNAS, null));
  private readonly global = signal<string[] | null>(null);
  protected readonly visaoEdicao = signal<VisaoColunas>('pessoal');
  protected readonly arrastando = signal<string | null>(null);
  protected novaColuna = '';
  protected readonly colunasEscolhidas = computed(() => this.sanear(this.pessoal() ?? this.global() ?? PADRAO));
  protected readonly colunasMostradas = computed(() => this.colunasEscolhidas().map((id) => COLUNAS.find((c) => c.id === id)!));
  /** Colunas da visão que está sendo editada na janela (as fixas vêm marcadas). */
  protected readonly colunasEditadas = computed(() => this.idsEditados().map((id) => ({ ...COLUNAS.find((c) => c.id === id)!, fixa: FIXAS.includes(id) })));
  protected readonly colunasDisponiveis = computed(() => COLUNAS.filter((c) => !this.idsEditados().includes(c.id)));
  private readonly idsEditados = computed(() => this.sanear(this.visaoEdicao() === 'global' ? (this.global() ?? PADRAO) : (this.pessoal() ?? this.global() ?? PADRAO)));

  protected readonly marcador = classeMarcador;
  protected readonly cores = COR_SITUACAO;
  protected readonly situacoesMapa = ROTULOS_SITUACAO;
  protected readonly conservacaoMapa = ROTULOS_CONSERVACAO;
  protected readonly situacoes = Object.entries(ROTULOS_SITUACAO);
  protected readonly conservacoes = Object.entries(ROTULOS_CONSERVACAO);
  protected readonly garantias = Object.entries(ROTULOS_GARANTIA);

  constructor() {
    this.digitou.pipe(debounceTime(300)).subscribe(() => this.carregar(1));
  }

  ngOnInit(): void {
    this.carregar(1);
    // As colunas da conta (se a pessoa já escolheu) valem em qualquer navegador e aparelho
    this.preferencias.ler(TELA_COLUNAS).subscribe({
      next: (p) => { this.pessoal.set(p.colunas); this.global.set(p.padrao_global); gravarLocal(CHAVE_COLUNAS, p.colunas); },
      error: () => undefined,
    });
  }

  protected carregar(pagina: number): void {
    this.carregando.set(true);
    this.pagina.set(pagina);
    this.api.bens({ ...this.filtros, pagina, tamanho: TAMANHO }).subscribe({
      next: (r) => { this.bens.set(r.itens); this.total.set(r.total); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar os bens'); },
    });
  }

  protected trocarVisao(visao: 'cartoes' | 'lista'): void {
    this.visao.set(visao);
    gravarLocal(CHAVE_VISAO, visao);
  }

  /** Só ids que a tela conhece, sem repetir, com as fixas (chapa e descrição) sempre na frente. */
  private sanear(ids: string[]): string[] {
    const validos = [...new Set(ids)].filter((id) => COLUNAS.some((c) => c.id === id) && !FIXAS.includes(id));
    return [...FIXAS, ...validos];
  }

  /** Grava a visão em edição na hora (como no GLPI), na conta ou como visão global. */
  private guardarColunas(ids: string[]): void {
    const visao = this.visaoEdicao();
    const limpo = this.sanear(ids);
    if (visao === 'global') this.global.set(limpo); else { this.pessoal.set(limpo); gravarLocal(CHAVE_COLUNAS, limpo); }
    this.preferencias.salvar(TELA_COLUNAS, limpo, visao).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar as colunas') });
    // Se a lista estava ordenada por uma coluna que saiu da tela, volta para a chapa
    if (!this.colunasEscolhidas().includes(this.filtros.ordenar_por ?? 'chapa')) this.ordenar('chapa');
  }

  protected adicionarColuna(): void {
    if (!this.novaColuna) return;
    this.guardarColunas([...this.idsEditados(), this.novaColuna]);
    this.novaColuna = '';
  }

  protected alternarColuna(id: string): void {
    if (FIXAS.includes(id)) return;
    this.guardarColunas(this.idsEditados().filter((x) => x !== id));
  }

  /** Arrastar e soltar: a coluna arrastada vai para a posição da coluna em que foi solta. */
  protected soltarSobre(alvo: string): void {
    const origem = this.arrastando();
    this.arrastando.set(null);
    if (!origem || origem === alvo || FIXAS.includes(alvo)) return;
    const ids = this.idsEditados().filter((x) => x !== origem);
    ids.splice(ids.indexOf(alvo) + (this.idsEditados().indexOf(origem) < this.idsEditados().indexOf(alvo) ? 1 : 0), 0, origem);
    this.guardarColunas(ids);
  }

  protected restaurarColunas(): void {
    const visao = this.visaoEdicao();
    if (visao === 'global') this.global.set(null); else { this.pessoal.set(null); gravarLocal(CHAVE_COLUNAS, null); }
    this.preferencias.restaurar(TELA_COLUNAS, visao).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível restaurar as colunas') });
  }

  /** Clique no cabeçalho: ordena por esta coluna; clicar de novo inverte o sentido. A ordem é do servidor (vale para todas as páginas). */
  protected ordenar(coluna: string): void {
    this.filtros.direcao = this.filtros.ordenar_por === coluna && this.filtros.direcao === 'asc' ? 'desc' : 'asc';
    this.filtros.ordenar_por = coluna;
    this.carregar(1);
  }

  protected sentido(coluna: string): 'ascending' | 'descending' | 'none' {
    return this.filtros.ordenar_por === coluna ? (this.filtros.direcao === 'asc' ? 'ascending' : 'descending') : 'none';
  }

  /** Texto simples das colunas que não pedem formatação própria. */
  protected valorTexto(b: Bem, coluna: string): string {
    const v: Record<string, string | null> = {
      descricao: b.descricao, sala: b.sala_rotulo, grupo: b.grupo_nome, responsavel: b.responsavel_nome, marca: b.marca, modelo: b.modelo, numero_serie: b.numero_serie,
      uge: b.uge, ua: b.ua, divisao: b.divisao, nota_fiscal: b.nota_fiscal, fornecedor: b.fornecedor, observacoes: b.observacoes, andar: b.andar === null ? null : b.andar === -1 ? 'Subsolo' : b.andar === 0 ? 'Térreo' : `${b.andar}º`,
      setor: b.setor_nome, criado_por: b.criado_por_nome, origem: b.origem === 'terceiros' ? 'Terceiros' : 'Próprio', garantia_meses: b.garantia_meses === null ? null : String(b.garantia_meses),
    };
    return v[coluna] || '—';
  }

  protected limpar(): void {
    this.filtros = { q: '', situacao: '', conservacao: '', garantia: '', grupo_id: '', localizacao_id: '', ordenar_por: this.filtros.ordenar_por, direcao: this.filtros.direcao };
    this.carregar(1);
  }

  protected exportar(formato: 'xlsx' | 'pdf'): void {
    const { pagina, tamanho, ordenar_por, direcao, ...filtros } = this.filtros;
    this.dialogos.executar(this.api.exportar('bens', formato, filtros), 'Gerando o relatório…').subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar o relatório') });
  }

  /** Código lido: abre o bem; se ele não existe, abre o cadastro já com a chapa preenchida. */
  protected aoLer(codigo: string): void {
    this.lendo.set(false);
    this.api.bemPorChapa(codigo).subscribe({
      next: (b) => void this.roteador.navigate(['/patrimonio/bens', b.id]),
      error: () => void this.roteador.navigate(['/patrimonio/bens/novo'], { queryParams: { chapa: codigo } }),
    });
  }
}
