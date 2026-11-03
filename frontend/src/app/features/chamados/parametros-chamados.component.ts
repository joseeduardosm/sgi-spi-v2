// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela de Parâmetros dos Chamados (abas: geral, categorias, status, SLAs, expedientes, setores, recorrentes, TVs, RH e saúde).

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { Observable } from 'rxjs';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoChamadosComponent } from './cabecalho-chamados.component';
import { ChamadosApiService } from './chamados-api.service';
import { MigracaoGlpiComponent } from './migracao-glpi.component';
import { CampoEscolhaComponent, OpcaoEscolha } from '../../shared/componentes/campo-escolha/campo-escolha.component';
import {
  CampoLeitura, Categoria, CorStatus, dataHora, DIAS_SEMANA, GravacaoRecorrente, ParametrosGerais, Recorrente, ROTULOS_COR, SaudeChamados, SetorAtendimento,
  StatusApresentacao, Substatus, Expediente, FaixaExpediente, GravacaoCampo, GravacaoCategoria, ROTULOS_PRIORIDADE, ROTULOS_TIPO_CAMPO, ROTULOS_UNIDADE, SetorResumo, Sla,
  TipoCampo, ColunaPainel, ConfigPainel, ParametrosRh, ServicoRh, GravacaoRespostaPronta, MotivoPendencia, RespostaPronta, CategoriaItil, GravacaoCategoriaItil,
} from './chamados.models';

type Aba = 'geral' | 'categorias' | 'itil' | 'glpi' | 'status' | 'slas' | 'expedientes' | 'setores' | 'recorrentes' | 'respostas' | 'motivos' | 'painel' | 'rh' | 'saude';

function recorrenteVazio(): GravacaoRecorrente {
  return { nome: '', categoria_id: '', titulo: '', descricao: '', periodicidade_quantidade: 1, periodicidade_unidade: 'dia', antecedencia_min: 0, so_dias_uteis: true,
    proxima_em: '', fim_em: null, ativo: true, solicitante_id: null };
}

/** ISO (UTC) → valor do campo datetime-local, no horário de São Paulo. */
function paraCampoLocal(iso: string): string {
  const partes = new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    .format(new Date(iso));
  return partes.replace(' ', 'T');
}

/** Valor do campo datetime-local (horário de São Paulo, sem horário de verão desde 2019) → ISO com o fuso. */
function deCampoLocal(valor: string): string {
  return `${valor}:00-03:00`;
}

function campoVazio(): GravacaoCampo {
  return { rotulo: '', tipo: 'texto', obrigatorio: false, dado_pessoal: false, ajuda: null, opcoes: null, condicao: null, ordem: 0, ativo: true };
}

function categoriaVazia(): GravacaoCategoria {
  return {
    nome: '', pai_id: null, ativa: true, visivel_solicitante: true, permite_incidente: true, permite_requisicao: true, setor_id: null, responsavel_id: null,
    sla_tto_id: null, sla_ttr_id: null, prioridade_padrao: null, perguntar_impedindo: true, sigilosa: false, ordem: 0, categoria_itil_id: null,
    setores_permitidos: [],
  };
}

