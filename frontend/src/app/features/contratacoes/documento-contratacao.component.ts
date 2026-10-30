// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela do documento (ETP ou TR): árvore de seções e itens, edição rica, revisões, histórico do item,
// compartilhamento, vínculo com contrato, conferência antes de concluir e exportação.

import { DatePipe } from '@angular/common';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { debounceTime, Observable, Subject } from 'rxjs';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { ContratosApiService } from '../contratos/compartilhado/contratos-api.service';
import { ResumoContrato } from '../contratos/compartilhado/contratos.models';
import { ContratacoesApiService } from './contratacoes-api.service';
import {
  Conferencia, DocumentoContratacao, EntradaHistorico, ItemDocumento, ROTULOS_ITEM, ROTULOS_PAPEL, ROTULOS_SITUACAO, ROTULOS_TIPO, SecaoDocumento, Situacao, TipoItem,
} from './contratacoes.models';
import { EditorRicoComponent } from './editor-rico.component';
import { HtmlConfiavelPipe } from './html-confiavel.pipe';
import { LinkificarPipe } from '../../shared/utilitarios/linkificar.pipe';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
type Janela = null | 'edicao' | 'revisoes' | 'historico' | 'lote' | 'compartilhar' | 'contrato' | 'conferencia' | 'dados' | 'tabela' | 'secao';

interface Linha {
  item: ItemDocumento;
  profundidade: number;
  primeiro: boolean;
  ultimo: boolean;
}

interface Edicao {
  id: string | null;
  secaoId: string;
  paiId: string | null;
  tipo: TipoItem;
  html: string;
  precisa: boolean;
  posicao?: number;
}

