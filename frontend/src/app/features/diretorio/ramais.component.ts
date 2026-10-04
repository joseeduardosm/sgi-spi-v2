// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o diretório de ramais em cartões de visita, com busca, filtros, favoritos, lista compacta e impressão.

import { Component, ElementRef, HostListener, inject, OnInit, signal, viewChild } from '@angular/core';

import { PaginacaoComponent } from '../../shared/componentes/paginacao/paginacao.component';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CartaoContatoComponent } from './cartao-contato.component';
import { DetalheContatoComponent } from './detalhe-contato.component';
import { Contato, FiltrosRamais, OpcoesFiltro, seloFerias } from './diretorio.models';
import { DiretorioApiService } from './diretorio-api.service';
import { PreferenciasDiretorioComponent } from './preferencias-diretorio.component';
import { AvatarComponent } from './avatar.component';

// Página maior para preencher telas largas (a API aceita até 200)
const TAMANHO_PAGINA = 60;
const CHAVE_MODO = 'diretorio.modo';

@Component({
  selector: 'app-ramais',
  imports: [PaginacaoComponent, TrilhaComponent, CartaoContatoComponent, DetalheContatoComponent, PreferenciasDiretorioComponent, AvatarComponent],
  template: `
    <div class="cabecalho-pagina sem-impressao">
      <div>
        <app-trilha [itens]="[{ rotulo: 'Ramais', rota: '/ramais' }]" />
        <h1>Ramais</h1>
        <small>Diretório de contatos da SPI em cartões de visita. Pressione / para pesquisar.</small>
      </div>
      <div class="acoes-cabecalho-diretorio">
        <button type="button" class="acao-secundaria" (click)="preferencias.set(true)">Minha foto e privacidade</button>
        <button type="button" class="acao-secundaria" (click)="imprimir()" [disabled]="imprimindo()">{{ imprimindo() ? 'Preparando…' : 'Imprimir' }}</button>
      </div>
    </div>

    <form class="barra-diretorio sem-impressao" (submit)="$event.preventDefault(); buscar()" role="search">
      <input #busca type="search" class="form-control" name="q" placeholder="Pesquisar por nome, cargo, setor, ramal ou e-mail"
             [value]="filtros().q" (input)="digitar($any($event.target).value)" aria-label="Pesquisar contatos" />
      <select class="form-control" aria-label="Setor" [value]="filtros().setor" (change)="definir('setor', $any($event.target).value)">
        <option value="">Todos os setores</option>
        @for (s of opcoes().setores; track s) { <option [value]="s" [selected]="s === filtros().setor">{{ s }}</option> }
      </select>
      <select class="form-control" aria-label="Andar" [value]="filtros().andar" (change)="definir('andar', $any($event.target).value)">
        <option value="">Todos os andares</option>
        @for (a of opcoes().andares; track a) { <option [value]="a" [selected]="a === filtros().andar">{{ a }}</option> }
      </select>
      <select class="form-control" aria-label="Prédio" [value]="filtros().predio" (change)="definir('predio', $any($event.target).value)">
        <option value="">Todos os prédios</option>
        @for (p of opcoes().predios; track p) { <option [value]="p" [selected]="p === filtros().predio">{{ p }}</option> }
      </select>
      <button type="button" class="ficha" [class.ativa]="filtros().favoritos" [attr.aria-pressed]="filtros().favoritos" (click)="alternar('favoritos')">★ Favoritos</button>
      <button type="button" class="ficha" [class.ativa]="filtros().em_ferias" [attr.aria-pressed]="filtros().em_ferias" (click)="alternar('em_ferias')">🌴 De férias</button>
      <div class="modos-diretorio" role="group" aria-label="Modo de exibição">
        <button type="button" [class.ativo]="modo() === 'cartoes'" (click)="trocarModo('cartoes')">Cartões</button>
        <button type="button" [class.ativo]="modo() === 'lista'" (click)="trocarModo('lista')">Lista</button>
      </div>
    </form>

    <section class="sem-impressao" aria-live="polite">
      @if (modo() === 'cartoes') {
        <div class="grade-cartoes-visita">
          @for (c of itens(); track c.id) {
            <app-cartao-contato [contato]="c" (abrir)="aberto.set($event.id)" (favoritar)="favoritar($event)" />
          } @empty { <p class="estado-vazio">{{ carregando() ? 'Carregando…' : 'Nenhum contato encontrado.' }}</p> }
        </div>
      } @else {
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao lista-ramais">
            <thead><tr><th></th><th>Nome</th><th>Setor</th><th>Cargo</th><th>Ramal</th><th>E-mail</th><th>Local</th></tr></thead>
            <tbody>
              @for (c of itens(); track c.id) {
                <tr (click)="aberto.set(c.id)" tabindex="0" (keydown.enter)="aberto.set(c.id)">
                  <td><app-avatar [nome]="c.nome" [foto]="c.foto_url" /></td>
                  <td><strong>{{ c.nome }}</strong>@if (selo(c)) { <small class="selo-ferias">🌴 {{ selo(c) }}</small> }</td>
                  <td>{{ c.setor }}</td><td>{{ c.cargo }}</td><td><strong>{{ c.ramal }}</strong></td><td>{{ c.email }}</td><td>{{ c.local }}</td>
                </tr>
              } @empty { <tr><td colspan="7" class="estado-vazio">{{ carregando() ? 'Carregando…' : 'Nenhum contato encontrado.' }}</td></tr> }
            </tbody>
          </table>
        </div>
      }
      <app-paginacao [pagina]="pagina()" [tamanhoPagina]="tamanho" [total]="total()" (mudar)="irPara($event)" />
    </section>

    <!-- Só aparece na impressão: lista completa, agrupada pelos filtros atuais, em tabela -->
    <section class="so-impressao">
      <h1>Ramais — SPI{{ filtros().setor ? ' · ' + filtros().setor : '' }}</h1>
      <table>
        <thead><tr><th>Nome</th><th>Setor</th><th>Cargo</th><th>Ramal</th><th>E-mail</th><th>Local</th></tr></thead>
        <tbody>@for (c of paraImpressao(); track c.id) { <tr><td>{{ c.nome }}</td><td>{{ c.setor }}</td><td>{{ c.cargo }}</td><td>{{ c.ramal }}</td><td>{{ c.email }}</td><td>{{ c.local }}</td></tr> }</tbody>
      </table>
    </section>

    @if (aberto(); as id) {
      <app-detalhe-contato [contatoId]="id" (fechar)="aberto.set(null)" (abrirOutro)="aberto.set($event)" />
    }
    @if (preferencias()) {
      <app-preferencias-diretorio (fechar)="preferencias.set(false)" (alterou)="carregar()" />
    }
  `,
})
export class RamaisComponent implements OnInit {
  private readonly api = inject(DiretorioApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly campoBusca = viewChild<ElementRef<HTMLInputElement>>('busca');
  protected readonly tamanho = TAMANHO_PAGINA;
  protected readonly filtros = signal<FiltrosRamais>({ q: '', setor: '', andar: '', predio: '', favoritos: false, em_ferias: false });
  protected readonly opcoes = signal<OpcoesFiltro>({ setores: [], andares: [], predios: [] });
  protected readonly itens = signal<Contato[]>([]);
  protected readonly total = signal(0);
  protected readonly pagina = signal(1);
  protected readonly carregando = signal(true);
  protected readonly modo = signal<'cartoes' | 'lista'>(this.modoSalvo());
  protected readonly aberto = signal<number | null>(null);
  protected readonly preferencias = signal(false);
  protected readonly paraImpressao = signal<Contato[]>([]);
  protected readonly imprimindo = signal(false);
  protected readonly selo = seloFerias;
  private temporizador: ReturnType<typeof setTimeout> | null = null;

  ngOnInit(): void {
    this.api.filtros().subscribe({ next: (o) => this.opcoes.set(o), error: () => undefined });
    this.carregar();
  }

  /** Atalho "/" foca a pesquisa (como nos sistemas de busca), exceto quando já se está digitando num campo. */
  @HostListener('document:keydown', ['$event'])
  protected atalho(e: KeyboardEvent): void {
    const alvo = e.target as HTMLElement | null;
    if (e.key !== '/' || e.ctrlKey || e.metaKey || ['INPUT', 'TEXTAREA', 'SELECT'].includes(alvo?.tagName ?? '')) return;
    e.preventDefault();
    this.campoBusca()?.nativeElement.focus();
  }

  protected digitar(texto: string): void {
    this.filtros.update((f) => ({ ...f, q: texto }));
    if (this.temporizador) clearTimeout(this.temporizador);
    this.temporizador = setTimeout(() => this.buscar(), 300);
  }

  protected buscar(): void {
    this.pagina.set(1);
    this.carregar();
  }

  protected definir(campo: 'setor' | 'andar' | 'predio', valor: string): void {
    this.filtros.update((f) => ({ ...f, [campo]: valor }));
    this.buscar();
  }

  protected alternar(campo: 'favoritos' | 'em_ferias'): void {
    this.filtros.update((f) => ({ ...f, [campo]: !f[campo] }));
    this.buscar();
  }

  protected irPara(pagina: number): void {
    this.pagina.set(pagina);
    this.carregar();
  }

  protected trocarModo(modo: 'cartoes' | 'lista'): void {
    this.modo.set(modo);
    try { localStorage.setItem(CHAVE_MODO, modo); } catch { /* sem armazenamento: o modo vale só nesta visita */ }
  }

  protected carregar(): void {
    this.carregando.set(true);
    this.api.ramais(this.filtros(), this.pagina(), TAMANHO_PAGINA).subscribe({
      next: (r) => { this.itens.set(r.itens); this.total.set(r.total); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar os ramais'); },
    });
  }

  protected favoritar(c: Contato): void {
    const novo = !c.favorito;
    this.api.favoritar(c.id, novo).subscribe({
      next: () => { this.itens.update((l) => l.map((x) => (x.id === c.id ? { ...x, favorito: novo } : x))); if (this.filtros().favoritos) this.carregar(); },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  /** Busca todos os contatos do filtro atual (até 200 por vez) e abre a impressão do navegador. */
  protected imprimir(): void {
    this.imprimindo.set(true);
    this.api.ramais(this.filtros(), 1, 200).subscribe({
      next: (r) => {
        this.paraImpressao.set(r.itens);
        this.imprimindo.set(false);
        setTimeout(() => window.print(), 100);
      },
      error: (e) => { this.imprimindo.set(false); this.dialogos.mostrarErro(e); },
    });
  }

  private modoSalvo(): 'cartoes' | 'lista' {
    try { return localStorage.getItem(CHAVE_MODO) === 'lista' ? 'lista' : 'cartoes'; } catch { return 'cartoes'; }
  }
}
