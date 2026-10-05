// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a carteira de contratos (lista com busca, paginação, menu de ações e importação do SGI).

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { UpperCasePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { debounceTime, Subject } from 'rxjs';

import { PaginacaoComponent } from '../../../shared/componentes/paginacao/paginacao.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { CHAVE_CONTEXTO_CARTEIRA, ContratosApiService } from '../compartilhado/contratos-api.service';
import { ResumoContrato } from '../compartilhado/contratos.models';
import { ROTULOS_SITUACAO } from '../compartilhado/rotulos';
import { AcessoService } from '../../../core/acesso/acesso.service';
import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { ImportacaoSgiComponent } from './importacao-sgi.component';
import { ImportacaoXlsxComponent } from './importacao-xlsx.component';

/** Tela 1: carteira de contratos, com busca e paginação no servidor. */
const CHAVE_MEUS = 'contratos.meus';

function lerMeus(): boolean {
  try { return localStorage.getItem(CHAVE_MEUS) === '1'; } catch { return false; }
}

/** Colunas da carteira que a API sabe ordenar. */
export type ColunaCarteira = 'numero' | 'empresa' | 'data_inicio' | 'data_fim' | 'situacao' | 'base_mensal' | 'valor_global';

@Component({
  selector: 'app-carteira',
  imports: [UpperCasePipe, FormsModule, RouterLink, CabecalhoModuloComponent, PaginacaoComponent, ImportacaoSgiComponent, ImportacaoXlsxComponent, ...PIPES_FORMATACAO],
  templateUrl: './carteira.component.html',
  // Qualquer clique fora fecha o menu de ações aberto
  host: { '(document:click)': 'menuAberto.set(null)' },
})
export class CarteiraComponent implements OnInit {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  // `acesso` é usado no template para mostrar o botão "Novo contrato" só a quem pode modificar
  protected readonly acesso = inject(AcessoService);
  private readonly autenticacao = inject(AutenticacaoService);
  // Botão "Importar do SGI": só a conta root (abre o cadastro preenchido com um contrato do SGI, sem salvar)
  protected readonly contaRoot = computed(() => !!this.autenticacao.usuario()?.conta_root);

  // Estado da lista: busca, página, itens e o menu de ações aberto (id do contrato)
  protected readonly rotulos = ROTULOS_SITUACAO;
  protected busca = '';
  protected readonly pagina = signal(1);
  protected readonly tamanhoPagina = 20;
  protected readonly itens = signal<ResumoContrato[]>([]);
  protected readonly total = signal(0);
  protected readonly carregando = signal(true);
  protected readonly menuAberto = signal<string | null>(null);
  // Ordenação por coluna (feita na API, antes de paginar); padrão: número, mais recentes primeiro
  protected readonly ordenarPor = signal<ColunaCarteira>('numero');
  protected readonly direcao = signal<'asc' | 'desc'>('desc');
  private readonly pesquisa$ = new Subject<void>();

  constructor() {
    // Pesquisa 300 ms depois da última tecla, sempre a partir da página 1
    this.pesquisa$.pipe(debounceTime(300), takeUntilDestroyed()).subscribe(() => this.carregar(1));
  }

  ngOnInit(): void {
    this.carregar(1);
  }

  /** Chamado a cada tecla no campo de busca. */
  protected aoDigitar(): void {
    this.pesquisa$.next();
  }

  /** "Meus contratos": só onde a pessoa integra a equipe vigente; a escolha fica lembrada neste navegador. */
  protected readonly meus = signal(lerMeus());

  protected alternarMeus(valor: boolean): void {
    this.meus.set(valor);
    try { localStorage.setItem(CHAVE_MEUS, valor ? '1' : '0'); } catch { /* sem armazenamento: só não lembra */ }
    this.carregar(1);
  }

  /** Busca uma página da carteira na API. */
  protected carregar(pagina: number): void {
    this.carregando.set(true);
    this.api.listar(this.busca.trim(), pagina, this.tamanhoPagina, this.meus(), this.ordenarPor(), this.direcao()).subscribe({
      next: (resposta) => {
        this.itens.set(resposta.itens);
        this.guardarContexto();
        this.total.set(resposta.total);
        this.pagina.set(pagina);
        this.carregando.set(false);
      },
      error: (erro) => {
        this.carregando.set(false);
        this.dialogos.mostrarErro(erro, 'Não foi possível carregar os contratos');
      },
    });
  }

  /** Guarda a busca, o filtro "Meus contratos" e a ordenação desta lista: o detalhe do contrato usa para navegar ‹ › entre os contratos dela. */
  private guardarContexto(): void {
    try {
      sessionStorage.setItem(CHAVE_CONTEXTO_CARTEIRA, JSON.stringify({ busca: this.busca.trim(), meus: this.meus(), ordenarPor: this.ordenarPor(), direcao: this.direcao() }));
    } catch {
      // sem armazenamento: o anterior/próximo usa a ordem padrão
    }
  }

  /** Clique no título da coluna: ordena por ela (crescente); clicar de novo inverte o sentido. Volta à página 1. */
  protected ordenar(coluna: ColunaCarteira): void {
    if (this.ordenarPor() === coluna) {
      this.direcao.update((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      this.ordenarPor.set(coluna);
      // Textos e datas começam crescentes; valores em dinheiro, do maior para o menor
      this.direcao.set(coluna === 'base_mensal' || coluna === 'valor_global' ? 'desc' : 'asc');
    }
    this.carregar(1);
  }

  /** Valor de `aria-sort` do título da coluna. */
  protected sentido(coluna: ColunaCarteira): 'ascending' | 'descending' | 'none' {
    if (this.ordenarPor() !== coluna) return 'none';
    return this.direcao() === 'asc' ? 'ascending' : 'descending';
  }

  /** Abre o detalhe do contrato ao clicar na linha. */
  protected abrir(contrato: ResumoContrato): void {
    void this.roteador.navigate(['/contratos', contrato.id]);
  }

  /** Clique na linha: abre o contrato, exceto quando o clique foi no link do número (o navegador cuida: Ctrl+clique, botão do meio, "abrir em nova aba") ou com tecla modificadora. */
  protected abrirLinha(evento: MouseEvent, contrato: ResumoContrato): void {
    if (evento.ctrlKey || evento.metaKey || evento.shiftKey || (evento.target as HTMLElement).closest('a')) return;
    this.abrir(contrato);
  }

  /** Abre o contrato em uma nova aba do navegador (item do menu de ações). */
  protected abrirEmNovaAba(contrato: ResumoContrato): void {
    window.open(this.roteador.serializeUrl(this.roteador.createUrlTree(['/contratos', contrato.id])), '_blank', 'noopener');
    this.menuAberto.set(null);
  }

  /** Abre ou fecha o menu de ações da linha; `stopPropagation` evita que o clique abra o contrato. */
  protected alternarMenu(evento: Event, id: string): void {
    evento.stopPropagation();
    this.menuAberto.set(this.menuAberto() === id ? null : id);
  }

  /** Pede confirmação (com contagem de 5 s) e exclui o contrato. */
  protected async excluir(evento: Event, contrato: ResumoContrato): Promise<void> {
    evento.stopPropagation();
    this.menuAberto.set(null);
    const confirmado = await this.dialogos.confirmar({
      titulo: `Excluir o contrato ${contrato.numero}?`,
      mensagem: 'O contrato e tudo o que depende dele (itens, execução, documentos, NEs) serão removidos. Esta ação não pode ser desfeita.',
      rotuloConfirmar: 'Excluir contrato',
      segundos: 5,
    });
    if (!confirmado) return;
    this.api.excluir(contrato.id).subscribe({ next: () => this.carregar(this.pagina()), error: (e) => this.dialogos.mostrarErro(e) });
  }
}
