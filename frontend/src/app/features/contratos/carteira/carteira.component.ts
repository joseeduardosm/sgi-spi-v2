import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { debounceTime, Subject } from 'rxjs';

import { PaginacaoComponent } from '../../../shared/componentes/paginacao/paginacao.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { ResumoContrato } from '../compartilhado/contratos.models';
import { ROTULOS_SITUACAO } from '../compartilhado/rotulos';
import { AcessoService } from '../../../core/acesso/acesso.service';
import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { ImportacaoSgiComponent } from './importacao-sgi.component';

/** Tela 1: carteira de contratos, com busca e paginação no servidor. */
@Component({
  selector: 'app-carteira',
  imports: [FormsModule, RouterLink, CabecalhoModuloComponent, PaginacaoComponent, ImportacaoSgiComponent, ...PIPES_FORMATACAO],
  templateUrl: './carteira.component.html',
  host: { '(document:click)': 'menuAberto.set(null)' },
})
export class CarteiraComponent implements OnInit {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  protected readonly acesso = inject(AcessoService);
  private readonly autenticacao = inject(AutenticacaoService);
  protected readonly superRoot = computed(() => this.autenticacao.possuiPapel('SuperRoot'));

  protected readonly rotulos = ROTULOS_SITUACAO;
  protected busca = '';
  protected readonly pagina = signal(1);
  protected readonly tamanhoPagina = 20;
  protected readonly itens = signal<ResumoContrato[]>([]);
  protected readonly total = signal(0);
  protected readonly carregando = signal(true);
  protected readonly menuAberto = signal<string | null>(null);
  private readonly pesquisa$ = new Subject<void>();

  constructor() {
    this.pesquisa$.pipe(debounceTime(300), takeUntilDestroyed()).subscribe(() => this.carregar(1));
  }

  ngOnInit(): void {
    this.carregar(1);
  }

  protected aoDigitar(): void {
    this.pesquisa$.next();
  }

  protected carregar(pagina: number): void {
    this.carregando.set(true);
    this.api.listar(this.busca.trim(), pagina, this.tamanhoPagina).subscribe({
      next: (resposta) => {
        this.itens.set(resposta.itens);
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

  protected abrir(contrato: ResumoContrato): void {
    void this.roteador.navigate(['/contratos', contrato.id]);
  }

  protected alternarMenu(evento: Event, id: string): void {
    evento.stopPropagation();
    this.menuAberto.set(this.menuAberto() === id ? null : id);
  }

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
