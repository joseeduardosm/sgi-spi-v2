// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela "Verificar documento": confere um PDF gerado pelo sistema pelo código de verificação ou pelo próprio arquivo.

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
          <div class="acoes-formulario" style="align-self: end"><button type="button" class="acao-primaria" [disabled]="!codigo.trim() || carregando()" (click)="verificarCodigo()">Verificar código</button></div>
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

  protected verificarCodigo(): void {
    this.executar(this.api.verificarCodigo(this.codigo.trim()));
  }

  protected verificarArquivo(arquivo: File | null): void {
    if (!arquivo) return;
    this.executar(this.api.verificarArquivo(arquivo));
  }

  private executar(chamada: ReturnType<ContratosApiService['verificarCodigo']>): void {
    this.carregando.set(true);
    chamada.subscribe({
      next: (r) => { this.carregando.set(false); this.resultado.set(r); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível verificar o documento'); },
    });
  }
}
