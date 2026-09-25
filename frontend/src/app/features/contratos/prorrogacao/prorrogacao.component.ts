import { DatePipe } from '@angular/common';
import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { AlteracoesApiService, GravacaoProrrogacao } from '../compartilhado/alteracoes-api.service';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { CamposParecer, DetalheContrato, ProcessoProrrogacao, RegraSobDemanda } from '../compartilhado/contratos.models';
import { paraDecimalApi, paraDecimalTela, ROTULOS_PAPEL } from '../compartilhado/rotulos';

const CAMPOS: { campo: keyof CamposParecer; rotulo: string }[] = [
  { campo: 'avaliacao_geral', rotulo: 'Avaliação geral da execução contratual' },
  { campo: 'resumo_qualidade', rotulo: 'Resumo executivo das avaliações de qualidade' },
  { campo: 'historico_ocorrencias', rotulo: 'Histórico de ocorrências' },
  { campo: 'reclamacoes', rotulo: 'Reclamações de servidores e tratativas' },
  { campo: 'atendimento_chamados', rotulo: 'Atendimento de chamados e obrigações' },
  { campo: 'parecer', rotulo: 'Parecer para prorrogação contratual' },
];

/** Tela 4: prorrogação com prazo, itens sob demanda, parecer opcional, ciências opcionais e termo aditivo. */
@Component({
  selector: 'app-prorrogacao',
  imports: [FormsModule, RouterLink, DatePipe, CabecalhoModuloComponent, EnvioPdfComponent, ...PIPES_FORMATACAO],
  templateUrl: './prorrogacao.component.html',
})
export class ProrrogacaoComponent implements OnInit {
  readonly id = input.required<string>();

  private readonly api = inject(AlteracoesApiService);
  private readonly contratos = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  private readonly autenticacao = inject(AutenticacaoService);

  protected readonly campos = CAMPOS;
  protected readonly papeis = ROTULOS_PAPEL;
  protected readonly contrato = signal<DetalheContrato | null>(null);
  protected readonly processo = signal<ProcessoProrrogacao | null>(null);

  protected meses: number | null = null;
  protected regra: RegraSobDemanda = 'saldo_remanescente';
  protected parecer: CamposParecer = { avaliacao_geral: '', resumo_qualidade: '', historico_ocorrencias: '', reclamacoes: '', atendimento_chamados: '', parecer: '' };
  protected limites: Record<string, string> = {};
  protected grade: Record<string, Record<string, string>> = {};
  protected assinadaEm = '';
  protected numeroTermo = '';
  protected termo: File | null = null;