/** Tela do documento. Todas as ações chamam a API, que devolve o documento inteiro atualizado. */
@Component({
  selector: 'app-documento-contratacao',
  host: { '(document:click)': 'menuAberto.set(null)' },
  imports: [EsqueletoComponent, LinkificarPipe, FormsModule, DatePipe, RouterLink, TrilhaComponent, EditorRicoComponent, HtmlConfiavelPipe, SeletorUsuariosComponent],
  template: `
    @if (doc(); as d) {
      <div class="cabecalho-pagina">
        <div>
          <app-trilha [itens]="[{ rotulo: 'Contratações', rota: '/contratacoes' }, { rotulo: d.nome }]" />
          <h1><span [class]="'selo-tipo ' + d.tipo">{{ rotuloTipo[d.tipo] }}</span> {{ d.nome }}</h1>
          <small>Processo SEI: {{ d.processo || '—' }} · {{ papeis[d.meu_papel] }} · criado por {{ d.criador_nome }}</small>
        </div>
        <div class="acoes-cabecalho">
          <a class="acao-secundaria" [routerLink]="['/contratacoes', d.id, 'versoes']">Versões</a>
          <button type="button" class="acao-secundaria" (click)="exportar('word')">Word</button>
          <button type="button" class="acao-secundaria" (click)="exportar('pdf')">PDF</button>
        </div>
      </div>

      <section class="painel-gestao contratacoes">
        <div class="faixa-documento">
          <div class="campo curto"><label for="dc-sit">Situação</label>
            <select id="dc-sit" [ngModel]="d.situacao" (ngModelChange)="mudarSituacao($event)" [disabled]="!d.pode_editar">
              @for (s of situacoes; track s[0]) { <option [value]="s[0]">{{ s[1] }}</option> }
            </select></div>
          <div class="resumo-doc">
            @if (d.contrato_numero) { <span>Contrato <a [routerLink]="['/contratos', d.contrato_id]">{{ d.contrato_numero }}</a></span> } @else { <span>Sem contrato vinculado</span> }
            <span>{{ d.revisoes_abertas }} revisão(ões) aberta(s)</span>
            <span>Atualizado em {{ d.atualizado_em | date: 'dd/MM/yyyy HH:mm' }}</span>
          </div>
          <span class="espacador"></span>
          @if (d.pode_editar) {
            @if (d.situacao === 'concluido') {
              <button type="button" class="acao-secundaria acao-pequena" (click)="reabrirEdicao()">Reabrir edição</button>
            } @else {
              <button type="button" class="acao-positiva acao-pequena" (click)="conferir()">Conferir e concluir</button>
            }
          }
          <!-- Demais ações do documento no menu ⋮ (mesmo padrão da carteira de contratos) -->
          <div class="menu-acoes-doc">
            <button type="button" class="acao-secundaria acao-pequena" aria-label="Mais ações do documento" aria-haspopup="menu"
                    [attr.aria-expanded]="menuAberto() === 'doc'" (click)="alternarMenu($event, 'doc')">⋮</button>
            @if (menuAberto() === 'doc') {
              <div class="menu-flutuante" role="menu">
                @if (d.pode_editar) {
                  <button type="button" role="menuitem" (click)="abrirJanela('dados')">Dados do documento</button>
                  <button type="button" role="menuitem" (click)="salvarVersao()">Salvar versão</button>
                }
                @if (d.pode_gerir) {
                  <button type="button" role="menuitem" (click)="abrirJanela('compartilhar')">Compartilhar ({{ d.membros.length }})</button>
                  <button type="button" role="menuitem" (click)="abrirJanela('contrato')">Vincular contrato</button>
                }
                <button type="button" role="menuitem" (click)="duplicar()">Duplicar documento</button>
                @if (d.pode_gerir) {
                  <span class="separador" role="separator"></span>
                  <button type="button" role="menuitem" class="perigo" (click)="excluir()">Excluir documento</button>
                }
              </div>
            }
          </div>
        </div>

        @if (d.secoes.length) {
          <div class="doc-com-sumario">
            <!-- Sumário lateral: lista de seções com destaque na ativa -->
            <nav class="sumario-doc" aria-label="Sumário do documento">
              <span class="sumario-titulo">Sumário</span>
              @for (s of d.secoes; track s.id) {
                <button type="button" [class.ativo]="secaoAtiva() === s.id" (click)="selecionarSecao(s.id)">
                  <span class="sumario-num">{{ s.ordem }}.</span> {{ s.titulo }}
                </button>
              }
            </nav>
            <!-- Conteúdo: apenas a seção ativa -->
            <div class="conteudo-doc">
              @for (s of d.secoes; track s.id; let i = $index) {
                @if (secaoAtiva() === s.id) {
                <article class="secao-doc" [id]="'s-' + s.id">
                  <header>
                    <h2>{{ s.ordem }}. {{ s.titulo }}</h2>
                    <div class="acoes-linha">
                      @if (copiada() === s.id) { <span class="aviso-copiado" role="status">Texto copiado</span> }
                      @if (d.pode_editar) {
                        <button type="button" class="acao-secundaria acao-pequena" (click)="novoItem(s, null, 'item')">+ Item</button>
                      } @else {
                        <button type="button" class="acao-secundaria acao-pequena" [disabled]="!s.itens.length" (click)="copiarSecao(s)">Copiar</button>
                      }
                      @if (d.pode_editar) {
                        <div class="menu-acoes-doc">
                          <button type="button" class="acao-secundaria acao-pequena" [attr.aria-label]="'Mais ações da seção ' + s.titulo" aria-haspopup="menu"
                                  [attr.aria-expanded]="menuAberto() === 's:' + s.id" (click)="alternarMenu($event, 's:' + s.id)">⋮</button>
                          @if (menuAberto() === 's:' + s.id) {
                            <div class="menu-flutuante" role="menu">
                              <button type="button" role="menuitem" [disabled]="!s.itens.length" (click)="copiarSecao(s)">Copiar texto da seção</button>
                              <button type="button" role="menuitem" (click)="editarSecao(s)">Editar seção</button>
                              <button type="button" role="menuitem" (click)="abrirLote(s, null)">Entrada em lote</button>
                              <button type="button" role="menuitem" [disabled]="i === 0" (click)="moverSecao(s, s.ordem - 1)">Subir seção</button>
                              <button type="button" role="menuitem" [disabled]="i === d.secoes.length - 1" (click)="moverSecao(s, s.ordem + 1)">Descer seção</button>
                              <span class="separador" role="separator"></span>
                              <button type="button" role="menuitem" class="perigo" (click)="excluirSecao(s)">Excluir seção</button>
                            </div>
                          }
                        </div>
                      }
                    </div>
                  </header>
                  @if (s.descricao) { <p class="orientacao-secao">{{ s.descricao }}</p> }
                  @for (l of linhas(s); track l.item.id) {
                    <div class="linha-item" [class.precisa-revisao]="l.item.precisa_revisao" [style.margin-left.px]="l.profundidade * 26">
                      <div class="texto-item">
                        <span class="marcador">{{ l.item.marcador }}</span>
                        <div class="conteudo-item" [innerHTML]="(l.item.conteudo_html || l.item.conteudo) | htmlConfiavel"></div>
                      </div>
                      @if (l.item.tem_tabela_tr) {
                        <div class="tabela-tr">
                          <table class="tabela-gestao"><thead><tr><th>#</th><th>Descrição</th><th>CATMAT/CATSER</th><th>Siafísico</th><th>UF</th><th>Qtd. mensal</th><th>Qtd. objeto</th><th></th></tr></thead>
                            <tbody>@for (t of l.item.linhas_tabela; track t.id) {
                              <tr><td>{{ t.ordem }}</td><td>{{ t.descricao }}</td><td>{{ t.catser_catmat }}</td><td>{{ t.siafisico }}</td><td>{{ t.unidade }}</td><td>{{ t.quantidade_mensal }}</td><td>{{ t.quantidade_objeto }}</td>
                                <td>@if (d.pode_editar) { <button type="button" class="acao-recusar acao-pequena" (click)="excluirLinhaTr(t.id)">Excluir</button> }</td></tr> }</tbody></table>
                          @if (d.pode_editar) { <button type="button" class="acao-secundaria acao-pequena" (click)="abrirTabela(l.item)">+ Linha da tabela</button> }
                        </div>
                      }
                      @for (c of l.item.comentarios_importados; track $index) {
                        <p class="comentario-importado" title="Comentário do Word (somente leitura)">💬 <b>{{ c.autor }}</b>: {{ c.comentario }}</p>
                      }
                      <div class="acoes-item">
                        <small class="tipo-item">{{ rotuloItem[l.item.tipo] }}@if (l.item.precisa_revisao) { · <b>precisa de revisão</b> }@if (l.item.revisoes.length) { · {{ l.item.revisoes.length }} revisão(ões) }</small>
                        @if (d.pode_editar) {
                          <button type="button" class="acao-secundaria acao-pequena" (click)="editar(l.item)">Editar</button>
                        } @else {
                          <button type="button" class="acao-secundaria acao-pequena" (click)="abrirRevisoes(l.item)">Revisões@if (l.item.revisoes.length) { ({{ l.item.revisoes.length }}) }</button>
                        }
                        <div class="menu-acoes-doc">
                          <button type="button" class="acao-secundaria acao-pequena" [attr.aria-label]="'Mais ações do item ' + l.item.marcador" aria-haspopup="menu"
                                  [attr.aria-expanded]="menuAberto() === 'i:' + l.item.id" (click)="alternarMenu($event, 'i:' + l.item.id)">⋮</button>
                          @if (menuAberto() === 'i:' + l.item.id) {
                            <div class="menu-flutuante" role="menu">
                              @if (d.pode_editar) {
                                <button type="button" role="menuitem" (click)="novoItem(s, l.item, 'subitem')">+ Filho</button>
                                <button type="button" role="menuitem" (click)="novoIrmao(s, l)">+ Irmão</button>
                                <button type="button" role="menuitem" (click)="abrirLote(s, l.item)">Filhos em lote</button>
                                <button type="button" role="menuitem" (click)="duplicarItem(l.item)">Duplicar</button>
                                <button type="button" role="menuitem" [disabled]="l.primeiro" (click)="moverItem(l.item, -1)">Subir</button>
                                <button type="button" role="menuitem" [disabled]="l.ultimo" (click)="moverItem(l.item, 1)">Descer</button>
                                <span class="separador" role="separator"></span>
                                <button type="button" role="menuitem" (click)="abrirRevisoes(l.item)">Revisões@if (l.item.revisoes.length) { ({{ l.item.revisoes.length }}) }</button>
                              }
                              <button type="button" role="menuitem" (click)="abrirHistorico(l.item)">Histórico</button>
                              @if (d.pode_editar) {
                                <span class="separador" role="separator"></span>
                                <button type="button" role="menuitem" class="perigo" (click)="excluirItem(l.item)">Excluir item</button>
                              }
                            </div>
                          }
                        </div>
                      </div>
                    </div>
                  } @empty { <p class="estado-vazio">Seção sem itens.</p> }
                </article>
                }
              }
              @if (d.pode_editar) { <button type="button" class="acao-secundaria" (click)="novaSecao()">+ Nova seção</button> }
            </div>
          </div>
        } @else {
          <p class="estado-vazio">O documento ainda não tem seções.</p>
          @if (d.pode_editar) { <button type="button" class="acao-secundaria" (click)="novaSecao()">+ Nova seção</button> }
        }
      </section>

      @if (janela()) {
        <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="fechar()"></div>
      }

      @if (janela() === 'edicao' && edicao(); as e) {
        <section animate.leave="mov-modal-sai" class="modal-portal modal-tela-cheia" role="dialog" aria-modal="true" aria-labelledby="t-ed">
          <header><div><span class="modal-sobretitulo">{{ e.id ? 'Editar' : 'Novo' }}</span><h2 id="t-ed">{{ rotuloItem[e.tipo] }}</h2></div><button type="button" aria-label="Fechar" (click)="fechar()">×</button></header>
          <div class="form-contratacoes">
            <div class="grade-formulario">
              <div><label for="ed-tipo">Tipo do item</label>
                <select id="ed-tipo" [ngModel]="e.tipo" (ngModelChange)="atualizarEdicao({ tipo: $event })">
                  @for (t of tiposItem; track t[0]) { <option [value]="t[0]">{{ t[1] }}</option> }
                </select></div>
              <div class="marca"><label><input type="checkbox" [ngModel]="e.precisa" (ngModelChange)="atualizarEdicao({ precisa: $event })" /> Marcar como "precisa de revisão"</label></div>
            </div>
            @defer (on idle) { <app-editor-rico [html]="e.html" (htmlChange)="atualizarEdicao({ html: $event })" rotulo="Conteúdo do item" /> } @placeholder { <app-esqueleto tipo="formulario" [linhas]="3" /> }
            <footer><button type="button" class="acao-secundaria" (click)="fechar()">Cancelar</button>
              <button type="button" class="acao-positiva" [disabled]="ocupado()" (click)="salvarItem()">Salvar</button></footer>
          </div>
        </section>
      }

      @if (janela() === 'revisoes' && itemAtual(); as it) {
        <section animate.leave="mov-modal-sai" class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="t-rev">
          <header><div><span class="modal-sobretitulo">Revisões de {{ it.marcador }}</span><h2 id="t-rev">Comentários e propostas</h2></div><button type="button" aria-label="Fechar" (click)="fechar()">×</button></header>
          <div class="form-contratacoes">
            @for (r of it.revisoes; track r.id) {
              <div class="revisao" [class.resolvida]="r.resolvida_em || r.aplicada_em">
                <p><b>{{ r.autor_nome }}</b> · {{ r.criada_em | date: 'dd/MM/yyyy HH:mm' }}
                  @if (r.aplicada_em) { <span class="selo-ok">Aplicada por {{ r.aplicada_por_nome }}</span> }
                  @if (r.resolvida_em) { <span class="selo-ok">Resolvida por {{ r.resolvida_por_nome }}</span> }</p>
                <p [innerHTML]="r.comentario | linkificar"></p>
                @if (r.conteudo_proposto_html || r.conteudo_proposto) {
                  <div class="proposta"><small>Proposta de texto:</small><div [innerHTML]="(r.conteudo_proposto_html || r.conteudo_proposto) | htmlConfiavel"></div></div>
                }
                @if (doc()!.pode_editar && !r.aplicada_em) {
                  <div class="acoes-item">
                    @if (r.conteudo_proposto_html || r.conteudo_proposto) { <button type="button" class="acao-positiva acao-pequena" (click)="aplicarRevisao(it, r.id)">Aplicar proposta</button> }
                    <button type="button" class="acao-secundaria acao-pequena" (click)="resolverRevisao(it, r.id, !r.resolvida_em)">{{ r.resolvida_em ? 'Reabrir' : 'Marcar como resolvida' }}</button>
                  </div>
                }
              </div>
            } @empty { <p class="estado-vazio">Nenhuma revisão neste item.</p> }
            <h3>Nova revisão</h3>
            <label for="rv-com">Comentário *</label>
            <textarea id="rv-com" rows="3" maxlength="4000" [(ngModel)]="revisaoComentario"></textarea>
            <label><input type="checkbox" [(ngModel)]="revisaoComProposta" (ngModelChange)="iniciarProposta(it)" /> Propor novo texto para este item</label>
            @if (revisaoComProposta) { @defer (on idle) { <app-editor-rico [html]="revisaoHtml" (htmlChange)="revisaoHtml = $event" rotulo="Texto proposto" /> } @placeholder { <app-esqueleto tipo="formulario" [linhas]="3" /> } }
            <footer><button type="button" class="acao-secundaria" (click)="fechar()">Fechar</button>
              <button type="button" class="acao-positiva" [disabled]="!revisaoComentario.trim() || ocupado()" (click)="enviarRevisao(it)">Enviar</button></footer>
          </div>
        </section>
      }

      @if (janela() === 'historico' && itemAtual(); as it) {
        <section animate.leave="mov-modal-sai" class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="t-his">
          <header><div><span class="modal-sobretitulo">Histórico de {{ it.marcador }}</span><h2 id="t-his">O que mudou neste item</h2></div><button type="button" aria-label="Fechar" (click)="fechar()">×</button></header>
          <div class="form-contratacoes">
            @for (h of historico(); track h.id) {
              <div class="entrada-historico">
                <p><b>{{ rotuloMudanca[h.mudanca] }}</b> por {{ h.autor_nome || '—' }} em {{ h.ocorrido_em | date: 'dd/MM/yyyy HH:mm' }} @if (h.detalhe) { <small>· {{ h.detalhe }}</small> }</p>
                @if (h.diferenca) { <div class="diferenca" [innerHTML]="h.diferenca | htmlConfiavel"></div> }
                @else if (h.depois_html) { <div class="diferenca" [innerHTML]="h.depois_html | htmlConfiavel"></div> }
                @if (doc()!.pode_editar && (h.mudanca === 'editou' || h.mudanca === 'restaurou')) {
                  <div class="acoes-item">
                    <button type="button" class="acao-secundaria acao-pequena" (click)="restaurarItem(h, 'antes')">Voltar a este texto (antes da edição)</button>
                  </div>
                }
              </div>
            } @empty { <p class="estado-vazio">Sem histórico: o item não foi editado desde que o histórico começou.</p> }
            <footer><button type="button" class="acao-secundaria" (click)="fechar()">Fechar</button></footer>
          </div>
        </section>
      }

      @if (janela() === 'lote') {
        <section animate.leave="mov-modal-sai" class="modal-portal modal-tela-cheia" role="dialog" aria-modal="true" aria-labelledby="t-lote">
          <header><div><span class="modal-sobretitulo">Entrada em lote</span><h2 id="t-lote">Criar vários itens de uma vez</h2></div><button type="button" aria-label="Fechar" (click)="fechar()">×</button></header>
          <div class="form-contratacoes">
            <p class="ajuda">Uma linha por item. <code>#</code> item, <code>##</code> subitem (até <code>######</code>), <code>&#64;</code> subseção, <code>**</code> inciso, <code>$$</code> alínea. Linha sem marcador continua a anterior.</p>
            <textarea rows="10" [(ngModel)]="loteTexto" aria-label="Texto do lote"></textarea>
            <footer><button type="button" class="acao-secundaria" (click)="fechar()">Cancelar</button>
              <button type="button" class="acao-positiva" [class.carregando]="ocupado()" [disabled]="!loteTexto.trim() || ocupado()" (click)="gravarLote()">Criar itens</button></footer>
          </div>
        </section>
      }

      @if (janela() === 'compartilhar') {
        <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="t-comp">
          <header><div><span class="modal-sobretitulo">Acesso</span><h2 id="t-comp">Compartilhar o documento</h2></div><button type="button" aria-label="Fechar" (click)="fechar()">×</button></header>
          <div class="form-contratacoes">
            <p class="ajuda"><b>Editor</b> edita e aplica propostas. <b>Revisor</b> só comenta e propõe. O criador e a administração sempre têm acesso total.</p>
            <ul class="membros">
              @for (m of d.membros; track m.usuario_id) {
                <li><span>{{ m.nome }} <small>({{ m.login }})</small></span>
                  <select [ngModel]="m.papel" (ngModelChange)="compartilhar(m.usuario_id, $event)"><option value="editor">Editor</option><option value="revisor">Revisor</option></select>
                  <button type="button" class="acao-recusar acao-pequena" (click)="descompartilhar(m.usuario_id)">Remover</button></li>
              } @empty { <li class="estado-vazio">Ninguém além de você.</li> }
            </ul>
            <label>Adicionar pessoa</label>
            <app-seletor-usuarios [fonte]="fonteUsuarios" [multiplo]="false" [(selecionados)]="novosMembros" />
            <div class="campo curto"><label for="cp-papel">Papel</label>
              <select id="cp-papel" [(ngModel)]="novoPapel"><option value="editor">Editor</option><option value="revisor">Revisor</option></select></div>
            <footer><button type="button" class="acao-secundaria" (click)="fechar()">Fechar</button>
              <button type="button" class="acao-positiva" [disabled]="!novosMembros.length" (click)="adicionarMembro()">Adicionar</button></footer>
          </div>
        </section>
      }

      @if (janela() === 'contrato') {
        <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="t-con">
          <header><div><span class="modal-sobretitulo">Vínculo</span><h2 id="t-con">Contrato do documento</h2></div><button type="button" aria-label="Fechar" (click)="fechar()">×</button></header>
          <div class="form-contratacoes">
            <label for="vc-busca">Buscar contrato</label>
            <input id="vc-busca" placeholder="Número ou apelido" [ngModel]="buscaContrato()" (ngModelChange)="buscarContratos($event)" />
            <ul class="membros">@for (c of contratos(); track c.id) { <li><span>{{ c.numero }} {{ c.apelido ? '· ' + c.apelido : '' }}</span>
              <button type="button" class="acao-positiva acao-pequena" (click)="vincular(c.id)">Vincular</button></li> }</ul>
            <footer><button type="button" class="acao-secundaria" (click)="fechar()">Fechar</button>
              @if (d.contrato_id) { <button type="button" class="acao-recusar" (click)="vincular(null)">Desfazer vínculo</button> }</footer>
          </div>
        </section>
      }

      @if (janela() === 'conferencia' && conferencia(); as c) {
        <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="t-conf">
          <header><div><span class="modal-sobretitulo">Antes de concluir</span><h2 id="t-conf">Conferência do documento</h2></div><button type="button" aria-label="Fechar" (click)="fechar()">×</button></header>
          <div class="form-contratacoes">
            @if (!c.bloqueios.length && !c.alertas.length) { <p>Nenhuma pendência encontrada.</p> }
            @if (c.bloqueios.length) { <div class="avisos-importacao erro"><strong>Impedem concluir</strong><ul>@for (b of c.bloqueios; track b) { <li>{{ b }}</li> }</ul></div> }
            @if (c.alertas.length) { <div class="avisos-importacao"><strong>Atenção</strong><ul>@for (a of c.alertas; track a) { <li>{{ a }}</li> }</ul></div> }
            <footer><button type="button" class="acao-secundaria" (click)="fechar()">Voltar a editar</button>
              <button type="button" class="acao-positiva" [disabled]="!c.pode_concluir || ocupado()" (click)="concluir()">{{ c.alertas.length ? 'Concluir mesmo assim' : 'Concluir' }}</button></footer>
          </div>
        </section>
      }

      @if (janela() === 'secao') {
        <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="t-sec">
          <header><div><span class="modal-sobretitulo">Seção</span><h2 id="t-sec">{{ secaoEditandoId ? 'Editar seção' : 'Nova seção' }}</h2></div><button type="button" aria-label="Fechar" (click)="fechar()">×</button></header>
          <form class="form-contratacoes" (ngSubmit)="salvarSecao()">
            <div class="grade-formulario uma-coluna">
              <div><label for="sc-titulo">Título *</label><input id="sc-titulo" name="titulo" maxlength="300" [(ngModel)]="secaoTitulo" /></div>
              <div><label for="sc-desc">Descrição</label>
                <textarea id="sc-desc" name="descricao" rows="5" maxlength="4000" [(ngModel)]="secaoDescricao"
                          placeholder="Orientação para quem vai preencher esta seção"></textarea>
                <small class="ajuda">Aparece só na tela, logo abaixo do título. Não vai para o botão Copiar, nem para o Word e o PDF.</small></div>
            </div>
            <footer><button type="button" class="acao-secundaria" (click)="fechar()">Cancelar</button>
              <button type="submit" class="acao-positiva" [class.carregando]="ocupado()" [disabled]="!secaoTitulo.trim() || ocupado()">Salvar</button></footer>
          </form>
        </section>
      }

      @if (janela() === 'dados') {
        <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="t-dad">
          <header><div><span class="modal-sobretitulo">Documento</span><h2 id="t-dad">Dados do documento</h2></div><button type="button" aria-label="Fechar" (click)="fechar()">×</button></header>
          <form class="form-contratacoes" (ngSubmit)="salvarDados()">
            <div class="grade-formulario uma-coluna">
              <div><label for="dd-nome">Nome *</label><input id="dd-nome" name="nome" maxlength="300" [(ngModel)]="dadosNome" /></div>
              <div><label for="dd-proc">Processo SEI</label><input id="dd-proc" name="processo" maxlength="100" [(ngModel)]="dadosProcesso" /></div>
              <div><label for="dd-link">Link do SEI</label><input id="dd-link" name="link" maxlength="500" [(ngModel)]="dadosLink" /></div>
            </div>
            <footer><button type="button" class="acao-secundaria" (click)="fechar()">Cancelar</button><button type="submit" class="acao-positiva" [disabled]="!dadosNome.trim()">Salvar</button></footer>
          </form>
        </section>
      }

      @if (janela() === 'tabela') {
        <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="t-tab">
          <header><div><span class="modal-sobretitulo">Item 1.1 do TR</span><h2 id="t-tab">Linha da tabela</h2></div><button type="button" aria-label="Fechar" (click)="fechar()">×</button></header>
          <form class="form-contratacoes" (ngSubmit)="salvarLinhaTr()">
            <div class="grade-formulario">
              <div class="inteira"><label for="tb-desc">Descrição *</label><textarea id="tb-desc" name="descricao" rows="3" [(ngModel)]="linhaTr.descricao"></textarea></div>
              <div><label for="tb-cat">CATMAT/CATSER</label><input id="tb-cat" name="catser_catmat" [(ngModel)]="linhaTr.catser_catmat" /></div>
              <div><label for="tb-sia">Siafísico</label><input id="tb-sia" name="siafisico" [(ngModel)]="linhaTr.siafisico" /></div>
              <div><label for="tb-uf">Unidade</label><input id="tb-uf" name="unidade" [(ngModel)]="linhaTr.unidade" /></div>
              <div><label for="tb-qm">Quantidade mensal</label><input id="tb-qm" name="quantidade_mensal" inputmode="decimal" [(ngModel)]="linhaTr.quantidade_mensal" /></div>
              <div><label for="tb-qo">Quantidade do objeto</label><input id="tb-qo" name="quantidade_objeto" inputmode="decimal" [(ngModel)]="linhaTr.quantidade_objeto" /></div>
            </div>
            <footer><button type="button" class="acao-secundaria" (click)="fechar()">Cancelar</button><button type="submit" class="acao-positiva" [disabled]="!linhaTr.descricao.trim()">Incluir</button></footer>
          </form>
        </section>
      }
    } @else {
      @if (erro()) { <p class="estado-vazio">{{ erro() }}</p> } @else { <app-esqueleto tipo="formulario" [linhas]="5" /> }
    }
  `,
})
export class DocumentoContratacaoComponent implements OnInit {
  private readonly api = inject(ContratacoesApiService);
  private readonly contratosApi = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  private readonly digitacao = new Subject<string>();

