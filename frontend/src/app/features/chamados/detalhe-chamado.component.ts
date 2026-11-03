// Criado por José Eduardo Santana Martins
// Este arquivo serve para mostrar um chamado (descrição, linha do tempo e dados ao lado) e para responder, assumir e resolver.

import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { debounceTime, filter, map, Observable, of, tap } from 'rxjs';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { EditorRicoComponent } from '../contratacoes/editor-rico.component';
import { CabecalhoChamadosComponent } from './cabecalho-chamados.component';
import { ChamadosApiService } from './chamados-api.service';
import { ChamadosTempoRealService } from './chamados-tempo-real.service';
import {
  AlteracaoChamado, AnexoChamado, CategoriaCatalogo, CategoriaItilResumo, ChamadoDetalhe, COR_STATUS, dataHora, ItemLinhaTempo, nivelPrazo, PessoaResumo, PrazoSla, Prioridade,
  ROTULOS_PRIORIDADE, ROTULOS_STATUS, rotuloStatusSolicitante, SetorResumo, Substatus, tamanhoLegivel, textoPrazo, MotivoPendencia, NOTAS_SATISFACAO,
  RespostaPronta,
} from './chamados.models';

const FORMATOS = '.pdf,.docx,.xlsx,.pptx,.odt,.ods,.odp,.doc,.xls,.ppt,.png,.jpg,.jpeg,.txt,.csv';
// Ícones da linha do tempo (balão de conversa, cadeado, engrenagem e visto)
const ICONES: Record<string, string> = {
  comentario: 'M4 4h16v11H8l-4 4z',
  privado: 'M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z',
  editada: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v3M12 19v3M2 12h3M19 12h3',
  validada: 'M5 12l4 4 10-10',
};

/** Pessoa da API dos Chamados no formato do seletor de usuários. */
function paraOpcao(p: PessoaResumo): OpcaoUsuario {
  return { id: p.id, login: p.login ?? '', nome_completo: p.nome, cargo: p.cargo ?? '', ativo: true };
}

