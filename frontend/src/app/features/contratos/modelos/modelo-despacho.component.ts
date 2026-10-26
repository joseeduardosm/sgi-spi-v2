// Criado por José Eduardo Santana Martins
// Este arquivo serve para a página de detalhe da máscara do despacho de pagamento (Contratos → Modelos): texto e placeholders permitidos.

import { Component, inject, input, OnInit, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { EditorRicoComponent } from '../../contratacoes/editor-rico.component';
import { semAcento } from '../../tarefas/marcadores.paleta';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { Modelo, PlaceholderPortaria } from '../compartilhado/contratos.models';

import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
/** Texto sugerido ao criar a máscara: o despacho padrão, com blocos de assinatura centralizados (nome em negrito). */
const TEXTO_EXEMPLO = `<p>Sr. Subsecretário,</p>
<p>Trata-se do pagamento referente ao Contrato nº ##nrocontrato##, celebrado entre a Secretaria de Parcerias em Investimentos e ##razaosocialempresa##, objeto do Processo nº ##processogestao##, relativo ao período de ##iniciocompetencia## a ##fimcompetencia##.</p>
<p>Considerando a Medição - ##mescompetencia## (Doc. SEI XXXXXXXXX), acompanhado da nota fiscal com vencimento em ##vencimentodanotafiscal##, do checklist de documentação para pagamento, das certidões de regularidade e do resumo executivo:</p>
<ul><li>Atesto que os serviços discriminados na referida nota fiscal foram executados a contento, no prazo e nos termos do contrato.</li></ul>
<p>À consideração superior.</p>
<p>São Paulo, na data da assinatura digital.</p>
<p style="text-align:center">__________________________________________</p>
<p style="text-align:center"><strong>##nomegestor##</strong></p>
<p style="text-align:center">##funcaogestor##</p>
<p style="text-align:center">##cargogestor##</p>
<p style="text-align:center">##setorgestor##</p>
<p>I. De acordo.</p>
<p>II. Autorizo o pagamento, observadas as informações e documentos constantes dos autos e do consolidado da respectiva medição.</p>
<p>III. Encaminhe-se à DOF para providências.</p>
<p style="text-align:center">__________________________________________</p>
<p style="text-align:center"><strong>##nomeautoridade##</strong></p>
<p style="text-align:center">##cargoautoridade##</p>
<p style="text-align:center">##setorautoridade##</p>`;

/**
 * Página da máscara do despacho (`/contratos/modelos/despacho/novo` ou `.../despacho/:id`). O editor ocupa a largura toda e a lista de
 * placeholders fica ao lado, sempre visível; a barra de ações fica fixa no pé da página. A API só aceita os placeholders da lista.
 */
@Component({
  selector: 'app-modelo-despacho',
  imports: [EsqueletoComponent, FormsModule, RouterLink, CabecalhoModuloComponent, EditorRicoComponent],
  template: `
    <app-cabecalho-modulo [titulo]="id() === 'novo' ? 'Nova máscara do despacho' : 'Máscara do despacho'" [trilha]="['Modelos', 'Despacho de pagamento']"
      descricao="Texto-base do despacho que abre o documento consolidado. Os placeholders (#nome, #nome# ou ##nome##) são trocados pelos dados do contrato e da competência." />

    @if (carregando()) {
      <app-esqueleto tipo="formulario" [linhas]="5" />
    } @else {
      <form class="pagina-mascara" (ngSubmit)="salvar()">
        <section class="cartao-dados dados-mascara">
          <div class="grade-formulario">
            <div><label for="mascara-nome">Nome *</label><input id="mascara-nome" name="nome" required maxlength="300" [(ngModel)]="nome" /></div>
            <div class="linha-caixas ocupa-duas"><label><input type="checkbox" name="ativo" [(ngModel)]="ativo" /> Ativa (só uma máscara de despacho ativa)</label></div>
          </div>
        </section>

        <div class="corpo-mascara">
          <section class="cartao-dados editor-mascara" aria-labelledby="titulo-texto-mascara">
            <header><h2 id="titulo-texto-mascara">Texto do despacho</h2></header>
            @defer (on idle) { <app-editor-rico [(html)]="html" rotulo="Texto da máscara do despacho" /> } @placeholder { <app-esqueleto tipo="formulario" [linhas]="3" /> }
          </section>
          <aside class="cartao-dados placeholders-mascara" aria-labelledby="titulo-placeholders">
            <header><div><h2 id="titulo-placeholders">Placeholders permitidos</h2>
              <small>Clique para inserir no cursor. Qualquer outro <code>#</code> impede salvar.</small></div></header>
            <div class="busca-placeholders"><input type="search" name="busca-placeholder" autocomplete="off" placeholder="Pesquisar placeholder…" aria-label="Pesquisar placeholder" [ngModel]="busca()" (ngModelChange)="busca.set($event)" /></div>
            <ul>
              @for (p of placeholdersFiltrados(); track p.nome) {
                <li><button type="button" class="acao-secundaria acao-pequena texto-codigo" (click)="inserir(p)">#{{ p.nome }}</button><small>{{ p.descricao }}</small></li>
              } @empty { <li><small>Nenhum placeholder encontrado.</small></li> }
            </ul>
          </aside>
        </div>

        <footer class="acoes-mascara">
          <a class="acao-secundaria" routerLink="/contratos/modelos">Voltar aos modelos</a>
          <button [class.carregando]="salvando()" type="submit" class="acao-primaria" [disabled]="salvando() || !nome.trim() || !html.trim()">Salvar máscara</button>
        </footer>
      </form>
    }
  `,
  styles: `
    .pagina-mascara { display: grid; gap: 16px; }
    .dados-mascara { padding: 16px 20px 0; }
    .corpo-mascara { display: grid; grid-template-columns: minmax(0, 1fr) 270px; gap: 16px; align-items: start; }
    .editor-mascara { padding-bottom: 16px; }
    .editor-mascara > header, .placeholders-mascara > header { padding: 14px 20px 8px; }
    .editor-mascara app-editor-rico { display: block; margin: 0 20px; }
    :host ::ng-deep .editor-mascara .editor-rico .superficie-editor { min-height: max(420px, calc(100vh - 430px)); font-size: 14px; line-height: 1.6; }
    .placeholders-mascara { position: sticky; top: 12px; max-height: min(520px, calc(100vh - 100px)); overflow: auto; padding-bottom: 12px; }
    .busca-placeholders { padding: 0 20px 10px; }
    .placeholders-mascara ul { display: grid; gap: 10px; margin: 0; padding: 0 20px; list-style: none; }
    .placeholders-mascara li { display: grid; gap: 4px; }
    .placeholders-mascara li button { justify-self: start; }
    .placeholders-mascara li small { color: var(--spi-apagado); }
    .acoes-mascara { position: sticky; bottom: 0; z-index: 20; display: flex; justify-content: flex-end; gap: 10px; padding: 12px 20px;
      border-top: 1px solid var(--cor-e2e5e8); background: var(--cor-ffffff); }
    @media (max-width: 1000px) { .corpo-mascara { grid-template-columns: 1fr; } .placeholders-mascara { position: static; max-height: none; } }
  `,
})
export class ModeloDespachoComponent implements OnInit {
  /** `novo` ou o id da máscara (vem da URL). */
  readonly id = input.required<string>();

  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  private readonly editor = viewChild(EditorRicoComponent);

  protected readonly carregando = signal(true);
  protected readonly salvando = signal(false);
  protected readonly placeholders = signal<PlaceholderPortaria[]>([]);
  protected readonly busca = signal('');
  protected nome = '';
  protected ativo = true;
  protected html = '';

  ngOnInit(): void {
    this.api.placeholdersDespacho().subscribe({ next: (p) => this.placeholders.set(p), error: (e) => this.dialogos.mostrarErro(e) });
    if (this.id() === 'novo') {
      this.html = TEXTO_EXEMPLO;
      this.carregando.set(false);
      return;
    }
    this.api.modelos('despacho', false).subscribe({
      next: (lista) => {
        const modelo = lista.find((m) => m.id === this.id());
        if (modelo) this.aplicar(modelo);
        else void this.roteador.navigate(['/contratos/modelos']);
        this.carregando.set(false);
      },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar a máscara'); },
    });
  }

  private aplicar(modelo: Modelo): void {
    this.nome = modelo.nome;
    this.ativo = modelo.ativo;
    this.html = modelo.conteudo.html ?? '';
  }

  /** A pesquisa casa o nome ou a descrição do placeholder (sem acento). */
  protected placeholdersFiltrados(): PlaceholderPortaria[] {
    const termo = semAcento(this.busca().trim().replace(/^#/, ''));
    return this.placeholders().filter((p) => !termo || semAcento(`${p.nome} ${p.descricao}`).includes(termo));
  }

  protected inserir(placeholder: PlaceholderPortaria): void {
    this.editor()?.inserir(`#${placeholder.nome}`);
  }

  protected salvar(): void {
    this.salvando.set(true);
    const dados = { tipo: 'despacho', nome: this.nome.trim(), ativo: this.ativo, html: this.html };
    this.api.salvarModelo(dados, this.id() === 'novo' ? undefined : this.id()).subscribe({
      next: () => void this.roteador.navigate(['/contratos/modelos']),
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível salvar a máscara'); },
    });
  }
}
