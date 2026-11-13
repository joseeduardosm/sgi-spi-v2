/**
 * =============================================================================
 * ARQUIVO: rdm-tarefa.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Página da RDM (Requisição de Mudança) de uma tarefa: formulário da matriz da
 * Prodesp, envio para aprovação e, para a liderança, aprovar (gera o PDF e
 * envia o e-mail) ou reprovar com motivo.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template inline. Carrega a RDM pela API ao abrir,
 * guarda uma cópia editável do formulário (f) e liga os campos com ngModel.
 * Um fieldset desabilitado deixa tudo só leitura quando pode_editar é falso.
 * Salvar, enviar, aprovar e reprovar passam pelo método executar(), que
 * controla o estado de carregamento do botão e mostra o erro em diálogo.
 *
 * FINALIDADE DE NEGÓCIO:
 * Uma RDM documenta uma mudança em infraestrutura ou sistemas (o que muda,
 * riscos, janela, plano de execução e de retorno). O registro e a aprovação
 * pela liderança antes da execução dão controle e rastreabilidade à SPI; o
 * PDF aprovado fica anexado à tarefa e vai por e-mail aos envolvidos.
 *
 * CONTEXTO NO SISTEMA:
 * Rota filha do Módulo Tarefas (tarefas.routes.ts). Usa TarefasApiService
 * (rotas /api/tarefas/{numero}/rdm), os tipos e listas de rdm.models.ts,
 * CabecalhoTarefasComponent, EsqueletoComponent e DialogosService.
 *
 * =============================================================================
 */

import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoTarefasComponent } from './cabecalho-tarefas.component';
import {
  ACOES_CONHECIMENTO_RDM, ACOES_RDM, CATEGORIAS_RDM, ETAPAS_RDM, FINALIDADES_RDM, FormularioRdm, IMPACTOS_PREVISTOS_RDM, NIVEIS_RDM, PRE_REQUISITOS_RDM,
  PRIORIDADES_RDM, RdmLeitura, SITUACOES_RDM, TIPOS_RDM,
} from './rdm.models';
import { TarefasApiService } from './tarefas-api.service';

