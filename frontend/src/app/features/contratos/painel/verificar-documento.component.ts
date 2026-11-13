/**
 * =============================================================================
 * ARQUIVO: verificar-documento.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Tela "Verificar documento": confere se um PDF gerado pelo sistema (relatório
 * de avaliação ou memória de cálculo) é autêntico, pelo código de verificação
 * impresso na Folha de autenticação ou pelo envio do próprio arquivo.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template embutido. Tem duas entradas: o campo de
 * código (chama ContratosApiService.verificarCodigo) e o envio de PDF via
 * app-envio-pdf (verificarArquivo). As duas usam o mesmo método executar, que
 * liga o indicador de carregamento e guarda o resultado num signal. O
 * resultado mostra se é válido, o motivo e os dados do registro.
 *
 * FINALIDADE DE NEGÓCIO:
 * Permite que qualquer pessoa (servidor, empresa ou controle externo) confirme
 * que um documento de avaliação ou cálculo não foi alterado depois de gerado,
 * e veja quem o gerou e quem deu ciência, dando segurança jurídica ao processo.
 * Não confere assinatura digital (essa é feita no gov.br).
 *
 * CONTEXTO NO SISTEMA:
 * Rota do módulo Contratos. Depende de ContratosApiService, do tipo
 * VerificacaoDocumento (contratos.models) e do componente compartilhado
 * EnvioPdfComponent. No backend, a Folha de autenticação é acrescentada aos
 * PDFs pelo serviço de documentos.
 *
 * =============================================================================
 */

import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { VerificacaoDocumento } from '../compartilhado/contratos.models';

/**
 * Verificação de autenticidade: o relatório de avaliação e a memória de cálculo levam, no fim, uma Folha de autenticação com um código. Aqui o código
 * mostra o registro (quem gerou, quando, quem deu ciência) e o envio do PDF prova que o arquivo é exatamente o gerado pelo sistema. Não verifica
 * assinatura digital (a assinatura da contratada é feita no gov.br).
 */
@Component({
  selector: 'app-verificar-documento',
  imports: [FormsModule, DatePipe, RouterLink, CabecalhoModuloComponent, EnvioPdfComponent],
  template: `
    <app-cabecalho-modulo titulo="Verificar documento" [trilha]="['Verificar documento']"
                          descricao="Confira se um PDF do sistema (relatório de avaliação ou memória de cálculo) é o original, pelo código ou pelo arquivo." />

    <section class="cartao-dados" aria-labelledby="titulo-verificar">
      <header><div><h2 id="titulo-verificar">Como verificar</h2></div></header>
      <div class="corpo">
        <div class="grade-formulario">
          <div><label for="codigo-verificacao">Código de verificação (da Folha de autenticação)</label>
            <input id="codigo-verificacao" name="codigo" maxlength="40" placeholder="XXXX-XXXX-XXXX-XXXX" [(ngModel)]="codigo" (keydown.enter)="verificarCodigo()" /></div>
          <div class="acoes-formulario" style="align-self: end"><button type="button" class="acao-primaria" [class.carregando]="carregando()" [disabled]="!codigo.trim() || carregando()" (click)="verificarCodigo()">Verificar código</button></div>
        </div>
        <p class="secao-formulario">Ou envie o PDF</p>
        <div class="acoes-cartao esquerda"><app-envio-pdf rotulo="Selecionar PDF para verificar" (selecionado)="verificarArquivo($event)" /></div>

        @if (resultado(); as r) {
          <p class="aviso-bloco" [class.erro]="!r.valido" [class.informativo]="r.valido" role="status">{{ r.valido ? '✔ ' : '✖ ' }}{{ r.motivo }}</p>
          @if (r.documento; as d) {
            <dl class="campos-detalhe">
              <div><dt>Documento</dt><dd>{{ d.tipo }}</dd></div>
              <div><dt>Contrato</dt><dd><a [routerLink]="['/contratos', d.contrato_id]">{{ d.contrato_numero }}</a></dd></div>
              <div><dt>Competência</dt><dd>{{ d.competencia ?? '—' }}</dd></div>
              <div><dt>Gerado por</dt><dd>{{ d.gerado_por }}</dd></div>
              <div><dt>Gerado em</dt><dd>{{ d.gerado_em | date: 'dd/MM/yyyy HH:mm' }}</dd></div>
              <div><dt>Código</dt><dd>{{ d.codigo }}</dd></div>
            </dl>
            @if (d.ciencias.length) {
              <p class="secao-formulario">Ciências registradas quando o documento foi gerado</p>
              <ul class="lista-ciencias">@for (c of d.ciencias; track c.nome + c.em) { <li><span>{{ c.nome }} <small>{{ c.papel }}</small></span><small>{{ c.em }}</small></li> }</ul>
            }
          }
        }
      </div>
    </section>
  `,
})
export class VerificarDocumentoComponent {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);

  protected codigo = '';
  protected readonly resultado = signal<VerificacaoDocumento | null>(null);
  protected readonly carregando = signal(false);

  /** Verifica pelo código digitado (sem espaços nas pontas). */
  protected verificarCodigo(): void {
    this.executar(this.api.verificarCodigo(this.codigo.trim()));
  }

  /** Verifica pelo PDF escolhido; null significa que o usuário cancelou a seleção. */
  protected verificarArquivo(arquivo: File | null): void {
    if (!arquivo) return;
    this.executar(this.api.verificarArquivo(arquivo));
  }

  /**
   * Executa a verificação (por código ou por arquivo) e exibe o resultado.
   * Recebe o Observable já montado; o tipo é o mesmo nas duas chamadas da API,
   * por isso o parâmetro usa ReturnType do método verificarCodigo.
   * A requisição HTTP só é disparada no `subscribe`.
   */
  private executar(chamada: ReturnType<ContratosApiService['verificarCodigo']>): void {
    this.carregando.set(true);
    chamada.subscribe({
      next: (r) => { this.carregando.set(false); this.resultado.set(r); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível verificar o documento'); },
    });
  }
}
