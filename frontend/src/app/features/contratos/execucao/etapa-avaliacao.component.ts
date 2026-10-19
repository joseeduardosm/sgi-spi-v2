// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a etapa 2 (avaliação dos serviços): notas, ocorrências do diário, ateste, PDF, e-mail à contratada e reconsideração.

import { DatePipe } from '@angular/common';
import { RascunhoGuardado, RascunhoService } from '../../../core/rascunho/rascunho.service';
import { AvisoRascunhoComponent } from '../../../shared/componentes/aviso-rascunho/aviso-rascunho.component';
import { Component, computed, DestroyRef, inject, input, OnChanges, output, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { DetalheCompetencia, OcorrenciaAvaliacao, RespostaAvaliacao } from '../compartilhado/contratos.models';
import { ROTULOS_PAPEL } from '../compartilhado/rotulos';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { RascunhoServidorComponent } from '../compartilhado/rascunho-servidor.component';
import { OpcaoEmailComponent } from '../compartilhado/opcao-email.component';
import { LinkificarPipe } from '../../../shared/utilitarios/linkificar.pipe';

/** Nota e justificativa digitadas para um item. */
type Resposta = { nota: string; justificativa: string };

/** Notas e justificativas ainda não salvas, guardadas como rascunho; `base` identifica a avaliação gravada a que elas se referem. */
interface RascunhoAvaliacao {
  base: string;
  iniciais: Record<string, Resposta>;
  gestor: Record<string, Resposta>;
  complemento: string;
}

/** Etapa 2: avaliação inicial, avaliação do gestor, ateste, PDF assinado e reconsideração. */
@Component({
  selector: 'app-etapa-avaliacao',
  imports: [RascunhoServidorComponent, AvisoRascunhoComponent, LinkificarPipe, FormsModule, RouterLink, DatePipe, EnvioPdfComponent, OpcaoEmailComponent, ...PIPES_FORMATACAO],
  templateUrl: './etapa-avaliacao.component.html',
  // Colunas fixas: Peso, Nota e Justificativa ficam alinhadas em todos os grupos, qualquer que seja o tamanho dos textos
  styles: `
    .tabela-avaliacao { width: 100%; table-layout: fixed; }
    .tabela-avaliacao .col-peso { width: 92px; }
    .tabela-avaliacao .col-nota { width: 210px; }
    .tabela-avaliacao .col-justificativa { width: 34%; }
    .tabela-avaliacao td, .tabela-avaliacao th { vertical-align: top; overflow-wrap: anywhere; }
    .tabela-avaliacao td:not(:first-child) { vertical-align: middle; }
    .tabela-avaliacao .campo-tabela { width: 100%; }
  `,
})
export class EtapaAvaliacaoComponent implements OnChanges {
  readonly detalhe = input.required<DetalheCompetencia>();
  readonly editavel = input(false);
  readonly atualizado = output<DetalheCompetencia>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly autenticacao = inject(AutenticacaoService);
  private readonly rascunhos = inject(RascunhoService);
  private readonly destruir = inject(DestroyRef);

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
  // Ocorrências do diário por item impactado
  protected readonly ocorrenciasPorItem = computed(() => {
    const mapa: Record<string, OcorrenciaAvaliacao[]> = {};
    for (const o of this.avaliacao().ocorrencias ?? []) for (const id of o.itens) (mapa[id] ??= []).push(o);
    return mapa;
  });
  protected readonly reenviando = signal(false);
  // "Enviar por e-mail" começa desmarcado: só envia quem marcar
  protected readonly enviarEmail = signal(false);
  protected readonly prepostosIds = signal<(string | number)[] | null>(null);
  protected readonly fontePrepostos = () => this.api.gruposPrepostos(this.detalhe().contrato_id);
  // O usuário logado já registrou ciência no ateste?
  protected readonly jaRegistrei = computed(() => this.avaliacao().ciencias.some((c) => c.usuario_id === this.autenticacao.usuario()?.id));
  // Notas fechadas: avaliação inicial salva e, se alguma nota ficou abaixo da máxima, a do gestor também
  protected readonly notasFechadas = computed(() => {
    const a = this.avaliacao();
    return !!a.avaliacao_inicial_em && (!a.precisa_avaliacao_gestor || !!a.avaliacao_gestor_em);
  });

  // Retrato das respostas gravadas já carregadas na tela: a atualização periódica da competência (ex.: acompanhamento do envio do e-mail)
  // traz um objeto novo, mas não pode apagar as notas escolhidas e ainda não salvas
  private assinatura = '';
  // Respostas como vieram do servidor (para saber se há algo digitado e ainda não salvo) e controle do rascunho
  private base = '';
  private vigiando = false;
  protected readonly rascunhoRestaurado = signal<RascunhoGuardado<RascunhoAvaliacao> | null>(null);

  /** Quando a competência muda de verdade (respostas gravadas ou outra avaliação), recarrega as respostas a partir dela. */
  ngOnChanges(): void {
    const a = this.avaliacao();
    const assinatura = JSON.stringify([this.detalhe().id, a.definicao, a.respostas_iniciais, a.respostas_gestor, a.complemento_gestor, a.concluida_em]);
    if (assinatura === this.assinatura) return;
    this.assinatura = assinatura;
    // Converte as respostas da API em {item: {nota, justificativa}}
    const mapa = (respostas: RespostaAvaliacao[]) => Object.fromEntries(respostas.map((r) => [r.item_id, { nota: String(Number(r.nota)), justificativa: r.justificativa }]));
    const itens = a.definicao.grupos.flatMap((g) => g.itens.map((i) => i.id));
    const vazio = () => Object.fromEntries(itens.map((id) => [id, { nota: '', justificativa: '' }]));
    this.iniciais = { ...vazio(), ...mapa(a.respostas_iniciais) };
    // O gestor começa com as notas dele ou, se ainda não avaliou, com as da avaliação inicial
    this.gestor = { ...vazio(), ...(a.respostas_gestor.length ? mapa(a.respostas_gestor) : mapa(a.respostas_iniciais)) };
    this.complemento = a.complemento_gestor;
    this.base = this.retratoDasRespostas();
    this.restaurarRascunho();
    if (!this.vigiando) {
      this.vigiando = true;
      // Guarda as notas e justificativas digitadas e ainda não salvas (some ao salvar; não vale se a avaliação já mudou no servidor)
      this.rascunhos.vigiar<RascunhoAvaliacao>(this.destruir, this.chaveRascunho(), () => this.estadoDoRascunho());
    }
  }

  private chaveRascunho(): string {
    return `avaliacao:${this.detalhe().id}`;
  }

  private retratoDasRespostas(): string {
    return JSON.stringify([this.iniciais, this.gestor, this.complemento]);
  }

  /** Só há rascunho quando se pode editar e algo difere do que está salvo. */
  private estadoDoRascunho(): RascunhoAvaliacao | null {
    if (!this.editavel() || this.avaliacao().concluida_em || this.retratoDasRespostas() === this.base) return null;
    return { base: this.assinatura, iniciais: this.iniciais, gestor: this.gestor, complemento: this.complemento };
  }

  /** Preenche de novo o que foi digitado e não salvo, se a avaliação gravada continua a mesma; senão descarta o rascunho velho. */
  private restaurarRascunho(): void {
    this.rascunhoRestaurado.set(null);
    const guardado = this.rascunhos.ler<RascunhoAvaliacao>(this.chaveRascunho());
    if (!guardado) return;
    if (guardado.dados.base !== this.assinatura || !this.editavel() || this.avaliacao().concluida_em) {
      this.rascunhos.limpar(this.chaveRascunho());
      return;
    }
    this.iniciais = { ...this.iniciais, ...guardado.dados.iniciais };
    this.gestor = { ...this.gestor, ...guardado.dados.gestor };
    this.complemento = guardado.dados.complemento;
    this.rascunhoRestaurado.set(guardado);
  }

  /** Campos para o rascunho salvo no servidor (visível à equipe): sempre as notas da tela, mesmo incompletas. */
  protected readonly dadosDoRascunhoServidor = (): Record<string, unknown> | null => ({ iniciais: this.iniciais, gestor: this.gestor, complemento: this.complemento });

  /** Preenche a tela com o rascunho salvo pela equipe. */
  protected carregarRascunhoDaEquipe(dados: Record<string, unknown>): void {
    this.iniciais = { ...this.iniciais, ...(dados['iniciais'] as Record<string, Resposta>) };
    this.gestor = { ...this.gestor, ...(dados['gestor'] as Record<string, Resposta>) };
    this.complemento = String(dados['complemento'] ?? '');
    this.rascunhoRestaurado.set(null);
  }

  /** Descarta o rascunho e volta às notas salvas. */
  protected descartarRascunho(): void {
    this.rascunhos.limpar(this.chaveRascunho());
    this.rascunhoRestaurado.set(null);
    this.assinatura = '';
    this.ngOnChanges();
  }

  /** A nota está preenchida e abaixo da máxima (exige justificativa). */
  protected abaixo(nota: string): boolean {
    return nota !== '' && Number(nota) < this.notaMaxima();
  }

  /** Justificativa obrigatória: nota abaixo da máxima ou nota máxima em item com ocorrência do diário. */
  protected exigeJustificativa(itemId: string, nota: string): boolean {
    return this.abaixo(nota) || (nota !== '' && !!this.ocorrenciasPorItem()[itemId]?.length);
  }

  /** Converte as respostas da tela para o formato da API. */
  private respostas(origem: Record<string, Resposta>): RespostaAvaliacao[] {
    return Object.entries(origem).map(([item_id, r]) => ({ item_id, nota: r.nota, justificativa: r.justificativa.trim() }));
  }

  /** Todas as notas preenchidas e as abaixo da máxima com justificativa. */
  protected completas(origem: Record<string, Resposta>): boolean {
    return Object.entries(origem).every(([id, r]) => r.nota !== '' && (!this.exigeJustificativa(id, r.nota) || r.justificativa.trim()));
  }

  /** Reenvia o relatório de avaliação à contratada. */
  protected reenviarEmail(): void {
    const d = this.detalhe();
    this.reenviando.set(true);
    this.api.reenviarEmailAvaliacao(d.contrato_id, d.id).subscribe({
      next: (novo) => {
        this.reenviando.set(false);
        this.atualizado.emit(novo);
      },
      error: (e) => {
        this.reenviando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível reenviar o e-mail');
      },
    });
  }

  /** Executa a chamada (com a janela "Executando" se houver mensagem) e devolve a competência atualizada. */
  private emitir(requisicao: ReturnType<ExecucaoApiService['acaoAvaliacao']>, titulo: string, processando?: string, apagarRascunho = false): void {
    const fluxo = processando ? this.dialogos.executar(requisicao, processando) : requisicao;
    fluxo.subscribe({
      next: (novo) => {
        // Notas gravadas de verdade: o rascunho da equipe não serve mais
        if (apagarRascunho) this.rascunhoDaEquipe()?.apagar();
        this.atualizado.emit(novo);
      },
      error: (e) => this.dialogos.mostrarErro(e, titulo),
    });
  }

  private readonly rascunhoDaEquipe = viewChild<RascunhoServidorComponent>('rascunhoServidor');

  /** Grava a avaliação inicial. */
  protected salvarInicial(): void {
    const d = this.detalhe();
    this.emitir(this.api.avaliacaoInicial(d.contrato_id, d.id, this.respostas(this.iniciais)), 'Não foi possível salvar a avaliação inicial', undefined, true);
  }

  /** Grava a avaliação do gestor. */
  protected salvarGestor(): void {
    const d = this.detalhe();
    this.emitir(this.api.avaliacaoGestor(d.contrato_id, d.id, this.respostas(this.gestor), this.complemento.trim()), 'Não foi possível salvar a avaliação do gestor', undefined, true);
  }

  /** Registra a ciência do usuário no ateste. */
  protected cienciaAteste(): void {
    const d = this.detalhe();
    this.emitir(this.api.acaoAvaliacao(d.contrato_id, d.id, 'ciencia'), 'Não foi possível registrar a ciência');
  }

  /** Gera o PDF do relatório de avaliação. */
  protected exportarPdf(): void {
    const d = this.detalhe();
    this.emitir(this.api.acaoAvaliacao(d.contrato_id, d.id, 'pdf', this.enviarEmail(), this.prepostosIds() as string[] | null), 'Não foi possível gerar o PDF', 'Gerando o relatório de avaliação…');
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