  protected readonly doc = signal<DocumentoContratacao | null>(null);
  protected readonly erro = signal('');
  protected readonly janela = signal<Janela>(null);
  protected readonly secaoAtiva = signal<string | null>(null);
  protected readonly ocupado = signal(false);
  protected readonly edicao = signal<Edicao | null>(null);
  protected readonly itemAtualId = signal<string | null>(null);
  // Menu ⋮ aberto: 'doc', 's:<seção>' ou 'i:<item>' (um por vez; clique fora fecha)
  protected readonly menuAberto = signal<string | null>(null);
  // Seção recém-copiada: o botão mostra "Copiado" por alguns segundos
  protected readonly copiada = signal<string | null>(null);
  private temporizadorCopia: ReturnType<typeof setTimeout> | undefined;
  protected readonly itemAtual = computed(() => this.doc()?.secoes.flatMap((s) => s.itens).find((i) => i.id === this.itemAtualId()) ?? null);
  protected readonly historico = signal<EntradaHistorico[]>([]);
  protected readonly conferencia = signal<Conferencia | null>(null);
  protected readonly contratos = signal<ResumoContrato[]>([]);
  protected readonly buscaContrato = signal('');

  protected readonly rotuloTipo = ROTULOS_TIPO;
  protected readonly rotuloItem = ROTULOS_ITEM;
  protected readonly papeis = ROTULOS_PAPEL;
  protected readonly situacoes = Object.entries(ROTULOS_SITUACAO);
  protected readonly tiposItem = Object.entries(ROTULOS_ITEM);
  protected readonly rotuloMudanca = { criou: 'Criado', editou: 'Editado', moveu: 'Movido', removeu: 'Removido', restaurou: 'Restaurado' };
  protected readonly fonteUsuarios = (busca: string): Observable<OpcaoUsuario[]> => this.api.opcoesUsuarios(busca);