@Component({
  selector: 'app-rdm-tarefa',
  imports: [DatePipe, EsqueletoComponent, FormsModule, RouterLink, CabecalhoTarefasComponent],
  styles: [`
    /* Linhas repetíveis (atividades, comunicação, rollback): campos lado a lado e o "Remover" no fim */
    .linha-rdm { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 1fr) minmax(0, 1fr) auto; gap: 8px 12px; align-items: end; margin-bottom: 10px;
      &.quatro { grid-template-columns: minmax(0, 2fr) minmax(0, 1.5fr) minmax(0, 1fr) minmax(0, 1fr) auto; }
      label { display: block; margin: 0 0 4px; color: var(--spi-rotulo); font-size: var(--spi-texto-legenda); font-weight: 600; }
      input, select { width: 100%; margin-bottom: 0; } }
    .tabela-fixa { display: grid; grid-template-columns: minmax(120px, 1fr) repeat(3, minmax(0, 1fr)); gap: 8px 12px; align-items: center; margin-bottom: 8px;
      .rotulo-linha { font-weight: 600; font-size: 13px; } input, select { width: 100%; margin-bottom: 0; } }
    .lista-checks { display: grid; gap: 6px; margin: 0 0 12px;
      label { display: flex; gap: 8px; align-items: center; justify-content: flex-start; margin: 0; font-weight: 400; color: var(--spi-texto); }
      input[type='checkbox'] { flex: none; width: 16px; height: 16px; margin: 0; } }
    .situacao-rdm { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; margin: 0 0 16px; }
    .decisao-rdm { margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--spi-borda); }
    fieldset { margin: 0; padding: 0; border: 0; min-width: 0; }
    @media (max-width: 760px) { .linha-rdm, .linha-rdm.quatro, .tabela-fixa { grid-template-columns: minmax(0, 1fr); } }
  `],
  template: `
    @if (rdm(); as r) {
      <app-cabecalho-tarefas [titulo]="r.rotulo" [trilha]="[{ rotulo: 'Tarefa #' + r.tarefa_numero, rota: ['/tarefas', r.tarefa_numero] }, { rotulo: 'RDM' }]"
        descricao="Requisição de Mudança no modelo da Prodesp (FORM_RDM-V2.2_CAS1). Enviada, a liderança da equipe aprova ou reprova; aprovada, o PDF é anexado à tarefa e enviado por e-mail." />

      <div class="situacao-rdm">
        <span class="selo-status" [attr.data-chamado]="situacoes[r.situacao].cor">{{ situacoes[r.situacao].rotulo }}</span>
        @if (r.enviada_em) { <small>Enviada por {{ r.enviada_por_nome }} em {{ r.enviada_em | date: 'dd/MM/yyyy HH:mm' }}</small> }
        @if (r.decidida_em) { <small>· {{ r.situacao === 'reprovada' ? 'Reprovada' : 'Aprovada' }} por {{ r.decidida_por_nome }} em {{ r.decidida_em | date: 'dd/MM/yyyy HH:mm:ss' }}</small> }
        @if (r.tem_pdf) { <button type="button" class="acao-secundaria acao-pequena" (click)="baixarPdf(r)">Baixar PDF</button> }
      </div>
      @if (r.situacao === 'reprovada' && r.motivo_reprovacao) {
        <p class="aviso-bloco erro" style="margin: 0 0 16px"><strong>Motivo da reprovação:</strong> {{ r.motivo_reprovacao }}</p>
      }

      <form class="cartao-dados formulario-tarefa" style="max-width: none" (submit)="$event.preventDefault()">
        <div class="corpo">
        <fieldset [disabled]="!r.pode_editar">
          <section class="secao-tarefa">
            <h3><span>1</span> Identificação</h3>
            <div class="grade-formulario">
              <div class="ocupa-duas"><label for="rdm-titulo">Assunto (título da mudança) *</label>
                <input id="rdm-titulo" name="titulo" maxlength="300" [(ngModel)]="f.titulo" placeholder="Ex.: Instalar drivers VirtIO na VM 105" /></div>
              <div><label for="rdm-tipo">Tipo *</label>
                <select id="rdm-tipo" name="tipo" [(ngModel)]="f.identificacao.tipo"><option value="">Escolha</option>@for (o of tipos; track o) { <option [value]="o">{{ o }}</option> }</select></div>
              <div><label for="rdm-data">Data da solicitação</label><input id="rdm-data" name="data" type="date" [(ngModel)]="f.identificacao.data_solicitacao" /></div>
              <div><label for="rdm-solicitante">Requisitante</label><input id="rdm-solicitante" name="solicitante" maxlength="300" [(ngModel)]="f.identificacao.solicitante" /></div>
              <div><label for="rdm-area">Área / departamento</label><input id="rdm-area" name="area" maxlength="300" [(ngModel)]="f.identificacao.area" placeholder="Ex.: CAS1" /></div>
            </div>
          </section>

          <section class="secao-tarefa">
            <h3><span>2</span> Objetivo e justificativa</h3>
            <div class="grade-formulario">
              <div class="ocupa-duas"><label for="rdm-objetivo">Objetivo *</label><textarea id="rdm-objetivo" name="objetivo" rows="3" maxlength="4000" [(ngModel)]="f.objetivo" placeholder="O que se pretende realizar."></textarea></div>
              <div class="ocupa-duas"><label for="rdm-justificativa">Justificativa *</label><textarea id="rdm-justificativa" name="justificativa" rows="3" maxlength="4000" [(ngModel)]="f.justificativa" placeholder="Por que a mudança é necessária."></textarea></div>
            </div>
          </section>

          <section class="secao-tarefa">
            <h3><span>3</span> Categorização</h3>
            <div class="grade-formulario tres-colunas">
              <div><label for="rdm-acao">Ação</label><select id="rdm-acao" name="acao" [(ngModel)]="f.categorizacao.acao"><option value="">—</option>@for (o of acoes; track o) { <option [value]="o">{{ o }}</option> }</select></div>
              <div><label for="rdm-finalidade">Finalidade</label><select id="rdm-finalidade" name="finalidade" [(ngModel)]="f.categorizacao.finalidade"><option value="">—</option>@for (o of finalidades; track o) { <option [value]="o">{{ o }}</option> }</select></div>
              <div><label for="rdm-prioridade">Prioridade</label><select id="rdm-prioridade" name="prioridade" [(ngModel)]="f.categorizacao.prioridade"><option value="">—</option>@for (o of prioridades; track o) { <option [value]="o">{{ o }}</option> }</select></div>
              <div><label for="rdm-risco">Risco</label><select id="rdm-risco" name="risco" [(ngModel)]="f.categorizacao.risco"><option value="">—</option>@for (o of niveis; track o) { <option [value]="o">{{ o }}</option> }</select></div>
              <div><label for="rdm-impacto">Impacto</label><select id="rdm-impacto" name="impacto" [(ngModel)]="f.categorizacao.impacto"><option value="">—</option>@for (o of niveis; track o) { <option [value]="o">{{ o }}</option> }</select></div>
            </div>
          </section>

          <section class="secao-tarefa">
            <h3><span>4</span> Abrangência</h3>
            <div class="grade-formulario">
              <div class="ocupa-duas"><label for="rdm-departamentos">Departamentos afetados</label><input id="rdm-departamentos" name="departamentos" maxlength="4000" [(ngModel)]="f.abrangencia.departamentos" /></div>
              <div><label for="rdm-internos">Usuários internos</label><input id="rdm-internos" name="internos" maxlength="60" [(ngModel)]="f.abrangencia.usuarios_internos" /></div>
              <div><label for="rdm-externos">Usuários externos</label><input id="rdm-externos" name="externos" maxlength="60" [(ngModel)]="f.abrangencia.usuarios_externos" /></div>
              <div class="ocupa-duas"><label for="rdm-ics">ICs impactados (serviços, sistemas, equipamentos)</label><textarea id="rdm-ics" name="ics" rows="2" maxlength="4000" [(ngModel)]="f.abrangencia.ics"></textarea></div>
              <div><label for="rdm-indisp">Indisponibilidade</label><select id="rdm-indisp" name="indisp" [(ngModel)]="f.abrangencia.indisponibilidade"><option value="">—</option><option value="SIM">SIM</option><option value="NÃO">NÃO</option></select></div>
              <div><label for="rdm-tempo-indisp">Tempo de indisponibilidade</label><input id="rdm-tempo-indisp" name="tempo_indisp" maxlength="300" [(ngModel)]="f.abrangencia.tempo_indisponibilidade" placeholder="Ex.: 1 hora" /></div>
            </div>
          </section>

          <section class="secao-tarefa">
            <h3><span>5</span> Cronograma</h3>
            <div class="tabela-fixa" aria-hidden="true"><span></span><small>Início</small><small>Duração</small><small>Término</small></div>
            @for (l of f.cronograma; track l.etapa; let i = $index) {
              <div class="tabela-fixa">
                <span class="rotulo-linha">{{ l.etapa }}</span>
                <input [name]="'cr-ini-' + i" maxlength="60" [(ngModel)]="l.inicio" [attr.aria-label]="'Início da ' + l.etapa" placeholder="dd/mm/aaaa hh:mm" />
                <input [name]="'cr-dur-' + i" maxlength="60" [(ngModel)]="l.duracao" [attr.aria-label]="'Duração da ' + l.etapa" placeholder="Ex.: 2 horas" />
                <input [name]="'cr-fim-' + i" maxlength="60" [(ngModel)]="l.termino" [attr.aria-label]="'Término da ' + l.etapa" placeholder="dd/mm/aaaa hh:mm" />
              </div>
            }
          </section>

          <section class="secao-tarefa">
            <h3><span>6</span> Janela de implantação</h3>
            <div class="grade-formulario tres-colunas">
              <div><label for="rdm-ini-data">Início: data *</label><input id="rdm-ini-data" name="ini_data" type="date" [(ngModel)]="f.janela.inicio_data" /></div>
              <div><label for="rdm-ini-hora">Início: hora</label><input id="rdm-ini-hora" name="ini_hora" type="time" [(ngModel)]="f.janela.inicio_hora" /></div>
              <div><label for="rdm-tempo">Tempo de implantação</label><input id="rdm-tempo" name="tempo" maxlength="60" [(ngModel)]="f.janela.tempo" placeholder="Ex.: 03 horas" /></div>
              <div><label for="rdm-fim-data">Fim: data *</label><input id="rdm-fim-data" name="fim_data" type="date" [(ngModel)]="f.janela.fim_data" /></div>
              <div><label for="rdm-fim-hora">Fim: hora</label><input id="rdm-fim-hora" name="fim_hora" type="time" [(ngModel)]="f.janela.fim_hora" /></div>
            </div>
          </section>

          <section class="secao-tarefa">
            <h3><span>7</span> Plano de execução e validação *</h3>
            @for (l of f.plano_execucao; track $index; let i = $index) {
              <div class="linha-rdm">
                <div><label [for]="'pe-at-' + i">Atividade</label><input [id]="'pe-at-' + i" [name]="'pe-at-' + i" maxlength="1000" [(ngModel)]="l.atividade" /></div>
                <div><label [for]="'pe-ex-' + i">Executor(es)</label><input [id]="'pe-ex-' + i" [name]="'pe-ex-' + i" maxlength="300" [(ngModel)]="l.executor" /></div>
                <div><label [for]="'pe-et-' + i">Etapa</label><select [id]="'pe-et-' + i" [name]="'pe-et-' + i" [(ngModel)]="l.etapa">@for (o of etapas; track o) { <option [value]="o">{{ o }}</option> }</select></div>
                @if (r.pode_editar) { <button type="button" class="acao-perigo acao-pequena" (click)="f.plano_execucao.splice(i, 1)">Remover</button> }
              </div>
            } @empty { <p class="dica-formulario">Nenhuma atividade ainda.</p> }
            @if (r.pode_editar) { <button type="button" class="acao-secundaria acao-pequena" (click)="f.plano_execucao.push({ atividade: '', executor: '', etapa: 'EXECUÇÃO' })">Adicionar atividade</button> }
          </section>

          <section class="secao-tarefa">
            <h3><span>8</span> Plano de comunicação</h3>
            @for (l of f.comunicacao; track $index; let i = $index) {
              <div class="linha-rdm quatro">
                <div><label [for]="'co-q-' + i">Quem será comunicado / área</label><input [id]="'co-q-' + i" [name]="'co-q-' + i" maxlength="300" [(ngModel)]="l.quem" /></div>
                <div><label [for]="'co-m-' + i">Em que momento</label><input [id]="'co-m-' + i" [name]="'co-m-' + i" maxlength="300" [(ngModel)]="l.momento" placeholder="Ex.: Início da atividade" /></div>
                <div><label [for]="'co-meio-' + i">Meio</label><input [id]="'co-meio-' + i" [name]="'co-meio-' + i" maxlength="300" [(ngModel)]="l.meio" placeholder="Ex.: E-mail" /></div>
                <div><label [for]="'co-r-' + i">Responsável</label><input [id]="'co-r-' + i" [name]="'co-r-' + i" maxlength="300" [(ngModel)]="l.responsavel" /></div>
                @if (r.pode_editar) { <button type="button" class="acao-perigo acao-pequena" (click)="f.comunicacao.splice(i, 1)">Remover</button> }
              </div>
            } @empty { <p class="dica-formulario">Ninguém a comunicar ainda.</p> }
            @if (r.pode_editar) { <button type="button" class="acao-secundaria acao-pequena" (click)="f.comunicacao.push({ quem: '', momento: '', meio: '', responsavel: '' })">Adicionar comunicação</button> }
          </section>

          <section class="secao-tarefa">
            <h3><span>9</span> Plano de remediação (rollback) *</h3>
            @for (l of f.rollback; track $index; let i = $index) {
              <div class="linha-rdm">
                <div><label [for]="'rb-at-' + i">Atividade</label><input [id]="'rb-at-' + i" [name]="'rb-at-' + i" maxlength="1000" [(ngModel)]="l.atividade" /></div>
                <div><label [for]="'rb-t-' + i">Tempo estimado</label><input [id]="'rb-t-' + i" [name]="'rb-t-' + i" maxlength="60" [(ngModel)]="l.tempo" placeholder="Ex.: 00:30" /></div>
                <div><label [for]="'rb-ex-' + i">Executor(es)</label><input [id]="'rb-ex-' + i" [name]="'rb-ex-' + i" maxlength="300" [(ngModel)]="l.executor" /></div>
                @if (r.pode_editar) { <button type="button" class="acao-perigo acao-pequena" (click)="f.rollback.splice(i, 1)">Remover</button> }
              </div>
            } @empty { <p class="dica-formulario">Nenhuma atividade de retorno ainda.</p> }
            @if (r.pode_editar) { <button type="button" class="acao-secundaria acao-pequena" (click)="f.rollback.push({ atividade: '', tempo: '', executor: '' })">Adicionar atividade de retorno</button> }
            <div class="grade-formulario" style="margin-top: 12px">
              <div class="ocupa-duas"><label for="rdm-rb-just">Justificativa do rollback</label><textarea id="rdm-rb-just" name="rb_just" rows="2" maxlength="4000" [(ngModel)]="f.rollback_justificativa"></textarea></div>
            </div>
          </section>

          <section class="secao-tarefa">
            <h3><span>10</span> Gestão do conhecimento</h3>
            <div class="tabela-fixa" aria-hidden="true"><span></span><small>Ação</small><small>Responsável</small><span></span></div>
            @for (l of f.conhecimento; track l.tipo_documento; let i = $index) {
              <div class="tabela-fixa">
                <span class="rotulo-linha">{{ l.tipo_documento }}</span>
                <select [name]="'gc-a-' + i" [(ngModel)]="l.acao" [attr.aria-label]="'Ação para ' + l.tipo_documento"><option value="">—</option>@for (o of acoesConhecimento; track o) { <option [value]="o">{{ o }}</option> }</select>
                <input [name]="'gc-r-' + i" maxlength="300" [(ngModel)]="l.responsavel" [attr.aria-label]="'Responsável por ' + l.tipo_documento" />
                <span></span>
              </div>
            }
            <div class="grade-formulario"><div class="ocupa-duas"><label for="rdm-gc-obs">Observações</label><textarea id="rdm-gc-obs" name="gc_obs" rows="2" maxlength="4000" [(ngModel)]="f.conhecimento_observacoes"></textarea></div></div>
          </section>

          <section class="secao-tarefa">
            <h3><span>11</span> Informações complementares <small>(vão no anexo da RDM)</small></h3>
            <div class="grade-formulario">
              <div><label for="rdm-categoria">Categoria</label><select id="rdm-categoria" name="categoria" [(ngModel)]="f.complementares.categoria"><option value="">—</option>@for (o of categorias; track o) { <option [value]="o">{{ o }}</option> }</select></div>
              <div><label for="rdm-impacto-prev">Impacto previsto</label><select id="rdm-impacto-prev" name="impacto_prev" [(ngModel)]="f.complementares.impacto_previsto"><option value="">—</option>@for (o of impactos; track o) { <option [value]="o">{{ o }}</option> }</select></div>
              <div><label for="rdm-resp-exec">Responsável pela execução</label><input id="rdm-resp-exec" name="resp_exec" maxlength="300" [(ngModel)]="f.complementares.responsavel_execucao" /></div>
              <div><label for="rdm-equipes">Equipes envolvidas</label><input id="rdm-equipes" name="equipes" maxlength="300" [(ngModel)]="f.complementares.equipes_envolvidas" placeholder="Ex.: Servidores, Redes e Segurança" /></div>
              <div class="ocupa-duas"><label for="rdm-escopo">Descrição técnica / escopo</label><textarea id="rdm-escopo" name="escopo" rows="3" maxlength="4000" [(ngModel)]="f.complementares.descricao_tecnica"></textarea></div>
              <div class="ocupa-duas"><label for="rdm-riscos">Riscos identificados</label><textarea id="rdm-riscos" name="riscos" rows="2" maxlength="4000" [(ngModel)]="f.complementares.riscos"></textarea></div>
              <div class="ocupa-duas"><label for="rdm-medidas">Medidas preventivas</label><textarea id="rdm-medidas" name="medidas" rows="2" maxlength="4000" [(ngModel)]="f.complementares.medidas_preventivas"></textarea></div>
              <div class="ocupa-duas"><label for="rdm-valid">Procedimentos de validação</label><textarea id="rdm-valid" name="valid" rows="2" maxlength="4000" [(ngModel)]="f.complementares.procedimentos_validacao"></textarea></div>
              <div class="ocupa-duas"><label for="rdm-criterios">Critérios de sucesso</label><textarea id="rdm-criterios" name="criterios" rows="2" maxlength="4000" [(ngModel)]="f.complementares.criterios_sucesso"></textarea></div>
              <div class="ocupa-duas"><span class="rotulo-campo">Pré-requisitos e documentação</span>
                <div class="lista-checks">
                  @for (p of preRequisitos; track p; let i = $index) {
                    <label><input type="checkbox" [name]="'pr-' + i" [checked]="f.complementares.pre_requisitos.includes(p)" (change)="alternarPreRequisito(p)" /> {{ p }}</label>
                  }
                </div></div>
              <div><label for="rdm-analise">Responsável pela análise técnica</label><input id="rdm-analise" name="analise" maxlength="300" [(ngModel)]="f.complementares.responsavel_analise_tecnica" /></div>
              <div class="ocupa-duas"><label for="rdm-obs">Observações adicionais</label><textarea id="rdm-obs" name="obs" rows="2" maxlength="4000" [(ngModel)]="f.complementares.observacoes_adicionais"></textarea></div>
            </div>
          </section>
        </fieldset>

        @if (r.pode_editar) {
          <footer class="acoes-formulario">
            <button type="button" class="acao-secundaria" [class.carregando]="salvando() === 'salvar'" [disabled]="!!salvando()" (click)="salvar()">Salvar rascunho</button>
            <button type="button" class="acao-primaria" [class.carregando]="salvando() === 'enviar'" [disabled]="!!salvando()" (click)="enviar()">{{ r.situacao === 'reprovada' ? 'Reenviar para aprovação' : 'Enviar para aprovação' }}</button>
          </footer>
        }

        @if (r.pode_decidir) {
          <!-- Decisão da liderança: aprovar (verde) ou reprovar com motivo (vermelho), separados -->
          <section class="secao-tarefa decisao-rdm" aria-labelledby="titulo-decisao-rdm">
            <h3 id="titulo-decisao-rdm"><span>✓</span> Decisão da liderança</h3>
            <div class="grade-formulario">
              <div class="ocupa-duas"><label for="rdm-motivo">Motivo (obrigatório só para reprovar)</label>
                <textarea id="rdm-motivo" name="motivo" rows="2" maxlength="4000" [(ngModel)]="motivo"></textarea></div>
            </div>
            <footer class="acoes-formulario">
              <button type="button" class="acao-recusar" [class.carregando]="salvando() === 'reprovar'" [disabled]="!!salvando() || !motivo.trim()" (click)="reprovar()">Reprovar RDM</button>
              <button type="button" class="acao-positiva" [class.carregando]="salvando() === 'aprovar'" [disabled]="!!salvando()" (click)="aprovar()">Aprovar RDM</button>
            </footer>
          </section>
        }
        </div>
      </form>
      <p style="margin-top: 12px"><a class="acao-secundaria" [routerLink]="['/tarefas', r.tarefa_numero]">Voltar para a tarefa</a></p>
    } @else {
      <app-esqueleto tipo="formulario" [linhas]="8" />
    }
  `,
})
/**
 * Página da RDM de uma tarefa.
 *
 * Fluxo: rascunho → pendente (enviada) → aprovada ou reprovada. Quem pode
 * editar (pode_editar, decidido pela API) salva e envia; a liderança
 * (pode_decidir) aprova ou reprova. A tela não decide permissões: só mostra
 * ou esconde botões conforme o que a API devolve.
 *
 * Recursos do Angular usados aqui:
 * - `inject()` pega um serviço do sistema de injeção de dependências sem
 *   precisar declará-lo no construtor;
 * - `signal()` guarda um valor reativo: quando muda (com `set`), o template
 *   que o lê é redesenhado;
 * - `[(ngModel)]` no template liga o campo ao objeto `f` nos dois sentidos.
 */