@Component({
  selector: 'app-parametros-chamados',
  imports: [FormsModule, CabecalhoChamadosComponent, EsqueletoComponent, MigracaoGlpiComponent, CampoEscolhaComponent],
  template: `
    <div class="modulo-chamados">
      <app-cabecalho-chamados titulo="Parâmetros" descricao="Categorias, prazos e horários de trabalho. Nada disso fica no código: muda aqui e vale para os próximos chamados." />
      <section class="painel-gestao protocolo">
        <div class="abas abas-rolagem" role="tablist">
          @for (x of abas; track x[0]) {
            <button type="button" role="tab" [class.ativa]="aba() === x[0]" [attr.aria-selected]="aba() === x[0]" (click)="trocarAba(x[0])">{{ x[1] }}
              @if (x[0] === 'saude' && saude()?.problemas?.length) { <span class="contador-aba destaque">{{ saude()!.problemas.length }}</span> }</button>
          }
        </div>

        @if (carregando()) {
          <app-esqueleto tipo="tabela" [linhas]="5" [colunas]="4" />
        } @else {
          @switch (aba()) {
            @case ('categorias') {
              @if (semSetor().length) { <p class="aviso-formulario erro">Categorias ativas sem setor responsável: {{ semSetor().length }}. Corrija antes de abrir o módulo.</p> }
              <form class="grade-formulario" (ngSubmit)="salvarCategoria()" #fc="ngForm">
                <div><label for="pc-nome">{{ editandoCategoria() ? 'Renomear categoria' : 'Nova categoria' }}</label>
                  <input id="pc-nome" name="nome" required maxlength="150" [(ngModel)]="categoria.nome" /></div>
                <div><label for="pc-pai">Dentro de</label>
                  <app-campo-escolha idCampo="pc-pai" name="pai" [opcoes]="opCategorias()" vazio="Nenhuma (categoria principal)" [excluir]="editandoCategoria() ?? undefined" [(ngModel)]="categoria.pai_id" /></div>
                <div><label for="pc-setor">Setor responsável</label>
                  <app-campo-escolha idCampo="pc-setor" name="setor" [opcoes]="opSetores()" [vazio]="categoria.pai_id ? 'Herdar da categoria-mãe' : 'Escolha o setor'" [(ngModel)]="categoria.setor_id" /></div>
                <div><label for="pc-prioridade">Prioridade padrão</label>
                  <app-campo-escolha idCampo="pc-prioridade" name="prioridade" [opcoes]="opPrioridades" [vazio]="categoria.pai_id ? 'Herdar' : 'Normal'" [(ngModel)]="categoria.prioridade_padrao" /></div>
                <div><label for="pc-tto">SLA de atendimento</label>
                  <app-campo-escolha idCampo="pc-tto" name="tto" [opcoes]="opSlasTto()" [vazio]="categoria.pai_id ? 'Herdar' : 'Sem prazo'" [(ngModel)]="categoria.sla_tto_id" /></div>
                <div><label for="pc-ttr">SLA de solução</label>
                  <app-campo-escolha idCampo="pc-ttr" name="ttr" [opcoes]="opSlasTtr()" [vazio]="categoria.pai_id ? 'Herdar' : 'Sem prazo'" [(ngModel)]="categoria.sla_ttr_id" /></div>
                <div class="ocupa-duas"><label for="pc-itil">Categoria ITIL do chamado</label>
                  <app-campo-escolha idCampo="pc-itil" name="itil" [opcoes]="opItilAtivas()" [vazio]="categoria.pai_id ? 'Herdar da categoria-mãe (ou pendente)' : 'Pendente: o técnico classifica'" [(ngModel)]="categoria.categoria_itil_id" />
                  <small class="dica-formulario">O chamado aberto neste assunto já nasce com esta classificação técnica. Assuntos simples (ex.: Impressoras) podem ter uma fixa;
                    os amplos (ex.: Informática) podem ficar pendentes para o técnico escolher (Servidores, Wi-Fi, Liberação de acesso...).</small></div>
                <div class="ocupa-duas"><label for="pc-quem">Quem pode escolher este assunto</label>
                  <app-campo-escolha idCampo="pc-quem" name="quem" [opcoes]="opQuemEscolhe" [ngModel]="quemEscolhe" (ngModelChange)="trocarQuemEscolhe($event)" />
                  <small class="dica-formulario">{{ dicaQuemEscolhe() }}</small>
                  @if (quemEscolhe === 'setores') {
                    @if (categoria.setores_permitidos.length) {
                      <ul class="fichas-setores" aria-label="Setores que podem escolher">
                        @for (id of categoria.setores_permitidos; track id) {
                          <li>{{ nomeSetor(id) }}<button type="button" [attr.aria-label]="'Tirar ' + nomeSetor(id)" (click)="tirarSetorPermitido(id)">×</button></li>
                        }
                      </ul>
                    }
                    <label for="pc-quem-setor">Acrescentar setor</label>
                    <app-campo-escolha idCampo="pc-quem-setor" name="quem-setor" placeholder="Digite o nome do setor (ex.: CGP)" [opcoes]="opSetoresNaoPermitidos()"
                      [ngModel]="null" (ngModelChange)="acrescentarSetorPermitido($event)" />
                  }
                </div>
                <div class="ocupa-duas">
                  <label class="linha-caixa"><input type="checkbox" name="ativa" [(ngModel)]="categoria.ativa" /> Em uso</label>
                  <small class="dica-formulario">Desmarcada, ninguém abre chamado novo aqui; os antigos continuam.</small>
                  <label class="linha-caixa"><input type="checkbox" name="impedindo" [(ngModel)]="categoria.perguntar_impedindo" /> Perguntar "Isso está te impedindo de trabalhar?"</label>
                  <small class="dica-formulario">Se a pessoa responder sim, a prioridade sobe um nível.</small>
                  <label class="linha-caixa"><input type="checkbox" name="sigilosa" [(ngModel)]="categoria.sigilosa" /> Assunto sigiloso</label>
                  <small class="dica-formulario">Só quem pediu e a equipe que atende leem o título e a descrição; no painel aparece "Chamado sigiloso".</small>
                </div>
                <div class="ocupa-duas acoes-formulario">
                  @if (editandoCategoria()) { <button type="button" class="acao-secundaria" (click)="novaCategoria()">Cancelar edição</button> }
                  <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fc.invalid || salvando()">{{ editandoCategoria() ? 'Salvar categoria' : 'Criar categoria' }}</button>
                </div>
              </form>
              @if (editandoCategoria()) {
                <section class="campos-categoria" aria-labelledby="titulo-campos">
                  <h3 id="titulo-campos">Campos adicionais de "{{ categoria.nome }}"</h3>
                  <p class="dica-formulario">Perguntas extras na abertura de chamados desta categoria e das subcategorias. Use no lugar dos formulários simples.</p>
                  @if (campos().length) {
                    <div class="tabela-gestao-envoltorio">
                      <table class="tabela-gestao">
                        <thead><tr><th>Campo</th><th>Tipo</th><th>Regras</th><th></th></tr></thead>
                        <tbody>
                          @for (f of campos(); track f.id) {
                            <tr>
                              <td><strong>{{ f.rotulo }}</strong>@if (!f.ativo) { <span class="selo-status" data-chamado="neutro">Inativo</span> }</td>
                              <td>{{ rotuloTipo(f.tipo) }}@if (f.opcoes?.length) { <br /><small>{{ f.opcoes!.join(' · ') }}</small> }</td>
                              <td>{{ f.obrigatorio ? 'Obrigatório' : 'Opcional' }}@if (f.dado_pessoal) { · <span class="selo-status" data-chamado="alerta">Dado pessoal</span> }
                                @if (f.condicao) { <br /><small>Só se "{{ rotuloCampo(f.condicao.campo_id) }}" = {{ f.condicao.igual }}</small> }</td>
                              <td><div class="botoes-linha"><button type="button" class="acao-secundaria acao-pequena" (click)="editarCampo(f)">Editar</button>
                                <button type="button" class="acao-perigo acao-pequena" (click)="excluirCampo(f)">Excluir</button></div></td>
                            </tr>
                          }
                        </tbody>
                      </table>
                    </div>
                  }
                  <form class="grade-formulario" (ngSubmit)="salvarCampo()" #fcampo="ngForm">
                    <div><label for="pcf-rotulo">{{ editandoCampo() ? 'Alterar campo' : 'Novo campo' }}</label>
                      <input id="pcf-rotulo" name="rotulo" required maxlength="150" placeholder="Ex.: Ramal" [(ngModel)]="campo.rotulo" /></div>
                    <div><label for="pcf-tipo">Tipo</label>
                      <app-campo-escolha idCampo="pcf-tipo" name="tipo" [opcoes]="opTiposCampo" [(ngModel)]="campo.tipo" /></div>
                    @if (campo.tipo === 'lista') {
                      <div class="ocupa-duas"><label for="pcf-opcoes">Opções (uma por linha)</label>
                        <textarea id="pcf-opcoes" name="opcoes" rows="3" [(ngModel)]="opcoesTexto"></textarea></div>
                    }
                    <div><label for="pcf-ajuda">Ajuda <small>(opcional)</small></label><input id="pcf-ajuda" name="ajuda" maxlength="300" [(ngModel)]="campo.ajuda" /></div>
                    <div><label for="pcf-cond">Mostrar só se <small>(opcional)</small></label>
                      <app-campo-escolha idCampo="pcf-cond" name="cond" [opcoes]="opCampos()" vazio="Sempre mostrar" [excluir]="editandoCampo() ?? undefined" [(ngModel)]="condicaoCampoId" /></div>
                    @if (condicaoCampoId) {
                      <div><label for="pcf-igual">for igual a</label><input id="pcf-igual" name="igual" required maxlength="150" placeholder="Ex.: Sim" [(ngModel)]="condicaoIgual" /></div>
                    }
                    <div class="ocupa-duas">
                      <label class="linha-caixa"><input type="checkbox" name="obrigatorio" [(ngModel)]="campo.obrigatorio" /> Obrigatório</label>
                      <label class="linha-caixa"><input type="checkbox" name="pessoal" [(ngModel)]="campo.dado_pessoal" /> Dado pessoal (CPF, RG, telefone pessoal: aparece mascarado)</label>
                      <label class="linha-caixa"><input type="checkbox" name="campo-ativo" [(ngModel)]="campo.ativo" /> Ativo</label>
                    </div>
                    <div class="ocupa-duas acoes-formulario">
                      @if (editandoCampo()) { <button type="button" class="acao-secundaria" (click)="novoCampo()">Cancelar edição</button> }
                      <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fcampo.invalid || salvando()">{{ editandoCampo() ? 'Salvar campo' : 'Criar campo' }}</button>
                    </div>
                  </form>
                </section>
              }
              <div class="tabela-gestao-envoltorio">
                <table class="tabela-gestao">
                  <thead><tr><th>Categoria</th><th>Setor responsável</th><th>Situação</th><th></th></tr></thead>
                  <tbody>
                    @for (c of categorias(); track c.id) {
                      <tr>
                        <td [style.padding-left.px]="12 + (c.nivel - 1) * 20"><strong>{{ c.nome }}</strong>@if (c.nivel > 1) { <br /><small>{{ c.caminho }}</small> }</td>
                        <td>{{ c.setor_efetivo_nome || '—' }}@if (c.herda_setor && c.setor_efetivo_nome) { <small> (herdado)</small> }</td>
                        <td>
                          @if (!c.ativa) { <span class="selo-status" data-chamado="neutro">Inativa</span> }
                          @else if (!c.setor_efetivo_id) { <span class="selo-situacao" data-prazo="perigo">Sem setor</span> }
                          @else { <span class="selo-status" data-chamado="sucesso">Ativa</span> }
                          @if (c.sigilosa) { <span class="selo-status" data-chamado="alerta">Sigilosa</span> }
                        </td>
                        <td><div class="botoes-linha"><button type="button" class="acao-secundaria acao-pequena" (click)="editarCategoria(c)">Editar</button>
                          <button type="button" class="acao-perigo acao-pequena" (click)="excluirCategoria(c)">Excluir</button></div></td>
                      </tr>
                    } @empty { <tr><td colspan="4" class="estado-vazio">Nenhuma categoria. Crie a primeira acima.</td></tr> }
                  </tbody>
                </table>
              </div>
            }

            @case ('itil') {
              <p class="dica-formulario">A <strong>categoria ITIL</strong> é a classificação técnica do chamado (Servidores, Wi-Fi, Liberação de acesso...). É separada das
                <strong>categorias</strong> de assunto que quem abre escolhe: só quem atende vê e classifica. As categorias do GLPI entram aqui na migração.</p>
              <form class="grade-formulario" (ngSubmit)="salvarItil()" #fi="ngForm">
                <div><label for="pi-nome">{{ editandoItil() ? 'Renomear categoria ITIL' : 'Nova categoria ITIL' }}</label>
                  <input id="pi-nome" name="nome" required maxlength="150" placeholder="Ex.: Servidores" [(ngModel)]="itil.nome" /></div>
                <div><label for="pi-pai">Dentro de</label>
                  <app-campo-escolha idCampo="pi-pai" name="pai" [opcoes]="opItil()" vazio="Nenhuma (categoria principal)" [excluir]="editandoItil() ?? undefined" [(ngModel)]="itil.pai_id" /></div>
                <div class="ocupa-duas"><label class="linha-caixa"><input type="checkbox" name="ativa" [(ngModel)]="itil.ativa" /> Ativa</label></div>
                <div class="ocupa-duas acoes-formulario">
                  @if (editandoItil()) { <button type="button" class="acao-secundaria" (click)="novaItil()">Cancelar edição</button> }
                  <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fi.invalid || salvando()">{{ editandoItil() ? 'Salvar categoria ITIL' : 'Criar categoria ITIL' }}</button>
                </div>
              </form>
              <div class="tabela-gestao-envoltorio">
                <table class="tabela-gestao">
                  <thead><tr><th>Categoria ITIL</th><th>Chamados</th><th>Situação</th><th></th></tr></thead>
                  <tbody>
                    @for (i of categoriasItil(); track i.id) {
                      <tr>
                        <td [style.padding-left.px]="12 + (i.nivel - 1) * 20"><strong>{{ i.nome }}</strong>@if (i.nivel > 1) { <br /><small>{{ i.caminho }}</small> }</td>
                        <td>{{ i.chamados }}</td>
                        <td>@if (i.ativa) { <span class="selo-status" data-chamado="sucesso">Ativa</span> } @else { <span class="selo-status" data-chamado="neutro">Inativa</span> }</td>
                        <td><div class="botoes-linha"><button type="button" class="acao-secundaria acao-pequena" (click)="editarItil(i)">Editar</button>
                          <button type="button" class="acao-perigo acao-pequena" (click)="excluirItil(i)">Excluir</button></div></td>
                      </tr>
                    } @empty { <tr><td colspan="4" class="estado-vazio">Nenhuma categoria ITIL. Crie a primeira acima ou traga as do GLPI na migração.</td></tr> }
                  </tbody>
                </table>
              </div>
            }

            @case ('glpi') { <app-migracao-glpi /> }

            @case ('geral') {
              @if (gerais) {
                <form class="grade-formulario" (ngSubmit)="salvarGeral()" #fg="ngForm">
                  <div><label for="pg-dias">Dias úteis para dizer "Não resolveu"</label>
                    <input id="pg-dias" name="dias" type="number" min="1" max="30" required [(ngModel)]="gerais.dias_reabrir" /></div>
                  <div><label for="pg-pf">Ponto facultativo do RH</label>
                    <app-campo-escolha idCampo="pg-pf" name="pf" [opcoes]="opPontoFacultativo" [(ngModel)]="gerais.ponto_facultativo_util" /></div>
                  <div class="ocupa-duas"><p class="dica-formulario">Cor do prazo na fila, no chamado e no painel de TV, pela parte do prazo já consumida (cumprido fica verde):</p></div>
                  <div><label for="pg-alerta">Âmbar a partir de (%)</label><input id="pg-alerta" name="alerta" type="number" min="1" max="100" required [(ngModel)]="gerais.limite_alerta" /></div>
                  <div><label for="pg-atencao">Laranja a partir de (%)</label><input id="pg-atencao" name="atencao" type="number" min="1" max="100" required [(ngModel)]="gerais.limite_atencao" /></div>
                  <div><label for="pg-perigo">Vermelho a partir de (%)</label><input id="pg-perigo" name="perigo" type="number" min="1" max="100" required [(ngModel)]="gerais.limite_perigo" /></div>
                  <div class="ocupa-duas"><label for="pg-inicio">Atendimento no SGI a partir de</label>
                    <input id="pg-inicio" name="inicio" type="date" [ngModel]="gerais.inicio_atendimento" (ngModelChange)="gerais.inicio_atendimento = $event || null" />
                    <small class="dica-formulario">Nesse dia o "Abrir chamado" do sistema passa a abrir aqui, para todos. Até lá ele continua indo para o GLPI, e só quem
                      tem Controle total abre chamado no SGI (para testar e treinar). As equipes terminam os pendentes no GLPI. Vazio = sem data marcada.</small></div>
                  <div class="ocupa-duas acoes-formulario">
                    <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fg.invalid || salvando()">Salvar</button>
                  </div>
                </form>
              }
            }

            @case ('status') {
              <p class="dica-formulario">Os cinco status são fixos (as regras de prazo e de encerramento dependem deles). Aqui muda só o nome exibido e a cor.</p>
              <div class="tabela-gestao-envoltorio">
                <table class="tabela-gestao">
                  <thead><tr><th>Status</th><th>Nome exibido</th><th>Cor</th><th>Prévia</th><th></th></tr></thead>
                  <tbody>
                    @for (x of statusEdicao; track x.status_base) {
                      <tr>
                        <td><span class="texto-codigo">{{ x.status_base }}</span></td>
                        <td><input [name]="'st-nome-' + x.status_base" [attr.aria-label]="'Nome de ' + x.status_base" maxlength="60" [(ngModel)]="x.nome" /></td>
                        <td><app-campo-escolha [name]="'st-cor-' + x.status_base" [rotuloAcessivel]="'Cor de ' + x.status_base" [opcoes]="opCores" [(ngModel)]="x.cor" /></td>
                        <td><span class="selo-status" [attr.data-chamado]="x.cor">{{ x.nome }}</span></td>
                        <td><button type="button" class="acao-secundaria acao-pequena" [disabled]="salvando()" (click)="salvarStatus(x.status_base, x.nome, x.cor)">Salvar</button></td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
              <h3 class="titulo-secao-parametros">Sub-status</h3>
              <p class="dica-formulario">Detalham um status sem mudar as regras dele (ex.: "Aguardando peça" dentro de "Em atendimento"). Quem atende escolhe no chamado.</p>
              <form class="grade-formulario" (ngSubmit)="salvarSubstatus()" #fs2="ngForm">
                <div><label for="ps-sub-nome">{{ editandoSubstatus() ? 'Alterar sub-status' : 'Novo sub-status' }}</label>
                  <input id="ps-sub-nome" name="sub-nome" required maxlength="60" [(ngModel)]="sub.nome" /></div>
                <div><label for="ps-sub-base">Dentro de</label>
                  <app-campo-escolha idCampo="ps-sub-base" name="sub-base" [opcoes]="opStatus()" [(ngModel)]="sub.status_base" /></div>
                <div><label for="ps-sub-cor">Cor</label>
                  <app-campo-escolha idCampo="ps-sub-cor" name="sub-cor" [opcoes]="opCores" [(ngModel)]="sub.cor" /></div>
                <div><label class="linha-caixa"><input type="checkbox" name="sub-ativo" [(ngModel)]="sub.ativo" /> Ativo</label></div>
                <div class="ocupa-duas acoes-formulario">
                  @if (editandoSubstatus()) { <button type="button" class="acao-secundaria" (click)="novoSubstatus()">Cancelar edição</button> }
                  <button type="submit" class="acao-primaria" [disabled]="fs2.invalid || salvando()">{{ editandoSubstatus() ? 'Salvar sub-status' : 'Criar sub-status' }}</button>
                </div>
              </form>
              <div class="tabela-gestao-envoltorio">
                <table class="tabela-gestao">
                  <thead><tr><th>Sub-status</th><th>Dentro de</th><th></th></tr></thead>
                  <tbody>
                    @for (x of listaSubstatus(); track x.id) {
                      <tr><td><span class="selo-status" [attr.data-chamado]="x.cor">{{ x.nome }}</span>@if (!x.ativo) { <span class="selo-status" data-chamado="neutro">Inativo</span> }</td>
                        <td>{{ nomeStatus(x.status_base) }}</td>
                        <td><div class="botoes-linha"><button type="button" class="acao-secundaria acao-pequena" (click)="editarSubstatus(x)">Editar</button>
                          <button type="button" class="acao-perigo acao-pequena" (click)="excluirSubstatus(x)">Excluir</button></div></td></tr>
                    } @empty { <tr><td colspan="3" class="estado-vazio">Nenhum sub-status.</td></tr> }
                  </tbody>
                </table>
              </div>
            }

            @case ('setores') {
              <p class="dica-formulario">Todo setor ativo pode atender chamados. Marque "vê todos" para os membros que atendem enxergarem os chamados de todos os setores.</p>
              <div class="barra-protocolo"><div class="campo"><label for="pst-busca">Buscar setor</label>
                <input id="pst-busca" type="search" [ngModel]="buscaSetor()" (ngModelChange)="buscaSetor.set($event)" /></div></div>
              <div class="tabela-gestao-envoltorio">
                <table class="tabela-gestao">
                  <thead><tr><th>Setor</th><th>Vê todos os chamados</th></tr></thead>
                  <tbody>
                    @for (x of setoresFiltrados(); track x.setor_id) {
                      <tr><td><strong>{{ x.nome }}</strong>@if (x.caminho !== x.nome) { <br /><small>{{ x.caminho }}</small> }</td>
                        <td><label class="linha-caixa"><input type="checkbox" [checked]="x.ve_todos" (change)="salvarSetor(x, $any($event.target).checked)" /> {{ x.ve_todos ? 'Sim' : 'Não' }}</label></td></tr>
                    }
                  </tbody>
                </table>
              </div>
            }

            @case ('recorrentes') {
              <form class="grade-formulario" (ngSubmit)="salvarRecorrente()" #fr="ngForm">
                <div><label for="pr-nome">{{ editandoRecorrente() ? 'Alterar recorrente' : 'Novo recorrente' }}</label>
                  <input id="pr-nome" name="nome" required maxlength="200" placeholder="Ex.: Validar os backups" [(ngModel)]="rec.nome" /></div>
                <div><label for="pr-cat">Categoria</label>
                  <app-campo-escolha idCampo="pr-cat" name="cat" required [opcoes]="opCategoriasAtivas()" [(ngModel)]="rec.categoria_id" /></div>
                <div class="ocupa-duas"><label for="pr-titulo">Título do chamado</label><input id="pr-titulo" name="titulo" required minlength="3" maxlength="250" [(ngModel)]="rec.titulo" /></div>
                <div class="ocupa-duas"><label for="pr-desc">Descrição <small>(opcional)</small></label><textarea id="pr-desc" name="desc" rows="2" [(ngModel)]="rec.descricao"></textarea></div>
                <div><label for="pr-qtd">A cada</label><input id="pr-qtd" name="qtd" type="number" min="1" required [(ngModel)]="rec.periodicidade_quantidade" /></div>
                <div><label for="pr-uni">Período</label>
                  <app-campo-escolha idCampo="pr-uni" name="uni" [opcoes]="opPeriodicidade" [(ngModel)]="rec.periodicidade_unidade" /></div>
                <div><label for="pr-prox">Próxima ocorrência</label><input id="pr-prox" name="prox" type="datetime-local" required [(ngModel)]="proximaLocal" /></div>
                <div><label for="pr-ant">Abrir antes (minutos)</label><input id="pr-ant" name="ant" type="number" min="0" max="10080" [(ngModel)]="rec.antecedencia_min" /></div>
                <div><label for="pr-fim">Termina em <small>(opcional)</small></label><input id="pr-fim" name="fim" type="datetime-local" [(ngModel)]="fimLocal" /></div>
                <div class="ocupa-duas">
                  <label class="linha-caixa"><input type="checkbox" name="uteis" [(ngModel)]="rec.so_dias_uteis" /> Só em dia útil (fim de semana e feriado do RH passam para o próximo dia útil)</label>
                  <label class="linha-caixa"><input type="checkbox" name="rec-ativo" [(ngModel)]="rec.ativo" /> Ativo</label>
                </div>
                <div class="ocupa-duas acoes-formulario">
                  @if (editandoRecorrente()) { <button type="button" class="acao-secundaria" (click)="novoRecorrente()">Cancelar edição</button> }
                  <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fr.invalid || salvando()">{{ editandoRecorrente() ? 'Salvar recorrente' : 'Criar recorrente' }}</button>
                </div>
              </form>
              <div class="tabela-gestao-envoltorio">
                <table class="tabela-gestao">
                  <thead><tr><th>Recorrente</th><th>Período</th><th>Próxima</th><th>Última</th><th></th></tr></thead>
                  <tbody>
                    @for (r of recorrentes(); track r.id) {
                      <tr><td><strong>{{ r.nome }}</strong>@if (!r.ativo) { <span class="selo-status" data-chamado="neutro">Inativo</span> }<br /><small>{{ r.categoria_caminho }} · em nome de {{ r.solicitante_nome }}</small></td>
                        <td>A cada {{ r.periodicidade_quantidade }} {{ rotuloPeriodo(r) }}{{ r.so_dias_uteis ? ' (dias úteis)' : '' }}</td>
                        <td>{{ dataHora(r.proxima_em) }}</td><td>{{ r.ultima_geracao_em ? dataHora(r.ultima_geracao_em) : '—' }}</td>
                        <td><div class="botoes-linha"><button type="button" class="acao-secundaria acao-pequena" (click)="editarRecorrente(r)">Editar</button>
                          <button type="button" class="acao-perigo acao-pequena" (click)="excluirRecorrente(r)">Excluir</button></div></td></tr>
                    } @empty { <tr><td colspan="5" class="estado-vazio">Nenhum chamado recorrente.</td></tr> }
                  </tbody>
                </table>
              </div>
            }

            @case ('respostas') {
              <p class="dica-formulario">Textos que quem atende insere na resposta com um clique. Sem setor, valem para todos os que atendem.</p>
              <form class="grade-formulario" (ngSubmit)="salvarResposta(fp)" #fp="ngForm">
                <div><label for="prp-titulo">{{ editandoResposta() ? 'Alterar resposta pronta' : 'Nova resposta pronta' }}</label>
                  <input id="prp-titulo" name="titulo" required minlength="2" maxlength="120" placeholder="Ex.: Reiniciar e testar" [(ngModel)]="resposta.titulo" /></div>
                <div><label for="prp-setor">Setor <small>(opcional)</small></label>
                  <app-campo-escolha idCampo="prp-setor" name="setor" [opcoes]="opSetores()" vazio="Todos os que atendem" [(ngModel)]="resposta.setor_id" /></div>
                <div class="ocupa-duas"><label for="prp-texto">Texto</label>
                  <textarea id="prp-texto" name="texto" rows="4" required maxlength="20000" [(ngModel)]="respostaTexto"></textarea></div>
                <div class="ocupa-duas"><label class="linha-caixa"><input type="checkbox" name="resp-ativo" [(ngModel)]="resposta.ativo" /> Ativa</label></div>
                <div class="ocupa-duas acoes-formulario">
                  @if (editandoResposta()) { <button type="button" class="acao-secundaria" (click)="novaResposta(fp)">Cancelar edição</button> }
                  <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fp.invalid || salvando()">{{ editandoResposta() ? 'Salvar resposta' : 'Criar resposta' }}</button>
                </div>
              </form>
              <div class="tabela-gestao-envoltorio">
                <table class="tabela-gestao">
                  <thead><tr><th>Resposta pronta</th><th>Setor</th><th></th></tr></thead>
                  <tbody>
                    @for (r of respostas(); track r.id) {
                      <tr><td><strong>{{ r.titulo }}</strong>@if (!r.ativo) { <span class="selo-status" data-chamado="neutro">Inativa</span> }</td>
                        <td>{{ r.setor_nome || 'Todos' }}</td>
                        <td><div class="botoes-linha"><button type="button" class="acao-secundaria acao-pequena" (click)="editarResposta(r)">Editar</button>
                          <button type="button" class="acao-perigo acao-pequena" (click)="excluirResposta(r)">Excluir</button></div></td></tr>
                    } @empty { <tr><td colspan="3" class="estado-vazio">Nenhuma resposta pronta.</td></tr> }
                  </tbody>
                </table>
              </div>
            }

            @case ('motivos') {
              <p class="dica-formulario">Motivos para escolher ao pôr um chamado em "Pendente". Quem atende ainda pode escrever outro.</p>
              <form class="grade-formulario" (ngSubmit)="salvarMotivo(fm)" #fm="ngForm">
                <div class="ocupa-duas"><label for="pmo-nome">{{ editandoMotivo() ? 'Alterar motivo' : 'Novo motivo' }}</label>
                  <input id="pmo-nome" name="nome" required minlength="3" maxlength="120" placeholder="Ex.: Aguardando peça" [(ngModel)]="motivo.nome" /></div>
                <div class="ocupa-duas"><label class="linha-caixa"><input type="checkbox" name="mot-ativo" [(ngModel)]="motivo.ativo" /> Ativo</label></div>
                <div class="ocupa-duas acoes-formulario">
                  @if (editandoMotivo()) { <button type="button" class="acao-secundaria" (click)="novoMotivo(fm)">Cancelar edição</button> }
                  <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fm.invalid || salvando()">{{ editandoMotivo() ? 'Salvar motivo' : 'Criar motivo' }}</button>
                </div>
              </form>
              <div class="tabela-gestao-envoltorio">
                <table class="tabela-gestao">
                  <thead><tr><th>Motivo</th><th></th></tr></thead>
                  <tbody>
                    @for (m of motivos(); track m.id) {
                      <tr><td><strong>{{ m.nome }}</strong>@if (!m.ativo) { <span class="selo-status" data-chamado="neutro">Inativo</span> }</td>
                        <td><div class="botoes-linha"><button type="button" class="acao-secundaria acao-pequena" (click)="editarMotivo(m)">Editar</button>
                          <button type="button" class="acao-perigo acao-pequena" (click)="excluirMotivo(m)">Excluir</button></div></td></tr>
                    } @empty { <tr><td colspan="2" class="estado-vazio">Nenhum motivo cadastrado.</td></tr> }
                  </tbody>
                </table>
              </div>
            }

            @case ('painel') {
              <p class="dica-formulario">O painel é sempre com login: cada pessoa vê os chamados em que o seu setor é o setor responsável (Chamados › Painel).
                Aqui fica como ele aparece para todos. As cores do prazo (amarelo, laranja e vermelho) mudam na aba Geral.</p>
              @if (painel(); as pc) {
                <form class="grade-formulario" (ngSubmit)="salvarPainel()">
                  <div><label for="pp-linhas">Linhas por página</label>
                    <input id="pp-linhas" name="linhas" type="number" min="0" max="50" [(ngModel)]="pc.linhas_por_pagina" />
                    <small class="ajuda">0 = automático: quantas couberem na tela.</small></div>
                  <div><label for="pp-tamanho">Tamanho do texto</label>
                    <app-campo-escolha idCampo="pp-tamanho" name="tamanho" [opcoes]="opTamanhos" [(ngModel)]="pc.tamanho" /></div>
                  <div><label for="pp-segundos">Segundos em cada página</label>
                    <input id="pp-segundos" name="segundos" type="number" min="5" max="300" [(ngModel)]="pc.segundos_pagina" /></div>
                  <fieldset class="ocupa-duas grupo-caixas"><legend>Colunas mostradas</legend>
                    <div class="linha-caixas">
                      @for (c of colunasPainel; track c[0]) {
                        <label><input type="checkbox" [name]="'col-' + c[0]" [disabled]="c[0] === 'titulo'" [checked]="pc.colunas.includes(c[0])"
                          (change)="alternarColuna(c[0])" /> {{ c[1] }}</label>
                      }
                    </div>
                  </fieldset>
                  <div class="ocupa-duas">
                    <label class="linha-caixa"><input type="checkbox" name="cor-linha" [(ngModel)]="pc.cor_linha" /> Cor do prazo na linha inteira (desmarcado: só no selo da coluna Situação)</label>
                    <label class="linha-caixa"><input type="checkbox" name="voz" [(ngModel)]="pc.voz" /> Anunciar por voz os chamados novos ("Novo chamado de …")</label>
                  </div>
                  <div class="ocupa-duas acoes-formulario">
                    <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando()">Salvar</button>
                  </div>
                </form>
              } @else {
                <app-esqueleto tipo="formulario" [linhas]="4" />
              }
            }

            @case ('rh') {
              @if (rh(); as r) {
                <p class="dica-formulario">Na Nomeação (RH &gt; Admissão) e na Exoneração (RH &gt; Cargos &gt; Vagar, motivo Exoneração), cada serviço marcado vira um chamado.
                  Enquanto o destino for o GLPI, nada muda para o RH. Para virar, escolha a fila (o setor que atende), a prioridade e os prazos de cada serviço e troque o destino.</p>
                <form class="grade-formulario" (ngSubmit)="salvarRh()">
                  <div class="ocupa-duas"><label for="prh-destino">Para onde vão os chamados da Nomeação</label>
                    <app-campo-escolha idCampo="prh-destino" name="destino" [opcoes]="opDestinosRh" [(ngModel)]="r.destino" />
                    @if (r.destino === 'na_data') {
                      <small class="dica-formulario">Vira no mesmo dia que os chamados (Geral &gt; Atendimento no SGI a partir de). Hoje o RH envia para
                        <strong>{{ r.destino_atual === 'chamados' ? 'o SGI' : 'o GLPI' }}</strong>.</small>
                    }</div>
                  @for (grupo of gruposRh(r); track grupo.chave) {
                    <h3 class="ocupa-duas titulo-grupo-rh">{{ grupo.titulo }}@if (grupo.nota) { <small>{{ grupo.nota }}</small> }</h3>
                    @for (s of grupo.servicos; track s.servico) {
                      <h4 class="ocupa-duas subtitulo-servico-rh">{{ s.rotulo }}</h4>
                      <div><label [for]="grupo.chave + '-fila-' + s.servico">Fila</label>
                        <app-campo-escolha [idCampo]="grupo.chave + '-fila-' + s.servico" [name]="grupo.chave + '-fila-' + s.servico" [opcoes]="opSetores()" vazio="Sem fila" [(ngModel)]="s.setor_id" /></div>
                      <div><label [for]="grupo.chave + '-prio-' + s.servico">Prioridade</label>
                        <app-campo-escolha [idCampo]="grupo.chave + '-prio-' + s.servico" [name]="grupo.chave + '-prio-' + s.servico" [opcoes]="opPrioridades" [(ngModel)]="s.prioridade" /></div>
                      <div><label [for]="grupo.chave + '-tto-' + s.servico">Prazo de atendimento</label>
                        <app-campo-escolha [idCampo]="grupo.chave + '-tto-' + s.servico" [name]="grupo.chave + '-tto-' + s.servico" [opcoes]="opSlasTto()" vazio="Sem prazo" [(ngModel)]="s.sla_tto_id" /></div>
                      <div><label [for]="grupo.chave + '-ttr-' + s.servico">Prazo de solução</label>
                        <app-campo-escolha [idCampo]="grupo.chave + '-ttr-' + s.servico" [name]="grupo.chave + '-ttr-' + s.servico" [opcoes]="opSlasTtr()" vazio="Sem prazo" [(ngModel)]="s.sla_ttr_id" /></div>
                    }
                  }
                  <div class="ocupa-duas acoes-formulario">
                    <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando()">Salvar</button>
                  </div>
                </form>
              } @else {
                <app-esqueleto tipo="formulario" [linhas]="4" />
              }
            }

            @case ('saude') {
              @if (saude(); as sd) {
                @if (sd.problemas.length) {
                  @for (p of sd.problemas; track p) { <p class="aviso-formulario erro">{{ p }}</p> }
                } @else {
                  <p class="aviso-formulario">Tudo funcionando: as tarefas automáticas estão rodando e os e-mails estão saindo.</p>
                }
                <div class="tabela-gestao-envoltorio">
                  <table class="tabela-gestao">
                    <thead><tr><th>Tarefa automática</th><th>Última rodada</th><th>Situação</th><th>Última com sucesso</th><th>Resultado</th></tr></thead>
                    <tbody>
                      @for (t of sd.tarefas; track t.tarefa) {
                        <tr><td><strong>{{ t.tarefa === 'minuto' ? 'Prazos e recorrentes (a cada minuto)' : 'Vigia (a cada 5 minutos)' }}</strong></td>
                          <td>{{ t.ultima_em ? dataHora(t.ultima_em) : 'Nunca rodou' }}</td>
                          <td><span class="selo-status" [attr.data-chamado]="t.ultimo_estado === 'ok' ? 'sucesso' : t.ultimo_estado === 'erro' ? 'perigo' : 'neutro'">
                            {{ t.ultimo_estado === 'ok' ? 'Funcionando' : t.ultimo_estado === 'erro' ? 'Falhou' : t.ultimo_estado === 'rodando' ? 'Rodando' : 'Sem registro' }}</span></td>
                          <td>{{ t.ultima_ok_em ? dataHora(t.ultima_ok_em) : '—' }}</td>
                          <td><small>{{ t.ultimo_erro || t.ultimo_resumo }}</small></td></tr>
                      }
                      <tr><td><strong>E-mails</strong></td><td>{{ sd.email_mais_antigo ? 'Mais antigo na fila: ' + dataHora(sd.email_mais_antigo) : 'Fila vazia' }}</td>
                        <td><span class="selo-status" [attr.data-chamado]="sd.email_parados || sd.email_falhas_24h ? 'perigo' : 'sucesso'">
                          {{ sd.email_parados || sd.email_falhas_24h ? 'Com problema' : 'Funcionando' }}</span></td>
                        <td>{{ sd.email_parados }} parado(s) · {{ sd.email_falhas_24h }} falha(s) em 24h</td><td><small>{{ sd.ultimo_erro_email }}</small></td></tr>
                    </tbody>
                  </table>
                </div>
                <div class="acoes-formulario"><button type="button" class="acao-secundaria" (click)="carregarSaude()">Atualizar</button></div>
              }
            }

            @case ('slas') {
              @if (!expedientes().length) { <p class="aviso-formulario erro">Cadastre antes um expediente: todo SLA conta só dentro do horário de trabalho.</p> }
              <form class="grade-formulario" (ngSubmit)="salvarSla()" #fs="ngForm">
                <div><label for="ps-nome">Nome</label><input id="ps-nome" name="nome" required maxlength="150" [(ngModel)]="sla.nome" /></div>
                <div><label for="ps-tipo">Tipo</label>
                  <app-campo-escolha idCampo="ps-tipo" name="tipo" [opcoes]="opTiposSla" [(ngModel)]="sla.tipo" /></div>
                <div><label for="ps-tempo">Tempo</label><input id="ps-tempo" name="tempo" type="number" min="1" required [(ngModel)]="sla.tempo" /></div>
                <div><label for="ps-unidade">Unidade</label>
                  <app-campo-escolha idCampo="ps-unidade" name="unidade" [opcoes]="opUnidadesSla" [(ngModel)]="sla.unidade" /></div>
                <div class="ocupa-duas"><label for="ps-exp">Expediente</label>
                  <app-campo-escolha idCampo="ps-exp" name="expediente" required [opcoes]="opExpedientes()" [(ngModel)]="sla.expediente_id" />
                  <small class="dica-formulario">O prazo só anda dentro do expediente e para nos feriados do RH.</small></div>
                <div class="ocupa-duas"><label class="linha-caixa"><input type="checkbox" name="ativo" [(ngModel)]="sla.ativo" /> Ativo</label></div>
                <div class="ocupa-duas acoes-formulario">
                  @if (editandoSla()) { <button type="button" class="acao-secundaria" (click)="novoSla()">Cancelar edição</button> }
                  <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fs.invalid || salvando()">{{ editandoSla() ? 'Salvar SLA' : 'Criar SLA' }}</button>
                </div>
              </form>
              <div class="tabela-gestao-envoltorio">
                <table class="tabela-gestao">
                  <thead><tr><th>SLA</th><th>Tipo</th><th>Prazo</th><th>Expediente</th><th></th></tr></thead>
                  <tbody>
                    @for (s of slas(); track s.id) {
                      <tr><td><strong>{{ s.nome }}</strong>@if (!s.ativo) { <span class="selo-status" data-chamado="neutro">Inativo</span> }</td>
                        <td>{{ s.tipo === 'tto' ? 'Atendimento' : 'Solução' }}</td><td>{{ s.tempo }} {{ unidade(s) }}</td><td>{{ s.expediente_nome }}</td>
                        <td><div class="botoes-linha"><button type="button" class="acao-secundaria acao-pequena" (click)="editarSla(s)">Editar</button>
                          <button type="button" class="acao-perigo acao-pequena" (click)="excluirSla(s)">Excluir</button></div></td></tr>
                    } @empty { <tr><td colspan="5" class="estado-vazio">Nenhum SLA cadastrado.</td></tr> }
                  </tbody>
                </table>
              </div>
            }

            @case ('expedientes') {
              <form (ngSubmit)="salvarExpediente()" #fe="ngForm">
                <div class="grade-formulario">
                  <div class="ocupa-duas"><label for="pe-nome">Nome</label><input id="pe-nome" name="nome" required maxlength="120" [(ngModel)]="expediente.nome" /></div>
                </div>
                @for (f of expediente.faixas; track $index) {
                  <div class="faixa-expediente">
                    <div><label [for]="'pe-dia-' + $index">Dia</label>
                      <app-campo-escolha [idCampo]="'pe-dia-' + $index" [name]="'dia' + $index" [opcoes]="opDias" [(ngModel)]="f.dia_semana" /></div>
                    <div><label [for]="'pe-ini-' + $index">Início</label><input [id]="'pe-ini-' + $index" type="time" [name]="'ini' + $index" required [(ngModel)]="f.inicio" /></div>
                    <div><label [for]="'pe-fim-' + $index">Fim</label><input [id]="'pe-fim-' + $index" type="time" [name]="'fim' + $index" required [(ngModel)]="f.fim" /></div>
                    <button type="button" class="acao-perigo acao-pequena" (click)="removerFaixa($index)" [disabled]="expediente.faixas.length === 1">Remover</button>
                  </div>
                }
                <label class="linha-caixa"><input type="checkbox" name="ativo" [(ngModel)]="expediente.ativo" /> Ativo</label>
                <div class="acoes-formulario">
                  <button type="button" class="acao-secundaria" (click)="adicionarFaixa()">Adicionar faixa</button>
                  @if (editandoExpediente()) { <button type="button" class="acao-secundaria" (click)="novoExpediente()">Cancelar edição</button> }
                  <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fe.invalid || salvando()">{{ editandoExpediente() ? 'Salvar expediente' : 'Criar expediente' }}</button>
                </div>
              </form>
              <div class="tabela-gestao-envoltorio">
                <table class="tabela-gestao">
                  <thead><tr><th>Expediente</th><th>Horários</th><th></th></tr></thead>
                  <tbody>
                    @for (e of expedientes(); track e.id) {
                      <tr><td><strong>{{ e.nome }}</strong>@if (!e.ativo) { <span class="selo-status" data-chamado="neutro">Inativo</span> }</td>
                        <td>{{ resumoFaixas(e.faixas) }}</td>
                        <td><div class="botoes-linha"><button type="button" class="acao-secundaria acao-pequena" (click)="editarExpediente(e)">Editar</button>
                          <button type="button" class="acao-perigo acao-pequena" (click)="excluirExpediente(e)">Excluir</button></div></td></tr>
                    } @empty { <tr><td colspan="3" class="estado-vazio">Nenhum expediente cadastrado.</td></tr> }
                  </tbody>
                </table>
              </div>
            }
          }
        }
      </section>
    </div>
  `,
})
export class ParametrosChamadosComponent implements OnInit {
  private readonly api = inject(ChamadosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);