  protected revisaoComentario = '';
  protected revisaoComProposta = false;
  protected revisaoHtml = '';
  protected loteTexto = '';
  private loteAlvo: { secaoId: string; paiId: string | null } | null = null;
  protected novosMembros: OpcaoUsuario[] = [];
  protected novoPapel: 'editor' | 'revisor' = 'editor';
  protected dadosNome = '';
  // Formulário da seção (nova ou em edição)
  protected secaoEditandoId: string | null = null;
  protected secaoTitulo = '';
  protected secaoDescricao = '';
  protected dadosProcesso = '';
  protected dadosLink = '';
  protected linhaTr = { descricao: '', siafisico: '', catser_catmat: '', unidade: '', quantidade_mensal: '0', quantidade_objeto: '0' };
  private itemTabelaId: string | null = null;

  constructor() {
    this.digitacao.pipe(debounceTime(300), takeUntilDestroyed(inject(DestroyRef))).subscribe((termo) => {
      if (termo.trim().length < 2) { this.contratos.set([]); return; }
      this.contratosApi.listar(termo.trim(), 1, 10).subscribe({ next: (p) => this.contratos.set(p.itens), error: () => this.contratos.set([]) });
    });
  }

  private get id(): string {
    return this.rota.snapshot.paramMap.get('id') ?? '';
  }