@Component({
  selector: 'app-detalhe-chamado',
  imports: [FormsModule, RouterLink, CabecalhoChamadosComponent, EditorRicoComponent, EsqueletoComponent, SeletorUsuariosComponent],
  template: `
    <div class="modulo-chamados">
      <app-cabecalho-chamados [titulo]="chamado()?.titulo || 'Chamado #' + numero"
        [descricao]="chamado() ? 'Chamado #' + numero + ' · ' + chamado()!.categoria_caminho : ''" />
      @if (recemAberto()) {
        <p class="aviso-formulario" role="status">Chamado aberto. {{ chamado()?.setor_nome }} já foi avisado e você acompanha tudo por aqui e pelo sino.</p>
      }
      @if (mudouPorOutro()) {
        <p class="aviso-formulario" role="status">Este chamado foi atualizado enquanto você escrevia.
          <button type="button" class="acao-secundaria acao-pequena" (click)="atualizarAgora()">Ver a versão nova</button></p>
      }
      @if (!chamado()) {
        <app-esqueleto tipo="painel" />
      } @else {
        @let c = chamado()!;
        <div class="detalhe-chamado">
          <div class="coluna-chamado">
            <section class="cartao-chamado" aria-labelledby="titulo-descricao">
              <header><h2 id="titulo-descricao">Descrição</h2><small>Aberto por {{ c.solicitante_nome }} em {{ data(c.aberto_em) }}</small></header>
              <div class="texto-evento texto-evento-html" [innerHTML]="c.descricao"></div>
              @if (c.anexos.length) { <ul class="lista-anexos-evento">@for (a of c.anexos; track a.id) { <li>
                <button type="button" class="acao-secundaria acao-pequena" (click)="baixar(a)">{{ a.nome }} ({{ tamanho(a.tamanho) }})</button></li> }</ul> }
            </section>

            @if (c.campos.length) {
              <section class="cartao-chamado" aria-labelledby="titulo-informacoes">
                <header><h2 id="titulo-informacoes">Informações</h2></header>
                <dl class="grade-informacoes">
                  @for (v of c.campos; track v.campo_id) {
                    <div><dt>{{ v.rotulo }}</dt><dd>
                      <span [class.texto-codigo]="v.dado_pessoal">{{ revelados()[v.campo_id] ?? v.valor }}</span>
                      @if (v.pode_revelar && !revelados()[v.campo_id]) {
                        <button type="button" class="acao-secundaria acao-pequena" (click)="revelar(v.campo_id)" title="Ver o valor completo (fica registrado)">Mostrar</button>
                      }
                    </dd></div>
                  }
                </dl>
              </section>
            }

            @if (c.acoes.tarefas || c.tarefas.length) {
              <section class="cartao-chamado" aria-labelledby="titulo-tarefas">
                <header><h2 id="titulo-tarefas">Tarefas</h2><small>{{ tarefasFeitas() }} de {{ c.tarefas.length }} feita(s)</small></header>
                @if (c.tarefas.length) {
                  <ul class="lista-tarefas-chamado">
                    @for (t of c.tarefas; track t.id) {
                      <li [class.feita]="t.estado === 'feita'">
                        <label class="linha-caixa">
                          <input type="checkbox" [checked]="t.estado === 'feita'" [disabled]="!c.acoes.tarefas || enviando()" (change)="marcarTarefa(t.id, $any($event.target).checked)" />
                          <span>{{ t.texto }}</span>
                        </label>
                        <small>{{ t.responsavel_nome ? 'Com ' + t.responsavel_nome + ' · ' : '' }}{{ t.privada ? 'Privada' : 'Visível ao solicitante' }}</small>
                      </li>
                    }
                  </ul>
                }
                @if (c.acoes.tarefas && c.status_base !== 'solucionado') {
                  <form class="formulario-linha-chamado" (submit)="$event.preventDefault(); criarTarefa()">
                    <div class="campo-linha"><label for="dc-tarefa">Nova tarefa</label>
                      <input id="dc-tarefa" name="tarefa" maxlength="500" placeholder="Ex.: pedir toner ao fornecedor" [(ngModel)]="novaTarefa" /></div>
                    <div class="campo-linha"><label for="dc-tarefa-resp">Com quem</label>
                      <app-seletor-usuarios idCampo="dc-tarefa-resp" [multiplo]="false" [(selecionados)]="tarefaPessoa" [fonte]="fonteResponsaveis"
                        textoAjuda="Pesquisar alguém do setor responsável" /></div>
                    <button type="submit" class="acao-secundaria" [disabled]="enviando() || novaTarefa.trim().length < 3">Adicionar tarefa</button>
                  </form>
                }
              </section>
            }

            @if (c.validacoes.length || c.acoes.pedir_aprovacao) {
              <section class="cartao-chamado" aria-labelledby="titulo-aprovacoes">
                <header><h2 id="titulo-aprovacoes">Aprovações</h2></header>
                @for (v of c.validacoes; track v.id) {
                  <div class="aprovacao-chamado">
                    <div class="selos-chamado">
                      <span class="selo-status" [attr.data-chamado]="v.status === 'aguardando' ? 'alerta' : v.status === 'aprovada' ? 'sucesso' : 'neutro'">
                        {{ v.status === 'aguardando' ? 'Aguardando ' + v.alvo_nome : v.status === 'aprovada' ? 'Aprovada por ' + v.respondida_por_nome : 'Não aprovada por ' + v.respondida_por_nome }}</span>
                    </div>
                    <p>{{ v.pedido }}<small> · pedida por {{ v.solicitante_nome }} em {{ data(v.criado_em) }}</small></p>
                    @if (v.resposta) { <p><strong>Resposta:</strong> {{ v.resposta }}</p> }
                    @if (v.posso_responder) {
                      <div class="campo-linha"><label [for]="'dc-resp-' + v.id">Sua resposta (obrigatória para não aprovar)</label>
                        <textarea [id]="'dc-resp-' + v.id" rows="2" maxlength="2000" [(ngModel)]="respostaAprovacao" [name]="'resp-' + v.id"></textarea></div>
                      <footer class="acoes-formulario">
                        <button type="button" class="acao-recusar" [disabled]="enviando() || respostaAprovacao.trim().length < 5" (click)="responderAprovacao(v.id, false)">Não aprovar</button>
                        <button type="button" class="acao-positiva" [disabled]="enviando()" (click)="responderAprovacao(v.id, true)">Aprovar</button>
                      </footer>
                    }
                  </div>
                }
                @if (c.acoes.pedir_aprovacao) {
                  @if (!pedindoAprovacao()) {
                    <button type="button" class="acao-secundaria acao-pequena" (click)="abrirPedidoAprovacao()">Pedir aprovação</button>
                  } @else {
                    <form class="formulario-linha-chamado" (submit)="$event.preventDefault(); pedirAprovacao()">
                      <div class="campo-linha"><label for="dc-aprov-tipo">Quem aprova</label>
                        <select id="dc-aprov-tipo" name="aprov-tipo" [(ngModel)]="alvoAprovacao.tipo" (ngModelChange)="alvoAprovacao.id = null; aprovacaoPessoa = []">
                          <option value="pessoa">Uma pessoa</option><option value="setor">Um setor (qualquer membro)</option>
                        </select></div>
                      @if (alvoAprovacao.tipo === 'pessoa') {
                        <div class="campo-linha"><label for="dc-aprov-busca">Pessoa</label>
                          <app-seletor-usuarios idCampo="dc-aprov-busca" [multiplo]="false" [selecionados]="aprovacaoPessoa"
                            (selecionadosChange)="aprovacaoPessoa = $event; alvoAprovacao.id = $event[0]?.id ?? null" [fonte]="fontePessoas" textoAjuda="Pesquisar usuário" /></div>
                      } @else {
                        <div class="campo-linha"><label for="dc-aprov-setor">Setor</label>
                          <select id="dc-aprov-setor" name="aprov-setor" [(ngModel)]="alvoAprovacao.id">
                            <option [ngValue]="null">Escolha</option>
                            @for (s of setores(); track s.id) { <option [ngValue]="s.id">{{ s.caminho }}</option> }
                          </select></div>
                      }
                      <div class="campo-linha"><label for="dc-aprov-pedido">O que precisa ser aprovado</label>
                        <textarea id="dc-aprov-pedido" name="aprov-pedido" rows="2" maxlength="2000" [(ngModel)]="pedidoAprovacao"></textarea></div>
                      <footer class="acoes-formulario">
                        <button type="button" class="acao-secundaria" (click)="pedindoAprovacao.set(false)">Cancelar</button>
                        <button type="submit" class="acao-primaria" [disabled]="enviando() || !alvoAprovacao.id || pedidoAprovacao.trim().length < 3">Pedir aprovação</button>
                      </footer>
                    </form>
                  }
                }
              </section>
            }

            @if (c.satisfacao; as sat) {
              <section class="cartao-chamado" aria-labelledby="titulo-satisfacao">
                <header><h2 id="titulo-satisfacao">{{ sat.pode_avaliar ? 'Como foi o atendimento?' : 'Nota do atendimento' }}</h2>
                  @if (sat.nota) { <small>{{ sat.pode_avaliar ? 'Sua nota' : 'Nota do solicitante' }}: {{ sat.rotulo }}</small> }</header>
                @if (sat.pode_avaliar) {
                  <div class="botoes-linha notas-satisfacao" role="group" aria-label="Nota do atendimento">
                    @for (n of notas; track n[0]) {
                      <button type="button" class="acao-secundaria acao-pequena" [class.nota-escolhida]="sat.nota === n[0]" [attr.aria-pressed]="sat.nota === n[0]"
                        [disabled]="enviando()" (click)="avaliar(n[0])">{{ n[1] }}</button>
                    }
                  </div>
                  @if (sat.nota) {
                    <div class="campo-linha"><label for="dc-comentario-nota">Quer comentar? <small>(opcional)</small></label>
                      <textarea id="dc-comentario-nota" rows="2" maxlength="2000" [(ngModel)]="comentarioNota" name="comentario-nota"></textarea></div>
                    <footer class="acoes-formulario"><button type="button" class="acao-secundaria acao-pequena" [disabled]="enviando()" (click)="avaliar(sat.nota)">Enviar comentário</button></footer>
                    @if (sat.nota <= 2 && c.acoes.nao_resolveu) { <p class="dica-formulario">Se o problema continua, use o botão "Não resolveu" deste chamado: ele volta para a equipe.</p> }
                  }
                } @else if (!sat.nota) {
                  <p class="estado-vazio-chamado">O solicitante ainda não deu a nota.</p>
                } @else if (sat.comentario) {
                  <p class="texto-evento">"{{ sat.comentario }}"</p>
                }
              </section>
            }

            <section class="cartao-chamado" aria-labelledby="titulo-andamento">
              <header><h2 id="titulo-andamento">Andamento</h2><small>{{ c.linha_do_tempo.length }} registro(s)</small></header>
              @if (c.linha_do_tempo.length) {
                <ol class="linha-do-tempo">
                  @for (i of c.linha_do_tempo; track i.id) {
                    <li [attr.data-tipo]="tipoItem(i)" [class.privado]="i.privado" [class.automatico]="i.automatico">
                      <span class="icone-evento" aria-hidden="true"><svg viewBox="0 0 24 24"><path [attr.d]="icone(i)" /></svg></span>
                      <div class="conteudo-evento">
                        <div class="topo-evento">
                          <strong>{{ tituloItem(i) }}</strong>
                          <small>{{ i.autor_nome }} · {{ data(i.criado_em) }}</small>
                        </div>
                        @if (!i.automatico) { <div class="texto-evento texto-evento-html" [innerHTML]="i.texto"></div> } @else { <small>{{ textoPuro(i.texto) }}</small> }
                        @if (i.anexos.length) { <ul class="lista-anexos-evento">@for (a of i.anexos; track a.id) { <li>
                          <button type="button" class="acao-secundaria acao-pequena" (click)="baixar(a)">{{ a.nome }} ({{ tamanho(a.tamanho) }})</button></li> }</ul> }
                      </div>
                    </li>
                  }
                </ol>
              } @else {
                <p class="estado-vazio-chamado">Ainda sem respostas. Quando a equipe responder, aparece aqui e você é avisado no sino.</p>
              }

              @if (c.acoes.responder || c.acoes.solucionar) {
                <form class="composicao-chamado" (submit)="$event.preventDefault(); enviar()">
                  @if (c.acoes.solucionar) {
                    <div class="abas" role="tablist">
                      <button type="button" role="tab" [class.ativa]="modo() === 'responder'" [attr.aria-selected]="modo() === 'responder'" (click)="modo.set('responder')">Responder</button>
                      <button type="button" role="tab" [class.ativa]="modo() === 'resolver'" [attr.aria-selected]="modo() === 'resolver'" (click)="modo.set('resolver')">Resolver</button>
                    </div>
                  }
                  @if (c.acoes.responder_privado && respostasProntas().length) {
                    <div class="campo-linha"><label for="dc-pronta">Resposta pronta</label>
                      <select id="dc-pronta" name="pronta" [ngModel]="''" (ngModelChange)="inserirPronta($event)">
                        <option value="">Inserir uma resposta pronta…</option>
                        @for (r of respostasProntas(); track r.id) { <option [value]="r.id">{{ r.titulo }}</option> }
                      </select></div>
                  }
                  <div class="editor-chamado">
                    @defer (on viewport) { <app-editor-rico [(html)]="texto" [rotulo]="modo() === 'resolver' ? 'Solução' : 'Resposta'" [colarFormatado]="true" /> }
                    @placeholder { <app-esqueleto tipo="formulario" [linhas]="2" /> }
                  </div>
                  @if (modo() === 'responder' && c.acoes.responder_privado) {
                    <label class="linha-caixa"><input type="checkbox" name="privado" [(ngModel)]="privado" /> Mensagem privada (só a equipe que atende vê)</label>
                  }
                  @if (modo() === 'resolver') { <p class="dica-formulario">Resolver encerra o chamado: o solicitante é avisado e tem alguns dias úteis para dizer que não resolveu.</p> }
                  @if (arquivos().length) {
                    <ul class="arquivos-chamado">@for (a of arquivos(); track $index) { <li>{{ a.name }} <small>{{ tamanho(a.size) }}</small>
                      <button type="button" class="acao-secundaria acao-pequena" [attr.aria-label]="'Remover ' + a.name" (click)="remover($index)">Remover</button></li> }</ul>
                  }
                  <footer class="acoes-formulario">
                    <label class="acao-secundaria botao-arquivo">Anexar arquivos
                      <input type="file" multiple [accept]="formatos" (change)="escolherArquivos($event)" /></label>
                    @if (modo() === 'resolver') {
                      <button type="submit" class="acao-positiva" [class.carregando]="enviando()" [disabled]="enviando() || !temTexto()">Resolver chamado</button>
                    } @else {
                      <button type="submit" class="acao-primaria" [class.carregando]="enviando()" [disabled]="enviando() || !temTexto()">Enviar resposta</button>
                    }
                  </footer>
                </form>
              } @else if (c.status_base === 'solucionado') {
                <p class="dica-formulario">Chamado resolvido em {{ data(c.solucionado_em) }}.</p>
              }
            </section>
          </div>

          <aside class="coluna-chamado" aria-label="Dados do chamado">
            <section class="cartao-chamado antes-da-conversa">
              <h2 class="rotulo-cartao">Situação</h2>
              <div class="selos-chamado">
                <span class="selo-status" [attr.data-chamado]="cor()">{{ status() }}</span>
                @if (c.importado) { <span class="selo-status" data-chamado="neutro">Importado do GLPI · somente leitura</span> }
              </div>
              @if (c.acoes.assumir) {
                <button type="button" class="acao-secundaria acao-pequena" [class.carregando]="enviando()" [disabled]="enviando()" (click)="assumir()">Assumir o chamado</button>
              }
              @if (c.pendente_desde) { <small class="dica-formulario">Pendente desde {{ data(c.pendente_desde) }}: o prazo de solução está parado.</small> }
              @if (c.reaberturas) { <small class="dica-formulario">Reaberto {{ c.reaberturas }} vez(es).</small> }
              @if (c.acoes.pendente) {
                @if (!pondoPendente()) {
                  <button type="button" class="acao-secundaria acao-pequena" (click)="pondoPendente.set(true)">Pôr em pendente</button>
                } @else {
                  @if (motivos().length) {
                    <div class="campo-linha"><label for="dc-motivo">Motivo</label>
                      <select id="dc-motivo" name="motivo" [ngModel]="''" (ngModelChange)="motivoPendente = $event">
                        <option value="">Escolha ou escreva abaixo</option>
                        @for (m of motivos(); track m.id) { <option [value]="m.nome">{{ m.nome }}</option> }
                      </select></div>
                  }
                  <div class="campo-linha"><label for="dc-pendente">Aguardando o quê? <small>(o solicitante é avisado)</small></label>
                    <input id="dc-pendente" maxlength="300" [(ngModel)]="motivoPendente" name="motivo-pendente" /></div>
                  <footer class="acoes-formulario">
                    <button type="button" class="acao-secundaria acao-pequena" (click)="pondoPendente.set(false)">Cancelar</button>
                    <button type="button" class="acao-primaria acao-pequena" [disabled]="enviando()" (click)="porPendente()">Pôr em pendente</button>
                  </footer>
                }
              }
              @if (c.acoes.retomar) {
                <button type="button" class="acao-secundaria acao-pequena" [disabled]="enviando()" (click)="retomar()">Retomar o atendimento</button>
              }
              @if (c.acoes.nao_resolveu) {
                <small class="dica-formulario">Se o problema continua, você pode reabrir até {{ data(c.reabrir_ate) }}.</small>
                <div class="campo-linha"><label for="dc-nao-resolveu">O que continua sem resolver?</label>
                  <textarea id="dc-nao-resolveu" rows="2" maxlength="2000" [(ngModel)]="motivoNaoResolveu" name="nao-resolveu"></textarea></div>
                <button type="button" class="acao-recusar acao-pequena" [disabled]="enviando() || motivoNaoResolveu.trim().length < 5" (click)="naoResolveu()">Não resolveu</button>
              }
            </section>
            <section class="cartao-chamado antes-da-conversa">
              <h2 class="rotulo-cartao">Prazos</h2>
              <dl>
                <div><dt>Atendimento</dt><dd><span class="selo-situacao" [attr.data-prazo]="nivel(c.atendimento)">{{ prazo(c.atendimento) }}</span>
                  @if (c.atendimento.vence_em && !c.atendimento.cumprido_em) { <small>vence {{ data(c.atendimento.vence_em) }}</small> }</dd></div>
                <div><dt>Solução</dt><dd><span class="selo-situacao" [attr.data-prazo]="nivel(c.solucao)">{{ prazo(c.solucao) }}</span>
                  @if (c.solucao.vence_em && !c.solucao.cumprido_em) { <small>vence {{ data(c.solucao.vence_em) }}</small> }</dd></div>
              </dl>
            </section>
            <section class="cartao-chamado">
              <h2 class="rotulo-cartao">Pessoas e setores</h2>
              <dl>
                <div><dt>Setor responsável</dt><dd>{{ c.setor_nome }}</dd></div>
                <div><dt>Responsável pelo atendimento</dt><dd>{{ c.responsavel_nome || 'Ninguém assumiu ainda' }}</dd></div>
                <div><dt>Solicitante</dt><dd>{{ c.solicitante_nome }}</dd></div>
                @if (c.setor_solicitante_nome) { <div><dt>Em nome do setor</dt><dd>{{ c.setor_solicitante_nome }}</dd></div> }
                @if (c.em_copia.length) {
                  <div><dt>Em cópia</dt><dd>
                    @for (x of c.em_copia; track x.id) {
                      <span class="item-copia">{{ x.nome }}@if (c.acoes.incluir_em_copia || x.usuario_id === null) {
                        <button type="button" class="acao-secundaria acao-pequena" [attr.aria-label]="'Tirar ' + x.nome + ' da cópia'" (click)="removerEmCopia(x.id)">Tirar</button> }</span>
                    }
                  </dd></div>
                }
              </dl>
              @if (c.acoes.incluir_em_copia) {
                <form class="formulario-linha-chamado" (submit)="$event.preventDefault(); incluirEmCopia()">
                  <div class="campo-linha"><label for="dc-copia-tipo">Pôr em cópia</label>
                    <select id="dc-copia-tipo" name="copia-tipo" [(ngModel)]="copiaTipo" (ngModelChange)="alvoCopia = null; copiaPessoa = []; carregarSetores()">
                      <option value="pessoa">Uma pessoa</option><option value="setor">Um setor</option>
                    </select></div>
                  @if (copiaTipo === 'pessoa') {
                    <div class="campo-linha"><label for="dc-copia-pessoa">Pessoa</label>
                      <app-seletor-usuarios idCampo="dc-copia-pessoa" [multiplo]="false" [selecionados]="copiaPessoa"
                        (selecionadosChange)="copiaPessoa = $event; alvoCopia = $event[0] ? 'u' + $event[0].id : null" [fonte]="fontePessoas" textoAjuda="Pesquisar usuário" /></div>
                  } @else {
                    <div class="campo-linha"><label for="dc-copia-setor">Setor</label>
                      <select id="dc-copia-setor" name="copia-setor" [(ngModel)]="alvoCopia">
                        <option [ngValue]="null">Escolha</option>
                        @for (s of setores(); track s.id) { <option [ngValue]="'s' + s.id">{{ s.caminho }}</option> }
                      </select></div>
                  }
                  <button type="submit" class="acao-secundaria acao-pequena" [disabled]="enviando() || !alvoCopia">Incluir</button>
                </form>
              }
            </section>
            <section class="cartao-chamado">
              <h2 class="rotulo-cartao">Classificação</h2>
              <dl>
                <div><dt>Prioridade</dt><dd><span class="selo-prioridade" [attr.data-prioridade-chamado]="c.prioridade">{{ rotuloPrioridade() }}</span>
                  @if (c.prioridade_origem === 'solicitante') { <small>Subiu porque está impedindo o trabalho</small> }
                  @if (c.prioridade_origem === 'sla') { <small>Urgente porque o prazo estourou</small> }</dd></div>
                <div><dt>Tipo</dt><dd>{{ c.tipo === 'incidente' ? 'Incidente' : 'Requisição' }}</dd></div>
                <!-- Categoria ITIL: classificação técnica, só para quem atende (o solicitante não vê) -->
                @if (c.acoes.classificar) {
                  <div><dt><label for="dc-itil">Categoria ITIL</label></dt><dd>
                    <select id="dc-itil" name="itil" [ngModel]="c.categoria_itil_id ?? null" (ngModelChange)="classificar($event)" [disabled]="enviando()">
                      <option [ngValue]="null">Pendente de classificação</option>
                      @for (i of categoriasItil(); track i.id) { <option [ngValue]="i.id">{{ i.caminho }}</option> }
                    </select>
                    @if (!c.categoria_itil_id) { <span class="selo-status" data-chamado="alerta">Pendente</span> }</dd></div>
                } @else if (c.categoria_itil) {
                  <div><dt>Categoria ITIL</dt><dd>{{ c.categoria_itil }}</dd></div>
                }
                <div><dt>Local</dt><dd>{{ c.local?.rotulo || 'Não informado' }}</dd></div>
                @if (c.relacionado) { <div><dt>Relacionado</dt><dd><a [routerLink]="['/chamados', c.relacionado.numero]">#{{ c.relacionado.numero }} · {{ c.relacionado.titulo }}</a></dd></div> }
              </dl>
              @if (c.acoes.alterar) {
                @if (!alterando()) {
                  <button type="button" class="acao-secundaria acao-pequena" (click)="abrirAlteracao()">Alterar sub-status, responsável, setor, categoria ou prioridade</button>
                } @else {
                  <form class="formulario-linha-chamado" (submit)="$event.preventDefault(); salvarAlteracao()">
                    @if (substatusDoStatus().length) {
                      <div class="campo-linha"><label for="dc-alt-sub">Sub-status</label>
                        <select id="dc-alt-sub" name="alt-sub" [(ngModel)]="alteracao.substatus_id">
                          <option [ngValue]="null">Nenhum</option>
                          @for (x of substatusDoStatus(); track x.id) { <option [ngValue]="x.id">{{ x.nome }}</option> }
                        </select></div>
                    }
                    <div class="campo-linha"><label for="dc-alt-resp">Responsável pelo atendimento</label>
                      <app-seletor-usuarios idCampo="dc-alt-resp" [multiplo]="false" [selecionados]="responsavelEscolhido"
                        (selecionadosChange)="responsavelEscolhido = $event; alteracao.responsavel_id = $event[0]?.id ?? null" [fonte]="fonteResponsaveis"
                        textoAjuda="Pesquisar alguém do setor responsável (vazio = ninguém)" /></div>
                    <div class="campo-linha"><label for="dc-alt-setor">Setor responsável</label>
                      <select id="dc-alt-setor" name="alt-setor" [(ngModel)]="alteracao.setor_id">
                        @for (s of setores(); track s.id) { <option [ngValue]="s.id">{{ s.caminho }}</option> }
                      </select></div>
                    <div class="campo-linha"><label for="dc-alt-cat">Categoria</label>
                      <select id="dc-alt-cat" name="alt-cat" [(ngModel)]="alteracao.categoria_id">
                        @for (k of categorias(); track k.id) { <option [ngValue]="k.id">{{ k.caminho }}</option> }
                      </select></div>
                    <div class="campo-linha"><label for="dc-alt-prio">Prioridade</label>
                      <select id="dc-alt-prio" name="alt-prio" [(ngModel)]="alteracao.prioridade">
                        @for (p of prioridades; track p[0]) { <option [ngValue]="p[0]">{{ p[1] }}</option> }
                      </select></div>
                    @if (alteracao.prioridade !== c.prioridade) {
                      <div class="campo-linha"><label for="dc-alt-motivo">Por que a prioridade mudou?</label>
                        <input id="dc-alt-motivo" name="alt-motivo" maxlength="300" [(ngModel)]="alteracao.motivo_prioridade" /></div>
                    }
                    <footer class="acoes-formulario">
                      <button type="button" class="acao-secundaria acao-pequena" (click)="alterando.set(false)">Cancelar</button>
                      <button type="submit" class="acao-primaria acao-pequena" [class.carregando]="enviando()" [disabled]="enviando()">Salvar</button>
                    </footer>
                  </form>
                }
              }
            </section>
          </aside>
        </div>
      }
    </div>
  `,
})
export class DetalheChamadoComponent implements OnInit {
  private readonly api = inject(ChamadosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);

