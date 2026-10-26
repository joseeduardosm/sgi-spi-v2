// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar as etapas 5 (checklist mensal), 6 (documento consolidado) e 7 (Ordem Bancária).

import { DatePipe } from '@angular/common';
import { Component, effect, inject, input, output, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { BotaoCopiarComponent } from '../../../shared/componentes/botao-copiar/botao-copiar.component';
import { CampoArquivoComponent } from '../../../shared/componentes/campo-arquivo/campo-arquivo.component';
import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { HtmlConfiavelPipe } from '../../contratacoes/html-confiavel.pipe';
import { DetalheCompetencia, DocumentoMensal, Etapa } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { ROTULOS_ETAPA } from '../compartilhado/rotulos';
import { LinkificarPipe } from '../../../shared/utilitarios/linkificar.pipe';

/** Etapas 5 (checklist mensal), 6 (documento consolidado) e 7 (Ordem Bancária). */
@Component({
  selector: 'app-etapa-finais',
  imports: [HtmlConfiavelPipe, LinkificarPipe, DatePipe, FormsModule, BotaoCopiarComponent, CampoArquivoComponent, EnvioPdfComponent, ...PIPES_FORMATACAO],
  template: `
    @let d = detalhe();
    @switch (etapa()) {
      @case ('checklist') {
        <section class="cartao-dados" aria-labelledby="titulo-checklist-mensal">
          <header>
            <div><h2 id="titulo-checklist-mensal">Documentos mensais do checklist
                @if (d.empresa_cnpj) { <app-botao-copiar class="copiar-cnpj" [valor]="soNumeros(d.empresa_cnpj)" rotulo="Copiar CNPJ" titulo="Copiar o CNPJ da contratada (só números)" tamanho="pequeno" /> }</h2>
              <small>Os obrigatórios precisam ser anexados; os opcionais podem ficar sem anexo. Com todos anexados, a etapa conclui sozinha.</small></div>
            @if (obrigatoriosPendentes(d) === 0) { <span class="selo-situacao">Obrigatórios completos</span> } @else { <span class="selo-situacao alerta">{{ obrigatoriosPendentes(d) }} obrigatório(s) pendente(s)</span> }
          </header>
          <div class="resumo-medicao" aria-label="Resumo do checklist">
            <div [class.ok]="obrigatoriosPendentes(d) === 0" [class.alerta]="obrigatoriosPendentes(d) > 0"><span>Obrigatórios anexados</span><strong>{{ obrigatoriosAnexados(d) }} de {{ obrigatoriosTotal(d) }}</strong></div>
            <div><span>Opcionais anexados</span><strong>{{ opcionaisAnexados(d) }} de {{ opcionaisTotal(d) }}</strong></div>
            <div [class.alerta]="vencendo(d) > 0"><span>Validade a vencer ou vencida</span><strong>{{ vencendo(d) }}</strong><small>{{ vencendo(d) ? 'confira os documentos com validade' : 'nenhum documento com validade em risco' }}</small></div>
          </div>
          <div class="tabela-gestao-envoltorio">
            <table class="tabela-gestao">
              <thead><tr><th>Nº</th><th>Documento</th><th>Tipo</th><th>Situação</th><th>Arquivo</th></tr></thead>
              <tbody>
                @for (doc of d.documentos; track doc.id) {
                  <tr class="linha-checklist" [class.doc-anexado]="!!doc.arquivo" [class.doc-pendente]="!doc.arquivo">
                    <td>{{ $index + 1 }}</td>
                    <td><strong>{{ doc.nome }}</strong>@if (doc.observacao) { <small [innerHTML]="doc.observacao | linkificar"></small> }</td>
                    <td>{{ doc.obrigatorio ? 'Obrigatório' : 'Opcional' }}@if (doc.com_validade) { <small>Com validade</small> }</td>
                    <td><span class="selo-situacao" [class.perigo]="!doc.arquivo">{{ doc.arquivo ? 'Anexado' : doc.obrigatorio ? 'Pendente' : 'Não anexado' }}</span></td>
                    <td>
                      <div class="acoes-arquivo-doc">
                        @if (doc.arquivo) { <button type="button" class="acao-secundaria acao-pequena" (click)="baixar(doc.arquivo.anexo_id)">Baixar</button> }
                        @if (editavel() && doc.com_validade) {
                          <label class="campo-validade">Válido até *
                            <input type="date" [name]="'validade-' + doc.id" [ngModel]="validades[doc.id] ?? doc.validade_ate ?? ''" (ngModelChange)="validades[doc.id] = $event" /></label>
                        }
                        @if (editavel()) { <app-envio-pdf [pequeno]="true" [mostrarNome]="false" [rotulo]="doc.arquivo ? 'Substituir' : 'Selecionar documento PDF'" (selecionado)="enviarDocumento(doc, $event)" /> }
                      </div>
                      @if (doc.com_validade && doc.arquivo && doc.validade_ate) {
                        <small class="validade-doc" [attr.data-situacao]="vencimento(doc.validade_ate)">
                          Válido até {{ doc.validade_ate | dataBr }}@if (vencimento(doc.validade_ate) === 'perto') { (vence em até 30 dias) }@if (vencimento(doc.validade_ate) === 'vencido') { (vencido) }
                        </small>
                      }
                      @if (doc.reaproveitado_contrato) {
                        <small class="reaproveitado-contrato">Reaproveitado do contrato {{ doc.reaproveitado_contrato }} (competência {{ doc.reaproveitado_de | date: 'MM/yyyy' }})@if (doc.validade_ate) { · válido até {{ doc.validade_ate | dataBr }} }: confira e conclua</small>
                      } @else if (doc.reaproveitado_de) { <small class="reaproveitado-contrato">Reaproveitado da competência de {{ doc.reaproveitado_de | date: 'MM/yyyy' }}: confira e conclua</small> }
                      @if (editavel() && doc.sugestao_outro_contrato; as s) {
                        <div class="sugestao-outro-contrato">
                          <small>Disponível do contrato {{ s.contrato_numero }} (competência {{ s.competencia | date: 'MM/yyyy' }})@if (s.validade_ate) { · válido até {{ s.validade_ate | dataBr }} }</small>
                          <button type="button" class="acao-secundaria acao-pequena" (click)="usarDeOutroContrato(doc, s.origem_id)">Usar este documento</button>
                        </div>
                      }
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
          @if (editavel()) {
            <div class="barra-envio-nf barra-medicao">
              <div class="texto-envio">
                @if (obrigatoriosPendentes(d) > 0) { <span class="pendencias-nf">Anexe os {{ obrigatoriosPendentes(d) }} documento(s) obrigatório(s) pendente(s).</span> }
                @else { <span class="dica-formulario">Obrigatórios completos. Conclua o checklist para liberar o documento consolidado.</span> }
              </div>
              <div class="botoes-barra">
                @if (sugestoes(d) > 0) { <button type="button" class="acao-secundaria" (click)="trazerTodos()">Trazer os documentos válidos de outros contratos ({{ sugestoes(d) }})</button> }
                <button type="button" class="acao-primaria" [disabled]="obrigatoriosPendentes(d) > 0" (click)="concluirChecklist()" [title]="obrigatoriosPendentes(d) ? 'Anexe os documentos obrigatórios' : ''">Concluir checklist</button>
              </div>
            </div>
          }
        </section>
      }
      @case ('consolidado') {
        <section class="cartao-dados" aria-labelledby="titulo-consolidado">
          <header>
            <div><h2 id="titulo-consolidado">Documento consolidado</h2>
              <small>Um único PDF na ordem de execução, com folha de autenticação (código e hash) e resumo executivo.</small></div>
            @if (d.consolidado) { <span class="selo-situacao">Gerado</span> }
            @else if (d.etapa_atual === 'consolidado' || d.etapa_atual === 'ordem_bancaria' || d.etapa_atual === 'concluida') { <span class="selo-situacao alerta">Pronto para gerar</span> }
            @else { <span class="selo-situacao inativo">Aguardando etapas</span> }
          </header>
          <div class="corpo">
            <details class="como-funciona-nf" style="margin-bottom: 12px">
              <summary>O que entra no documento</summary>
              <p>Medição, avaliação (quando houver), nota fiscal, retenção de tributos, CADIN, checklist, folha de autenticação e resumo executivo. Cada documento enviado vem precedido de uma contracapa, e as páginas são numeradas em sequência.</p>
            </details>
            @if (d.etapa_atual !== 'consolidado' && d.etapa_atual !== 'ordem_bancaria' && d.etapa_atual !== 'concluida') {
              <p class="aviso-bloco">Liberado quando todas as etapas anteriores estiverem concluídas.
                @if (d.etapas_abertas.length) { Falta concluir: <b>{{ faltando(d) }}</b>. }
              </p>
            }
            @if (d.consolidado) {
              <article class="cartao-arquivo-final">
                <span class="icone-arquivo" aria-hidden="true">PDF</span>
                <div class="dados-arquivo"><strong>Documento consolidado</strong><small>Gerado em {{ d.consolidado.enviado_em | date: 'dd/MM/yyyy HH:mm' }} · {{ d.consolidado.tamanho | tamanho }}</small></div>
                <button type="button" class="acao-primaria" (click)="baixar(d.consolidado.anexo_id)">Baixar</button>
              </article>
            }
            <div class="acoes-cartao esquerda">
              <!-- 1ª geração: quem pode editar. Gerar novamente (substitui o atual): mesmo direito de quem edita, inclusive após a OB -->
              @if (!d.consolidado && d.pode_editar && (d.etapa_atual === 'consolidado' || d.etapa_atual === 'ordem_bancaria')) {
                <button type="button" class="acao-primaria" (click)="gerarConsolidado()">Gerar e baixar documento unificado</button>
              }
              @if (d.consolidado && d.pode_gerar_consolidado_novamente) {
                <button type="button" class="acao-secundaria" (click)="gerarConsolidado(true)">Gerar novamente</button>
              }
            </div>
          </div>
        </section>
        @if (despacho(); as desp) {
          <section class="cartao-dados cartao-dobravel" aria-labelledby="titulo-despacho">
            <header>
              <h2 id="titulo-despacho" style="flex: 1; min-width: 0">
                <button type="button" class="cabecalho-dobravel" [attr.aria-expanded]="despachoAberto()" aria-controls="corpo-despacho" (click)="despachoAberto.set(!despachoAberto())">
                  <span class="seta" [class.aberta]="despachoAberto()" aria-hidden="true">▸</span>
                  <span>Despacho de pagamento</span>
                  <small>Texto padrão com os dados do contrato e da competência. Copie e cole no SEI (a formatação é mantida).</small>
                </button>
              </h2>
              <app-botao-copiar rotulo="Copiar despacho" titulo="Copiar o despacho formatado" (acionar)="copiarDespacho()" />
            </header>
            @if (despachoAberto()) {
              <div class="corpo" id="corpo-despacho">
                <div class="texto-despacho" [innerHTML]="desp.html | htmlConfiavel"></div>
              </div>
            }
          </section>
        }
      }
      @case ('ordem_bancaria') {
        <section class="cartao-dados" aria-labelledby="titulo-ob">
          <header>
            <div><h2 id="titulo-ob">Ordem Bancária</h2><small>Ao anexar a OB, o valor é debitado nas NEs e a competência é concluída. Com o processo financeiro no contrato, a OB paga no SIGEO conclui sozinha (todo dia às 08:00).</small></div>
            @if (d.ordem_bancaria) { <span class="selo-situacao">Concluída</span> } @else { <span class="selo-situacao alerta">Aguardando a OB</span> }
          </header>
          <div class="resumo-medicao" aria-label="Resumo do pagamento">
            <div><span>Valor a pagar (soma das notas, brutos)</span><strong>{{ d.valor_a_pagar | moeda }}</strong></div>
            <div><span>NEs debitadas, em ordem</span><strong class="texto-codigo">{{ d.notas_selecionadas.map(n => n.numero).join(' → ') || '—' }}</strong></div>
            @if (d.concluida_em) { <div class="ok"><span>Concluída em</span><strong>{{ d.concluida_em | date: 'dd/MM/yyyy HH:mm' }}</strong></div> }
            @if (d.ob_origem === 'sigeo') { <div class="ok"><span>Paga conforme o SIGEO</span><strong class="texto-codigo">{{ d.ob_numero }}</strong><small>{{ d.ob_valor | moeda }} · lançada em {{ d.ob_data | dataBr }}</small></div> }
          </div>
          <div class="corpo">
            @if (d.ordem_bancaria) {
              <article class="cartao-arquivo-final">
                <span class="icone-arquivo" aria-hidden="true">PDF</span>
                <div class="dados-arquivo"><strong>{{ d.ob_origem === 'sigeo' ? 'Comprovante de pagamento (SIGEO)' : 'Ordem Bancária' }}</strong><small>O valor de {{ d.valor_a_pagar | moeda }} foi debitado nas NEs.</small></div>
                <button type="button" class="acao-secundaria" (click)="baixar(d.ordem_bancaria.anexo_id)">{{ d.ob_origem === 'sigeo' ? 'Baixar comprovante' : 'Baixar Ordem Bancária' }}</button>
              </article>
              <!-- E-mail aos prepostos avisando o pagamento (máscara "E-mail de pagamento") -->
              @if (d.email_ob; as e) {
                @if (e.ok === true) { <p class="dica-formulario">E-mail de pagamento enviado a {{ e.destinatarios.join(', ') }}.</p> }
                @else if (e.ok === false) { <p class="dica-formulario texto-erro">E-mail de pagamento não enviado: {{ e.erro }}</p> }
                @else { <p class="dica-formulario">E-mail de pagamento em envio…</p> }
                @if (e.ok !== true && e.enviado_em && d.pode_lancar_ob) { <button type="button" class="acao-secundaria acao-pequena" (click)="reenviarEmailOb()">Reenviar e-mail de pagamento</button> }
              }
              <div class="espaco-fim-etapa"></div>
            } @else if (editavel()) {
              <!-- O que a conferência diária do SIGEO viu nesta competência (só quando não pôde concluir sozinha) -->
              @if (d.ob_sigeo_pendencia) { <p class="aviso-bloco" role="status"><strong>SIGEO:</strong> {{ d.ob_sigeo_pendencia }}</p> }
              <app-campo-arquivo tipo="pdf" rotulo="Ordem Bancária (PDF)" [obrigatorio]="true" (selecionado)="ob = $event" />
              <div class="barra-envio-nf barra-medicao">
                <div class="texto-envio">
                  @if (!ob) { <span class="pendencias-nf">Falta: PDF da Ordem Bancária.</span> }
                  @else { <span class="dica-formulario">Ao anexar, {{ d.valor_a_pagar | moeda }} será debitado nas NEs {{ d.notas_selecionadas.map(n => n.numero).join(', ') }}, nessa ordem.</span> }
                </div>
                <button type="button" class="acao-primaria" [disabled]="!ob" (click)="enviarOb()">Anexar OB e concluir</button>
              </div>
            }
          </div>
        </section>
      }
    }
  `,
})
export class EtapaFinaisComponent {
  readonly detalhe = input.required<DetalheCompetencia>();
  // Etapa a exibir (a tela da competência escolhe entre as três)
  readonly etapa = input.required<Etapa>();
  readonly editavel = input(false);
  readonly atualizado = output<DetalheCompetencia>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  /** Despacho de pagamento da competência (nulo enquanto não há máscara ativa ou fora da etapa Download). */
  protected readonly despacho = signal<{ html: string; titulo: string } | null>(null);
  /** O cartão do despacho é dobrável e nasce dobrado (quem vai analisar abre). */
  protected readonly despachoAberto = signal(false);

  constructor() {
    // Ao abrir a etapa Download (ou trocar de competência), busca o despacho preenchido
    effect(() => {
      const d = this.detalhe();
      if (this.etapa() !== 'consolidado') return;
      untracked(() => this.api.despacho(d.contrato_id, d.id).subscribe({
        next: (r) => this.despacho.set(r.html ? { html: r.html, titulo: r.titulo } : null),
        error: () => this.despacho.set(null),
      }));
    });
  }

  /** Copia o despacho com a formatação (HTML) e, por garantia, em texto puro: no SEI ou no Word, o negrito e o centralizado vêm junto. */
  protected copiarDespacho(): void {
    const html = this.despacho()?.html;
    if (!html) return;
    const caixa = document.createElement('div');
    caixa.innerHTML = html;
    document.body.appendChild(caixa);
    const texto = caixa.innerText;
    caixa.remove();
    const item = typeof ClipboardItem !== 'undefined'
      ? new ClipboardItem({ 'text/html': new Blob([html], { type: 'text/html' }), 'text/plain': new Blob([texto], { type: 'text/plain' }) })
      : null;
    const gravar = item ? navigator.clipboard.write([item]) : navigator.clipboard.writeText(texto);
    void gravar.catch(() => navigator.clipboard?.writeText(texto).catch(() => undefined));
  }

  // Validade digitada para cada documento com validade (por id), antes de escolher o arquivo
  protected validades: Record<string, string> = {};
  // PDF da OB escolhido
  protected ob: File | null = null;

  /** Situação da validade: vencida, a vencer em até 30 dias ou em dia. */
  protected vencimento(validade: string): 'vencido' | 'perto' | 'ok' {
    const dias = (new Date(validade + 'T00:00:00').getTime() - new Date().setHours(0, 0, 0, 0)) / 86_400_000;
    return dias < 0 ? 'vencido' : dias <= 30 ? 'perto' : 'ok';
  }

  /** Anexa o PDF de um documento do checklist. */
  protected enviarDocumento(documento: DocumentoMensal, arquivo: File | null): void {
    if (!arquivo) return;
    const d = this.detalhe();
    const validade = this.validades[documento.id] ?? '';
    if (documento.com_validade && !validade) {
      this.dialogos.avisar('Informe a validade', 'Este é um documento com validade: preencha "Válido até" e escolha o arquivo de novo.');
      return;
    }
    this.dialogos.executar(this.api.documentoMensal(d.contrato_id, d.id, documento.id, arquivo, documento.com_validade ? validade : undefined), 'Enviando o documento…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível anexar o documento'),
    });
  }

  /** Só os dígitos (CNPJ sem pontos, barra nem traço), para colar nas consultas. */
  protected soNumeros(valor: string | null | undefined): string {
    return (valor ?? '').replace(/\D/g, '');
  }

  protected obrigatoriosTotal(d: DetalheCompetencia): number { return d.documentos.filter((x) => x.obrigatorio).length; }
  protected obrigatoriosAnexados(d: DetalheCompetencia): number { return d.documentos.filter((x) => x.obrigatorio && x.arquivo).length; }
  protected opcionaisTotal(d: DetalheCompetencia): number { return d.documentos.filter((x) => !x.obrigatorio).length; }
  protected opcionaisAnexados(d: DetalheCompetencia): number { return d.documentos.filter((x) => !x.obrigatorio && x.arquivo).length; }
  /** Documentos com validade vencida ou a vencer em até 30 dias. */
  protected vencendo(d: DetalheCompetencia): number {
    return d.documentos.filter((x) => x.com_validade && x.arquivo && x.validade_ate && this.vencimento(x.validade_ate) !== 'ok').length;
  }

  /** Quantos documentos têm um igual, ainda válido, em outro contrato da mesma empresa. */
  protected sugestoes(d: DetalheCompetencia): number {
    return d.documentos.filter((doc) => !doc.arquivo && doc.sugestao_outro_contrato).length;
  }

  /** Traz o documento de outro contrato da mesma empresa (confirmação do usuário: nada é copiado sozinho). */
  protected usarDeOutroContrato(documento: DocumentoMensal, origemId: string): void {
    const d = this.detalhe();
    this.api.reaproveitarDocumento(d.contrato_id, d.id, documento.id, origemId).subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível trazer o documento'),
    });
  }

  /** Traz de uma vez todos os documentos válidos de outros contratos da mesma empresa. */
  protected async trazerTodos(): Promise<void> {
    const d = this.detalhe();
    const ok = await this.dialogos.confirmar({
      titulo: 'Trazer os documentos de outros contratos?',
      mensagem: `${this.sugestoes(d)} documento(s) ainda válido(s) de outros contratos da empresa serão copiados para esta competência. Confira antes de concluir.`,
      rotuloConfirmar: 'Trazer documentos',
    });
    if (!ok) return;
    this.api.reaproveitarTodos(d.contrato_id, d.id).subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível trazer os documentos'),
    });
  }

  /** Quantos documentos obrigatórios ainda estão sem anexo (desabilita "Concluir checklist"). */
  protected obrigatoriosPendentes(d: DetalheCompetencia): number {
    return d.documentos.filter((doc) => doc.obrigatorio && !doc.arquivo).length;
  }

  /** Conclui o checklist; se faltarem opcionais, pede confirmação. */
  protected async concluirChecklist(): Promise<void> {
    const d = this.detalhe();
    const semAnexo = d.documentos.filter((doc) => !doc.arquivo).length;
    if (semAnexo) {
      const ok = await this.dialogos.confirmar({
        titulo: 'Concluir o checklist?',
        mensagem: `${semAnexo} documento(s) opcional(is) ficará(ão) sem anexo. Depois de concluída, a etapa só pode ser reaberta pelo SuperRoot ou pelo gestor.`,
        rotuloConfirmar: 'Concluir checklist',
      });
      if (!ok) return;
    }
    this.api.concluirChecklist(d.contrato_id, d.id).subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível concluir o checklist'),
    });
  }

  /** Gera o consolidado e já baixa o arquivo; ao gerar novamente, confirma antes a substituição. */
  protected async gerarConsolidado(novamente = false): Promise<void> {
    const d = this.detalhe();
    if (novamente) {
      const ok = await this.dialogos.confirmar({
        titulo: 'Gerar novamente o documento consolidado?',
        mensagem: 'O documento atual será substituído por um novo, montado com os arquivos que estão na competência agora.',
        rotuloConfirmar: 'Gerar novamente',
      });
      if (!ok) return;
    }
    this.dialogos.executar(this.api.consolidado(d.contrato_id, d.id), 'Gerando o documento consolidado…').subscribe({
      next: (novo) => {
        this.atualizado.emit(novo);
        if (novo.consolidado) this.baixar(novo.consolidado.anexo_id);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar o documento consolidado'),
    });
  }

  /** Reenvia o e-mail de pagamento aos prepostos (quando o primeiro envio falhou). */
  protected reenviarEmailOb(): void {
    const d = this.detalhe();
    this.dialogos.executar(this.api.reenviarEmailOb(d.contrato_id, d.id), 'Reenviando o e-mail…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível reenviar o e-mail'),
    });
  }

  /** Anexa a OB depois de confirmar: debita as NEs e conclui a competência. */
  protected async enviarOb(): Promise<void> {
    if (!this.ob) return;
    const d = this.detalhe();
    const ok = await this.dialogos.confirmar({
      titulo: 'Anexar a OB e concluir a competência?',
      mensagem: `O valor será debitado nas Notas de Empenho e a competência ficará concluída. A equipe do contrato, o criador e o SuperRoot podem reabrir (com estorno).`,
      rotuloConfirmar: 'Anexar OB e concluir',
      segundos: 5,
    });
    if (!ok) return;
    this.dialogos.executar(this.api.ordemBancaria(d.contrato_id, d.id, this.ob), 'Registrando a Ordem Bancária…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível anexar a OB'),
    });
  }

  /** Baixa um PDF da competência. */
  protected baixar(anexoId: string): void {
    const d = this.detalhe();
    this.api.baixar(d.contrato_id, d.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Etapas ainda abertas (ex.: retenção, CADIN, checklist) antes do consolidado. */
  protected faltando(d: DetalheCompetencia): string {
    return d.etapas_abertas.map((e) => ROTULOS_ETAPA[e]).join(', ');
  }
}