  protected readonly aba = signal<Aba>('geral');
  protected readonly carregando = signal(true);
  protected readonly salvando = signal(false);
  protected readonly categorias = signal<Categoria[]>([]);
  protected readonly slas = signal<Sla[]>([]);
  protected readonly expedientes = signal<Expediente[]>([]);
  protected readonly setores = signal<SetorResumo[]>([]);
  protected readonly semSetor = computed(() => this.categorias().filter((c) => c.ativa && !c.setor_efetivo_id));
  protected readonly editandoCategoria = signal<string | null>(null);
  protected readonly editandoSla = signal<string | null>(null);
  protected readonly editandoExpediente = signal<string | null>(null);
  protected readonly prioridades = Object.entries(ROTULOS_PRIORIDADE);
  protected readonly dias = DIAS_SEMANA;

  // Opções dos campos de escolha com busca (app-campo-escolha): calculadas uma vez e reaproveitadas
  protected readonly opCategorias = computed<OpcaoEscolha[]>(() => this.categorias().map((c) => ({ valor: c.id, rotulo: c.caminho })));
  protected readonly opCategoriasAtivas = computed<OpcaoEscolha[]>(() => this.categorias().filter((c) => c.ativa).map((c) => ({ valor: c.id, rotulo: c.caminho })));
  protected readonly opSetores = computed<OpcaoEscolha[]>(() => this.setores().map((s) => ({ valor: s.id, rotulo: s.caminho || s.nome })));
  protected readonly opSlasTto = computed<OpcaoEscolha[]>(() => this.slasDo('tto').map((s) => ({ valor: s.id, rotulo: `${s.nome} (${s.tempo} ${this.unidade(s)})` })));
  protected readonly opSlasTtr = computed<OpcaoEscolha[]>(() => this.slasDo('ttr').map((s) => ({ valor: s.id, rotulo: `${s.nome} (${s.tempo} ${this.unidade(s)})` })));
  protected readonly opItil = computed<OpcaoEscolha[]>(() => this.categoriasItil().map((i) => ({ valor: i.id, rotulo: i.caminho })));
  protected readonly opItilAtivas = computed<OpcaoEscolha[]>(() => this.categoriasItil().filter((i) => i.ativa).map((i) => ({ valor: i.id, rotulo: i.caminho })));
  protected readonly opCampos = computed<OpcaoEscolha[]>(() => this.campos().map((f) => ({ valor: f.id, rotulo: f.rotulo })));
  protected readonly opExpedientes = computed<OpcaoEscolha[]>(() => this.expedientes().map((e) => ({ valor: e.id, rotulo: e.nome })));
  protected readonly opPrioridades: OpcaoEscolha[] = (Object.entries(ROTULOS_PRIORIDADE) as [string, string][]).map(([valor, rotulo]) => ({ valor, rotulo }));
  protected readonly opTiposCampo: OpcaoEscolha[] = (Object.entries(ROTULOS_TIPO_CAMPO) as [string, string][]).map(([valor, rotulo]) => ({ valor, rotulo }));
  protected readonly opCores: OpcaoEscolha[] = (Object.entries(ROTULOS_COR) as [string, string][]).map(([valor, rotulo]) => ({ valor, rotulo }));
  protected readonly opDias: OpcaoEscolha[] = DIAS_SEMANA.map((rotulo, valor) => ({ valor, rotulo }));
  protected readonly opPontoFacultativo: OpcaoEscolha[] = [{ valor: false, rotulo: 'Não conta como dia útil (o prazo para)' }, { valor: true, rotulo: 'Conta como dia útil (o prazo anda)' }];
  protected readonly opPeriodicidade: OpcaoEscolha[] = [{ valor: 'dia', rotulo: 'Dia(s)' }, { valor: 'semana', rotulo: 'Semana(s)' }, { valor: 'mes', rotulo: 'Mês(es)' }];
  protected readonly opTamanhos: OpcaoEscolha[] = [{ valor: 'compacto', rotulo: 'Compacto (cabem mais chamados)' }, { valor: 'normal', rotulo: 'Normal' },
    { valor: 'grande', rotulo: 'Grande (para ler de longe)' }];
  protected readonly opDestinosRh: OpcaoEscolha[] = [{ valor: 'glpi', rotulo: 'GLPI (formulário "CGP - Nomeações", como hoje)' },
    { valor: 'na_data', rotulo: 'GLPI até a data "a partir de", depois o SGI (vira sozinho)' },
    { valor: 'chamados', rotulo: 'Chamados do SGI (um chamado por serviço)' }];
  protected readonly opTiposSla: OpcaoEscolha[] = [{ valor: 'tto', rotulo: 'Atendimento (até a primeira ação)' }, { valor: 'ttr', rotulo: 'Solução' }];
  protected readonly opUnidadesSla: OpcaoEscolha[] = [{ valor: 'minuto', rotulo: 'Minutos úteis' }, { valor: 'hora', rotulo: 'Horas úteis' }, { valor: 'dia', rotulo: 'Dias úteis' }];