  protected readonly numero = Number(this.rota.snapshot.paramMap.get('numero'));
  protected readonly recemAberto = signal(this.rota.snapshot.queryParamMap.has('aberto'));
  protected readonly chamado = signal<ChamadoDetalhe | null>(null);
  protected readonly enviando = signal(false);
  protected readonly modo = signal<'responder' | 'resolver'>('responder');
  protected readonly arquivos = signal<File[]>([]);
  protected readonly formatos = FORMATOS;
  protected texto = '';
  protected privado = false;
  protected data = dataHora;
  protected tamanho = tamanhoLegivel;

  // Quem atende vê os nomes técnicos do status; quem pediu, a linguagem simples
  protected readonly status = computed(() => {
    const c = this.chamado();
    if (!c) return '';
    return c.acoes.solucionar || c.acoes.responder_privado ? c.status_nome || ROTULOS_STATUS[c.status_base] : rotuloStatusSolicitante(c);
  });
  protected readonly cor = computed(() => {
    const c = this.chamado();
    if (!c) return 'info';
    return c.acoes.responder_privado ? c.status_cor || COR_STATUS[c.status_base] : COR_STATUS[c.status_base];
  });
  /** Sub-status ativos do status-base atual (para o "alterar"). */
  protected readonly substatusDoStatus = computed(() => this.listaSubstatus().filter((x) => x.ativo && x.status_base === this.chamado()?.status_base));
  protected readonly listaSubstatus = signal<Substatus[]>([]);
  protected readonly rotuloPrioridade = computed(() => (this.chamado() ? ROTULOS_PRIORIDADE[this.chamado()!.prioridade] : ''));