  ngOnInit(): void {
    this.api.abrir(this.id).subscribe({
      next: (d) => {
        this.doc.set(d);
        // Activa a primeira seção ao carregar (se nenhuma estiver ativa)
        if (!this.secaoAtiva() && d.secoes.length) this.secaoAtiva.set(d.secoes[0].id);
      },
      error: (e) => { this.erro.set(e?.status === 404 ? 'Documento não encontrado ou sem acesso.' : 'Não foi possível abrir o documento.'); },
    });
  }

  /** Exibe somente a seção escolhida no painel lateral. */
  protected selecionarSecao(id: string): void {
    this.secaoAtiva.set(id);
  }

  /** Abre ou fecha um menu ⋮; `stopPropagation` evita que o clique no documento o feche na mesma hora. */
  protected alternarMenu(evento: Event, chave: string): void {
    evento.stopPropagation();
    this.menuAberto.set(this.menuAberto() === chave ? null : chave);
  }

  /**
   * Copia o texto da seção, sem o título, com o índice de cada item em negrito e o recuo dos subitens.
   * Vai como HTML (cola formatado no Word e no SEI) e como texto puro, para onde não aceita formatação.
   */
  protected async copiarSecao(secao: SecaoDocumento): Promise<void> {
    const html: string[] = [];
    const texto: string[] = [];
    for (const l of this.linhas(secao)) {
      // O conteúdo já vem sanitizado pela API; o DOMParser só lê, não executa nada
      const corpo = new DOMParser().parseFromString(l.item.conteudo_html || `<p>${escaparHtml(l.item.conteudo)}</p>`, 'text/html').body;
      if (l.item.marcador) {
        const negrito = document.createElement('b');
        negrito.textContent = l.item.marcador + ' ';
        const alvo = corpo.querySelector('p, li, h1, h2, h3, h4') ?? corpo;
        alvo.insertBefore(negrito, alvo.firstChild);
      }
      html.push(`<div style="margin-left:${l.profundidade * 24}px">${corpo.innerHTML}</div>`);
      texto.push('    '.repeat(l.profundidade) + (corpo.textContent ?? '').trim());
    }
    try {
      if (typeof ClipboardItem !== 'undefined') {
        await navigator.clipboard.write([new ClipboardItem({
          'text/html': new Blob([html.join('')], { type: 'text/html' }),
          'text/plain': new Blob([texto.join('\n')], { type: 'text/plain' }),
        })]);
      } else {
        await navigator.clipboard.writeText(texto.join('\n'));
      }
      this.copiada.set(secao.id);
      clearTimeout(this.temporizadorCopia);
      this.temporizadorCopia = setTimeout(() => this.copiada.set(null), 2500);
    } catch (e) {
      this.dialogos.mostrarErro(e, 'Não foi possível copiar a seção');
    }
  }

