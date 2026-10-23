// Criado por José Eduardo Santana Martins
// Este arquivo serve para a lista de fichas de pré-cadastro do RH (quem vai entrar na SPI), com busca e filtro por situação.

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { ImportacaoFichasComponent } from './importacao-fichas.component';
import { RhPreCadastroApiService } from './rh-pre-cadastro-api.service';
import { ResumoFicha, ROTULOS_STATUS_FICHA, StatusFicha } from './rh-pre-cadastro.models';

/** Lista de fichas de pré-cadastro: dados pessoais sensíveis, só para o RH. */
@Component({
  selector: 'app-pre-cadastros',
  imports: [FormsModule, RouterLink, CabecalhoRhComponent, EsqueletoComponent, ImportacaoFichasComponent],
  template: `
    <app-cabecalho-rh titulo="Pré-cadastro" [trilha]="['Pré-cadastro']" descricao="Ficha de quem vai entrar na SPI. O login proposto vai para a TI e a ficha se liga à conta quando ela aparece no AD." />

    <section class="painel-gestao" aria-labelledby="titulo-fichas">
      <div class="barra-ferramentas">
        <div><h2 id="titulo-fichas">Fichas</h2><p>{{ fichas().length }} ficha(s) encontrada(s).</p></div>
        <div class="acoes-formulario">
          <button type="button" class="acao-secundaria" (click)="importacaoAberta.set(true)">Ficha por planilha</button>
          <a class="acao-primaria" routerLink="/rh/pre-cadastros/nova"><span>+</span> Nova ficha</a>
        </div>
      </div>
      <div class="filtros-gestao">
        <input type="search" aria-label="Buscar" placeholder="Buscar por nome, login, CPF, documento ou RS/PV" [(ngModel)]="busca" (ngModelChange)="carregar()" />
      </div>
      <div class="chips-filtro" role="group" aria-label="Situação">
        <button type="button" [class.ativo]="status === ''" (click)="filtrar('')">Todas</button>
        @for (s of situacoes; track s[0]) { <button type="button" [class.ativo]="status === s[0]" (click)="filtrar(s[0])">{{ s[1] }}</button> }
        <button type="button" [class.ativo]="status === 'validar'" (click)="filtrar('validar')">Aguardando validação</button>
      </div>
      <div class="tabela-gestao-envoltorio">
        <table class="tabela-gestao">
          <thead><tr><th>Nome</th><th>Login proposto</th><th>Cargo pretendido</th><th>Início previsto</th><th>Situação</th><th class="coluna-acoes">Ações</th></tr></thead>
          <tbody>
            @if (carregando()) { <tr><td colspan="6"><app-esqueleto tipo="tabela" [colunas]="5" [linhas]="5" /></td></tr> }
            @for (f of fichas(); track f.id) {
              <tr>
                <td><strong>{{ f.nome_completo }}</strong></td>
                <td>@if (f.login_proposto) { <span class="texto-codigo">{{ f.login_proposto }}</span> } @else { — }</td>
                <td>{{ f.cargo_rotulo || '—' }}</td>
                <td>{{ f.inicio_previsto ? dataBr(f.inicio_previsto) : '—' }}</td>
                <td><span [class]="classe(f.status)">{{ rotulo(f.status) }}</span></td>
                <td class="coluna-acoes"><div class="acoes-linha"><a class="acao-secundaria acao-pequena" [routerLink]="['/rh/pre-cadastros', f.id]">{{ f.status === 'vinculado' || f.status === 'cancelado' ? 'Ver' : 'Abrir' }}</a></div></td>
              </tr>
            } @empty {
              @if (!carregando()) { <tr><td class="estado-vazio" colspan="6">Nenhuma ficha encontrada.</td></tr> }
            }
          </tbody>
        </table>
      </div>
    </section>

    <app-importacao-fichas [(aberta)]="importacaoAberta" (importado)="carregar()" />
  `,
})
export class PreCadastrosComponent implements OnInit {
  private readonly api = inject(RhPreCadastroApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly situacoes = Object.entries(ROTULOS_STATUS_FICHA);
  protected readonly fichas = signal<ResumoFicha[]>([]);
  protected readonly carregando = signal(true);
  protected readonly importacaoAberta = signal(false);
  protected busca = '';
  protected status = '';

  ngOnInit(): void {
    this.carregar();
  }

  protected carregar(): void {
    this.carregando.set(true);
    this.api.listar(this.busca.trim(), this.status === 'validar' ? '' : this.status, this.status === 'validar').subscribe({
      next: (l) => { this.fichas.set(l); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar as fichas'); },
    });
  }

  protected filtrar(status: string): void {
    this.status = status;
    this.carregar();
  }

  protected rotulo(s: StatusFicha): string {
    return ROTULOS_STATUS_FICHA[s];
  }

  protected classe(s: StatusFicha): string {
    // Selos globais: situação (verde, cinza, âmbar), nível (azul) e origem (vermelho)
    return { rascunho: 'selo-nivel', aguardando_conta: 'selo-situacao alerta', vinculado: 'selo-situacao', cancelado: 'selo-origem' }[s];
  }

  protected dataBr(iso: string): string {
    return iso.split('-').reverse().join('/');
  }
}
