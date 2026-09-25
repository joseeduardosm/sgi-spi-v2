// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de detalhe do contrato e a troca entre as suas abas.

import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { hojeIso } from '../../../shared/utilitarios/formatadores';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { AlteracoesApiService } from '../compartilhado/alteracoes-api.service';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { AlteracaoCampo, DetalheContrato, Prorrogacao } from '../compartilhado/contratos.models';
import { HistoricoCampoComponent } from '../compartilhado/historico-campo.component';
import { LinhaDoTempoComponent } from '../compartilhado/linha-do-tempo.component';
import { MESES, PAPEIS, PERIODICIDADES, ROTULOS_CAMPO, ROTULOS_SITUACAO, ROTULOS_TIPO_ITEM } from '../compartilhado/rotulos';
import { AbaChecklistsComponent } from './aba-checklists.component';
import { AbaDocumentosComponent } from './aba-documentos.component';
import { AbaExecucaoComponent } from './aba-execucao.component';
import { AbaFormulariosComponent } from './aba-formularios.component';
import { AbaNotasComponent } from './aba-notas.component';
import { AbaPrevisaoComponent } from './aba-previsao.component';

/** Abas da tela de detalhe. */
type Aba = 'principal' | 'itens' | 'previsao' | 'processos' | 'equipe' | 'documentos' | 'checklists' | 'formularios' | 'notas' | 'execucao';

/** Tela 3: detalhe do contrato com abas. */
@Component({
  selector: 'app-detalhe-contrato',
  imports: [
    RouterLink, CabecalhoModuloComponent, HistoricoCampoComponent, LinhaDoTempoComponent, AbaPrevisaoComponent, AbaDocumentosComponent,
    AbaChecklistsComponent, AbaFormulariosComponent, AbaNotasComponent, AbaExecucaoComponent, ...PIPES_FORMATACAO,
  ],
  templateUrl: './detalhe-contrato.component.html',
})
export class DetalheContratoComponent implements OnInit {
  // Id do contrato, vindo da URL (/contratos/:id) graças ao withComponentInputBinding
  readonly id = input.required<string>();

  private readonly api = inject(ContratosApiService);
  private readonly alteracoes = inject(AlteracoesApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);

  // Abas na ordem de exibição
  protected readonly abas: { id: Aba; rotulo: string }[] = [
    { id: 'principal', rotulo: 'Principal' },
    { id: 'itens', rotulo: 'Itens' },
    { id: 'previsao', rotulo: 'Previsão orçamentária' },
    { id: 'processos', rotulo: 'Processos' },
    { id: 'equipe', rotulo: 'Equipe' },
    { id: 'documentos', rotulo: 'Documentos Importantes' },
    { id: 'checklists', rotulo: 'Checklists' },
    { id: 'formularios', rotulo: 'Formulários de avaliação' },
    { id: 'notas', rotulo: 'Notas de Empenho' },
    { id: 'execucao', rotulo: 'Execução' },
  ];
  // Estado: aba aberta, contrato, histórico de campos e prorrogações
  protected readonly aba = signal<Aba>('principal');
  protected readonly contrato = signal<DetalheContrato | null>(null);
  protected readonly historico = signal<AlteracaoCampo[]>([]);
  protected readonly prorrogacoes = signal<Prorrogacao[]>([]);
  // Constantes expostas ao template
  protected readonly hoje = hojeIso();
  protected readonly papeis = PAPEIS;
  protected readonly rotulosSituacao = ROTULOS_SITUACAO;
  protected readonly rotulosTipo = ROTULOS_TIPO_ITEM;
  protected readonly rotulosCampo = ROTULOS_CAMPO;
  protected readonly meses = MESES;

  // Integrante da equipe por papel, para montar a aba Equipe
  protected readonly membro = computed(() => {
    const equipe = this.contrato()?.equipe ?? [];
    return Object.fromEntries(equipe.map((m) => [m.papel, m]));
  });
  protected readonly periodicidade = computed(() => PERIODICIDADES.find((p) => p.valor === this.contrato()?.periodicidade_meses)?.rotulo ?? '');
  // Só permite prorrogar quem pode editar e com todos os códigos orçamentários dos itens preenchidos
  protected readonly podeProrrogar = computed(() => {
    const c = this.contrato();
    return !!c?.permissoes.pode_editar && c.itens.every((i) => i.codigo_classe && i.codigo_natureza_despesa && i.codigo_siafisico && i.codigo_catmat_catser);
  });
  protected readonly totais = computed(() => {
    const c = this.contrato();
    return c ? { base: c.base_mensal, global: c.valor_global } : null;
  });

  /** Abre a aba indicada na URL (?aba=...) e carrega os dados. */
  ngOnInit(): void {
    const aba = this.rota.snapshot.queryParamMap.get('aba') as Aba | null;
    if (aba && this.abas.some((a) => a.id === aba)) this.aba.set(aba);
    this.carregar();
  }

  /** Carrega contrato, histórico e prorrogações em paralelo (`forkJoin` espera as três respostas). */
  protected carregar(): void {
    forkJoin({
      contrato: this.api.consultar(this.id()),
      historico: this.api.historico(this.id()),
      prorrogacoes: this.alteracoes.prorrogacoes(this.id()),
    }).subscribe({
      next: ({ contrato, historico, prorrogacoes }) => {
        this.contrato.set(contrato);
        this.historico.set(historico);
        this.prorrogacoes.set(prorrogacoes);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o contrato'),
    });
  }

  /** Troca de aba e guarda a escolha na URL (recarregar a página mantém a aba). */
  protected escolher(aba: Aba): void {
    this.aba.set(aba);
    void this.roteador.navigate([], { queryParams: { aba }, replaceUrl: true });
  }

  // Traduz o id da empresa no histórico para a razão social
  protected nomeEmpresa = (valor: unknown): string => (valor === this.contrato()?.empresa.id ? this.contrato()!.empresa.razao_social : '');

  /** Pede confirmação e desfaz a última prorrogação. */
  protected async desfazer(prorrogacao: Prorrogacao): Promise<void> {
    const confirmado = await this.dialogos.confirmar({
      titulo: 'Desfazer a última prorrogação?',
      mensagem: `A vigência volta a terminar em ${prorrogacao.fim_anterior.split('-').reverse().join('/')}. O termo aditivo sai dos documentos importantes e a previsão da vigência é removida.`,
      rotuloConfirmar: 'Desfazer prorrogação',
      segundos: 5,
    });
    if (!confirmado) return;
    this.alteracoes.desfazerProrrogacao(this.id(), prorrogacao.id).subscribe({ next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Baixa o Termo Aditivo da prorrogação (guardado como documento importante). */
  protected baixarTermo(prorrogacao: Prorrogacao): void {
    if (prorrogacao.codigo_documento) this.api.baixarDocumento(this.id(), prorrogacao.codigo_documento).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