  // Marco 2: estado dos formulários da tela
  private readonly roteador = inject(Router);
  protected readonly revelados = signal<Record<string, string>>({});
  protected readonly responsaveis = signal<PessoaResumo[]>([]);
  protected readonly setores = signal<SetorResumo[]>([]);
  protected readonly categorias = signal<CategoriaCatalogo[]>([]);
  protected readonly pondoPendente = signal(false);
  protected readonly pedindoAprovacao = signal(false);
  protected readonly alterando = signal(false);
  protected readonly prioridades = Object.entries(ROTULOS_PRIORIDADE) as [Prioridade, string][];
  protected readonly tarefasFeitas = computed(() => this.chamado()?.tarefas.filter((t) => t.estado === 'feita').length ?? 0);
  protected motivoPendente = '';
  // Marco 6: nota de satisfação, respostas prontas e motivos de pendência
  protected readonly notas = NOTAS_SATISFACAO;
  protected comentarioNota = '';
  protected readonly respostasProntas = signal<RespostaPronta[]>([]);
  protected readonly categoriasItil = signal<CategoriaItilResumo[]>([]);
  protected readonly motivos = signal<MotivoPendencia[]>([]);
  private extrasCarregados = false;
  protected motivoNaoResolveu = '';
  protected novaTarefa = '';
  // Escolhas de pessoa: sempre pelo seletor de usuários (o mesmo da Equipe do contrato)
  protected tarefaPessoa: OpcaoUsuario[] = [];
  protected aprovacaoPessoa: OpcaoUsuario[] = [];
  protected copiaPessoa: OpcaoUsuario[] = [];
  protected responsavelEscolhido: OpcaoUsuario[] = [];
  protected copiaTipo: 'pessoa' | 'setor' = 'pessoa';
  /** Qualquer usuário ativo (aprovação e em cópia). */
  protected readonly fontePessoas = (busca: string): Observable<OpcaoUsuario[]> => this.api.pessoas(busca).pipe(map((l) => l.map(paraOpcao)));
  /** Só quem é do setor responsável (tarefa e responsável), filtrado aqui pelo texto. */
  protected readonly fonteResponsaveis = (busca: string): Observable<OpcaoUsuario[]> => {
    const termo = busca.trim().toLowerCase();
    const lista$ = this.responsaveis().length ? of(this.responsaveis()) : this.api.responsaveis(this.numero).pipe(tap((r) => this.responsaveis.set(r)));
    return lista$.pipe(map((l) => l.filter((p) => !termo || p.nome.toLowerCase().includes(termo) || (p.login ?? '').toLowerCase().includes(termo)).map(paraOpcao)));
  };
  protected respostaAprovacao = '';
  protected pedidoAprovacao = '';
  protected alvoAprovacao: { tipo: 'pessoa' | 'setor'; id: number | null } = { tipo: 'pessoa', id: null };
  protected alvoCopia: string | null = null;
  protected alteracao: AlteracaoChamado & { responsavel_id: number | null } = { versao: 0, responsavel_id: null };