export class RdmTarefaComponent implements OnInit {
  private readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  // Número da tarefa lido da URL (/tarefas/:numero/rdm) uma única vez (snapshot).
  private readonly numero = Number(inject(ActivatedRoute).snapshot.paramMap.get('numero'));

  /** RDM carregada da API; `null` enquanto carrega (o template mostra o esqueleto). */
  protected readonly rdm = signal<RdmLeitura | null>(null);
  /** Ação em andamento (o botão dela mostra o carregamento). */
  protected readonly salvando = signal<'salvar' | 'enviar' | 'aprovar' | 'reprovar' | null>(null);
  /** Cópia editável do formulário. */
  protected f!: FormularioRdm;
  /** Motivo digitado pela liderança; obrigatório apenas para reprovar. */
  protected motivo = '';
  // Listas de opções da matriz da Prodesp expostas ao template (os selects
  // e as caixas de seleção leem daqui).
  protected readonly situacoes = SITUACOES_RDM;
  protected readonly tipos = TIPOS_RDM;
  protected readonly acoes = ACOES_RDM;
  protected readonly finalidades = FINALIDADES_RDM;
  protected readonly prioridades = PRIORIDADES_RDM;
  protected readonly niveis = NIVEIS_RDM;
  protected readonly etapas = ETAPAS_RDM;
  protected readonly acoesConhecimento = ACOES_CONHECIMENTO_RDM;
  protected readonly categorias = CATEGORIAS_RDM;
  protected readonly impactos = IMPACTOS_PREVISTOS_RDM;
  protected readonly preRequisitos = PRE_REQUISITOS_RDM;

