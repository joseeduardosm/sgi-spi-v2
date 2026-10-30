// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de prorrogação: meses, meses quebrados, itens sob demanda, memória de cálculo, checklist e registro do termo.

import { EtapaTrilha, TrilhaEtapasComponent } from '../../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { DatePipe } from '@angular/common';
import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom, forkJoin } from 'rxjs';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { AlteracoesApiService, GravacaoProrrogacao } from '../compartilhado/alteracoes-api.service';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { CalculoMesQuebrado, DetalheContrato, DocumentoProrrogacao, ProcessoProrrogacao, RegraSobDemanda, VigenciaRetroativa } from '../compartilhado/contratos.models';
import { paraDecimalApi, paraDecimalTela } from '../compartilhado/rotulos';
import { PosAssinaturaProrrogacaoComponent } from './pos-assinatura-prorrogacao.component';
import { LinkificarPipe } from '../../../shared/utilitarios/linkificar.pipe';

import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';

/**
 * Tela 4: prorrogação (para frente). Meses → meses quebrados (pro rata × integral, uma escolha para todos) → itens sob demanda →
 * memória de cálculo (PDF e XLSX) → checklist (padrão como ponto de partida, mais documentos incluídos) → termo e registro.
 */
@Component({
  selector: 'app-prorrogacao',
  imports: [PosAssinaturaProrrogacaoComponent, TrilhaEtapasComponent, EsqueletoComponent, LinkificarPipe, FormsModule, RouterLink, DatePipe, CabecalhoModuloComponent, EnvioPdfComponent, ...PIPES_FORMATACAO],
  templateUrl: './prorrogacao.component.html',
})
export class ProrrogacaoComponent implements OnInit {
  /** Etapas na trilha comum; meses quebrados e sob demanda só aparecem quando existem. */
  protected trilha(p: ProcessoProrrogacao): EtapaTrilha[] {
    const prazo = !!p.meses;
    const quebrados = !!p.memoria?.meses_quebrados.length;
    const escolhido = !p.memoria?.precisa_escolher;
    const formalizada = !!this.assinadaEm && !!this.termo;
    const pronto = prazo && escolhido && p.memoria_atualizada && p.obrigatorios_pendentes === 0;
    const etapas: EtapaTrilha[] = [{ id: 'prazo', rotulo: 'Meses', estado: prazo ? 'concluida' : 'atual', subtitulo: prazo ? `${p.meses} mês(es)` : undefined }];
    if (quebrados) etapas.push({ id: 'quebrados', rotulo: 'Meses quebrados', estado: escolhido ? 'concluida' : 'atual', subtitulo: p.memoria?.calculo_mes_quebrado === 'integral' ? 'integral' : escolhido ? 'pro rata' : 'escolha o cálculo' });
    if (p.itens_sob_demanda.length) etapas.push({ id: 'itens', rotulo: 'Itens sob demanda', estado: prazo ? 'concluida' : 'aguardando', opcional: true });
    etapas.push(
      { id: 'memoria', rotulo: 'Memória de cálculo', estado: p.memoria_atualizada ? 'concluida' : prazo && escolhido ? 'atual' : 'aguardando', subtitulo: p.memoria_atualizada ? `v${p.memorias.at(-1)?.versao}` : undefined },
      { id: 'checklist', rotulo: 'Checklist', estado: p.obrigatorios_pendentes === 0 ? 'concluida' : 'atual', subtitulo: p.obrigatorios_pendentes ? `${p.obrigatorios_pendentes} obrigatório(s) pendente(s)` : undefined },
      { id: 'registro', rotulo: 'Termo e registro', estado: pronto && formalizada ? 'atual' : 'bloqueada', subtitulo: pronto && formalizada ? 'pronto para registrar' : undefined },
    );
    return etapas;
  }

  /** Número da etapa na tela (meses quebrados e sob demanda só contam quando existem). */
  protected numero(p: ProcessoProrrogacao, etapa: 'quebrados' | 'itens' | 'memoria' | 'checklist' | 'registro'): number {
    const ordem = ['prazo', ...(p.memoria?.meses_quebrados.length ? ['quebrados'] : []), ...(p.itens_sob_demanda.length ? ['itens'] : []), 'memoria', 'checklist', 'registro'];
    return ordem.indexOf(etapa) + 1;
  }

  readonly id = input.required<string>();