  private readonly tempoReal = inject(ChamadosTempoRealService);
  private readonly destruir = inject(DestroyRef);
  /** Mudou enquanto a pessoa digitava: avisa em vez de recarregar (o texto em edição não se perde). */
  protected readonly mudouPorOutro = signal(false);

  ngOnInit(): void {
    this.carregar();
    this.tempoReal.eventos$.pipe(filter((e) => e.numero === this.numero), debounceTime(600), takeUntilDestroyed(this.destruir)).subscribe(() => {
      if (this.enviando()) return; // a própria ação já traz a versão nova
      if (this.temTexto()) this.mudouPorOutro.set(true);
      else this.carregar();
    });
  }

  protected atualizarAgora(): void {
    this.mudouPorOutro.set(false);
    this.carregar();
  }

  /** Aplica a resposta de uma ação; `null` = a pessoa deixou de ver o chamado (volta para a lista). */
  private aplicar(c: ChamadoDetalhe | null): void {
    this.enviando.set(false);
    if (!c) {
      void this.roteador.navigate(['/chamados/fila']);
      return;
    }
    this.chamado.set(c);
  }

  private executar(pedido: Observable<ChamadoDetalhe | null>, erro: string, depois?: () => void): void {
    this.enviando.set(true);
    pedido.subscribe({
      next: (c) => {
        this.aplicar(c);
        depois?.();
      },
      error: (e) => {
        this.enviando.set(false);
        this.dialogos.mostrarErro(e, erro);
        // 409: outra pessoa mexeu antes; a tela mostra como o chamado está agora
        this.carregar();
      },
    });
  }