  /**
   * Ao abrir a página, busca a RDM da tarefa. `subscribe` dispara a requisição
   * HTTP (um Observable não faz nada até alguém se inscrever) e recebe a
   * resposta em `next` ou a falha em `error`.
   */
  ngOnInit(): void {
    this.api.rdm(this.numero).subscribe({ next: (r) => this.aplicar(r), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível abrir a RDM') });
  }

  /**
   * Aplica uma resposta da API na tela: copia o formulário com
   * `structuredClone` (cópia profunda, para que editar `f` não altere o objeto
   * original guardado em `rdm`), atualiza a RDM e libera os botões.
   */
  private aplicar(r: RdmLeitura): void {
    this.f = structuredClone(r.formulario);
    this.rdm.set(r);
    this.salvando.set(null);
  }

  /**
   * Executa uma ação que devolve a RDM atualizada.
   *
   * @param acao   qual botão fica em "carregando" enquanto a requisição corre.
   * @param pedido requisição HTTP já montada (só é enviada no `subscribe`).
   * @param erro   título da mensagem de erro mostrada se a API recusar.
   * @param depois passo opcional após o sucesso (ex.: voltar para a tarefa).
   */
  private executar(acao: 'salvar' | 'enviar' | 'aprovar' | 'reprovar', pedido: Observable<RdmLeitura>, erro: string, depois?: (r: RdmLeitura) => void): void {
    this.salvando.set(acao);
    pedido.subscribe({
      next: (r) => { this.aplicar(r); depois?.(r); },
      error: (e) => { this.salvando.set(null); this.dialogos.mostrarErro(e, erro); },
    });
  }

  /**
   * Marca ou desmarca um pré-requisito na lista de caixas de seleção. Cria um
   * novo array em vez de alterar o atual, para o Angular perceber a mudança.
   */
  protected alternarPreRequisito(item: string): void {
    const lista = this.f.complementares.pre_requisitos;
    this.f.complementares.pre_requisitos = lista.includes(item) ? lista.filter((x) => x !== item) : [...lista, item];
  }

  /** Salva o formulário como rascunho, sem mudar a situação da RDM. */
  protected salvar(): void {
    this.executar('salvar', this.api.salvarRdm(this.numero, this.f), 'Não foi possível salvar a RDM');
  }

  /**
   * Pede confirmação e envia a RDM para aprovação. Os efeitos (tarefa em
   * validação, aviso à liderança, número do Protocolo no primeiro envio) são
   * feitos pelo backend; o texto do diálogo apenas os descreve ao usuário.
   */
  protected async enviar(): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Enviar a RDM para aprovação?',
      mensagem: 'A tarefa vai para Em validação e a liderança da equipe é avisada. No primeiro envio, a RDM recebe o número do Protocolo (RDM SGI 00000/AAAA).',
      rotuloConfirmar: 'Enviar',
    });
    if (ok) this.executar('enviar', this.api.enviarRdm(this.numero, this.f), 'Não foi possível enviar a RDM');
  }

  /**
   * Pede confirmação e aprova a RDM. O backend gera o PDF, anexa à tarefa,
   * envia o e-mail e devolve a tarefa para "Em andamento"; depois a tela volta
   * para a tarefa.
   */
  protected async aprovar(): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Aprovar a RDM?',
      mensagem: 'O PDF da RDM é gerado e anexado à tarefa, o e-mail "RDM aprovada" vai aos responsáveis e seguidores, e a tarefa volta para Em andamento para a execução.',
      rotuloConfirmar: 'Aprovar',
    });
    if (ok) this.executar('aprovar', this.api.aprovarRdm(this.numero), 'Não foi possível aprovar a RDM', () => this.voltar());
  }

  /** Reprova a RDM com o motivo digitado (o botão só habilita com motivo) e volta para a tarefa. */
  protected reprovar(): void {
    this.executar('reprovar', this.api.reprovarRdm(this.numero, this.motivo.trim()), 'Não foi possível reprovar a RDM', () => { this.motivo = ''; this.voltar(); });
  }

  /**
   * Baixa o PDF da RDM aprovada. O nome do arquivo troca a barra do número
   * ("00001/2026") por hífen, porque barra não é permitida em nome de arquivo.
   */
  protected baixarPdf(r: RdmLeitura): void {
    this.api.pdfRdm(this.numero, `RDM-SGI-${r.numero.replace('/', '-')}.pdf`).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar o PDF') });
  }

  /** Volta para a página da tarefa dona da RDM. */
  private voltar(): void {
    void this.roteador.navigate(['/tarefas', this.numero]);
  }
}