  private readonly api = inject(AlteracoesApiService);
  private readonly contratos = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);

  // Constantes do template e os dados carregados
  protected readonly calculos: CalculoMesQuebrado[] = ['pro_rata', 'integral'];
  protected readonly rotulosCalculo: Record<CalculoMesQuebrado, string> = { pro_rata: 'Opção 1 · Pro rata', integral: 'Opção 2 · Integral' };
  protected readonly contrato = signal<DetalheContrato | null>(null);
  protected readonly processo = signal<ProcessoProrrogacao | null>(null);
  protected readonly retroativas = signal<VigenciaRetroativa[]>([]);
  // Opção dos meses quebrados sendo gravada (botão com indicador de carregando)
  protected readonly escolhendo = signal<CalculoMesQuebrado | null>(null);

  // Campos do rascunho (ligados por [(ngModel)]): prazo, regra, limites e grade dos itens sob demanda
  protected meses: number | null = null;
  protected regra: RegraSobDemanda = 'saldo_remanescente';
  protected limites: Record<string, string> = {};
  protected grade: Record<string, Record<string, string>> = {};
  // Dados do registro: assinatura e número do Termo Aditivo e o PDF
  protected assinadaEm = '';
  protected numeroTermo = '';
  protected termo: File | null = null;
  // Inclusão de documento fora do checklist padrão
  protected readonly incluindoDocumento = signal(false);
  protected readonly enviandoInclusao = signal(false);
  protected novoDocumentoNome = '';
  protected novoDocumentoDescricao = '';
  protected novoDocumentoArquivo: File | null = null;
  // Dados do cadastro de uma vigência retroativa: prazo, assinatura, número do Termo Aditivo e o PDF
  protected mesesRetroativa: number | null = null;
  protected assinadaRetroativa = '';
  protected numeroRetroativa = '';
  protected termoRetroativa: File | null = null;

  /** Carrega o contrato, o rascunho da prorrogação e as vigências retroativas em paralelo. */
  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    forkJoin({ contrato: this.contratos.consultar(this.id()), processo: this.api.prorrogacao(this.id()), retroativas: this.api.vigenciasRetroativas(this.id()) }).subscribe({
      next: ({ contrato, processo, retroativas }) => {
        this.contrato.set(contrato);
        this.retroativas.set(retroativas);
        this.aplicar(processo);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a prorrogação'),
    });
  }

  /** Confirma e cadastra a vigência retroativa; o contrato recua o início e as vigências são renumeradas. */
  protected async cadastrarRetroativa(): Promise<void> {
    if (!this.mesesRetroativa || !this.assinadaRetroativa || !this.termoRetroativa) return;
    const c = this.contrato();
    const meses = Number(this.mesesRetroativa);
    const inicioAtual = c ? c.data_inicio.split('-').reverse().join('/') : 'o início atual';
    // Primeira confirmação (10 s): tudo o que esta ação muda, para a pessoa saber exatamente o que vai acontecer
    const leu = await this.dialogos.confirmar({
      titulo: 'Atenção: esta ação volta o contrato no tempo',
      mensagem:
        `Você vai cadastrar uma vigência retroativa de ${meses} mês(es), que termina na véspera do início atual do contrato (${inicioAtual}). Leia com calma o que isso provoca:\n\n` +
        '• O INÍCIO DO CONTRATO RECUA. A data inicial passa a ser a do começo da vigência retroativa, e todas as vigências são renumeradas: a mais antiga vira a 1ª.\n' +
        '• SURGEM COMPETÊNCIAS DE ÉPOCA. Os meses dessa vigência passam a existir para medição, nota fiscal, retenção, CADIN, checklist, consolidado e pagamento. Quem tem pendências e alertas passa a ser cobrado por elas.\n' +
        '• É PRECISO CADASTRAR OS EMPENHOS DA ÉPOCA. As Notas de Empenho e os cancelamentos daquele período precisam existir para que os pagamentos possam ser registrados.\n' +
        '• CHECKLISTS DA ÉPOCA. Cada competência retroativa copia o checklist ativo do contrato; o checklist precisa estar ativo e os documentos daquele período precisam ser reunidos.\n' +
        '• REAJUSTES DA ÉPOCA. Os preços da vigência retroativa só ficam corretos depois do reajuste retroativo (o preço volta pelo índice, em cada item). Até lá, ela usa os preços atuais.\n' +
        '• O TERMO ADITIVO ASSINADO ENTRA NOS DOCUMENTOS IMPORTANTES do contrato e o histórico registra quem fez e quando.\n' +
        '• OS PRAZOS NÃO MUDAM: a vigência retroativa não conta no prazo máximo nem nas prorrogações.\n' +
        '• NADA É APAGADO, mas desfazer só é possível enquanto não houver medição, reajuste ou aditamento nessa vigência.\n\n' +
        'Confira o prazo, a data de assinatura e o PDF do termo antes de continuar.',
      rotuloConfirmar: 'Li e entendi os impactos',
      segundos: 10,
    });
    if (!leu) return;
    // Segunda confirmação (3 s): última chance de desistir
    const ok = await this.dialogos.confirmar({
      titulo: 'Tem certeza que deseja continuar?',
      mensagem: `O contrato vai retroagir ${meses} mês(es) e as competências de época serão criadas. Esta alteração muda o contrato inteiro.`,
      rotuloConfirmar: 'Sim, cadastrar a vigência retroativa',
      segundos: 3,
      perigo: true,
    });
    if (!ok) return;
    this.dialogos.executar(this.api.cadastrarVigenciaRetroativa(this.id(), Number(this.mesesRetroativa), this.assinadaRetroativa, this.numeroRetroativa.trim(), this.termoRetroativa), 'Cadastrando a vigência retroativa…').subscribe({
      next: () => {
        this.mesesRetroativa = null;
        this.assinadaRetroativa = '';
        this.numeroRetroativa = '';
        this.termoRetroativa = null;
        this.carregar();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível cadastrar a vigência retroativa'),
    });
  }

  /** Pede confirmação e desfaz a vigência retroativa mais antiga. */
  protected async desfazerRetroativa(v: VigenciaRetroativa): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Desfazer a vigência retroativa?',
      mensagem: 'As competências e a previsão dela serão apagadas, o início do contrato volta ao que era e as vigências serão renumeradas.',
      rotuloConfirmar: 'Desfazer',
      segundos: 5,
    });
    if (ok) this.api.desfazerVigenciaRetroativa(this.id(), v.id).subscribe({ next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Baixa o termo de uma vigência retroativa. */
  protected baixarTermo(anexoId: string): void {
    this.api.baixarProrrogacao(this.id(), anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Preenche os campos da tela com o rascunho devolvido pela API. */
  private aplicar(p: ProcessoProrrogacao): void {
    this.processo.set(p);
    this.meses = p.meses;
    this.regra = p.regra_sob_demanda;
    this.limites = Object.fromEntries(p.itens_sob_demanda.map((i) => [i.item_id, paraDecimalTela(i.limite)]));
    this.grade = Object.fromEntries(
      p.itens_sob_demanda.map((i) => [i.item_id, Object.fromEntries(p.meses_nova_vigencia.map((m) => [m, paraDecimalTela(i.apontamentos[m] ?? '0') || '']))]),
    );
  }

  /** Saldo do item na nova vigência (limite − soma da grade). */
  protected saldo(itemId: string): number {
    const limite = Number(paraDecimalApi(this.limites[itemId])) || 0;
    return limite - Object.values(this.grade[itemId] ?? {}).reduce((t, q) => t + (Number(paraDecimalApi(q)) || 0), 0);
  }

  /** Ao trocar a regra, recalcula os limites sugeridos (na regra manual, mantém o digitado). */
  protected aoMudarRegra(): void {
    const p = this.processo();
    if (!p) return;
    for (const item of p.itens_sob_demanda) {
      if (this.regra === 'saldo_remanescente') this.limites[item.item_id] = paraDecimalTela(item.saldo_remanescente);
      if (this.regra === 'repetir_inicial') this.limites[item.item_id] = paraDecimalTela(item.quantidade_original);
    }
  }

  /** Monta o corpo do rascunho no formato da API. */
  private corpo(calculo?: CalculoMesQuebrado): GravacaoProrrogacao {
    return {
      meses: this.meses ? Number(this.meses) : null,
      regra_sob_demanda: this.regra,
      plano_sob_demanda: (this.processo()?.itens_sob_demanda ?? []).map((i) => ({
        item_id: i.item_id,
        limite: paraDecimalApi(this.limites[i.item_id]),
        apontamentos: Object.fromEntries(Object.entries(this.grade[i.item_id] ?? {}).map(([m, q]) => [m, paraDecimalApi(q)])),
      })),
      calculo_mes_quebrado: calculo ?? null,
    };
  }

  /** Salva o rascunho (com a escolha dos meses quebrados, se informada); devolve true se deu certo. */
  protected async salvar(calculo?: CalculoMesQuebrado): Promise<boolean> {
    try {
      this.aplicar(await firstValueFrom(this.api.salvarProrrogacao(this.id(), this.corpo(calculo))));
      return true;
    } catch (e) {
      this.dialogos.mostrarErro(e, 'Não foi possível salvar o rascunho');
      return false;
    }
  }

  /** Escolhe o cálculo dos meses quebrados (vale para todos), gera a memória e baixa o PDF e o XLSX. */
  protected async escolherCalculo(calculo: CalculoMesQuebrado): Promise<void> {
    if (this.escolhendo()) return;
    this.escolhendo.set(calculo);
    const ok = await this.salvar(calculo);
    if (ok) await this.gerarMemoria(true);
    this.escolhendo.set(null);
  }

  /** Gera a memória de cálculo (salvando antes o que foi digitado) e, se pedido, baixa o PDF e o XLSX da versão atual. */
  protected async gerarMemoria(baixar = true): Promise<boolean> {
    try {
      const p = await firstValueFrom(this.dialogos.executar(this.api.gerarMemoriaProrrogacao(this.id()), 'Gerando a memória de cálculo…'));
      this.aplicar(p);
      const ultima = p.memorias.at(-1);
      if (baixar && ultima) {
        this.baixar(ultima.pdf.anexo_id);
        this.baixar(ultima.xlsx.anexo_id);
      }
      return true;
    } catch (e) {
      this.dialogos.mostrarErro(e, 'Não foi possível gerar a memória de cálculo');
      return false;
    }
  }

  /** Salva o rascunho e gera a memória (botão da etapa da memória). */
  protected async salvarEGerar(): Promise<void> {
    if (await this.salvar()) await this.gerarMemoria(true);
  }

  // --- Checklist ---
  /** Anexa (ou substitui) o PDF de um documento do checklist. */
  protected anexarDocumento(documento: DocumentoProrrogacao, arquivo: File | null): void {
    if (!arquivo) return;
    this.dialogos.executar(this.api.anexarDocumentoProrrogacao(this.id(), documento.id, arquivo), 'Enviando o documento…').subscribe({
      next: (p) => this.aplicar(p),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível anexar o documento'),
    });
  }

  protected abrirInclusao(): void {
    this.novoDocumentoNome = '';
    this.novoDocumentoDescricao = '';
    this.novoDocumentoArquivo = null;
    this.incluindoDocumento.set(true);
  }

  /** Inclui um documento fora do checklist padrão (sempre opcional). */
  protected incluirDocumento(): void {
    if (!this.novoDocumentoNome.trim() || !this.novoDocumentoArquivo) return;
    this.enviandoInclusao.set(true);
    this.api.incluirDocumentoProrrogacao(this.id(), this.novoDocumentoNome.trim(), this.novoDocumentoDescricao.trim(), this.novoDocumentoArquivo).subscribe({
      next: (p) => {
        this.enviandoInclusao.set(false);
        this.incluindoDocumento.set(false);
        this.aplicar(p);
      },
      error: (e) => {
        this.enviandoInclusao.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível incluir o documento');
      },
    });
  }

  /** Exclui um documento incluído, depois de confirmar. */
  protected async excluirDocumento(documento: DocumentoProrrogacao): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir "${documento.nome}"?`, mensagem: 'O documento sai do checklist desta prorrogação e o arquivo é descartado.', rotuloConfirmar: 'Excluir documento' });
    if (ok) this.api.excluirDocumentoProrrogacao(this.id(), documento.id).subscribe({ next: (p) => this.aplicar(p), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Baixa um arquivo da prorrogação. */
  protected baixar(anexoId: string): void {
    this.api.baixarProrrogacao(this.id(), anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Salva o rascunho, gera a memória se estiver desatualizada, confirma e registra a prorrogação com o Termo Aditivo. */
  protected async registrar(): Promise<void> {
    if (!(await this.salvar())) return;
    let p = this.processo()!;
    if (p.memoria?.precisa_escolher) {
      this.dialogos.avisar('Escolha o cálculo dos meses quebrados', 'Antes de registrar, escolha pro rata ou integral na etapa dos meses quebrados.');
      return;
    }
    if (!p.memoria_atualizada && !(await this.gerarMemoria(false))) return;
    p = this.processo()!;
    if (p.obrigatorios_pendentes > 0) {
      this.dialogos.avisar('Checklist incompleto', `Anexe os ${p.obrigatorios_pendentes} documento(s) obrigatório(s) do checklist antes de registrar.`);
      return;
    }
    const ok = await this.dialogos.confirmar({
      titulo: 'Registrar a prorrogação?',
      mensagem: `A nova vigência (${p.nova_vigencia_inicio.split('-').reverse().join('/')} a ${p.nova_vigencia_fim?.split('-').reverse().join('/')}) será criada e o termo aditivo entrará nos documentos importantes.`,
      rotuloConfirmar: 'Registrar prorrogação',
      segundos: 5,
    });
    if (!ok || !this.termo) return;
    this.dialogos.executar(this.api.registrarProrrogacao(this.id(), this.assinadaEm, this.numeroTermo.trim(), this.termo), 'Registrando a prorrogação…').subscribe({
      next: () => void this.roteador.navigate(['/contratos', this.id()]),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível registrar a prorrogação'),
    });
  }

  /** Pede confirmação e descarta o rascunho. */
  protected async descartar(): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: 'Descartar o rascunho?', mensagem: 'Prazo, grade, memória de cálculo e checklist serão apagados.', rotuloConfirmar: 'Descartar' });
    if (ok) this.api.descartarProrrogacao(this.id()).subscribe({ next: () => void this.roteador.navigate(['/contratos', this.id()]), error: (e) => this.dialogos.mostrarErro(e) });
  }
}
