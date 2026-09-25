// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir a lista de empresas contratadas, com busca, ordenação e paginação no servidor.

import { Component, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { debounceTime, Subject } from 'rxjs';

import { AcessoService } from '../../../core/acesso/acesso.service';
import { PaginacaoComponent } from '../../../shared/componentes/paginacao/paginacao.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { ResumoEmpresa } from '../compartilhado/contratos.models';
import { formatarCnpj } from '../compartilhado/rotulos';

/** Colunas pelas quais a lista pode ser ordenada. */
type Coluna = 'cnpj' | 'razao_social' | 'nome_fantasia' | 'endereco';

/** Tela 8: empresas contratadas, com busca em qualquer dado e ordenação no servidor. */
@Component({
  selector: 'app-empresas',
  imports: [FormsModule, RouterLink, CabecalhoModuloComponent, PaginacaoComponent],
  host: { '(document:click)': 'menuAberto.set(null)' },
  template: `
    <app-cabecalho-modulo titulo="Empresas contratadas" [trilha]="['Empresas']" descricao="Cadastro das contratadas e de seus prepostos (contatos da empresa, não usuários do portal)." />
    <section class="painel-gestao" aria-labelledby="titulo-empresas">
      <div class="barra-ferramentas">
        <div><h2 id="titulo-empresas">Empresas</h2><p>{{ total() }} empresa(s) encontrada(s).</p></div>
        @if (acesso.pode('contratos', 'MODIFICACAO')) { <a class="acao-primaria" routerLink="/contratos/empresas/nova"><span>+</span> Cadastrar empresa</a> }
      </div>
      <div class="filtros-gestao" role="search">
        <input type="search" [(ngModel)]="busca" (ngModelChange)="pesquisa$.next()" aria-label="Pesquisar empresas"
               placeholder="Pesquisar empresas (CNPJ, nome, endereço, prepostos ou contratos)" />
      </div>
      <div class="tabela-gestao-envoltorio">
        <table class="tabela-gestao">
          <thead>
            <tr>
              @for (c of colunas; track c.id) {
                <th><button type="button" class="link-arquivo" style="color: inherit; text-decoration: none; font-size: inherit; text-transform: inherit; letter-spacing: inherit"
                            (click)="ordenar(c.id)">{{ c.rotulo }} {{ ordem === c.id ? (direcao === 'asc' ? '▲' : '▼') : '' }}</button></th>
              }
              <th>Prepostos</th><th>Contratos</th><th class="coluna-acoes">Ações</th>
            </tr>
          </thead>
          <tbody>
            @for (e of itens(); track e.id) {
              <tr class="linha-clicavel" (click)="abrir(e)">
                <td>{{ cnpj(e.cnpj) }}</td>
                <td><strong>{{ e.razao_social }}</strong>@if (!e.ativa) { <small class="texto-erro">Inativa</small> }</td>
                <td>{{ e.nome_fantasia || '—' }}</td>
                <td>{{ e.endereco || '—' }}</td>
                <td>{{ e.prepostos.join(', ') || '—' }}</td>
                <td>@for (c of e.contratos; track c.id) { <span class="etiqueta">{{ c.numero }}</span> } @empty { — }</td>
                <td>
                  <div class="acoes-linha" style="position: relative">
                    <button type="button" aria-label="Ações" (click)="alternarMenu($event, e.id)">⋮</button>
                    @if (menuAberto() === e.id) {
                      <div class="menu-flutuante" role="menu">
                        <button type="button" role="menuitem" (click)="abrir(e)">Visualizar</button>
                        @if (acesso.pode('contratos', 'CONTROLE_TOTAL')) { <button type="button" role="menuitem" (click)="excluir($event, e)">Excluir</button> }
                      </div>
                    }
                  </div>
                </td>
              </tr>
            } @empty {
              <tr><td class="estado-vazio" colspan="7">{{ carregando() ? 'Carregando…' : 'Nenhuma empresa encontrada.' }}</td></tr>
            }
          </tbody>
        </table>
      </div>
      <app-paginacao [pagina]="pagina()" [tamanhoPagina]="tamanhoPagina" [total]="total()" (mudar)="carregar($event)" />
    </section>
  `,
})
export class EmpresasComponent implements OnInit {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  protected readonly acesso = inject(AcessoService);

  // Cabeçalhos clicáveis da tabela (ordenação)
  protected readonly colunas: { id: Coluna; rotulo: string }[] = [
    { id: 'cnpj', rotulo: 'CNPJ' },
    { id: 'razao_social', rotulo: 'Razão social' },
    { id: 'nome_fantasia', rotulo: 'Nome fantasia' },
    { id: 'endereco', rotulo: 'Endereço' },
  ];
  // Estado: busca, ordenação, paginação e o menu de ações aberto
  protected busca = '';
  protected ordem: Coluna = 'razao_social';
  protected direcao: 'asc' | 'desc' = 'asc';
  protected readonly pagina = signal(1);
  protected readonly tamanhoPagina = 25;
  protected readonly itens = signal<ResumoEmpresa[]>([]);
  protected readonly total = signal(0);
  protected readonly carregando = signal(true);
  protected readonly menuAberto = signal<string | null>(null);
  // Fluxo da busca: público porque o template chama pesquisa$.next() a cada tecla
  protected readonly pesquisa$ = new Subject<void>();
  protected readonly cnpj = formatarCnpj;

  constructor() {
    // Pesquisa 300 ms depois da última tecla, a partir da página 1
    this.pesquisa$.pipe(debounceTime(300), takeUntilDestroyed()).subscribe(() => this.carregar(1));
  }

  ngOnInit(): void {
    this.carregar(1);
  }

  /** Busca uma página de empresas na API. */
  protected carregar(pagina: number): void {
    this.carregando.set(true);
    this.api.empresas(this.busca.trim(), this.ordem, this.direcao, pagina, this.tamanhoPagina).subscribe({
      next: (r) => {
        this.itens.set(r.itens);
        this.total.set(r.total);
        this.pagina.set(pagina);
        this.carregando.set(false);
      },
      error: (e) => {
        this.carregando.set(false);
        this.dialogos.mostrarErro(e);
      },
    });
  }

  /** Clique no cabeçalho: mesma coluna inverte a direção; outra coluna começa crescente. */
  protected ordenar(coluna: Coluna): void {
    this.direcao = this.ordem === coluna && this.direcao === 'asc' ? 'desc' : 'asc';
    this.ordem = coluna;
    this.carregar(1);
  }

  /** Abre o detalhe da empresa. */
  protected abrir(empresa: ResumoEmpresa): void {
    void this.roteador.navigate(['/contratos/empresas', empresa.id]);
  }

  /** Abre ou fecha o menu de ações da linha, sem abrir a empresa. */
  protected alternarMenu(evento: Event, id: string): void {
    evento.stopPropagation();
    this.menuAberto.set(this.menuAberto() === id ? null : id);
  }

  /** Pede confirmação e exclui a empresa (a API recusa se houver contratos). */
  protected async excluir(evento: Event, empresa: ResumoEmpresa): Promise<void> {
    evento.stopPropagation();
    this.menuAberto.set(null);
    const ok = await this.dialogos.confirmar({ titulo: `Excluir ${empresa.razao_social}?`, mensagem: 'A empresa e seus prepostos serão removidos. Empresas com contratos não podem ser excluídas (inative-as).', rotuloConfirmar: 'Excluir', segundos: 3 });
    if (ok) this.api.excluirEmpresa(empresa.id).subscribe({ next: () => this.carregar(this.pagina()), error: (e) => this.dialogos.mostrarErro(e) });
  }
}