  // "Quem pode escolher este assunto": qualquer pessoa, só quem atende (trabalho interno) ou só os setores escolhidos
  protected quemEscolhe: 'todos' | 'equipe' | 'setores' = 'todos';
  protected readonly opQuemEscolhe: OpcaoEscolha[] = [{ valor: 'todos', rotulo: 'Qualquer pessoa' },
    { valor: 'equipe', rotulo: 'Só quem atende (trabalho interno)' }, { valor: 'setores', rotulo: 'Só estes setores…' }];
  /** Setores que ainda não estão na lista (para o campo "Acrescentar setor"). */
  protected opSetoresNaoPermitidos(): OpcaoEscolha[] {
    return this.opSetores().filter((o) => !this.categoria.setores_permitidos.includes(o.valor as number));
  }

  protected dicaQuemEscolhe(): string {
    return { todos: 'Aparece para todo mundo na abertura de chamado.', equipe: 'Só quem atende chamados vê e usa (ex.: trabalho interno da equipe).',
      setores: 'Só os membros dos setores escolhidos (e dos setores abaixo deles) veem e abrem. Ex.: "CGP > Nomeação" só para a CGP.' }[this.quemEscolhe];
  }

  protected trocarQuemEscolhe(valor: 'todos' | 'equipe' | 'setores'): void {
    this.quemEscolhe = valor;
    this.categoria.visivel_solicitante = valor !== 'equipe';
    if (valor !== 'setores') this.categoria.setores_permitidos = [];
  }