  protected revelar(campoId: string): void {
    this.api.dadoPessoal(this.numero, campoId).subscribe({
      next: (r) => this.revelados.update((v) => ({ ...v, [campoId]: r.valor })),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível mostrar o dado'),
    });
  }

  protected porPendente(): void {
    this.executar(this.api.pendente(this.numero, this.motivoPendente), 'Não foi possível pôr em pendente', () => {
      this.motivoPendente = '';
      this.pondoPendente.set(false);
    });
  }

  protected retomar(): void {
    this.executar(this.api.retomar(this.numero), 'Não foi possível retomar o atendimento');
  }

  protected avaliar(nota: number): void {
    this.executar(this.api.avaliar(this.numero, nota, this.comentarioNota), 'Não foi possível gravar a nota', () => undefined);
  }

  /** Acrescenta o texto da resposta pronta ao que já está escrito. */
  protected inserirPronta(id: string): void {
    const r = this.respostasProntas().find((x) => x.id === id);
    if (r) this.texto = (this.texto || '') + r.texto;
  }

  /** Quem atende: carrega uma vez as respostas prontas e os motivos de pendência. */
  private carregarExtras(c: ChamadoDetalhe): void {
    if (c.acoes.classificar && !this.categoriasItil().length) this.api.categoriasItilAtivas().subscribe({ next: (x) => this.categoriasItil.set(x), error: () => undefined });
    if (this.extrasCarregados || !c.acoes.responder_privado) return;
    this.extrasCarregados = true;
    this.api.respostasProntas().subscribe({ next: (x) => this.respostasProntas.set(x), error: () => undefined });
    this.api.motivosPendencia().subscribe({ next: (x) => this.motivos.set(x), error: () => undefined });
  }