  /** Itens da seção em pré-ordem, com a profundidade e a posição entre os irmãos. */
  protected linhas(secao: SecaoDocumento): Linha[] {
    const profundidade = new Map<string, number>();
    const irmaos = new Map<string | null, ItemDocumento[]>();
    for (const i of secao.itens) irmaos.set(i.pai_id, [...(irmaos.get(i.pai_id) ?? []), i]);
    for (const i of secao.itens) {
      let n = 0;
      let atual: ItemDocumento | undefined = i;
      while (atual?.pai_id) { n++; atual = secao.itens.find((x) => x.id === atual!.pai_id); }
      profundidade.set(i.id, n);
    }
    return secao.itens.map((i) => {
      const lista = irmaos.get(i.pai_id) ?? [];
      return { item: i, profundidade: profundidade.get(i.id) ?? 0, primeiro: lista[0]?.id === i.id, ultimo: lista[lista.length - 1]?.id === i.id };
    });
  }

  /** Aplica o documento devolvido pela API e fecha a janela aberta. */
  private aplicar(d: DocumentoContratacao, fechar = true): void {
    this.ocupado.set(false);
    this.doc.set(d);
    // Mantém a seção ativa; se ela deixou de existir (foi excluída), ativa a primeira disponível
    const ativa = this.secaoAtiva();
    if (ativa && !d.secoes.find((s) => s.id === ativa)) {
      this.secaoAtiva.set(d.secoes[0]?.id ?? null);
    }
    if (fechar) this.janela.set(null);
  }

  private falha = (titulo: string) => (e: unknown): void => {
    this.ocupado.set(false);
    this.dialogos.mostrarErro(e, titulo);
  };

  private acao(chamada: Observable<DocumentoContratacao>, titulo: string, fechar = true): void {
    this.ocupado.set(true);
    chamada.subscribe({ next: (d) => this.aplicar(d, fechar), error: this.falha(titulo) });
  }