  protected acrescentarSetorPermitido(id: number | null): void {
    if (id !== null && !this.categoria.setores_permitidos.includes(id)) this.categoria.setores_permitidos = [...this.categoria.setores_permitidos, id];
  }

  protected tirarSetorPermitido(id: number): void {
    this.categoria.setores_permitidos = this.categoria.setores_permitidos.filter((x) => x !== id);
  }

  protected nomeSetor(id: number): string {
    return this.opSetores().find((o) => o.valor === id)?.rotulo ?? `Setor ${id}`;
  }

  protected opStatus(): OpcaoEscolha[] {
    return this.statusEdicao.map((x) => ({ valor: x.status_base, rotulo: x.nome }));
  }

  protected categoria: GravacaoCategoria = categoriaVazia();
  // Categorias ITIL (classificação técnica)
  protected readonly categoriasItil = signal<CategoriaItil[]>([]);
  protected readonly editandoItil = signal<string | null>(null);
  protected itil: GravacaoCategoriaItil = { nome: '', pai_id: null, ativa: true, ordem: 0 };
  // Marco 3: Geral, status, sub-status, setores, recorrentes e saúde
  protected readonly abas: [Aba, string][] = [['geral', 'Geral'], ['categorias', 'Categorias'], ['itil', 'Categorias ITIL'], ['status', 'Status'], ['slas', 'SLAs'], ['expedientes', 'Expedientes'],
    ['setores', 'Setores de atendimento'], ['recorrentes', 'Recorrentes'], ['respostas', 'Respostas prontas'], ['motivos', 'Motivos de pendência'], ['painel', 'Painel'], ['rh', 'RH'], ['glpi', 'Migração do GLPI'], ['saude', 'Saúde']];
  // Marco 4: TVs pareadas e chamados do RH
  protected readonly painel = signal<ConfigPainel | null>(null);
  protected readonly colunasPainel: [ColunaPainel, string][] = [['abertura', 'Abertura'], ['titulo', 'Título (sempre)'], ['usuario', 'Quem pediu'],
    ['local', 'Local'], ['espera', 'Tempo de espera'], ['situacao', 'Situação (prazo)'], ['responsavel', 'Responsável pelo atendimento']];
  protected readonly rh = signal<ParametrosRh | null>(null);
  // Marco 6: respostas prontas e motivos de pendência
  protected readonly respostas = signal<RespostaPronta[]>([]);
  protected readonly editandoResposta = signal<string | null>(null);
  protected resposta: GravacaoRespostaPronta = { titulo: '', texto: '', setor_id: null, ativo: true, ordem: 0 };
  /** O texto é editado como texto simples (cada linha vira um parágrafo); o que já era HTML volta sem as marcas. */
  protected respostaTexto = '';
  protected readonly motivos = signal<MotivoPendencia[]>([]);
  protected readonly editandoMotivo = signal<string | null>(null);
  protected motivo: Omit<MotivoPendencia, 'id'> = { nome: '', ativo: true, ordem: 0 };
  protected readonly cores = Object.entries(ROTULOS_COR) as [CorStatus, string][];
  protected gerais: ParametrosGerais | null = null;
  protected statusEdicao: StatusApresentacao[] = [];
  protected readonly listaSubstatus = signal<Substatus[]>([]);
  protected readonly editandoSubstatus = signal<string | null>(null);
  protected sub: Omit<Substatus, 'id'> = { status_base: 'em_atendimento', nome: '', cor: 'info', ordem: 0, ativo: true };
  protected readonly setoresAtendimento = signal<SetorAtendimento[]>([]);
  protected readonly buscaSetor = signal('');
  protected readonly setoresFiltrados = computed(() => {
    const termo = this.buscaSetor().trim().toLowerCase();
    return termo ? this.setoresAtendimento().filter((x) => x.caminho.toLowerCase().includes(termo)) : this.setoresAtendimento();
  });
  protected readonly recorrentes = signal<Recorrente[]>([]);
  protected readonly editandoRecorrente = signal<string | null>(null);
  protected rec: GravacaoRecorrente = recorrenteVazio();
  protected proximaLocal = '';
  protected fimLocal = '';
  protected readonly saude = signal<SaudeChamados | null>(null);
  protected dataHora = dataHora;
  // Campos adicionais da categoria em edição
  protected readonly campos = signal<CampoLeitura[]>([]);
  protected readonly editandoCampo = signal<string | null>(null);
  protected readonly tiposCampo = Object.entries(ROTULOS_TIPO_CAMPO) as [TipoCampo, string][];
  protected campo: GravacaoCampo = campoVazio();
  protected opcoesTexto = '';
  protected condicaoCampoId: string | null = null;
  protected condicaoIgual = '';
  protected sla: Omit<Sla, 'id' | 'expediente_nome'> = { nome: '', tipo: 'ttr', tempo: 4, unidade: 'hora', expediente_id: '', ativo: true };
  protected expediente: { nome: string; ativo: boolean; faixas: FaixaExpediente[] } = this.expedientePadrao();

