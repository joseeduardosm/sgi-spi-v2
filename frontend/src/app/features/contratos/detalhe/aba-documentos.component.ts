// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir e anexar os documentos importantes do contrato (aba "Documentos Importantes").

import { Component, inject, input, OnInit, signal } from '@angular/core';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { DocumentoContrato } from '../compartilhado/contratos.models';

/** Aba "Documentos Importantes": repositório opcional (001 a 023 + termos aditivos 024+). */
@Component({
  selector: 'app-aba-documentos',
  imports: [EnvioPdfComponent, ...PIPES_FORMATACAO],
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
                      <app-envio-pdf [rotulo]="d.anexado ? 'Substituir' : 'Selecionar documento'" (selecionado)="enviar(d, $event)" />
                    } @else { <small>Anexado pela prorrogação</small> }
                  </td>
                }
              </tr>
            }
          </tbody>
        </table>
      </div>
    </section>
  `,
})
export class AbaDocumentosComponent implements OnInit {
  // Id do contrato e se o usuário pode anexar (vindos da tela de detalhe)
  readonly contratoId = input.required<string>();
  readonly podeEditar = input(false);

  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly documentos = signal<DocumentoContrato[]>([]);

  /** Carrega o catálogo de documentos ao abrir a aba. */
  ngOnInit(): void {
    this.api.documentos(this.contratoId()).subscribe({ next: (d) => this.documentos.set(d), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Envia o PDF escolhido e atualiza a lista com a resposta da API. */
  protected enviar(documento: DocumentoContrato, arquivo: File | null): void {
    if (!arquivo) return;
    this.dialogos.executar(this.api.enviarDocumento(this.contratoId(), documento.codigo, arquivo), 'Enviando o documento…').subscribe({
      next: (d) => this.documentos.set(d),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível anexar o documento'),
    });
  }

  /** Baixa o PDF do documento. */
  protected baixar(documento: DocumentoContrato): void {
    this.api.baixarDocumento(this.contratoId(), documento.codigo).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