  protected abrirJanela(j: Janela): void {
    const d = this.doc()!;
    if (j === 'dados') { this.dadosNome = d.nome; this.dadosProcesso = d.processo; this.dadosLink = d.link_sei ?? ''; }
    if (j === 'compartilhar') { this.novosMembros = []; this.novoPapel = 'editor'; }
    if (j === 'contrato') { this.contratos.set([]); this.buscaContrato.set(''); }
    this.janela.set(j);
  }

  protected fechar(): void {
    this.janela.set(null);
    this.edicao.set(null);
  }

  // Documento
  protected salvarDados(): void {
    this.acao(this.api.alterar(this.id, { nome: this.dadosNome.trim(), processo: this.dadosProcesso.trim(), link_sei: this.dadosLink.trim() || null }), 'Não foi possível salvar');
  }

  protected mudarSituacao(situacao: Situacao): void {
    if (situacao === 'concluido') { this.conferir(); this.doc.update((d) => d && { ...d }); return; }
    this.acao(this.api.situacao(this.id, situacao, false), 'Não foi possível mudar a situação');
  }

  /** Volta o documento para rascunho para continuar editando após ter sido concluído. */
  protected reabrirEdicao(): void {
    this.acao(this.api.situacao(this.id, 'rascunho', false), 'Não foi possível reabrir o documento');
  }

  protected conferir(): void {
    this.api.conferencia(this.id).subscribe({ next: (c) => { this.conferencia.set(c); this.janela.set('conferencia'); }, error: this.falha('Não foi possível conferir') });
  }

  protected concluir(): void {
    this.acao(this.api.situacao(this.id, 'concluido', true), 'Não foi possível concluir');
  }

  protected salvarVersao(): void {
    const resumo = window.prompt('Descreva as alterações desta versão (opcional):', '');
    if (resumo === null) return;
    this.api.salvarVersao(this.id, resumo.trim()).subscribe({
      next: (v) => this.dialogos.avisar('Versão salva', `Versão ${v.numero} registrada. Veja em "Versões".`),
      error: this.falha('Não foi possível salvar a versão'),
    });
  }

  protected exportar(formato: 'word' | 'pdf'): void {
    this.dialogos.executar(this.api.exportar(this.id, formato, this.doc()!.nome), 'Gerando o arquivo…').subscribe({ error: this.falha('Não foi possível exportar') });
  }

  protected duplicar(): void {
    this.api.duplicar(this.id).subscribe({ next: (d) => { void this.roteador.navigate(['/contratacoes', d.id]).then(() => this.doc.set(d)); }, error: this.falha('Não foi possível duplicar') });
  }