  ngOnInit(): void {
    const aba = this.rota.snapshot.queryParamMap.get('aba') as Aba | null;
    if (aba && this.abas.some((x) => x[0] === aba)) this.aba.set(aba);
    this.carregar();
    this.carregarMarco3();
  }

  protected trocarAba(aba: Aba): void {
    this.aba.set(aba);
    if (aba === 'saude') this.carregarSaude();
  }

  private carregarMarco3(): void {
    this.api.categoriasItil().subscribe((r) => this.categoriasItil.set(r));
    this.api.geral().subscribe((g) => (this.gerais = g));
    this.api.statusBase().subscribe((x) => (this.statusEdicao = x.map((y) => ({ ...y }))));
    this.api.substatus().subscribe((x) => this.listaSubstatus.set(x));
    this.api.setoresAtendimento().subscribe((x) => this.setoresAtendimento.set(x));
    this.api.recorrentes().subscribe((x) => this.recorrentes.set(x));
    this.carregarSaude();
    this.api.configPainel().subscribe((x) => this.painel.set(x));
    this.api.parametrosRh().subscribe((x) => this.rh.set(x));
    this.api.parametrosRespostas().subscribe((x) => this.respostas.set(x));
    this.api.parametrosMotivos().subscribe((x) => this.motivos.set(x));
  }

  protected novaResposta(form?: NgForm): void {
    this.editandoResposta.set(null);
    this.resposta = { titulo: '', texto: '', setor_id: null, ativo: true, ordem: 0 };
    this.respostaTexto = '';
    form?.resetForm({ titulo: '', setor: null, texto: '', 'resp-ativo': true });
  }