  ngOnInit(): void {
    forkJoin({ contrato: this.contratos.consultar(this.id()), processo: this.api.prorrogacao(this.id()) }).subscribe({
      next: ({ contrato, processo }) => {
        this.contrato.set(contrato);
        this.aplicar(processo);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a prorrogação'),
    });
  }

  private aplicar(p: ProcessoProrrogacao): void {
    this.processo.set(p);
    this.meses = p.meses;
    this.regra = p.regra_sob_demanda;
    for (const c of CAMPOS) this.parecer[c.campo] = p[c.campo];
    this.limites = Object.fromEntries(p.itens_sob_demanda.map((i) => [i.item_id, paraDecimalTela(i.limite)]));
    this.grade = Object.fromEntries(
      p.itens_sob_demanda.map((i) => [i.item_id, Object.fromEntries(p.meses_nova_vigencia.map((m) => [m, paraDecimalTela(i.apontamentos[m] ?? '0') || '']))]),
    );
  }

  protected jaRegistrei(): boolean {
    return (this.processo()?.ciencias ?? []).some((c) => c.usuario_id === this.autenticacao.usuario()?.id);
  }

  protected possuiParecer(): boolean {
    return CAMPOS.some((c) => this.parecer[c.campo].trim());
  }

  protected parecerAlterado(): boolean {
    const p = this.processo();
    return !!p && CAMPOS.some((c) => this.parecer[c.campo] !== p[c.campo]);
  }

  protected saldo(itemId: string): number {
    const limite = Number(paraDecimalApi(this.limites[itemId])) || 0;
    return limite - Object.values(this.grade[itemId] ?? {}).reduce((t, q) => t + (Number(paraDecimalApi(q)) || 0), 0);
  }

  protected aoMudarRegra(): void {
    const p = this.processo();
    if (!p) return;
    for (const item of p.itens_sob_demanda) {
      if (this.regra === 'saldo_remanescente') this.limites[item.item_id] = paraDecimalTela(item.saldo_remanescente);
      if (this.regra === 'repetir_inicial') this.limites[item.item_id] = paraDecimalTela(item.quantidade_original);
    }
  }

  private corpo(): GravacaoProrrogacao {
    return {
      meses: this.meses ? Number(this.meses) : null,
      regra_sob_demanda: this.regra,
      plano_sob_demanda: (this.processo()?.itens_sob_demanda ?? []).map((i) => ({
        item_id: i.item_id,
        limite: paraDecimalApi(this.limites[i.item_id]),
        apontamentos: Object.fromEntries(Object.entries(this.grade[i.item_id] ?? {}).map(([m, q]) => [m, paraDecimalApi(q)])),
      })),
      ...this.parecer,
    };
  }

  protected async salvar(): Promise<boolean> {
    const p = this.processo();
    if (p?.ciencias.length && this.parecerAlterado()) {
      const ok = await this.dialogos.confirmar({
        titulo: 'Alterar o parecer?',
        mensagem: `As ${p.ciencias.length} ciências registradas serão apagadas.`,
        rotuloConfirmar: 'Salvar e apagar ciências',
        segundos: 3,
      });
      if (!ok) return false;
    }
    return new Promise((resolver) =>
      this.api.salvarProrrogacao(this.id(), this.corpo()).subscribe({
        next: (novo) => {
          this.aplicar(novo);
          resolver(true);
        },
        error: (e) => {
          this.dialogos.mostrarErro(e, 'Não foi possível salvar o rascunho');
          resolver(false);
        },
      }),
    );
  }

  protected ciencia(): void {
    this.api.acaoProrrogacao(this.id(), 'ciencia').subscribe({ next: (p) => this.aplicar(p), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected emitirParecer(): void {
    this.dialogos.executar(this.api.acaoProrrogacao(this.id(), 'parecer'), 'Gerando o parecer…').subscribe({
      next: (p) => {
        this.aplicar(p);
        if (p.relatorio) this.baixar(p.relatorio.anexo_id);
      },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected baixar(anexoId: string): void {
    this.api.baixarProrrogacao(this.id(), anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected async registrar(): Promise<void> {
    if (!(await this.salvar())) return;
    const p = this.processo()!;
    const ok = await this.dialogos.confirmar({
      titulo: 'Registrar a prorrogação?',
      mensagem: `A nova vigência (${p.nova_vigencia_inicio.split('-').reverse().join('/')} a ${p.nova_vigencia_fim?.split('-').reverse().join('/')}) será criada e o termo aditivo entrará nos documentos importantes.` +
        (this.possuiParecer() ? ' O PDF do parecer será emitido com as ciências registradas.' : ' Nenhum campo do parecer foi preenchido: a prorrogação será registrada sem relatório.'),
      rotuloConfirmar: 'Registrar prorrogação',
      segundos: 5,
    });
    if (!ok || !this.termo) return;
    this.dialogos.executar(this.api.registrarProrrogacao(this.id(), this.assinadaEm, this.numeroTermo.trim(), this.termo), 'Registrando a prorrogação…').subscribe({
      next: () => void this.roteador.navigate(['/contratos', this.id()]),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível registrar a prorrogação'),
    });
  }

  protected async descartar(): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: 'Descartar o rascunho?', mensagem: 'Prazo, grade e parecer serão apagados.', rotuloConfirmar: 'Descartar' });
    if (ok) this.api.descartarProrrogacao(this.id()).subscribe({ next: () => void this.roteador.navigate(['/contratos', this.id()]), error: (e) => this.dialogos.mostrarErro(e) });
  }
}