  protected async excluir(): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: 'Excluir o documento?', mensagem: 'O documento, as versões e o histórico serão apagados. Não há como desfazer.', rotuloConfirmar: 'Excluir documento', segundos: 3 });
    if (!ok) return;
    this.api.excluir(this.id).subscribe({ next: () => void this.roteador.navigate(['/contratacoes']), error: this.falha('Não foi possível excluir') });
  }

  // Membros e contrato
  protected adicionarMembro(): void {
    const u = this.novosMembros[0];
    if (!u) return;
    this.api.compartilhar(this.id, u.id, this.novoPapel).subscribe({ next: (m) => { this.doc.update((d) => d && { ...d, membros: m }); this.novosMembros = []; }, error: this.falha('Não foi possível compartilhar') });
  }

  protected compartilhar(usuarioId: number, papel: 'editor' | 'revisor'): void {
    this.api.compartilhar(this.id, usuarioId, papel).subscribe({ next: (m) => this.doc.update((d) => d && { ...d, membros: m }), error: this.falha('Não foi possível alterar o papel') });
  }

  protected descompartilhar(usuarioId: number): void {
    this.api.descompartilhar(this.id, usuarioId).subscribe({ next: (m) => this.doc.update((d) => d && { ...d, membros: m }), error: this.falha('Não foi possível remover') });
  }

  protected buscarContratos(termo: string): void {
    this.buscaContrato.set(termo);
    this.digitacao.next(termo);
  }

  protected vincular(contratoId: string | null): void {
    this.acao(this.api.vincular(this.id, contratoId), 'Não foi possível vincular');
  }

  // Seções
  protected novaSecao(): void {
    this.secaoEditandoId = null;
    this.secaoTitulo = '';
    this.secaoDescricao = '';
    this.janela.set('secao');
  }

  protected editarSecao(s: SecaoDocumento): void {
    this.secaoEditandoId = s.id;
    this.secaoTitulo = s.titulo;
    this.secaoDescricao = s.descricao;
    this.janela.set('secao');
  }

  /** Cria a seção (e a deixa ativa) ou grava título e descrição da seção em edição. */
  protected salvarSecao(): void {
    const titulo = this.secaoTitulo.trim();
    if (!titulo) return;
    const descricao = this.secaoDescricao.trim();
    if (this.secaoEditandoId) {
      this.acao(this.api.alterarSecao(this.id, this.secaoEditandoId, titulo, descricao), 'Não foi possível salvar a seção');
      return;
    }
    this.ocupado.set(true);
    this.api.criarSecao(this.id, titulo, descricao).subscribe({
      next: (d) => {
        this.aplicar(d);
        // Ativa a seção recém-criada (última da lista)
        const ultima = d.secoes[d.secoes.length - 1];
        if (ultima) this.secaoAtiva.set(ultima.id);
      },
      error: this.falha('Não foi possível criar a seção'),
    });
  }

  protected moverSecao(s: SecaoDocumento, ordem: number): void {
    this.acao(this.api.moverSecao(this.id, s.id, ordem), 'Não foi possível mover a seção', false);
  }

  protected async excluirSecao(s: SecaoDocumento): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir "${s.titulo}"?`, mensagem: 'A seção e todos os itens dela saem do documento (a versão guardada permite recuperar).', rotuloConfirmar: 'Excluir seção', segundos: 3 });
    if (ok) this.acao(this.api.excluirSecao(this.id, s.id), 'Não foi possível excluir a seção', false);
  }

  // Itens
  protected editar(i: ItemDocumento): void {
    this.edicao.set({ id: i.id, secaoId: i.secao_id, paiId: i.pai_id, tipo: i.tipo, html: i.conteudo_html || `<p>${i.conteudo}</p>`, precisa: i.precisa_revisao });
    this.janela.set('edicao');
  }

  protected novoItem(s: SecaoDocumento, pai: ItemDocumento | null, tipo: TipoItem): void {
    this.edicao.set({ id: null, secaoId: s.id, paiId: pai?.id ?? null, tipo, html: '<p></p>', precisa: false });
    this.janela.set('edicao');
  }

  protected novoIrmao(s: SecaoDocumento, l: Linha): void {
    this.edicao.set({ id: null, secaoId: s.id, paiId: l.item.pai_id, tipo: l.item.tipo, html: '<p></p>', precisa: false, posicao: l.item.ordem + 1 });
    this.janela.set('edicao');
  }

  protected atualizarEdicao(parte: Partial<Edicao>): void {
    this.edicao.update((e) => e && { ...e, ...parte });
  }

  protected salvarItem(): void {
    const e = this.edicao();
    if (!e) return;
    const chamada = e.id
      ? this.api.editarItem(this.id, e.id, { tipo: e.tipo, conteudo_html: e.html, precisa_revisao: e.precisa })
      : this.api.criarItem(this.id, { secao_id: e.secaoId, pai_id: e.paiId, tipo: e.tipo, conteudo_html: e.html, posicao: e.posicao });
    this.acao(chamada, 'Não foi possível salvar o item');
  }

  protected moverItem(i: ItemDocumento, delta: number): void {
    this.acao(this.api.moverItem(this.id, i.id, { secao_id: i.secao_id, pai_id: i.pai_id, ordem: i.ordem + delta }), 'Não foi possível mover o item', false);
  }

  protected duplicarItem(i: ItemDocumento): void {
    this.acao(this.api.duplicarItem(this.id, i.id), 'Não foi possível duplicar o item', false);
  }

  protected async excluirItem(i: ItemDocumento): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir ${i.marcador || 'o item'}?`, mensagem: 'O item e os filhos dele saem do documento. O histórico e as versões permitem recuperar.', rotuloConfirmar: 'Excluir item', segundos: 2 });
    if (ok) this.acao(this.api.excluirItem(this.id, i.id), 'Não foi possível excluir o item', false);
  }

  // Tabela do TR
  protected abrirTabela(i: ItemDocumento): void {
    this.itemTabelaId = i.id;
    this.linhaTr = { descricao: '', siafisico: '', catser_catmat: '', unidade: '', quantidade_mensal: '0', quantidade_objeto: '0' };
    this.janela.set('tabela');
  }

  protected salvarLinhaTr(): void {
    if (this.itemTabelaId) this.acao(this.api.incluirLinhaTr(this.id, this.itemTabelaId, this.linhaTr), 'Não foi possível incluir a linha');
  }

  protected excluirLinhaTr(linhaId: string): void {
    this.acao(this.api.excluirLinhaTr(this.id, linhaId), 'Não foi possível excluir a linha', false);
  }

  // Lote
  protected abrirLote(s: SecaoDocumento, pai: ItemDocumento | null): void {
    this.loteAlvo = { secaoId: s.id, paiId: pai?.id ?? null };
    this.loteTexto = '';
    this.janela.set('lote');
  }

  protected gravarLote(): void {
    if (!this.loteAlvo) return;
    this.ocupado.set(true);
    this.api.criarLote(this.id, { secao_id: this.loteAlvo.secaoId, pai_id: this.loteAlvo.paiId, texto: this.loteTexto }).subscribe({
      next: () => this.api.abrir(this.id).subscribe((d) => this.aplicar(d)),
      error: this.falha('Não foi possível criar os itens'),
    });
  }

  // Revisões
  protected abrirRevisoes(i: ItemDocumento): void {
    this.itemAtualId.set(i.id);
    this.revisaoComentario = '';
    this.revisaoComProposta = false;
    this.revisaoHtml = '';
    this.janela.set('revisoes');
  }

  protected iniciarProposta(i: ItemDocumento): void {
    if (this.revisaoComProposta && !this.revisaoHtml) this.revisaoHtml = i.conteudo_html || `<p>${i.conteudo}</p>`;
  }

  protected enviarRevisao(i: ItemDocumento): void {
    this.acao(this.api.criarRevisao(this.id, i.id, { comentario: this.revisaoComentario.trim(), conteudo_proposto_html: this.revisaoComProposta ? this.revisaoHtml : null }), 'Não foi possível enviar a revisão', false);
    this.revisaoComentario = '';
    this.revisaoComProposta = false;
  }

  protected async aplicarRevisao(i: ItemDocumento, revisaoId: string): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: 'Aplicar a proposta?', mensagem: 'O texto do item será substituído pela proposta. O texto atual fica no histórico e numa versão do documento.', rotuloConfirmar: 'Aplicar' });
    if (ok) this.acao(this.api.aplicarRevisao(this.id, i.id, revisaoId), 'Não foi possível aplicar', false);
  }

  protected resolverRevisao(i: ItemDocumento, revisaoId: string, resolvida: boolean): void {
    this.acao(this.api.resolverRevisao(this.id, i.id, revisaoId, resolvida), 'Não foi possível atualizar a revisão', false);
  }

  // Histórico do item
  protected abrirHistorico(i: ItemDocumento): void {
    this.itemAtualId.set(i.id);
    this.historico.set([]);
    this.janela.set('historico');
    this.api.historicoItem(this.id, i.id).subscribe({ next: (h) => this.historico.set(h), error: this.falha('Não foi possível carregar o histórico') });
  }

  protected async restaurarItem(h: EntradaHistorico, estado: 'antes' | 'depois'): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: 'Voltar a este texto?', mensagem: 'O conteúdo atual do item é substituído; essa troca também entra no histórico.', rotuloConfirmar: 'Restaurar' });
    if (ok) this.acao(this.api.restaurarItem(this.id, h.id, estado), 'Não foi possível restaurar o item');
  }
}

/** Escapa texto puro para entrar em HTML (itens antigos sem `conteudo_html`). */
function escaparHtml(texto: string): string {
  return texto.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