  /** Escolheu a categoria ITIL (ou "Pendente"): grava na hora; a linha do tempo ganha uma nota privada. */
  protected classificar(categoriaItilId: string | null): void {
    const c = this.chamado();
    if (!c || categoriaItilId === (c.categoria_itil_id ?? null)) return;
    this.executar(this.api.classificar(this.numero, c.versao, categoriaItilId), 'Não foi possível classificar o chamado');
  }

  protected naoResolveu(): void {
    this.executar(this.api.naoResolveu(this.numero, this.motivoNaoResolveu), 'Não foi possível reabrir o chamado', () => (this.motivoNaoResolveu = ''));
  }

  protected carregarSetores(): void {
    if (!this.setores().length) this.api.setoresAtivos().subscribe((s) => this.setores.set(s));
  }

  protected carregarResponsaveis(): void {
    if (!this.responsaveis().length) this.api.responsaveis(this.numero).subscribe((r) => this.responsaveis.set(r));
  }

  protected criarTarefa(): void {
    this.executar(this.api.criarTarefa(this.numero, this.novaTarefa, this.tarefaPessoa[0]?.id ?? null, true), 'Não foi possível criar a tarefa', () => {
      this.novaTarefa = '';
      this.tarefaPessoa = [];
    });
  }

  protected marcarTarefa(id: string, feita: boolean): void {
    this.executar(this.api.marcarTarefa(this.numero, id, feita), 'Não foi possível marcar a tarefa');
  }

  protected abrirPedidoAprovacao(): void {
    this.pedindoAprovacao.set(true);
    if (!this.setores().length) this.api.setoresAtivos().subscribe((s) => this.setores.set(s));
  }

  protected pedirAprovacao(): void {
    const alvo = this.alvoAprovacao.tipo === 'pessoa' ? { alvo_usuario_id: this.alvoAprovacao.id! } : { alvo_setor_id: this.alvoAprovacao.id! };
    this.executar(this.api.pedirAprovacao(this.numero, alvo, this.pedidoAprovacao), 'Não foi possível pedir a aprovação', () => {
      this.pedidoAprovacao = '';
      this.alvoAprovacao = { tipo: 'pessoa', id: null };
      this.aprovacaoPessoa = [];
      this.pedindoAprovacao.set(false);
    });
  }

