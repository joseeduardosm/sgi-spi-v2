// Criado por José Eduardo Santana Martins
// Este arquivo serve para acompanhar o que vem depois da assinatura da prorrogação: PNCP, DOE, garantia (com a planilha para a DOF) e Contratos.gov.

import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { AlteracoesApiService } from '../compartilhado/alteracoes-api.service';
import { Prorrogacao } from '../compartilhado/contratos.models';

// Dados digitados das planilhas de garantia (as mesmas chaves da API)
const CAMPOS_GARANTIA: { chave: string; rotulo: string }[] = [
  { chave: 'responsavel_nome', rotulo: 'Responsável pelas informações: nome completo' },
  { chave: 'responsavel_email', rotulo: 'Responsável: e-mail' },
  { chave: 'responsavel_fone', rotulo: 'Responsável: telefone' },
  { chave: 'ultima_nl', rotulo: 'Nº da última NL (SIAFEM)' },
  { chave: 'forma_prestacao', rotulo: 'Forma de prestação (caução em dinheiro)' },
  { chave: 'meio_prestacao', rotulo: 'Meio de prestação (caução em dinheiro)' },
  { chave: 'dare', rotulo: 'Nº de controle do DARE/SP (caução em dinheiro)' },
  { chave: 'valor_complemento', rotulo: 'Valor do complemento (caução em dinheiro)' },
  { chave: 'data_pagamento', rotulo: 'Data do pagamento (caução em dinheiro)' },
  { chave: 'endosso_numero', rotulo: 'Nº do endosso/aditamento (seguro ou fiança)' },
  { chave: 'endosso_valor', rotulo: 'Valor do endosso/aditamento (seguro ou fiança)' },
  { chave: 'endosso_vigencia', rotulo: 'Vigência do endosso/aditamento (seguro ou fiança)' },
];

/**
 * Pós-assinatura: a divulgação no PNCP é condição de eficácia do aditivo, então a tela mostra o prazo (dias úteis) e a situação, e registra a publicação,
 * o DOE, a comprovação da garantia (com a planilha de dados para a DOF) e a atualização do Contratos.gov.
 */
@Component({
  selector: 'app-pos-assinatura-prorrogacao',
  imports: [FormsModule, ...PIPES_FORMATACAO],
  template: `
    @for (p of lista(); track p.id) {
      <section class="cartao-dados" [attr.aria-labelledby]="'titulo-pos-' + p.id">
        <header>
          <div><h2 [id]="'titulo-pos-' + p.id">Depois da assinatura: {{ p.numero_termo || 'prorrogação de ' + p.meses + ' mês(es)' }}</h2>
            <small>Vigência de {{ p.data_inicio | dataBr }} a {{ p.data_fim | dataBr }} · assinada em {{ p.assinada_em | dataBr }}</small></div>
          <div class="acoes-linha">
            @switch (p.situacao_pncp) {
              @case ('publicado') { <span class="selo-situacao">PNCP publicado</span> }
              @case ('no_prazo') { <span class="selo-situacao alerta">PNCP até {{ p.pncp_prazo_ate | dataBr }} ({{ p.dias_uteis_pncp }} dia(s) útil(eis))</span> }
              @case ('vencido') { <span class="selo-situacao perigo">PNCP vencido em {{ p.pncp_prazo_ate | dataBr }}</span> }
              @default { <span class="selo-situacao inativo">PNCP sem prazo (falta a modalidade no contrato)</span> }
            }
            @if (p.garantia_pendente) { <span class="selo-situacao alerta">Garantia sem comprovação</span> }
            @if (p.precisa_analise_juridica) { <span class="selo-situacao perigo">Precisa de análise jurídica</span> }
          </div>
        </header>
        <div class="corpo">
          <div class="grade-formulario tres-colunas">
            <div><label [for]="'pncp-data-' + p.id">Divulgado no PNCP em</label><input [id]="'pncp-data-' + p.id" type="date" [disabled]="!podeEditar()" [(ngModel)]="formularios[p.id].pncp_publicado_em" /></div>
            <div><label [for]="'pncp-num-' + p.id">Número ou link do PNCP</label><input [id]="'pncp-num-' + p.id" maxlength="100" [disabled]="!podeEditar()" [(ngModel)]="formularios[p.id].pncp_numero" /></div>
            <div><label [for]="'doe-' + p.id">Extrato publicado no DOE em</label><input [id]="'doe-' + p.id" type="date" [disabled]="!podeEditar()" [(ngModel)]="formularios[p.id].doe_publicado_em" /></div>
            <div><label [for]="'gov-' + p.id">Contratos.gov atualizado em</label><input [id]="'gov-' + p.id" type="date" [disabled]="!podeEditar()" [(ngModel)]="formularios[p.id].contratos_gov_atualizado_em" />
              <small class="dica-formulario">Campo "Fiscalização e Gestão Contratual".</small></div>
            @if (p.exige_garantia) {
              <div><label [for]="'gar-comp-' + p.id">Garantia comprovada em</label><input [id]="'gar-comp-' + p.id" type="date" [disabled]="!podeEditar()" [(ngModel)]="formularios[p.id].garantia_comprovada_em" /></div>
              <div><label [for]="'gar-dof-' + p.id">Dados da garantia enviados à DOF em</label><input [id]="'gar-dof-' + p.id" type="date" [disabled]="!podeEditar()" [(ngModel)]="formularios[p.id].garantia_enviada_dof_em" /></div>
            }
          </div>
          @if (p.exige_garantia) {
            <p class="secao-formulario">Dados para a planilha de garantia (DOF)</p>
            <div class="grade-formulario">
              @for (c of campos(); track c.chave) {
                <div><label [for]="'gar-' + c.chave + '-' + p.id">{{ c.rotulo }}</label>
                  <input [id]="'gar-' + c.chave + '-' + p.id" [disabled]="!podeEditar()" [(ngModel)]="formularios[p.id].dados_garantia[c.chave]" /></div>
              }
            </div>
          }
          <div class="acoes-cartao">
            @if (p.exige_garantia) { <button type="button" class="acao-secundaria" (click)="baixarGarantia(p)">Baixar planilha de garantia (XLSX)</button> }
            @if (podeEditar()) { <button type="button" class="acao-primaria" [class.carregando]="salvando() === p.id" [disabled]="salvando() === p.id" (click)="salvar(p)">Salvar pós-assinatura</button> }
          </div>
        </div>
      </section>
    }
  `,
})
export class PosAssinaturaProrrogacaoComponent implements OnInit {
  readonly contratoId = input.required<string>();
  readonly podeEditar = input(false);