  protected editarResposta(r: RespostaPronta): void {
    this.editandoResposta.set(r.id);
    this.resposta = { titulo: r.titulo, texto: r.texto, setor_id: r.setor_id, ativo: r.ativo, ordem: r.ordem };
    const div = document.createElement('div');
    div.innerHTML = r.texto.replace(/<\/p>/g, '\n');
    this.respostaTexto = (div.textContent ?? '').trim();
  }

  protected salvarResposta(form: NgForm): void {
    // Texto simples → parágrafos (o servidor saneia de novo)
    const escapar = (t: string) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const html = this.respostaTexto.split(/\n+/).filter((l) => l.trim()).map((l) => `<p>${escapar(l.trim())}</p>`).join('');
    this.salvar(this.api.salvarResposta(this.editandoResposta(), { ...this.resposta, texto: html }), () => {
      this.novaResposta(form);
      this.api.parametrosRespostas().subscribe((x) => this.respostas.set(x));
    });
  }

  protected async excluirResposta(r: RespostaPronta): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir a resposta pronta "${r.titulo}"?`, mensagem: 'As respostas já enviadas com ela continuam.',
      rotuloConfirmar: 'Excluir resposta', segundos: 3 });
    if (ok) this.salvar(this.api.excluirResposta(r.id), () => this.api.parametrosRespostas().subscribe((x) => this.respostas.set(x)));
  }

  protected novoMotivo(form?: NgForm): void {
    this.editandoMotivo.set(null);
    this.motivo = { nome: '', ativo: true, ordem: 0 };
    form?.resetForm({ nome: '', 'mot-ativo': true });
  }

  protected editarMotivo(m: MotivoPendencia): void {
    this.editandoMotivo.set(m.id);
    this.motivo = { nome: m.nome, ativo: m.ativo, ordem: m.ordem };
  }

  protected salvarMotivo(form: NgForm): void {
    this.salvar(this.api.salvarMotivo(this.editandoMotivo(), this.motivo), () => {
      this.novoMotivo(form);
      this.api.parametrosMotivos().subscribe((x) => this.motivos.set(x));
    });
  }

  protected async excluirMotivo(m: MotivoPendencia): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir o motivo "${m.nome}"?`, mensagem: 'Os chamados que já ficaram pendentes por ele guardam o texto.',
      rotuloConfirmar: 'Excluir motivo', segundos: 3 });
    if (ok) this.salvar(this.api.excluirMotivo(m.id), () => this.api.parametrosMotivos().subscribe((x) => this.motivos.set(x)));
  }

  protected alternarColuna(c: ColunaPainel): void {
    const pc = this.painel();
    if (!pc || c === 'titulo') return;
    pc.colunas = pc.colunas.includes(c) ? pc.colunas.filter((x) => x !== c) : [...pc.colunas, c];
  }

  protected salvarPainel(): void {
    const pc = this.painel();
    if (pc) this.salvar(this.api.salvarConfigPainel(pc), () => this.api.configPainel().subscribe((x) => this.painel.set(x)));
  }

  /** Os dois fluxos do RH na mesma ordem da tela: Nomeação e, depois, a Exoneração (o inverso de cada serviço). */
  protected gruposRh(r: ParametrosRh): { chave: string; titulo: string; nota: string; servicos: ServicoRh[] }[] {
    return [
      { chave: 'prh', titulo: 'Nomeação', nota: '', servicos: r.servicos },
      { chave: 'prhx', titulo: 'Exoneração', nota: '(o inverso de cada serviço da nomeação)', servicos: r.servicos_exoneracao },
    ];
  }

  protected salvarRh(): void {
    const r = this.rh();
    if (!r) return;
    // Cada serviço vai como {fila, prioridade, prazos}; o backend recusa (409 servico_sem_fila) se o destino for o SGI e faltar fila.
    const config = (lista: ServicoRh[]) => Object.fromEntries(lista.map((s) => [s.servico, { setor_id: s.setor_id, prioridade: s.prioridade, sla_tto_id: s.sla_tto_id, sla_ttr_id: s.sla_ttr_id }]));
    this.salvando.set(true);
    this.api.salvarParametrosRh(r.destino, config(r.servicos), config(r.servicos_exoneracao)).subscribe({
      next: (x) => { this.salvando.set(false); this.rh.set(x); this.dialogos.avisar('RH salvo', x.destino === 'chamados' ? 'A Nomeação e a Exoneração passam a abrir os chamados aqui.'
        : x.destino === 'na_data' ? (x.destino_atual === 'chamados' ? 'A data já chegou: a Nomeação e a Exoneração abrem os chamados aqui.' : 'A Nomeação e a Exoneração vão para o GLPI até a data "a partir de" e, nesse dia, passam a abrir aqui.')
        : 'A Nomeação e a Exoneração continuam indo para o GLPI.'); },
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível salvar o RH'); },
    });
  }

  protected carregarSaude(): void {
    this.api.saude().subscribe({ next: (x) => this.saude.set(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível ler a saúde do módulo') });
  }

  protected salvarGeral(): void {
    if (this.gerais) this.salvar(this.api.salvarGeral(this.gerais), () => this.api.geral().subscribe((g) => (this.gerais = g)));
  }

  protected nomeStatus(base: string): string {
    return this.statusEdicao.find((x) => x.status_base === base)?.nome ?? base;
  }

  protected salvarStatus(base: string, nome: string, cor: string): void {
    this.salvar(this.api.salvarStatus(base, nome, cor), () => this.api.statusBase().subscribe((x) => (this.statusEdicao = x.map((y) => ({ ...y })))));
  }

  protected novoSubstatus(): void {
    this.sub = { status_base: 'em_atendimento', nome: '', cor: 'info', ordem: 0, ativo: true };
    this.editandoSubstatus.set(null);
  }

  protected editarSubstatus(x: Substatus): void {
    this.sub = { status_base: x.status_base, nome: x.nome, cor: x.cor, ordem: x.ordem, ativo: x.ativo };
    this.editandoSubstatus.set(x.id);
  }

  protected salvarSubstatus(): void {
    this.salvar(this.api.salvarSubstatus(this.editandoSubstatus(), this.sub), () => {
      this.novoSubstatus();
      this.api.substatus().subscribe((x) => this.listaSubstatus.set(x));
    });
  }

  protected async excluirSubstatus(x: Substatus): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir o sub-status "${x.nome}"?`, mensagem: 'Os chamados que estão nele ficam só com o status principal.',
      rotuloConfirmar: 'Excluir sub-status', segundos: 3 });
    if (ok) this.salvar(this.api.excluirSubstatus(x.id), () => this.api.substatus().subscribe((y) => this.listaSubstatus.set(y)));
  }

  protected salvarSetor(x: SetorAtendimento, veTodos: boolean): void {
    this.salvar(this.api.salvarSetorAtendimento(x.setor_id, veTodos), () => this.setoresAtendimento.update((l) => l.map((y) => (y.setor_id === x.setor_id ? { ...y, ve_todos: veTodos } : y))));
  }

  protected rotuloPeriodo(r: Recorrente): string {
    return { dia: 'dia(s)', semana: 'semana(s)', mes: 'mês(es)' }[r.periodicidade_unidade];
  }

  protected novoRecorrente(): void {
    this.rec = recorrenteVazio();
    this.proximaLocal = '';
    this.fimLocal = '';
    this.editandoRecorrente.set(null);
  }

  protected editarRecorrente(r: Recorrente): void {
    this.rec = { nome: r.nome, categoria_id: r.categoria_id, titulo: r.titulo, descricao: r.descricao, periodicidade_quantidade: r.periodicidade_quantidade,
      periodicidade_unidade: r.periodicidade_unidade, antecedencia_min: r.antecedencia_min, so_dias_uteis: r.so_dias_uteis, proxima_em: r.proxima_em,
      fim_em: r.fim_em, ativo: r.ativo, solicitante_id: r.solicitante_id };
    this.proximaLocal = paraCampoLocal(r.proxima_em);
    this.fimLocal = r.fim_em ? paraCampoLocal(r.fim_em) : '';
    this.editandoRecorrente.set(r.id);
  }

  protected salvarRecorrente(): void {
    const dados: GravacaoRecorrente = { ...this.rec, proxima_em: deCampoLocal(this.proximaLocal), fim_em: this.fimLocal ? deCampoLocal(this.fimLocal) : null };
    this.salvar(this.api.salvarRecorrente(this.editandoRecorrente(), dados), () => {
      this.novoRecorrente();
      this.api.recorrentes().subscribe((x) => this.recorrentes.set(x));
    });
  }

  protected async excluirRecorrente(r: Recorrente): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir o recorrente "${r.nome}"?`, mensagem: 'Os chamados que ele já abriu continuam.',
      rotuloConfirmar: 'Excluir recorrente', segundos: 3 });
    if (ok) this.salvar(this.api.excluirRecorrente(r.id), () => this.api.recorrentes().subscribe((x) => this.recorrentes.set(x)));
  }

  private carregar(): void {
    let pendentes = 4;
    const pronto = () => (pendentes -= 1) === 0 && this.carregando.set(false);
    const falha = (e: unknown) => {
      pronto();
      this.dialogos.mostrarErro(e, 'Não foi possível carregar os parâmetros');
    };
    this.api.categorias().subscribe({ next: (r) => { this.categorias.set(r); pronto(); }, error: falha });
    this.api.slas().subscribe({ next: (r) => { this.slas.set(r); pronto(); }, error: falha });
    this.api.expedientes().subscribe({ next: (r) => { this.expedientes.set(r); pronto(); }, error: falha });
    this.api.setores().subscribe({ next: (r) => { this.setores.set(r); pronto(); }, error: falha });
  }

  protected slasDo(tipo: 'tto' | 'ttr'): Sla[] {
    return this.slas().filter((s) => s.tipo === tipo && s.ativo);
  }

  protected unidade(s: Sla): string {
    return ROTULOS_UNIDADE[s.unidade];
  }

  protected resumoFaixas(faixas: FaixaExpediente[]): string {
    return faixas.map((f) => `${this.dias[f.dia_semana].slice(0, 3)} ${f.inicio.slice(0, 5)}–${f.fim.slice(0, 5)}`).join(' · ');
  }

  // --- Categorias ---

  protected novaCategoria(): void {
    this.categoria = categoriaVazia();
    this.quemEscolhe = 'todos';
    this.editandoCategoria.set(null);
    this.campos.set([]);
    this.novoCampo();
  }

  protected rotuloTipo(tipo: TipoCampo): string {
    return ROTULOS_TIPO_CAMPO[tipo];
  }

  protected rotuloCampo(id: string): string {
    return this.campos().find((f) => f.id === id)?.rotulo ?? 'outro campo';
  }

  private carregarCampos(categoriaId: string): void {
    this.api.camposDaCategoria(categoriaId).subscribe((r) => this.campos.set(r));
  }

  protected novoCampo(): void {
    this.campo = campoVazio();
    this.opcoesTexto = '';
    this.condicaoCampoId = null;
    this.condicaoIgual = '';
    this.editandoCampo.set(null);
  }

  protected editarCampo(f: CampoLeitura): void {
    this.campo = { rotulo: f.rotulo, tipo: f.tipo, obrigatorio: f.obrigatorio, dado_pessoal: f.dado_pessoal, ajuda: f.ajuda, opcoes: f.opcoes, condicao: f.condicao, ordem: f.ordem, ativo: f.ativo };
    this.opcoesTexto = (f.opcoes ?? []).join('\n');
    this.condicaoCampoId = f.condicao?.campo_id ?? null;
    this.condicaoIgual = f.condicao?.igual ?? '';
    this.editandoCampo.set(f.id);
  }

  protected salvarCampo(): void {
    const categoriaId = this.editandoCategoria();
    if (!categoriaId) return;
    const dados: GravacaoCampo = {
      ...this.campo,
      opcoes: this.campo.tipo === 'lista' ? this.opcoesTexto.split('\n').map((o) => o.trim()).filter(Boolean) : null,
      condicao: this.condicaoCampoId ? { campo_id: this.condicaoCampoId, igual: this.condicaoIgual.trim() } : null,
      ordem: this.editandoCampo() ? this.campo.ordem : this.campos().length,
    };
    this.salvar(this.api.salvarCampo(categoriaId, this.editandoCampo(), dados), () => {
      this.novoCampo();
      this.carregarCampos(categoriaId);
    });
  }

  protected async excluirCampo(f: CampoLeitura): Promise<void> {
    const categoriaId = this.editandoCategoria();
    if (!categoriaId) return;
    const ok = await this.dialogos.confirmar({
      titulo: `Excluir o campo "${f.rotulo}"?`, mensagem: 'Só é possível excluir um campo que nenhum chamado respondeu. Não há como desfazer.',
      rotuloConfirmar: 'Excluir campo', segundos: 3,
    });
    if (!ok) return;
    this.api.excluirCampo(categoriaId, f.id).subscribe({
      next: () => {
        if (this.editandoCampo() === f.id) this.novoCampo();
        this.carregarCampos(categoriaId);
      },
      error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível excluir o campo'),
    });
  }

  protected editarCategoria(c: Categoria): void {
    // Só os campos que vão de volta para a API (o resto é calculado)
    this.categoria = {
      nome: c.nome, pai_id: c.pai_id, ativa: c.ativa, visivel_solicitante: c.visivel_solicitante, permite_incidente: c.permite_incidente,
      permite_requisicao: c.permite_requisicao, setor_id: c.setor_id, responsavel_id: c.responsavel_id, sla_tto_id: c.sla_tto_id, sla_ttr_id: c.sla_ttr_id,
      prioridade_padrao: c.prioridade_padrao, perguntar_impedindo: c.perguntar_impedindo, sigilosa: c.sigilosa, ordem: c.ordem, categoria_itil_id: c.categoria_itil_id,
      setores_permitidos: [...(c.setores_permitidos ?? [])],
    };
    this.quemEscolhe = c.setores_permitidos?.length ? 'setores' : c.visivel_solicitante ? 'todos' : 'equipe';
    this.editandoCategoria.set(c.id);
    this.novoCampo();
    this.carregarCampos(c.id);
  }

  protected async excluirCategoria(c: Categoria): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Excluir a categoria "${c.nome}"?`, mensagem: 'Só é possível excluir uma categoria sem subcategorias e que nunca teve chamado. Não há como desfazer.',
      rotuloConfirmar: 'Excluir categoria', segundos: 3,
    });
    if (!ok) return;
    this.api.excluirCategoria(c.id).subscribe({
      next: () => {
        if (this.editandoCategoria() === c.id) this.novaCategoria();
        this.api.categorias().subscribe((r) => this.categorias.set(r));
      },
      error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível excluir a categoria'),
    });
  }

  // --- Categorias ITIL ---

  protected novaItil(): void {
    this.itil = { nome: '', pai_id: null, ativa: true, ordem: 0 };
    this.editandoItil.set(null);
  }

  protected editarItil(i: CategoriaItil): void {
    this.itil = { nome: i.nome, pai_id: i.pai_id, ativa: i.ativa, ordem: i.ordem };
    this.editandoItil.set(i.id);
  }

  protected salvarItil(): void {
    this.salvar(this.api.salvarCategoriaItil(this.editandoItil(), this.itil), () => {
      this.novaItil();
      this.api.categoriasItil().subscribe((r) => this.categoriasItil.set(r));
    });
  }

  protected async excluirItil(i: CategoriaItil): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Excluir a categoria ITIL "${i.nome}"?`, mensagem: 'Só é possível excluir sem subcategorias e sem chamados classificados nela (senão, desative). Não há como desfazer.',
      rotuloConfirmar: 'Excluir categoria ITIL', segundos: 3,
    });
    if (!ok) return;
    this.api.excluirCategoriaItil(i.id).subscribe({
      next: () => {
        if (this.editandoItil() === i.id) this.novaItil();
        this.api.categoriasItil().subscribe((r) => this.categoriasItil.set(r));
      },
      error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível excluir a categoria ITIL'),
    });
  }

  protected salvarCategoria(): void {
    if (this.quemEscolhe === 'setores' && !this.categoria.setores_permitidos.length) {
      this.dialogos.avisar('Falta o setor', 'Em "Só estes setores", acrescente ao menos um setor (ou escolha "Qualquer pessoa").');
      return;
    }
    this.salvar(this.api.salvarCategoria(this.editandoCategoria(), this.categoria), () => {
      this.novaCategoria();
      this.api.categorias().subscribe((r) => this.categorias.set(r));
    });
  }

  // --- SLAs ---

  protected novoSla(): void {
    this.sla = { nome: '', tipo: 'ttr', tempo: 4, unidade: 'hora', expediente_id: this.expedientes()[0]?.id ?? '', ativo: true };
    this.editandoSla.set(null);
  }

  protected editarSla(s: Sla): void {
    this.sla = { nome: s.nome, tipo: s.tipo, tempo: s.tempo, unidade: s.unidade, expediente_id: s.expediente_id, ativo: s.ativo };
    this.editandoSla.set(s.id);
  }

  protected async excluirSla(s: Sla): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Excluir o SLA "${s.nome}"?`, mensagem: 'Só é possível excluir um SLA que nenhuma categoria nem nenhum chamado usa. Não há como desfazer.',
      rotuloConfirmar: 'Excluir SLA', segundos: 3,
    });
    if (!ok) return;
    this.api.excluirSla(s.id).subscribe({
      next: () => {
        if (this.editandoSla() === s.id) this.novoSla();
        this.api.slas().subscribe((r) => this.slas.set(r));
      },
      error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível excluir o SLA'),
    });
  }

  protected salvarSla(): void {
    this.salvar(this.api.salvarSla(this.editandoSla(), this.sla), () => {
      this.novoSla();
      this.api.slas().subscribe((r) => this.slas.set(r));
    });
  }

  // --- Expedientes ---

  private expedientePadrao(): { nome: string; ativo: boolean; faixas: FaixaExpediente[] } {
    return { nome: '', ativo: true, faixas: [0, 1, 2, 3, 4].map((d) => ({ dia_semana: d, inicio: '08:00', fim: '18:00' })) };
  }

  protected novoExpediente(): void {
    this.expediente = this.expedientePadrao();
    this.editandoExpediente.set(null);
  }

  protected editarExpediente(e: Expediente): void {
    this.expediente = { nome: e.nome, ativo: e.ativo, faixas: e.faixas.map((f) => ({ dia_semana: f.dia_semana, inicio: f.inicio.slice(0, 5), fim: f.fim.slice(0, 5) })) };
    this.editandoExpediente.set(e.id);
  }

  protected adicionarFaixa(): void {
    this.expediente.faixas = [...this.expediente.faixas, { dia_semana: 0, inicio: '08:00', fim: '18:00' }];
  }

  protected removerFaixa(indice: number): void {
    this.expediente.faixas = this.expediente.faixas.filter((_, i) => i !== indice);
  }

  protected async excluirExpediente(e: Expediente): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Excluir o expediente "${e.nome}"?`, mensagem: 'Só é possível excluir um expediente que nenhum SLA usa. Não há como desfazer.',
      rotuloConfirmar: 'Excluir expediente', segundos: 3,
    });
    if (!ok) return;
    this.api.excluirExpediente(e.id).subscribe({
      next: () => {
        if (this.editandoExpediente() === e.id) this.novoExpediente();
        this.api.expedientes().subscribe((r) => this.expedientes.set(r));
      },
      error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível excluir o expediente'),
    });
  }

  protected salvarExpediente(): void {
    this.salvar(this.api.salvarExpediente(this.editandoExpediente(), this.expediente), () => {
      this.novoExpediente();
      this.api.expedientes().subscribe((r) => this.expedientes.set(r));
    });
  }

  private salvar<T>(pedido: Observable<T>, depois: () => void): void {
    this.salvando.set(true);
    pedido.subscribe({
      next: () => {
        this.salvando.set(false);
        depois();
      },
      error: (e) => {
        this.salvando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível salvar');
      },
    });
  }
}
