// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir e anexar os documentos importantes do contrato (aba "Documentos Importantes").

import { Component, inject, input, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { DocumentoContrato } from '../compartilhado/contratos.models';
import { ContratacoesApiService } from '../../contratacoes/contratacoes-api.service';
import { DocumentoResumo } from '../../contratacoes/contratacoes.models';
import { ProtocoloApiService } from '../../protocolo/protocolo-api.service';
import { NumeroProtocolo } from '../../protocolo/protocolo.models';

/** Aba "Documentos Importantes": repositório opcional (001 a 023 + termos aditivos 024+). */
@Component({
  selector: 'app-aba-documentos',
  imports: [EnvioPdfComponent, RouterLink, ...PIPES_FORMATACAO],
  template: `
    <section class="cartao-dados" aria-labelledby="titulo-documentos">
      <header>
        <div><h2 id="titulo-documentos">Documentos Importantes</h2><small>Repositório opcional: nenhuma etapa do sistema depende destes anexos.</small></div>
      </header>
      <div class="tabela-gestao-envoltorio">
        <table class="tabela-gestao">
          <thead><tr><th>Número</th><th>Documento</th><th>Enviado em</th>@if (podeEditar()) { <th>Anexar PDF</th> }</tr></thead>
          <tbody>
            @for (d of documentos(); track d.codigo) {
              <tr>
                <td>{{ d.numero }}</td>
                <td>
                  @if (d.anexado) {
                    <button type="button" class="link-arquivo" (click)="baixar(d)">{{ d.titulo }}</button>
                    <small>{{ d.nome_arquivo }} · {{ d.tamanho | tamanho }}</small>
                  } @else {
                    <strong>{{ d.titulo }}</strong><small>Não anexado</small>
                  }
                </td>
                <td>{{ d.enviado_em ? (d.enviado_em.slice(0, 10) | dataBr) : '—' }}@if (d.enviado_por_nome) { <small>{{ d.enviado_por_nome }}</small> }</td>
                @if (podeEditar()) {
                  <td>
                    @if (d.codigo <= 23) {
                      <div class="acoes-documento">
                        <app-envio-pdf [rotulo]="d.anexado ? 'Substituir' : 'Selecionar documento'" (selecionado)="enviar(d, $event)" />
                        @if (d.anexado) { <button type="button" class="acao-perigo acao-pequena" (click)="limpar(d)">Limpar</button> }
                      </div>
                    } @else { <small>Anexado pela prorrogação</small> }
                  </td>
                }
              </tr>
            }
          </tbody>
        </table>
      </div>
    </section>

    <!-- Documentos do Protocolo (portarias, ofícios…) vinculados a este contrato; só aparece para quem tem acesso ao Protocolo -->
    @if (protocolo().length) {
      <section class="cartao-dados" aria-labelledby="titulo-protocolo-contrato">
        <header><div><h2 id="titulo-protocolo-contrato">Documentos do Protocolo</h2><small>Números vinculados a este contrato. Documentos sigilosos só abrem para quem reservou o número e para o SuperRoot.</small></div>
          <a class="acao-secundaria acao-pequena" routerLink="/protocolo">Abrir o Protocolo</a></header>
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <thead><tr><th>Número</th><th>Tipo</th><th>Finalidade</th><th>Responsável</th><th>Situação</th></tr></thead>
            <tbody>
              @for (n of protocolo(); track n.id) {
                <tr><td><strong>{{ n.numero_formatado }}</strong></td><td>{{ n.tipo_nome }}</td><td>{{ n.finalidade }}</td><td>{{ n.reservado_por_nome }}</td>
                  <td>{{ n.estado === 'utilizado' ? 'Utilizado' : n.estado === 'anulado' ? 'Anulado' : 'Reservado' }}@if (n.sigiloso) { 🔒 }</td></tr>
              }
            </tbody>
          </table>
        </div>
      </section>
    }
    @if (contratacoes().length) {
      <section class="painel-gestao" aria-labelledby="titulo-contratacoes-contrato" style="margin-top: 18px">
        <header><div><h2 id="titulo-contratacoes-contrato">ETP e TR deste contrato</h2><small>Documentos de Contratações vinculados a este contrato.</small></div>
          <a class="acao-secundaria acao-pequena" routerLink="/contratacoes">Abrir Contratações</a></header>
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <thead><tr><th>Tipo</th><th>Nome</th><th>Processo SEI</th><th>Situação</th><th>Responsável</th></tr></thead>
            <tbody>
              @for (c of contratacoes(); track c.id) {
                <tr><td>{{ c.tipo.toUpperCase() }}</td><td><a [routerLink]="['/contratacoes', c.id]">{{ c.nome }}</a></td><td>{{ c.processo || '—' }}</td>
                  <td>{{ c.situacao === 'concluido' ? 'Concluído' : c.situacao === 'em_revisao' ? 'Em revisão' : 'Rascunho' }}</td><td>{{ c.criador_nome }}</td></tr>
              }
            </tbody>
          </table>
        </div>
      </section>
    }
  `,
})
export class AbaDocumentosComponent implements OnInit {
  // Id do contrato e se o usuário pode anexar (vindos da tela de detalhe)
  readonly contratoId = input.required<string>();
  readonly podeEditar = input(false);

  private readonly api = inject(ContratosApiService);
  private readonly protocoloApi = inject(ProtocoloApiService);
  protected readonly protocolo = signal<NumeroProtocolo[]>([]);
  private readonly contratacoesApi = inject(ContratacoesApiService);
  protected readonly contratacoes = signal<DocumentoResumo[]>([]);
  private readonly dialogos = inject(DialogosService);
  protected readonly documentos = signal<DocumentoContrato[]>([]);

  /** Carrega o catálogo de documentos ao abrir a aba. */
  ngOnInit(): void {
    this.api.documentos(this.contratoId()).subscribe({ next: (d) => this.documentos.set(d), error: (e) => this.dialogos.mostrarErro(e) });
    // Sem acesso ao Protocolo (403) a seção simplesmente não aparece
    this.protocoloApi.doContrato(this.contratoId()).subscribe({ next: (n) => this.protocolo.set(n), error: () => this.protocolo.set([]) });
    // Sem acesso a Contratações (403) a seção simplesmente não aparece
    this.contratacoesApi.doContrato(this.contratoId()).subscribe({ next: (c) => this.contratacoes.set(c), error: () => this.contratacoes.set([]) });
  }

  /** Envia o PDF escolhido e atualiza a lista com a resposta da API. */
  protected enviar(documento: DocumentoContrato, arquivo: File | null): void {
    if (!arquivo) return;
    this.dialogos.executar(this.api.enviarDocumento(this.contratoId(), documento.codigo, arquivo), 'Enviando o documento…').subscribe({
      next: (d) => this.documentos.set(d),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível anexar o documento'),
    });
  }

  /** Pede confirmação e retira o PDF do documento (ele volta a "Não anexado"). */
  protected async limpar(documento: DocumentoContrato): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Limpar "${documento.titulo}"?`,
      mensagem: 'O PDF deixa de aparecer no contrato e o documento volta a "Não anexado". O arquivo continua guardado no histórico (auditoria).',
      rotuloConfirmar: 'Limpar documento',
      segundos: 3,
    });
    if (!ok) return;
    this.api.limparDocumento(this.contratoId(), documento.codigo).subscribe({
      next: (d) => this.documentos.set(d),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível limpar o documento'),
    });
  }

  /** Baixa o PDF do documento. */
  protected baixar(documento: DocumentoContrato): void {
    this.api.baixarDocumento(this.contratoId(), documento.codigo).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
