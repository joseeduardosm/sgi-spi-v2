import { DatePipe } from '@angular/common';
import { Component, computed, inject, input, OnChanges, output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { AssinaturaAteste, DetalheCompetencia, MembroEquipe, RespostaAvaliacao } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';

type Resposta = { nota: string; justificativa: string };
const PAPEIS_ATESTE: { papel: AssinaturaAteste['papel']; rotulo: string }[] = [
  { papel: 'gestor', rotulo: 'Gestor' },
  { papel: 'fiscal_administrativo', rotulo: 'Fiscal administrativo' },
  { papel: 'fiscal_tecnico', rotulo: 'Fiscal técnico' },
];

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
  private readonly contratos = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly autenticacao = inject(AutenticacaoService);

  protected readonly papeisAteste = PAPEIS_ATESTE;
  protected iniciais: Record<string, Resposta> = {};
  protected gestor: Record<string, Resposta> = {};
  protected complemento = '';
  protected assinantes: Record<string, number | null> = {};
  protected equipe: MembroEquipe[] = [];
  private assinada: File | null = null;
  private justificativa: File | null = null;

  protected readonly avaliacao = computed(() => this.detalhe().avaliacao!);
  protected readonly notaMaxima = computed(() => Math.max(...this.avaliacao().definicao.escala.map((n) => Number(n.valor))));
  protected readonly souAssinante = computed(() =>
    this.avaliacao().assinaturas.some((a) => a.usuario_id === this.autenticacao.usuario()?.id && !a.ciencia_em),
  );

  ngOnChanges(): void {
    const a = this.avaliacao();
    const mapa = (respostas: RespostaAvaliacao[]) => Object.fromEntries(respostas.map((r) => [r.item_id, { nota: String(Number(r.nota)), justificativa: r.justificativa }]));
    const itens = a.definicao.grupos.flatMap((g) => g.itens.map((i) => i.id));
    const vazio = () => Object.fromEntries(itens.map((id) => [id, { nota: '', justificativa: '' }]));
    this.iniciais = { ...vazio(), ...mapa(a.respostas_iniciais) };
    this.gestor = { ...vazio(), ...(a.respostas_gestor.length ? mapa(a.respostas_gestor) : mapa(a.respostas_iniciais)) };
    this.complemento = a.complemento_gestor;
    this.assinantes = Object.fromEntries(PAPEIS_ATESTE.map((p) => [p.papel, a.assinaturas.find((s) => s.papel === p.papel)?.usuario_id ?? null]));
    this.contratos.consultar(this.detalhe().contrato_id).subscribe((c) => (this.equipe = c.equipe));
  }

  protected abaixo(nota: string): boolean {
    return nota !== '' && Number(nota) < this.notaMaxima();
  }

  private respostas(origem: Record<string, Resposta>): RespostaAvaliacao[] {
    return Object.entries(origem).map(([item_id, r]) => ({ item_id, nota: r.nota, justificativa: r.justificativa.trim() }));
  }

  protected completas(origem: Record<string, Resposta>): boolean {
    return Object.values(origem).every((r) => r.nota !== '' && (!this.abaixo(r.nota) || r.justificativa.trim()));
  }

  private emitir(requisicao: ReturnType<ExecucaoApiService['acaoAvaliacao']>, titulo: string, processando?: string): void {
    const fluxo = processando ? this.dialogos.executar(requisicao, processando) : requisicao;
    fluxo.subscribe({ next: (novo) => this.atualizado.emit(novo), error: (e) => this.dialogos.mostrarErro(e, titulo) });
  }

  protected salvarInicial(): void {
    const d = this.detalhe();
    this.emitir(this.api.avaliacaoInicial(d.contrato_id, d.id, this.respostas(this.iniciais)), 'Não foi possível salvar a avaliação inicial');
  }

  protected salvarGestor(): void {
    const d = this.detalhe();
    this.emitir(this.api.avaliacaoGestor(d.contrato_id, d.id, this.respostas(this.gestor), this.complemento.trim()), 'Não foi possível salvar a avaliação do gestor');
  }

  protected async salvarAssinaturas(): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Salvar as assinaturas do ateste?',
      mensagem: 'Cada pessoa indicada precisará registrar sua ciência no ateste antes da exportação do PDF.',
      rotuloConfirmar: 'Salvar assinaturas',
      segundos: 3,
    });
    if (!ok) return;
    const d = this.detalhe();
    const lista = Object.entries(this.assinantes).filter(([, id]) => id).map(([papel, id]) => ({ papel: papel as AssinaturaAteste['papel'], usuario_id: id! }));
    this.emitir(this.api.assinaturas(d.contrato_id, d.id, lista), 'Não foi possível salvar as assinaturas');
  }

  protected cienciaAteste(): void {
    const d = this.detalhe();
    this.emitir(this.api.acaoAvaliacao(d.contrato_id, d.id, 'ciencia'), 'Não foi possível registrar a ciência');
  }

  protected exportarPdf(): void {
    const d = this.detalhe();
    this.emitir(this.api.acaoAvaliacao(d.contrato_id, d.id, 'pdf'), 'Não foi possível gerar o PDF', 'Gerando o relatório de avaliação…');
  }

  protected escolherAssinada(arquivo: File | null): void {
    this.assinada = arquivo;
  }

  protected escolherJustificativa(arquivo: File | null): void {
    this.justificativa = arquivo;
  }

  protected temAssinada(): boolean {
    return !!this.assinada;
  }

  protected temJustificativa(): boolean {
    return !!this.justificativa;
  }

  protected enviarAssinada(): void {
    const d = this.detalhe();
    if (!this.assinada) return;
    this.dialogos.executar(this.api.enviarAvaliacao(d.contrato_id, d.id, 'assinada', this.assinada), 'Enviando o relatório assinado…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível enviar o relatório assinado'),
    });
  }

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

  protected baixar(anexoId: string): void {
    const d = this.detalhe();
    this.api.baixar(d.contrato_id, d.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected membrosDoPapel(papel: string): MembroEquipe[] {
    // Qualquer integrante vigente pode assinar; os do papel correspondente aparecem primeiro
    return [...this.equipe].sort((a, b) => Number(!a.papel.startsWith(papel)) - Number(!b.papel.startsWith(papel)));
  }
}