  protected responderAprovacao(id: string, aprovar: boolean): void {
    this.executar(this.api.responderAprovacao(id, aprovar, this.respostaAprovacao), 'Não foi possível responder a aprovação', () => (this.respostaAprovacao = ''));
  }

  protected incluirEmCopia(): void {
    const valor = this.alvoCopia ?? '';
    const alvo = valor.startsWith('u') ? { usuario_id: Number(valor.slice(1)) } : { setor_id: Number(valor.slice(1)) };
    this.executar(this.api.incluirEmCopia(this.numero, alvo), 'Não foi possível pôr em cópia', () => {
      this.alvoCopia = null;
      this.copiaPessoa = [];
    });
  }

  protected removerEmCopia(atorId: string): void {
    this.executar(this.api.removerEmCopia(this.numero, atorId), 'Não foi possível tirar da cópia');
  }

  protected abrirAlteracao(): void {
    const c = this.chamado()!;
    this.alteracao = { versao: c.versao, responsavel_id: c.responsavel_id, setor_id: c.setor_id, categoria_id: c.categoria_id, prioridade: c.prioridade, motivo_prioridade: '',
      substatus_id: c.substatus_id };
    this.responsavelEscolhido = c.responsavel_id ? [{ id: c.responsavel_id, login: '', nome_completo: c.responsavel_nome, cargo: '', ativo: true }] : [];
    if (!this.listaSubstatus().length) this.api.substatus().subscribe((x) => this.listaSubstatus.set(x));
    this.carregarResponsaveis();
    if (!this.setores().length) this.api.setoresAtivos().subscribe((s) => this.setores.set(s));
    if (!this.categorias().length) this.api.catalogo().subscribe((k) => this.categorias.set(k));
    this.alterando.set(true);
  }

  /** Manda só o que mudou (o servidor reaplica setor, SLAs e prioridade quando a categoria muda). */
  protected salvarAlteracao(): void {
    const c = this.chamado()!;
    const dados: AlteracaoChamado = { versao: c.versao };
    if (this.alteracao.categoria_id !== c.categoria_id) dados.categoria_id = this.alteracao.categoria_id;
    if (this.alteracao.setor_id !== c.setor_id) dados.setor_id = this.alteracao.setor_id;
    if (this.alteracao.responsavel_id !== c.responsavel_id) dados.responsavel_id = this.alteracao.responsavel_id;
    if ((this.alteracao.substatus_id ?? null) !== c.substatus_id) dados.substatus_id = this.alteracao.substatus_id ?? null;
    if (this.alteracao.prioridade !== c.prioridade) {
      dados.prioridade = this.alteracao.prioridade;
      dados.motivo_prioridade = this.alteracao.motivo_prioridade;
    }
    this.executar(this.api.alterar(this.numero, dados), 'Não foi possível alterar o chamado', () => {
      this.alterando.set(false);
      this.responsaveis.set([]);
    });
  }

  private carregar(): void {
    this.api.detalhe(this.numero).subscribe({
      next: (c) => { this.chamado.set(c); this.carregarExtras(c); this.comentarioNota = c.satisfacao?.comentario ?? ''; },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível abrir o chamado'),
    });
  }

  protected tipoItem(i: ItemLinhaTempo): string {
    if (i.tipo === 'solucao') return 'validada';
    return i.automatico ? 'editada' : 'comentario';
  }

  protected icone(i: ItemLinhaTempo): string {
    return ICONES[i.privado ? 'privado' : this.tipoItem(i)];
  }

  protected tituloItem(i: ItemLinhaTempo): string {
    if (i.tipo === 'solucao') return 'Solução';
    if (i.automatico) return 'Registro automático';
    return i.privado ? 'Mensagem privada da equipe' : 'Resposta';
  }

  protected textoPuro(html: string): string {
    return html.replace(/<[^>]*>/g, '');
  }

  protected nivel(p: PrazoSla): string {
    return nivelPrazo(p);
  }

  protected prazo(p: PrazoSla): string {
    return textoPrazo(p);
  }

  protected temTexto(): boolean {
    return this.texto.replace(/<[^>]*>/g, '').trim().length > 0 || /<img\b/i.test(this.texto);
  }

  protected escolherArquivos(evento: Event): void {
    const campo = evento.target as HTMLInputElement;
    this.arquivos.update((lista) => [...lista, ...Array.from(campo.files ?? [])].slice(0, 10));
    campo.value = '';
  }

  protected remover(indice: number): void {
    this.arquivos.update((lista) => lista.filter((_, i) => i !== indice));
  }

  protected baixar(a: AnexoChamado): void {
    this.api.baixarAnexo(this.numero, a.id, a.nome).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar o arquivo') });
  }

  protected assumir(): void {
    const c = this.chamado();
    if (!c) return;
    this.enviando.set(true);
    this.api.assumir(this.numero, c.versao).subscribe({
      next: (novo) => {
        this.enviando.set(false);
        this.chamado.set(novo);
      },
      error: (e) => {
        this.enviando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível assumir o chamado');
        // 409: outra pessoa mexeu antes; a tela mostra como o chamado está agora
        this.carregar();
      },
    });
  }

  protected enviar(): void {
    this.enviando.set(true);
    this.recemAberto.set(false);
    const pedido = this.modo() === 'resolver'
      ? this.api.solucionar(this.numero, this.texto, this.arquivos())
      : this.api.responder(this.numero, this.texto, this.privado, this.arquivos());
    pedido.subscribe({
      next: (c) => {
        this.enviando.set(false);
        this.chamado.set(c);
        this.texto = '';
        this.privado = false;
        this.arquivos.set([]);
        this.modo.set('responder');
      },
      error: (e) => {
        this.enviando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível enviar');
      },
    });
  }
}
