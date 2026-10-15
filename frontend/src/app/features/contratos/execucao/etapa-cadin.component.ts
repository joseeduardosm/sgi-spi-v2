// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a etapa 4 (consulta ao CADIN), com o histórico de consultas.

import { BotaoCopiarComponent } from '../../../shared/componentes/botao-copiar/botao-copiar.component';
import { DatePipe } from '@angular/common';
import { Component, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { CampoArquivoComponent } from '../../../shared/componentes/campo-arquivo/campo-arquivo.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { DetalheCompetencia } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';

/** Etapa 4: consulta ao CADIN. Com pendência, a etapa continua aberta; "Não" conclui. */
@Component({
  selector: 'app-etapa-cadin',
  imports: [BotaoCopiarComponent, CampoArquivoComponent, FormsModule, DatePipe],
  template: `
    @let d = detalhe();
    <section class="cartao-dados" aria-labelledby="titulo-cadin">
      <header>
        <div><h2 id="titulo-cadin">Consulta ao CADIN</h2><small>Consulte a contratada no CADIN estadual e registre o resultado com a certidão.</small></div>
        @if (ultima(); as u) {
          <span class="selo-situacao" [class.alerta]="u.possui_pendencia">{{ u.possui_pendencia ? 'Pendência registrada' : 'Sem pendência' }}</span>
        } @else { <span class="selo-situacao alerta">Aguardando consulta</span> }
      </header>
      <div class="corpo">
        @if (editavel()) {
          <ol class="passos-cadin">
            <li>
              <span class="numero-passo">1</span>
              <div class="conteudo-passo">
                <strong>Consulte o CNPJ no CADIN</strong>
                <div class="linha-cnpj">
                  @if (d.empresa_cnpj) {
                    <app-botao-copiar [valor]="soNumeros(d.empresa_cnpj)" rotulo="Copiar CNPJ" [titulo]="'Copiar o CNPJ da contratada (só números): ' + soNumeros(d.empresa_cnpj)" tamanho="pequeno" />
                  }
                  <a class="acao-secundaria" [href]="urlCadin" target="_blank" rel="noopener noreferrer">Abrir o CADIN estadual (Fazenda-SP) ↗</a>
                </div>
              </div>
            </li>
            <li>
              <span class="numero-passo">2</span>
              <div class="conteudo-passo">
                <strong>Há pendência no CADIN?</strong>
                <div class="opcoes-resultado" role="radiogroup" aria-label="Há pendência no CADIN?">
                  <label [class.escolhida]="!possuiPendencia"><input type="radio" name="pendencia" [value]="false" [(ngModel)]="possuiPendencia" /> Não, está regular</label>
                  <label [class.escolhida]="possuiPendencia" class="com-pendencia"><input type="radio" name="pendencia" [value]="true" [(ngModel)]="possuiPendencia" /> Sim, há pendência</label>
                </div>
              </div>
            </li>
            <li>
              <span class="numero-passo">3</span>
              <div class="conteudo-passo">
                <strong>Anexe o resultado</strong>
                @for (c of [ciclo()]; track c) {
                  <div class="zonas-arquivo">
                    <app-campo-arquivo tipo="pdf" rotulo="Certidão do CADIN" [obrigatorio]="true" (selecionado)="certidao = $event" />
                    @if (possuiPendencia) { <app-campo-arquivo tipo="pdf" rotulo="E-mail de comunicação" [obrigatorio]="true" (selecionado)="email = $event" /> }
                  </div>
                }
                @if (possuiPendencia) {
                  <div class="grade-formulario">
                    <div class="ocupa-duas"><label for="cadin-pendencia">Qual é a pendência? *</label><textarea id="cadin-pendencia" maxlength="2000" [(ngModel)]="pendencia"></textarea></div>
                    <div class="ocupa-duas"><label for="cadin-texto">Texto de notificação</label><textarea id="cadin-texto" maxlength="2500" [(ngModel)]="textoNotificacao"></textarea></div>
                  </div>
                }
              </div>
            </li>
          </ol>
          <div class="barra-envio-nf barra-medicao">
            <div class="texto-envio">
              @if (pendencias().length) { <span class="pendencias-nf">Falta: {{ pendencias().join(' · ') }}.</span> }
              @else { <span class="dica-formulario">{{ possuiPendencia ? 'A pendência fica registrada e a etapa continua aberta para nova consulta.' : 'Sem pendência: a etapa é concluída.' }}</span> }
            </div>
            <button type="button" class="acao-primaria" [disabled]="pendencias().length > 0" [title]="pendencias().join(', ')" (click)="registrar()">
              {{ possuiPendencia ? 'Registrar pendência' : 'Registrar consulta e concluir' }}
            </button>
          </div>
        }
        <p class="secao-formulario">Histórico de consultas</p>
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <thead><tr><th>Data</th><th>Resultado</th><th>Pendência</th><th>Usuário</th><th>Arquivos</th></tr></thead>
            <tbody>
              @for (c of d.consultas_cadin; track c.id) {
                <tr>
                  <td>{{ c.criado_em | date: 'dd/MM/yyyy HH:mm' }}</td>
                  <td><span class="selo-situacao" [class.alerta]="c.possui_pendencia">{{ c.possui_pendencia ? 'Pendência encontrada' : 'Sem pendência' }}</span></td>
                  <td>{{ c.pendencia || '—' }}@if (c.texto_notificacao) { <small>{{ c.texto_notificacao }}</small> }</td>
                  <td>{{ c.criado_por_nome }}</td>
                  <td>
                    <button type="button" class="acao-secundaria acao-pequena" (click)="baixar(c.certidao.anexo_id)">Baixar certidão</button>
                    @if (c.email) { · <button type="button" class="acao-secundaria acao-pequena" (click)="baixar(c.email.anexo_id)">Baixar e-mail</button> }
                  </td>
                </tr>
              } @empty {
                <tr><td class="estado-vazio" colspan="5">Nenhuma consulta registrada.</td></tr>
              }
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `,
})
export class EtapaCadinComponent {
  readonly detalhe = input.required<DetalheCompetencia>();
  readonly editavel = input(false);
  readonly atualizado = output<DetalheCompetencia>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  // Campos do formulário (ligados por [(ngModel)]) e os PDFs escolhidos
  protected possuiPendencia = false;
  protected pendencia = '';
  protected textoNotificacao = '';
  protected readonly urlCadin = 'https://www.fazenda.sp.gov.br/cadin_estadual/pages/publ/cadin.aspx';
  protected certidao: File | null = null;
  protected email: File | null = null;


  /** Só os dígitos do CNPJ (sem pontos, barra nem traço). */
  protected soNumeros(valor: string | null | undefined): string {
    return (valor ?? '').replace(/\D/g, '');
  }

  /** Muda a cada consulta registrada para limpar as áreas de arquivo. */
  protected readonly ciclo = signal(0);

  /** Resultado da consulta mais recente. */
  protected ultima(): DetalheCompetencia['consultas_cadin'][number] | null {
    const l = this.detalhe().consultas_cadin;
    return l.length ? [...l].sort((a, b) => b.criado_em.localeCompare(a.criado_em))[0] : null;
  }

  /** O que falta para registrar (aparece na barra de ações). */
  protected pendencias(): string[] {
    const falta: string[] = [];
    if (!this.certidao) falta.push('certidão do CADIN');
    if (this.possuiPendencia) {
      if (!this.pendencia.trim()) falta.push('descrição da pendência');
      if (!this.email) falta.push('e-mail de comunicação');
    }
    return falta;
  }

  /** Envia a consulta; em seguida, limpa o formulário para uma nova consulta. */
  protected registrar(): void {
    const d = this.detalhe();
    const campos = { possui_pendencia: this.possuiPendencia, certidao: this.certidao, pendencia: this.pendencia.trim(),
                     // O e-mail só vai quando há pendência
                     texto_notificacao: this.textoNotificacao.trim(), email: this.possuiPendencia ? this.email : null };
    this.dialogos.executar(this.api.cadin(d.contrato_id, d.id, campos), 'Registrando a consulta…').subscribe({
      next: (novo) => {
        this.pendencia = this.textoNotificacao = '';
        this.certidao = this.email = null;
        this.ciclo.update((v) => v + 1);
        this.atualizado.emit(novo);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível registrar a consulta'),
    });
  }

  /** Baixa a certidão ou o e-mail de uma consulta. */
  protected baixar(anexoId: string): void {
    const d = this.detalhe();
    this.api.baixar(d.contrato_id, d.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
