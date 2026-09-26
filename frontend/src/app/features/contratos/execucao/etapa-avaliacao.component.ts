// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a etapa 2 (avaliação dos serviços): notas, ateste, PDF assinado e reconsideração.

import { DatePipe } from '@angular/common';
import { Component, computed, inject, input, OnChanges, output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { DetalheCompetencia, RespostaAvaliacao } from '../compartilhado/contratos.models';
import { ROTULOS_PAPEL } from '../compartilhado/rotulos';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';

/** Nota e justificativa digitadas para um item. */
type Resposta = { nota: string; justificativa: string };

/** Etapa 2: avaliação inicial, avaliação do gestor, ateste, PDF assinado e reconsideração. */
@Component({
  selector: 'app-etapa-avaliacao',
  imports: [FormsModule, DatePipe, EnvioPdfComponent, ...PIPES_FORMATACAO],
  templateUrl: './etapa-avaliacao.component.html',
})
export class EtapaAvaliacaoComponent implements OnChanges {
  readonly detalhe = input.required<DetalheCompetencia>();
  readonly editavel = input(false);
  readonly atualizado = output<DetalheCompetencia>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly autenticacao = inject(AutenticacaoService);

  // Rótulos dos papéis da equipe (Gestor, Fiscal técnico...) para a lista de ciências
  protected readonly papeis = ROTULOS_PAPEL;
  // Respostas em edição (avaliação inicial e do gestor), indexadas pelo id do item
  protected iniciais: Record<string, Resposta> = {};
  protected gestor: Record<string, Resposta> = {};
  protected complemento = '';
  // PDFs escolhidos: via assinada e justificativa da reconsideração
  private assinada: File | null = null;
  private justificativa: File | null = null;

  // Avaliação da competência (esta etapa só aparece quando ela existe)
  protected readonly avaliacao = computed(() => this.detalhe().avaliacao!);
  // Maior nota da escala: abaixo dela, a justificativa é obrigatória
  protected readonly notaMaxima = computed(() => Math.max(...this.avaliacao().definicao.escala.map((n) => Number(n.valor))));
  // O usuário logado já registrou ciência no ateste?
  protected readonly jaRegistrei = computed(() => this.avaliacao().ciencias.some((c) => c.usuario_id === this.autenticacao.usuario()?.id));
  // Notas fechadas: avaliação inicial salva e, se alguma nota ficou abaixo da máxima, a do gestor também
  protected readonly notasFechadas = computed(() => {
    const a = this.avaliacao();
    return !!a.avaliacao_inicial_em && (!a.precisa_avaliacao_gestor || !!a.avaliacao_gestor_em);
  });

  /** Sempre que a competência muda, recarrega as respostas a partir dela. */
  ngOnChanges(): void {
    const a = this.avaliacao();
    // Converte as respostas da API em {item: {nota, justificativa}}
    const mapa = (respostas: RespostaAvaliacao[]) => Object.fromEntries(respostas.map((r) => [r.item_id, { nota: String(Number(r.nota)), justificativa: r.justificativa }]));
    const itens = a.definicao.grupos.flatMap((g) => g.itens.map((i) => i.id));
    const vazio = () => Object.fromEntries(itens.map((id) => [id, { nota: '', justificativa: '' }]));
    this.iniciais = { ...vazio(), ...mapa(a.respostas_iniciais) };
    // O gestor começa com as notas dele ou, se ainda não avaliou, com as da avaliação inicial
    this.gestor = { ...vazio(), ...(a.respostas_gestor.length ? mapa(a.respostas_gestor) : mapa(a.respostas_iniciais)) };
    this.complemento = a.complemento_gestor;
  }

  /** A nota está preenchida e abaixo da máxima (exige justificativa). */
  protected abaixo(nota: string): boolean {
    return nota !== '' && Number(nota) < this.notaMaxima();
  }

  /** Converte as respostas da tela para o formato da API. */
  private respostas(origem: Record<string, Resposta>): RespostaAvaliacao[] {
    return Object.entries(origem).map(([item_id, r]) => ({ item_id, nota: r.nota, justificativa: r.justificativa.trim() }));
  }

  /** Todas as notas preenchidas e as abaixo da máxima com justificativa. */
  protected completas(origem: Record<string, Resposta>): boolean {
    return Object.values(origem).every((r) => r.nota !== '' && (!this.abaixo(r.nota) || r.justificativa.trim()));
  }

  /** Executa a chamada (com a janela "Executando" se houver mensagem) e devolve a competência atualizada. */
  private emitir(requisicao: ReturnType<ExecucaoApiService['acaoAvaliacao']>, titulo: string, processando?: string): void {
    const fluxo = processando ? this.dialogos.executar(requisicao, processando) : requisicao;
    fluxo.subscribe({ next: (novo) => this.atualizado.emit(novo), error: (e) => this.dialogos.mostrarErro(e, titulo) });
  }

  /** Grava a avaliação inicial. */
  protected salvarInicial(): void {
    const d = this.detalhe();
    this.emitir(this.api.avaliacaoInicial(d.contrato_id, d.id, this.respostas(this.iniciais)), 'Não foi possível salvar a avaliação inicial');
  }

  /** Grava a avaliação do gestor. */
  protected salvarGestor(): void {
    const d = this.detalhe();
    this.emitir(this.api.avaliacaoGestor(d.contrato_id, d.id, this.respostas(this.gestor), this.complemento.trim()), 'Não foi possível salvar a avaliação do gestor');
  }

  /** Registra a ciência do usuário no ateste. */
  protected cienciaAteste(): void {
    const d = this.detalhe();
    this.emitir(this.api.acaoAvaliacao(d.contrato_id, d.id, 'ciencia'), 'Não foi possível registrar a ciência');
  }

  /** Gera o PDF do relatório de avaliação. */
  protected exportarPdf(): void {
    const d = this.detalhe();
    this.emitir(this.api.acaoAvaliacao(d.contrato_id, d.id, 'pdf'), 'Não foi possível gerar o PDF', 'Gerando o relatório de avaliação…');
  }

  // Guardam os PDFs escolhidos nos campos de envio
  protected escolherAssinada(arquivo: File | null): void {
    this.assinada = arquivo;
  }

  protected escolherJustificativa(arquivo: File | null): void {
    this.justificativa = arquivo;
  }

  // Informam ao template se já há arquivo escolhido (os campos são privados)
  protected temAssinada(): boolean {
    return !!this.assinada;
  }

  protected temJustificativa(): boolean {
    return !!this.justificativa;
  }

  /** Envia a via assinada pela contratada (conclui a etapa). */
  protected enviarAssinada(): void {
    const d = this.detalhe();
    if (!this.assinada) return;
    this.dialogos.executar(this.api.enviarAvaliacao(d.contrato_id, d.id, 'assinada', this.assinada), 'Enviando o relatório assinado…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível enviar o relatório assinado'),
    });
  }

  /** Envia a justificativa da contratada e reabre a avaliação (uma única vez). */
  protected async reconsiderar(): Promise<void> {
    const d = this.detalhe();
    if (!this.justificativa) return;
    const ok = await this.dialogos.confirmar({
      titulo: 'Registrar a reconsideração?',
      mensagem: 'A avaliação reabre para nova análise. A reconsideração só pode ser usada uma vez nesta competência.',
      rotuloConfirmar: 'Reabrir avaliação',
      segundos: 5,
    });
    if (!ok) return;
    this.api.enviarAvaliacao(d.contrato_id, d.id, 'reconsideracao', this.justificativa).subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  /** Baixa um PDF da competência. */
  protected baixar(anexoId: string): void {
    const d = this.detalhe();
    this.api.baixar(d.contrato_id, d.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