  private readonly api = inject(AlteracoesApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly lista = signal<Prorrogacao[]>([]);
  protected readonly salvando = signal<string | null>(null);
  protected formularios: Record<string, { pncp_publicado_em: string | null; pncp_numero: string; doe_publicado_em: string | null; garantia_comprovada_em: string | null; garantia_enviada_dof_em: string | null; contratos_gov_atualizado_em: string | null; dados_garantia: Record<string, string> }> = {};
  protected readonly campos = signal(CAMPOS_GARANTIA);

  ngOnInit(): void {
    this.api.prorrogacoes(this.contratoId()).subscribe({ next: (l) => this.aplicar(l), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar as prorrogações registradas') });
  }

  private aplicar(lista: Prorrogacao[]): void {
    // Da mais recente para a mais antiga: a que está em andamento fica no topo
    this.lista.set([...lista].reverse());
    this.formularios = Object.fromEntries(lista.map((p) => [p.id, {
      pncp_publicado_em: p.pncp_publicado_em, pncp_numero: p.pncp_numero, doe_publicado_em: p.doe_publicado_em, garantia_comprovada_em: p.garantia_comprovada_em,
      garantia_enviada_dof_em: p.garantia_enviada_dof_em, contratos_gov_atualizado_em: p.contratos_gov_atualizado_em, dados_garantia: { ...p.dados_garantia },
    }]));
  }

  protected salvar(p: Prorrogacao): void {
    this.salvando.set(p.id);
    const f = this.formularios[p.id];
    const vazio = (v: string | null) => v || null;
    const dados = { ...f, pncp_publicado_em: vazio(f.pncp_publicado_em), doe_publicado_em: vazio(f.doe_publicado_em), garantia_comprovada_em: vazio(f.garantia_comprovada_em),
      garantia_enviada_dof_em: vazio(f.garantia_enviada_dof_em), contratos_gov_atualizado_em: vazio(f.contratos_gov_atualizado_em) };
    this.api.salvarPosAssinatura(this.contratoId(), p.id, dados).subscribe({
      next: (l) => { this.salvando.set(null); this.aplicar(l); },
      error: (e) => { this.salvando.set(null); this.dialogos.mostrarErro(e, 'Não foi possível salvar o pós-assinatura'); },
    });
  }

  protected baixarGarantia(p: Prorrogacao): void {
    this.api.baixarPlanilhaGarantia(this.contratoId(), p.id).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
