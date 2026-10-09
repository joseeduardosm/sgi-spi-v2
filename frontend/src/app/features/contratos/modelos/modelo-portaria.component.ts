// Criado por José Eduardo Santana Martins
// Este arquivo serve para a página de detalhe de uma máscara de portaria (Contratos → Modelos): texto, variante e placeholders permitidos.

import { Component, inject, input, OnInit, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { EditorRicoComponent } from '../../contratacoes/editor-rico.component';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { Modelo, PlaceholderPortaria, VarianteMascara } from '../compartilhado/contratos.models';

/**
 * Página da máscara de portaria (`/contratos/modelos/portaria/novo` ou `.../portaria/:id`). O editor ocupa a largura toda e a lista de
 * placeholders fica ao lado, sempre visível; a barra de ações fica fixa no pé da página. A API só aceita os placeholders da lista.
 */
@Component({
  selector: 'app-modelo-portaria',
  imports: [FormsModule, RouterLink, CabecalhoModuloComponent, EditorRicoComponent],
  template: `
    <app-cabecalho-modulo [titulo]="id() === 'novo' ? 'Nova máscara de portaria' : 'Máscara de portaria'" [trilha]="['Modelos', 'Portaria']"
      descricao="Texto-base da portaria de designação. Os placeholders (#nome) são trocados pelos dados do contrato na emissão." />

    @if (carregando()) {
      <p class="estado-vazio">Carregando…</p>
    } @else {
      <form class="pagina-mascara" (ngSubmit)="salvar()">
        <section class="cartao-dados dados-mascara">
          <div class="grade-formulario">
            <div><label for="mascara-nome">Nome *</label><input id="mascara-nome" name="nome" required maxlength="300" [(ngModel)]="nome" /></div>
            <div><label for="mascara-variante">Usada quando *</label>
              <select id="mascara-variante" name="variante" [(ngModel)]="variante">
                <option value="sem_anterior">O contrato não tem portaria anterior</option>
                <option value="com_anterior">O contrato já tem portaria anterior (revoga a anterior)</option>
              </select></div>
            <div class="linha-caixas ocupa-duas"><label><input type="checkbox" name="ativo" [(ngModel)]="ativo" /> Ativa (só uma máscara ativa por variante)</label></div>
          </div>
        </section>

        <div class="corpo-mascara">
          <section class="cartao-dados editor-mascara" aria-labelledby="titulo-texto-mascara">
            <header><h2 id="titulo-texto-mascara">Texto da portaria</h2></header>
            <app-editor-rico [(html)]="html" rotulo="Texto da máscara da portaria" />
          </section>
          <aside class="cartao-dados placeholders-mascara" aria-labelledby="titulo-placeholders">
            <header><div><h2 id="titulo-placeholders">Placeholders permitidos</h2>
              <small>Clique para inserir no cursor. Qualquer outro <code>#</code> impede salvar.</small></div></header>
            <ul>
              @for (p of placeholdersDaVariante(); track p.nome) {
                <li><button type="button" class="link-arquivo" (click)="inserir(p)">#{{ p.nome }}</button><small>{{ p.descricao }}</small></li>
              }
            </ul>
          </aside>
        </div>

        <footer class="acoes-mascara">
          <a class="acao-secundaria" routerLink="/contratos/modelos">Voltar aos modelos</a>
          <button type="submit" class="acao-primaria" [disabled]="salvando() || !nome.trim() || !html.trim()">Salvar máscara</button>
        </footer>
      </form>
    }
  `,
  styles: `
    .pagina-mascara { display: grid; gap: 16px; }
    .dados-mascara { padding: 16px 20px 0; }
    .corpo-mascara { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 16px; align-items: start; }
    .editor-mascara { padding-bottom: 16px; }
    .editor-mascara > header, .placeholders-mascara > header { padding: 14px 20px 8px; }
    .editor-mascara app-editor-rico { display: block; margin: 0 20px; }
    :host ::ng-deep .editor-mascara .editor-rico .superficie-editor { min-height: max(420px, calc(100vh - 430px)); font-size: 14px; line-height: 1.6; }
    .placeholders-mascara { position: sticky; top: 12px; max-height: calc(100vh - 100px); overflow: auto; padding-bottom: 12px; }
    .placeholders-mascara ul { display: grid; gap: 10px; margin: 0; padding: 0 20px; list-style: none; }
    .placeholders-mascara li { display: grid; gap: 1px; }
    .placeholders-mascara li small { color: var(--spi-apagado); }
    .acoes-mascara { position: sticky; bottom: 0; z-index: 20; display: flex; justify-content: flex-end; gap: 10px; padding: 12px 20px;
      border-top: 1px solid var(--cor-e2e5e8); background: var(--cor-ffffff); }
    @media (max-width: 1000px) { .corpo-mascara { grid-template-columns: 1fr; } .placeholders-mascara { position: static; max-height: none; } }
  `,
})
export class ModeloPortariaComponent implements OnInit {
  /** `novo` ou o id da máscara (vem da URL). */
  readonly id = input.required<string>();

  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  private readonly editor = viewChild(EditorRicoComponent);

  protected readonly carregando = signal(true);
  protected readonly salvando = signal(false);
  protected readonly placeholders = signal<PlaceholderPortaria[]>([]);
  protected nome = '';
  protected ativo = true;
  protected variante: VarianteMascara = 'sem_anterior';
  protected html = '';

  ngOnInit(): void {
    this.api.placeholdersPortaria().subscribe({ next: (p) => this.placeholders.set(p), error: (e) => this.dialogos.mostrarErro(e) });
    if (this.id() === 'novo') {
      this.carregando.set(false);
      return;
    }
    this.api.modelos('portaria', false).subscribe({
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
    this.variante = modelo.conteudo.variante ?? 'sem_anterior';
    this.html = modelo.conteudo.html ?? '';
  }

  /** A máscara sem portaria anterior não usa os placeholders da anterior. */
  protected placeholdersDaVariante(): PlaceholderPortaria[] {
    return this.placeholders().filter((p) => this.variante === 'com_anterior' || !p.da_anterior);
  }

  protected inserir(placeholder: PlaceholderPortaria): void {
    this.editor()?.inserir(`#${placeholder.nome}`);
  }

  protected salvar(): void {
    this.salvando.set(true);
    const dados = { tipo: 'portaria', nome: this.nome.trim(), ativo: this.ativo, variante: this.variante, html: this.html };
    this.api.salvarModelo(dados, this.id() === 'novo' ? undefined : this.id()).subscribe({
      next: () => void this.roteador.navigate(['/contratos/modelos']),
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível salvar a máscara'); },
    });
  }
}
