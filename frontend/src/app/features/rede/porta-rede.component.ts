/**
 * =============================================================================
 * ARQUIVO: porta-rede.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Painel de uma porta de rede: o que está ligado nela, a configuração lógica,
 * a observação, o caminho até o core e os chamados da porta.
 *
 * RESUMO TÉCNICO:
 * Componente standalone (rota /rede/portas/:id). O cartão "Ligado a" vem
 * primeiro: numa porta comum há um bloco; na porta de patch panel há dois
 * (Terminal Punch Down e Conector RJ45), montados pelo mesmo ng-template com o lado no contexto e
 * um formulário por bloco (`forms`). A descrição é só leitura (o sistema a
 * gera pelas ligações). A configuração (modo, VLANs, IP, velocidade) só
 * aparece com algo ligado; sem nada, a porta fica Desligada ou Desativada.
 *
 * FINALIDADE DE NEGÓCIO:
 * Documentar cada cabo da rede: em switch, o que está na outra ponta; no
 * patch panel, o cabo do fundo e o da frente. É isso que desenha a topologia
 * e o caminho até o core.
 *
 * CONTEXTO NO SISTEMA:
 * Usa RedeApiService (/api/rede/portas), CaminhoRedeComponent,
 * SeletorVlansComponent e BuscaBemRedeComponent. Regras no backend em
 * app/services/rede/servico.py.
 *
 * =============================================================================
 */

import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom, Observable } from 'rxjs';

import { AcessoService } from '../../core/acesso/acesso.service';
import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { dataHora, ROTULOS_STATUS } from '../chamados/chamados.models';
import { BuscaBemRedeComponent } from './busca-bem-rede.component';
import { CabecalhoRedeComponent } from './cabecalho-rede.component';
import { CaminhoRedeComponent } from './caminho-rede.component';
import { RedeApiService } from './rede-api.service';
import { SeletorVlansComponent } from './seletor-vlans.component';
import {
  COR_STATUS_PORTA, Conexao, EquipamentoResumo, GravacaoPorta, LADOS_PATCH, LadoPatch, ladoLivre, MODOS_PORTA, ModoPorta, modoPorta, Porta, PortaDetalhe,
  ROTULOS_STATUS_PORTA, velocidade, Vlan,
} from './rede.models';

/** Chave do bloco de ligação: o lado da porta de patch panel, ou `unico` nas demais portas. */
type ChaveBloco = LadoPatch | 'unico';

/** O formulário de um bloco "Ligado a" (cada lado do patch panel tem o seu). */
interface FormLigacao {
  tipo: 'bem' | 'porta' | 'descricao';
  outroEquipamento: string | null;
  outraPorta: string | null;
  outroLado: LadoPatch | null;
  descricao: string;
  bem: string | null;
  /** Na troca para um lado de patch panel: ligar o outro lado daquela porta no destino de hoje (pôr o patch panel no meio do cabo). */
  religar: boolean;
}

/** Formulário vazio, com o tipo mais provável de cada bloco (decisão do usuário): a frente do patch panel costuma receber o patch cord de um
 *  switch; o fundo, o cabo que vai até a sala (um bem ou uma descrição). */
function formVazio(chave: ChaveBloco = 'unico'): FormLigacao {
  return { tipo: chave === 'frente' ? 'porta' : 'bem', outroEquipamento: null, outraPorta: null, outroLado: null, descricao: '', bem: null, religar: true };
}

@Component({
  selector: 'app-porta-rede',
  imports: [DatePipe, FormsModule, NgTemplateOutlet, RouterLink, BuscaBemRedeComponent, CabecalhoRedeComponent, CaminhoRedeComponent, EsqueletoComponent, SeletorVlansComponent],
  styles: [`
    /* Resumo da configuração (modo leitura): pares rótulo/valor em duas colunas; as linhas longas ocupam as duas */
    .resumo-config { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--spi-espaco-12) var(--spi-espaco-16); margin: 0 0 var(--spi-espaco-12);
      dt { color: var(--spi-apagado); font-size: var(--spi-texto-legenda); font-weight: 600; }
      dd { margin: var(--spi-espaco-4) 0 0; overflow-wrap: anywhere; }
      .ocupa-tudo { grid-column: 1 / -1; } }
    @media (max-width: 600px) { .resumo-config { grid-template-columns: minmax(0, 1fr); } }
    /* Seis botões de velocidade não cabem num celular: quebram linha em vez de sair da tela */
    .seletor-segmentado { flex-wrap: wrap; max-width: 100%; }
    /* Campo "Outra" velocidade logo abaixo dos botões */
    .seletor-segmentado + input { margin-top: calc(-1 * var(--spi-espaco-8)); }
    /* Fundo e Frente do patch panel: dois cartões lado a lado (empilham quando não cabem), borda de 1px */
    .lados-patch { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: var(--spi-espaco-16); }
    .lado-patch { display: grid; align-content: start; gap: var(--spi-espaco-12); min-width: 0; padding: var(--spi-espaco-16);
      border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-g); }
    .lado-patch > header { display: flex; align-items: center; justify-content: space-between; gap: var(--spi-espaco-8); }
    .lado-patch p { margin: 0; overflow-wrap: anywhere; }
    .lado-patch .grade-formulario { grid-template-columns: minmax(0, 1fr); }
    /* "Nada ligado." com espaço antes do formulário, e o botão Ligar logo abaixo do último campo */
    .bloco-unico > .estado-vazio-chamado { margin-bottom: var(--spi-espaco-12); }
    .form-ligacao .acoes-formulario { padding-top: 0; }
    /* Descrição gerada pelo sistema: texto de leitura, com o espaço de um campo antes da próxima linha */
    .descricao-gerada { display: grid; gap: var(--spi-espaco-4); margin-bottom: var(--spi-espaco-16); }
    .descricao-gerada p { margin: 0; color: var(--spi-texto); }
    /* O que está ligado do outro lado: cartão com borda de 1px, nome e porta à esquerda, botões à direita (quebram no celular) */
    .ligacao-atual { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--spi-espaco-8) var(--spi-espaco-12);
      padding: var(--spi-espaco-12); border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-m); background: var(--spi-superficie-alt); }
    .ligacao-atual-texto { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--spi-espaco-8); min-width: 0; overflow-wrap: anywhere; }
    /* Corrente de dispositivos na porta: número, nome e onde está ligado, um por linha */
    .cadeia-dispositivos { display: flex; flex-direction: column; gap: 8px; margin: 0 0 16px; padding: 0; list-style: none;
      li { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; padding: 10px 12px; border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-m); }
      .texto-codigo { display: grid; place-items: center; width: 24px; height: 24px; border-radius: var(--spi-raio-pilula); background: var(--spi-superficie-alt); font-size: 12px; }
      small { color: var(--spi-apagado); }
      button { margin-left: auto; } }
  `],
  template: `
    <div class="modulo-chamados">
      <!-- Trilha Rede › equipamento › porta: o nome do equipamento volta para a face dele -->
      <app-cabecalho-rede [titulo]="p() ? p()!.equipamento_nome + ' · porta ' + (p()!.nome || p()!.numero_logico) : 'Porta'"
        [descricao]="subtitulo()"
        [trilha]="p() ? [{ rotulo: p()!.equipamento_nome, rota: ['/rede/equipamentos', p()!.equipamento_id] }, { rotulo: 'Porta ' + (p()!.nome || p()!.numero_logico) }] : []" />
      @if (p(); as p) {
        <div class="detalhe-chamado">
          <div class="coluna-chamado">
            <!-- "Ligado a" vem primeiro (decisão do usuário): o que está em cada ponta do cabo; a descrição da porta sai daqui -->
            <section class="cartao-chamado" aria-labelledby="rp-ligado">
              <header><h2 id="rp-ligado">Ligado a</h2>
                <small>{{ passiva() ? 'Cada porta do patch panel tem um cabo no Terminal Punch Down e outro no Conector RJ45.' : 'O que está na outra ponta do cabo desta porta.' }}</small></header>
              @if (passiva()) {
                <!-- Fundo e Frente lado a lado; o formulário de ligar só abre no lado escolhido (decisão do usuário) -->
                <div class="lados-patch">
                  @for (l of lados; track l.valor) {
                    <section class="lado-patch" [attr.aria-label]="l.rotulo + ' da porta'">
                      <header><h3 class="rotulo-cartao">{{ l.rotulo }}</h3>
                        @if (papeis()?.editar && !(l.valor === 'fundo' ? p.fundo : p.frente) && !abertos()[l.valor]) {
                          <button type="button" class="acao-secundaria acao-pequena" (click)="abrir(l.valor)">Ligar</button>
                        }</header>
                      @if ((l.valor === 'fundo' ? p.fundo : p.frente) || abertos()[l.valor]) {
                        <ng-container *ngTemplateOutlet="blocoLigacao; context: { $implicit: l.valor, c: l.valor === 'fundo' ? p.fundo : p.frente }" />
                      } @else {
                        <p class="estado-vazio-chamado">Nada ligado.</p>
                      }
                    </section>
                  }
                </div>
              } @else {
                <div class="bloco-unico"><ng-container *ngTemplateOutlet="blocoLigacao; context: { $implicit: 'unico', c: p.conexao }" /></div>
              }
            </section>

            <section class="cartao-chamado" aria-labelledby="rp-config">
              <header><h2 id="rp-config">{{ passiva() ? 'Observação' : 'Configuração' }}</h2>
                <small>{{ passiva() ? 'Patch panel não tem configuração lógica: só a anotação da porta.' : 'É o cadastro do que está configurado no equipamento: o SGI não muda o switch.' }}</small></header>
              @if (ligada() && !passiva() && !editandoConfig()) {
                <!-- Modo leitura (decisão do usuário): o resumo da configuração; os campos só abrem em "Editar configuração" -->
                <dl class="resumo-config">
                  <div><dt>Modo</dt><dd>{{ modoLeitura().curto }}</dd></div>
                  @if (modoLeitura().nativa) { <div><dt>{{ modoLeitura().nativa }}</dt><dd>{{ nomeVlan(p.vlan_nativa_id) }}</dd></div> }
                  @if (modoLeitura().ip) { <div><dt>IP da interface</dt><dd class="texto-codigo">{{ p.ip_interface || '—' }}</dd></div> }
                  @if (modoLeitura().semTag) { <div><dt>VLANs sem tag</dt><dd class="texto-codigo">{{ faixas(p.vlans_sem_tag) }}</dd></div> }
                  @if (modoLeitura().tag) { <div class="ocupa-tudo"><dt>VLANs com tag</dt><dd><span class="texto-codigo">{{ faixas(p.vlans_tag) }}</span>@if (p.vlans_tag.length) { <small> ({{ p.vlans_tag.length }} VLANs)</small> }</dd></div> }
                  @if (p.vlan_voz) { <div><dt>VLAN de voz</dt><dd class="texto-codigo">{{ p.vlan_voz }}</dd></div> }
                  <div><dt>Velocidade</dt><dd>{{ vel(p.velocidade_mbps) }}</dd></div>
                  <div><dt>Duplex</dt><dd>{{ p.duplex === 'full' ? 'Full' : p.duplex === 'half' ? 'Half' : '—' }}</dd></div>
                  <div class="ocupa-tudo"><dt>Observação</dt><dd>{{ p.observacao || '—' }}</dd></div>
                </dl>
                @if (papeis()?.editar) {
                  <footer class="acoes-formulario">
                    @if (temOutraPonta()) { <button type="button" class="acao-secundaria" [class.carregando]="copiando()" [disabled]="copiando()" (click)="copiarDaOutraPonta()">Copiar da outra ponta</button> }
                    <button type="button" class="acao-primaria" (click)="editandoConfig.set(true)">Editar configuração</button>
                  </footer>
                }
              } @else {
              <form class="grade-formulario" (ngSubmit)="salvar()">
                @if (copiadoDe()) { <p class="ocupa-duas dica-formulario">Configuração copiada de {{ copiadoDe() }}. Confira e salve.</p> }
                @if (passiva()) {
                  <!-- Patch panel: sem configuração lógica nem situação para escolher; só a observação -->
                } @else if (!ligada()) {
                  <p class="ocupa-duas dica-formulario">Sem nada em "Ligado a", a porta fica desligada (ou desativada) e em branco. A configuração aparece depois de ligar algo nela.</p>
                  <div><label for="rp-status">Situação</label>
                    <select id="rp-status" name="status" [disabled]="!papeis()?.editar" [(ngModel)]="cfg.status">
                      <option value="down">Desligada</option><option value="desativada">Desativada</option>
                    </select></div>
                } @else {
                  <!-- Modo | VLAN principal (ou IP, na roteada) lado a lado -->
                  <div><label for="rp-modo">Modo</label>
                    <select id="rp-modo" name="modo" [ngModel]="cfg.modo" (ngModelChange)="trocarModo($event)">
                      @for (m of modos; track m.valor) { <option [value]="m.valor">{{ m.rotulo }}</option> }
                    </select>
                    <small class="dica-formulario">{{ modo().dica }}</small></div>
                  @if (modo().nativa) {
                    <div><label for="rp-nativa">{{ modo().nativa }}</label>
                      <select id="rp-nativa" name="nativa" [(ngModel)]="cfg.vlan_nativa_id">
                        <option [ngValue]="null">Nenhuma</option>
                        @for (v of vlans(); track v.id) { <option [ngValue]="v.id">{{ v.numero }} · {{ v.nome }}</option> }
                      </select></div>
                  } @else if (modo().ip) {
                    <div><label for="rp-ip">IP da interface</label>
                      <input id="rp-ip" name="ip" maxlength="49" class="texto-codigo" placeholder="Ex.: 10.23.0.1/30" [(ngModel)]="cfg.ip_interface" /></div>
                  } @else { <div></div> }
                  @if (modo().semTag) {
                    <div class="ocupa-duas">
                      <app-seletor-vlans idCampo="rp-sem-tag" rotuloCampo="VLANs sem tag" detalheRotulo="(untagged, além da PVID)" prefixoResumo="Sem tag"
                        rotulo="Adicionar VLAN sem tag" [vlans]="vlans()" [valor]="cfg.vlans_sem_tag" [excluir]="cfg.vlans_tag"
                        [podeGerir]="!!papeis()?.administrar" (valorChange)="cfg.vlans_sem_tag = $event" (vlanAlterada)="atualizarVlan($event)" /></div>
                  }
                  @if (modo().tag) {
                    <div class="ocupa-duas">
                      <app-seletor-vlans idCampo="rp-tag" rotuloCampo="VLANs com tag" detalheRotulo="(tagged)" prefixoResumo="Com tag"
                        rotulo="Adicionar VLAN com tag" [vlans]="vlans()" [valor]="cfg.vlans_tag" [excluir]="cfg.vlans_sem_tag"
                        [podeGerir]="!!papeis()?.administrar" (valorChange)="cfg.vlans_tag = $event" (vlanAlterada)="atualizarVlan($event)" /></div>
                  }
                  <!-- Velocidade | Duplex lado a lado, em botões (as velocidades usuais; "Outra" abre o campo) -->
                  <div><span class="rotulo-campo" id="rp-vel-rotulo">Velocidade</span>
                    <div class="seletor-segmentado" role="radiogroup" aria-labelledby="rp-vel-rotulo">
                      @for (v of velocidades; track v.valor) {
                        <button type="button" role="radio" [class.ativo]="!velocidadeOutra() && cfg.velocidade_mbps === v.valor" [attr.aria-checked]="!velocidadeOutra() && cfg.velocidade_mbps === v.valor"
                          (click)="cfg.velocidade_mbps = v.valor; velocidadeOutra.set(false)">{{ v.rotulo }}</button>
                      }
                      <button type="button" role="radio" [class.ativo]="velocidadeOutra()" [attr.aria-checked]="velocidadeOutra()" (click)="velocidadeOutra.set(true)">Outra</button>
                    </div>
                    @if (velocidadeOutra()) {
                      <input id="rp-vel" name="vel" type="number" min="1" placeholder="Em Mb/s, ex.: 40000" aria-label="Velocidade em Mb/s" [(ngModel)]="cfg.velocidade_mbps" />
                    }</div>
                  <div><span class="rotulo-campo" id="rp-duplex-rotulo">Duplex</span>
                    <div class="seletor-segmentado" role="radiogroup" aria-labelledby="rp-duplex-rotulo">
                      @for (d of duplexes; track d.rotulo) {
                        <button type="button" role="radio" [class.ativo]="cfg.duplex === d.valor" [attr.aria-checked]="cfg.duplex === d.valor" (click)="cfg.duplex = d.valor">{{ d.rotulo }}</button>
                      }
                    </div></div>
                }
                <div class="ocupa-duas"><label for="rp-obs">Observação <small>(opcional)</small></label>
                  <textarea id="rp-obs" name="obs" rows="2" maxlength="4000" placeholder="Ex.: cabo danificado, reservada para a sala de som" [disabled]="!papeis()?.editar" [(ngModel)]="cfg.observacao"></textarea></div>
                @if (papeis()?.editar) {
                  <div class="ocupa-duas acoes-formulario">
                    @if (ligada() && !passiva()) { <button type="button" class="acao-secundaria" (click)="cancelarEdicao()">Cancelar</button> }
                    <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando()">{{ passiva() ? 'Salvar observação' : 'Salvar configuração' }}</button>
                  </div>
                }
              </form>
              }
            </section>

            <section class="cartao-chamado" aria-labelledby="rp-caminho">
              <header><h2 id="rp-caminho">Caminho até o core</h2><small>Por onde esta porta chega ao núcleo da rede, cabo a cabo.</small></header>
              <app-caminho-rede [portaId]="p.id" [versao]="p" />
            </section>

            <section class="cartao-chamado" aria-labelledby="rp-chamados">
              <header><h2 id="rp-chamados">Chamados desta porta</h2><small>Da porta e do ponto de rede que chega nela.</small></header>
              @for (c of p.chamados; track c.numero) {
                <p><a [routerLink]="['/chamados', c.numero]"><span class="texto-codigo">#{{ c.numero }}</span> {{ c.titulo }}</a>
                  <small> · {{ rotuloChamado(c.status_base) }} · {{ data(c.aberto_em) }}</small></p>
              } @empty { <p class="estado-vazio-chamado">Nenhum chamado ligado a esta porta.</p> }
              <footer class="acoes-formulario">
                <a class="acao-secundaria acao-pequena" routerLink="/chamados" [queryParams]="{ rede_porta: p.id }">Abrir chamado desta porta</a>
              </footer>
            </section>
          </div>

          <aside class="coluna-chamado" aria-label="Dados da porta">
            <section class="cartao-chamado">
              <h2 class="rotulo-cartao">Situação</h2>
              <dl>
                <div><dt>Estado</dt><dd>@if (p.status) { <span class="selo-status" [attr.data-chamado]="cor(p)">{{ rotuloStatus(p) }}</span> } @else { Não informado }</dd></div>
                @if (!passiva()) { <div><dt>Velocidade</dt><dd>{{ vel(p.velocidade_mbps) }}{{ p.duplex ? ' · ' + p.duplex : '' }}</dd></div> }
                @if (p.mac) { <div><dt>MAC</dt><dd class="texto-codigo">{{ p.mac }}</dd></div> }
                @if (p.ultima_mudanca) { <div><dt>Última mudança</dt><dd>{{ data(p.ultima_mudanca) }}</dd></div> }
                @if (!passiva()) { <div><dt>Erros (entrada / saída)</dt><dd>{{ p.erros_entrada }} / {{ p.erros_saida }}</dd></div> }
                <div><dt>Ponto de rede</dt><dd>@if (p.ponto) { <span class="texto-codigo">{{ p.ponto }}</span> } @else { Nenhum }</dd></div>
                <!-- Quem fez a última alteração da porta (configuração, ligação, ponto...): vale para a porta inteira -->
                <div><dt>Última alteração</dt><dd>@if (p.alterado_em) { {{ p.alterado_por }}<small class="texto-codigo">{{ p.alterado_em | date: 'dd/MM/yyyy HH:mm:ss' }}</small> } @else { Nenhuma registrada }</dd></div>
              </dl>
            </section>
          </aside>
        </div>

        <!-- Um bloco "Ligado a": o que está ligado (com Desligar e os dispositivos de trás) ou o formulário para ligar -->
        <ng-template #blocoLigacao let-chave let-c="c">
          @if (c) {
            @if (c.tipo === 'porta') {
              <!-- O equipamento do outro lado num cartão: nome, porta e as ações em botões (sem link solto) -->
              <div class="ligacao-atual">
                <div class="ligacao-atual-texto"><strong>{{ partes(c.texto)[0] }}</strong>
                  @if (partes(c.texto)[1]) { <span>porta <span class="texto-codigo">{{ partes(c.texto)[1].replace('porta ', '') }}</span></span> }</div>
                <div class="botoes-linha">
                  <a class="acao-secundaria acao-pequena" [routerLink]="['/rede/portas', c.porta_id]">Abrir porta</a>
                  @if (papeis()?.editar && !emTroca(chave)) {
                    <button type="button" class="acao-secundaria acao-pequena" [disabled]="salvando()" (click)="abrirTroca(chave)">Trocar</button>
                    <button type="button" class="acao-recusar acao-pequena" [disabled]="salvando()" (click)="desligar(chave, c)">Desligar</button>
                  }
                </div>
              </div>
              @if (emTroca(chave)) { <ng-container *ngTemplateOutlet="formLigar; context: { $implicit: chave, c: c }" /> }
            } @else {
              <!-- Em cascata: porta → primeiro dispositivo → os que estão atrás dele (ex.: telefone IP → PC) -->
              <ol class="cadeia-dispositivos">
                <li><span class="texto-codigo">1</span>
                  @if (c.bem_id) { <a [routerLink]="['/patrimonio/bens', c.bem_id]">{{ c.texto }}</a> } @else { <span>{{ c.texto }}</span> }
                  <small>direto na porta</small></li>
                @for (d of c.atras ?? []; track d.id) {
                  <li><span class="texto-codigo">{{ d.ordem + 1 }}</span>
                    @if (d.bem_id) { <a [routerLink]="['/patrimonio/bens', d.bem_id]">{{ d.texto }}</a> } @else { <span>{{ d.texto }}</span> }
                    <small>atrás do {{ d.ordem }}</small>
                    @if (papeis()?.editar) {
                      <button type="button" class="acao-recusar acao-pequena" [disabled]="salvando()" [attr.aria-label]="'Tirar ' + d.texto" (click)="removerAtras(d.id)">Tirar</button>
                    }</li>
                }
              </ol>
              @if (emTroca(chave)) {
                <ng-container *ngTemplateOutlet="formLigar; context: { $implicit: chave, c: c }" />
              } @else if (papeis()?.editar) {
                <form class="grade-formulario form-ligacao" (ngSubmit)="adicionarAtras(chave)">
                  <div class="ocupa-duas"><span class="rotulo-campo" [id]="'rp-tipo-atras-' + chave">Ligar outro dispositivo atrás <small>(ex.: o PC ligado no telefone IP)</small></span>
                    @if (chave === 'unico') {
                      <div class="seletor-segmentado" role="radiogroup" [attr.aria-labelledby]="'rp-tipo-atras-' + chave">
                        @for (o of tiposAtras; track o.valor) {
                          <button type="button" role="radio" [class.ativo]="tipoAtras(chave) === o.valor" [attr.aria-checked]="tipoAtras(chave) === o.valor"
                            (click)="form(chave).tipo = o.valor">{{ o.rotulo }}</button>
                        }
                      </div>
                    }</div>
                  @if (chave === 'unico' && form(chave).tipo === 'descricao') {
                    <div class="ocupa-duas"><label [for]="'rp-texto-atras-' + chave">Descrição</label>
                      <input [id]="'rp-texto-atras-' + chave" name="texto-atras" maxlength="250" placeholder="Ex.: Notebook do visitante" [(ngModel)]="form(chave).descricao" /></div>
                  } @else {
                    <div class="ocupa-duas"><label [for]="'rp-bem-atras-' + chave">Bem do Patrimônio</label>
                      <app-busca-bem-rede [idCampo]="'rp-bem-atras-' + chave" [(bemId)]="form(chave).bem" /></div>
                  }
                  <div class="ocupa-duas acoes-formulario">
                    <button type="button" class="acao-recusar" [disabled]="salvando()" (click)="desligar(chave, c)">Desligar</button>
                    <button type="button" class="acao-secundaria" [disabled]="salvando()" (click)="abrirTroca(chave)">Trocar</button>
                    <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando() || !podeAdicionarAtras(chave)">Ligar atrás</button>
                  </div>
                </form>
              }
            }
          } @else {
            @if (chave === 'unico') { <p class="estado-vazio-chamado">Nada ligado.</p> }
            @if (papeis()?.editar) {
              <ng-container *ngTemplateOutlet="formLigar; context: { $implicit: chave, c: null }" />
            }
          }
        </ng-template>

        <!-- Formulário de ligar (c = null) ou de trocar a ligação atual (c = o que está ligado hoje): o mesmo campo a campo -->
        <ng-template #formLigar let-chave let-c="c">
            <form class="grade-formulario form-ligacao" (ngSubmit)="c ? trocar(chave, c) : ligar(chave)">
              <!-- O que está ligado: botões lado a lado (seletor segmentado global); no patch panel, só bem ou equipamento de rede (decisão do usuário) -->
              <div class="ocupa-duas"><span class="rotulo-campo" [id]="'rp-tipo-' + chave">{{ c ? 'Trocar por' : 'O que está ligado' }}</span>
                <div class="seletor-segmentado" role="radiogroup" [attr.aria-labelledby]="'rp-tipo-' + chave">
                  @for (o of tiposLigacao(chave); track o.valor) {
                    <button type="button" role="radio" [class.ativo]="form(chave).tipo === o.valor" [attr.aria-checked]="form(chave).tipo === o.valor"
                      (click)="form(chave).tipo = o.valor">{{ o.rotulo }}</button>
                  }
                </div></div>
              @switch (form(chave).tipo) {
                @case ('bem') {
                  <div class="ocupa-duas"><label [for]="'rp-bem-' + chave">Bem do Patrimônio</label>
                    <app-busca-bem-rede [idCampo]="'rp-bem-' + chave" [(bemId)]="form(chave).bem" /></div>
                }
                @case ('porta') {
                  <div class="ocupa-duas"><label [for]="'rp-equip-' + chave">Equipamento do outro lado</label>
                    <select [id]="'rp-equip-' + chave" name="equip" [(ngModel)]="form(chave).outroEquipamento" (ngModelChange)="carregarPortasDe(chave, $event)">
                      <option [ngValue]="null">Escolha</option>
                      @for (e of equipamentos(); track e.id) { @if (e.id !== p.equipamento_id) { <option [ngValue]="e.id">{{ e.nome }}</option> } }
                    </select></div>
                  <div><label [for]="'rp-outra-' + chave">Porta</label>
                    <select [id]="'rp-outra-' + chave" name="outra" [disabled]="!form(chave).outroEquipamento" [(ngModel)]="form(chave).outraPorta" (ngModelChange)="form(chave).outroLado = null">
                      <option [ngValue]="null">{{ form(chave).outroEquipamento ? 'Escolha' : 'Escolha o equipamento antes' }}</option>
                      @for (x of portasDe(chave); track x.id) {
                        <option [ngValue]="x.id" [disabled]="ocupada(chave, x)">{{ x.nome || x.numero_logico }}{{ ocupada(chave, x) ? ' (ocupada)' : '' }}</option>
                      }
                    </select></div>
                  @if (outroEhPatch(chave)) {
                    <!-- Lado da porta do patch panel em botões (Fundo | Frente): é onde chega o cabo desta porta -->
                    <div><span class="rotulo-campo" [id]="'rp-outro-lado-' + chave">Lado da porta do patch panel</span>
                      <div class="seletor-segmentado" role="radiogroup" [attr.aria-labelledby]="'rp-outro-lado-' + chave">
                        @for (l of lados; track l.valor) {
                          <button type="button" role="radio" [class.ativo]="form(chave).outroLado === l.valor" [attr.aria-checked]="form(chave).outroLado === l.valor"
                            [disabled]="!form(chave).outraPorta || !ladoLivreDe(chave, l.valor)" (click)="form(chave).outroLado = l.valor">{{ l.rotulo }}</button>
                        }
                      </div>
                      @if (!form(chave).outraPorta) { <small class="dica-formulario">Escolha a porta do patch panel antes.</small> }
                      @for (l of lados; track l.valor) {
                        <!-- Legenda do lado ocupado: o que já está ligado nele (por isso o botão fica bloqueado) -->
                        @if (ocupacaoLado(chave, l.valor); as texto) { <small class="dica-formulario">{{ l.rotulo }} ocupado: já ligado em {{ texto }}.</small> }
                      }</div>
                  }
                }
                @case ('descricao') {
                  <div class="ocupa-duas"><label [for]="'rp-texto-' + chave">Descrição</label>
                    <input [id]="'rp-texto-' + chave" name="texto" maxlength="250" placeholder="Ex.: Telefone da recepção" [(ngModel)]="form(chave).descricao" /></div>
                }
              }
              @if (c?.tipo === 'porta' && form(chave).tipo === 'porta' && outroEhPatch(chave) && form(chave).outroLado && !ocupacaoLado(chave, ladoOposto(form(chave).outroLado))) {
                <!-- Pôr um patch panel no meio do cabo de hoje: o outro lado da porta do patch panel fica com o destino atual (só se esse lado está livre) -->
                <div class="ocupa-duas"><label class="linha-caixa"><input type="checkbox" name="religar" [(ngModel)]="form(chave).religar" />
                  Manter {{ c.texto }} ligado, agora pelo {{ ladoOposto(form(chave).outroLado) }} desta porta do patch panel</label>
                  <small class="dica-formulario">O cabo de hoje passa a atravessar o patch panel: esta porta → {{ form(chave).outroLado }} · {{ ladoOposto(form(chave).outroLado) }} → {{ c.texto }}.</small></div>
              }
              <div class="ocupa-duas acoes-formulario">
                @if (c) { <button type="button" class="acao-secundaria" (click)="fecharTroca(chave)">Cancelar</button> }
                @else if (chave !== 'unico') { <button type="button" class="acao-secundaria" (click)="fechar(chave)">Cancelar</button> }
                <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando() || !podeLigar(chave)">{{ c ? 'Trocar' : 'Ligar' }}</button>
              </div>
            </form>
        </ng-template>
      } @else {
        <app-esqueleto tipo="painel" />
      }
    </div>
  `,
})
export class PortaRedeComponent implements OnInit {
  private readonly api = inject(RedeApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly destruir = inject(DestroyRef);
  /** Porta aberta. Muda sem recriar a tela quando um link leva a outra porta. */
  private id = this.rota.snapshot.paramMap.get('id')!;
  protected readonly papeis = inject(AcessoService).rede;

  protected readonly p = signal<PortaDetalhe | null>(null);
  /** Porta de patch panel: dois lados (fundo e frente) e sem parte lógica. */
  protected readonly passiva = computed(() => this.p()?.equipamento_tipo === 'patch_panel');
  /** Tem algo ligado (em qualquer lado): só então a configuração aparece. */
  protected readonly ligada = computed(() => { const x = this.p(); return !!(x && (x.conexao || x.fundo || x.frente)); });
  protected readonly vlans = signal<Vlan[]>([]);
  protected readonly equipamentos = signal<EquipamentoResumo[]>([]);
  /** Portas do equipamento escolhido em cada bloco (carregadas ao escolher o equipamento do outro lado). */
  private readonly portasOutro = signal<Record<string, Porta[]>>({});
  protected readonly salvando = signal(false);
  protected readonly lados = LADOS_PATCH;
  protected forms: Record<ChaveBloco, FormLigacao> = { unico: formVazio(), fundo: formVazio('fundo'), frente: formVazio('frente') };
  /** Lados do patch panel com o formulário de ligar aberto (um clique em "Ligar" abre; "Cancelar" fecha). */
  protected readonly abertos = signal<Partial<Record<LadoPatch, boolean>>>({});
  /** Blocos com o formulário de "Trocar" aberto (troca a ligação atual numa operação só). */
  protected readonly trocando = signal<Partial<Record<ChaveBloco, boolean>>>({});
  /** Subtítulo do cabeçalho: no patch panel, o resumo dos dois lados; nas demais portas, a descrição. */
  protected readonly subtitulo = computed(() => {
    const x = this.p();
    if (!x) return '';
    if (x.equipamento_tipo !== 'patch_panel') return x.descricao;
    return `Terminal Punch Down: ${x.fundo?.texto ?? '—'} · Conector RJ45: ${x.frente?.texto ?? '—'}`;
  });
  protected cfg: GravacaoPorta = { observacao: '', modo: 'access', vlan_nativa_id: null, vlans_tag: [], vlans_sem_tag: [], vlan_voz_id: null, ip_interface: '',
    velocidade_mbps: null, duplex: null, status: 'down' };
  protected readonly modos = MODOS_PORTA;
  /** Edição da configuração aberta (o padrão é o modo leitura, com o resumo). */
  protected readonly editandoConfig = signal(false);
  /** Velocidades usuais em botões; outro valor abre o campo "Outra". */
  protected readonly velocidades = [{ valor: 100, rotulo: '100M' }, { valor: 1000, rotulo: '1G' }, { valor: 2500, rotulo: '2,5G' }, { valor: 10000, rotulo: '10G' },
    { valor: 25000, rotulo: '25G' }];
  protected readonly duplexes: { valor: 'full' | 'half' | null; rotulo: string }[] = [{ valor: 'full', rotulo: 'Full' }, { valor: 'half', rotulo: 'Half' }, { valor: null, rotulo: 'Não informado' }];
  protected readonly velocidadeOutra = signal(false);
  /** De onde veio a configuração copiada ("SWCORE · porta 48"), para avisar que falta salvar. */
  protected readonly copiadoDe = signal('');
  protected readonly copiando = signal(false);
  /** O modo gravado na porta (o do resumo; o do formulário é `modo`). */
  protected readonly modoLeitura = computed(() => modoPorta(this.p()?.modo ?? 'access'));
  /** O modo escolhido no formulário (atualizado em `trocarModo`): diz quais campos aparecem. */
  protected readonly modo = signal(modoPorta('access'));
  protected readonly vel = velocidade;
  protected readonly data = dataHora;

  ngOnInit(): void {
    // A mesma tela é reaproveitada entre portas: a cada id novo, mostra o esqueleto e carrega a outra
    this.rota.paramMap.pipe(takeUntilDestroyed(this.destruir)).subscribe((p) => {
      const id = p.get('id')!;
      if (id === this.id && this.p()) return;
      this.id = id;
      this.p.set(null);
      this.api.porta(id).subscribe({ next: (x) => this.aplicar(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível abrir a porta') });
    });
    this.api.vlans().subscribe({ next: (x) => this.vlans.set(x), error: () => undefined });
    this.api.equipamentos().subscribe({ next: (x) => this.equipamentos.set(x), error: () => undefined });
  }

  private aplicar(x: PortaDetalhe): void {
    this.salvando.set(false);
    this.p.set(x);
    const ligada = !!(x.conexao || x.fundo || x.frente);
    this.cfg = { observacao: x.observacao ?? '', modo: x.modo, vlan_nativa_id: x.vlan_nativa_id, vlans_tag: [...x.vlans_tag_ids], vlans_sem_tag: [...(x.vlans_sem_tag_ids ?? [])],
      vlan_voz_id: x.vlan_voz_id ?? null, ip_interface: x.ip_interface ?? '', velocidade_mbps: x.velocidade_mbps, duplex: x.duplex,
      // Ligada: sempre "up"; sem nada ligado: desligada ou desativada (a que já está gravada)
      status: ligada ? 'up' : (x.status === 'desativada' ? 'desativada' : 'down') };
    this.modo.set(modoPorta(x.modo));
    this.editandoConfig.set(false);
    this.copiadoDe.set('');
    this.velocidadeOutra.set(!!x.velocidade_mbps && !this.velocidades.some((v) => v.valor === x.velocidade_mbps));
    this.forms = { unico: formVazio(), fundo: formVazio('fundo'), frente: formVazio('frente') };
    this.abertos.set({});
    this.trocando.set({});
    this.portasOutro.set({});
  }

  private executar(pedido: Observable<PortaDetalhe>, erro: string): void {
    this.salvando.set(true);
    pedido.subscribe({ next: (x) => this.aplicar(x), error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, erro); } });
  }

  /** O formulário de um bloco (o contexto do ng-template chega sem tipo; aqui ele volta a ser `ChaveBloco`). */
  protected form(chave: ChaveBloco): FormLigacao {
    return this.forms[chave];
  }

  /** Opções de "O que está ligado": no patch panel não há "outra coisa (descrever)" (decisão do usuário). */
  protected tiposLigacao(chave: ChaveBloco): { valor: FormLigacao['tipo']; rotulo: string }[] {
    const base: { valor: FormLigacao['tipo']; rotulo: string }[] = [{ valor: 'bem', rotulo: 'Bem do Patrimônio' }, { valor: 'porta', rotulo: 'Equipamento de rede' }];
    return chave === 'unico' ? [...base, { valor: 'descricao', rotulo: 'Outra coisa' }] : base;
  }

  protected readonly tiposAtras: { valor: FormLigacao['tipo']; rotulo: string }[] = [{ valor: 'bem', rotulo: 'Bem do Patrimônio' }, { valor: 'descricao', rotulo: 'Outra coisa' }];

  /** No formulário de "atrás" só há bem ou descrição: qualquer outro valor conta como bem. */
  protected tipoAtras(chave: ChaveBloco): FormLigacao['tipo'] {
    return this.form(chave).tipo === 'descricao' ? 'descricao' : 'bem';
  }

  /** "SWCORE · porta 1" → ["SWCORE", "porta 1"] (nome do equipamento e a porta, para o cartão do que está ligado). */
  protected partes(texto: string): [string, string] {
    const i = texto.indexOf(' · ');
    return i < 0 ? [texto, ''] : [texto.slice(0, i), texto.slice(i + 3)];
  }

  /** Abre o formulário de troca do bloco, começando em "Equipamento de rede" (o caso mais comum: mudar o cabo de porta ou pôr um patch panel). */
  protected abrirTroca(chave: ChaveBloco): void {
    this.forms[chave] = { ...formVazio(chave), tipo: 'porta' };
    this.portasOutro.update((m) => ({ ...m, [chave]: [] }));
    this.trocando.update((t) => ({ ...t, [chave]: true }));
  }

  protected fecharTroca(chave: ChaveBloco): void {
    this.forms[chave] = formVazio(chave);
    this.trocando.update((t) => ({ ...t, [chave]: false }));
  }

  /** O bloco está com o formulário de troca aberto? (o contexto do ng-template chega sem tipo) */
  protected emTroca(chave: ChaveBloco): boolean {
    return !!this.trocando()[chave];
  }

  protected ladoOposto(lado: LadoPatch | null): LadoPatch {
    return lado === 'fundo' ? 'frente' : 'fundo';
  }

  /** Troca o que está ligado (numa operação só). O sistema recusa se alguém ficar sem cabo para cima. */
  protected trocar(chave: ChaveBloco, c: Conexao): void {
    const f = this.form(chave);
    const lado = this.lado(chave);
    const paraPatch = f.tipo === 'porta' && this.outroEhPatch(chave);
    const dados = f.tipo === 'bem' ? { lado, bem_id: f.bem } : f.tipo === 'porta'
      ? { lado, porta_id: f.outraPorta, outro_lado: paraPatch ? f.outroLado : null, religar_antigo: paraPatch && c.tipo === 'porta' && f.religar && !this.ocupacaoLado(chave, this.ladoOposto(f.outroLado)) }
      : { lado, descricao: f.descricao };
    this.executar(this.api.trocar(this.id, dados), 'Não foi possível trocar a ligação');
  }

  protected abrir(lado: LadoPatch): void {
    this.abertos.update((a) => ({ ...a, [lado]: true }));
  }

  protected fechar(chave: ChaveBloco): void {
    if (chave === 'unico') return;
    this.forms[chave] = formVazio(chave);
    this.abertos.update((a) => ({ ...a, [chave]: false }));
  }

  /** O lado para a API: o do bloco no patch panel; nada nas demais portas. */
  private lado(chave: ChaveBloco): LadoPatch | null {
    return chave === 'unico' ? null : chave;
  }

  /** Desfaz o que foi mexido no formulário e volta ao resumo. */
  protected cancelarEdicao(): void {
    const x = this.p();
    if (x) this.aplicar(x);
  }

  protected nomeVlan(id: string | null): string {
    const v = this.vlans().find((x) => x.id === id);
    return v ? `${v.numero} · ${v.nome}` : '—';
  }

  /** Números em faixas: [300, 301, 400, 2469…2483] → "300–301, 400, 2469–2483". */
  protected faixas(numeros: number[]): string {
    const n = [...numeros].sort((a, b) => a - b);
    const partes: string[] = [];
    for (let i = 0; i < n.length; i++) {
      let j = i;
      while (j + 1 < n.length && n[j + 1] === n[j] + 1) j++;
      partes.push(j > i ? `${n[i]}–${n[j]}` : String(n[i]));
      i = j;
    }
    return partes.join(', ') || '—';
  }

  /** A porta está ligada a outra porta (direto ou por patch panel): dá para copiar a configuração da ponta de lá. */
  protected temOutraPonta(): boolean {
    return this.p()?.conexao?.tipo === 'porta';
  }

  /**
   * "Copiar da outra ponta": segue o cabo (atravessando patch panels pelo lado oposto) até a porta de switch do outro lado, traz a configuração
   * dela para o formulário e abre a edição para conferir e salvar. Num uplink, as duas pontas costumam ter a mesma configuração.
   */
  protected async copiarDaOutraPonta(): Promise<void> {
    const c = this.p()?.conexao;
    if (!c?.porta_id) return;
    this.copiando.set(true);
    try {
      let porta = await firstValueFrom(this.api.porta(c.porta_id));
      let ladoChegada = c.outro_lado ?? null;
      // Atravessa até 5 patch panels: sai pelo lado oposto ao que o cabo chegou
      for (let i = 0; i < 5 && porta.equipamento_tipo === 'patch_panel'; i++) {
        const saida = ladoChegada === 'fundo' ? porta.frente : porta.fundo;
        if (!saida?.porta_id) { porta = null as unknown as PortaDetalhe; break; }
        ladoChegada = saida.outro_lado ?? null;
        porta = await firstValueFrom(this.api.porta(saida.porta_id));
      }
      if (!porta || porta.equipamento_tipo === 'patch_panel') {
        this.dialogos.avisar('Sem porta de switch do outro lado', 'O cabo para num patch panel sem nada do outro lado: não há configuração para copiar.');
        return;
      }
      this.cfg = { ...this.cfg, modo: porta.modo, vlan_nativa_id: porta.vlan_nativa_id, vlans_tag: [...porta.vlans_tag_ids], vlans_sem_tag: [...(porta.vlans_sem_tag_ids ?? [])],
        vlan_voz_id: porta.vlan_voz_id ?? null, ip_interface: '', velocidade_mbps: porta.velocidade_mbps, duplex: porta.duplex };
      this.modo.set(modoPorta(porta.modo));
      this.velocidadeOutra.set(!!porta.velocidade_mbps && !this.velocidades.some((v) => v.valor === porta.velocidade_mbps));
      this.copiadoDe.set(`${porta.equipamento_nome} · porta ${porta.nome || porta.numero_logico}`);
      this.editandoConfig.set(true);
    } catch (e) {
      this.dialogos.mostrarErro(e, 'Não foi possível ler a outra ponta');
    } finally {
      this.copiando.set(false);
    }
  }

  /** Cor ou nome de VLAN trocados pelo selo: atualiza a lista (os dois campos e a VLAN nativa mostram o novo). */
  protected atualizarVlan(nova: Vlan): void {
    this.vlans.update((lista) => lista.map((v) => (v.id === nova.id ? nova : v)));
  }

  protected trocarModo(valor: ModoPorta): void {
    this.cfg.modo = valor;
    this.modo.set(modoPorta(valor));
  }

  /** Grava a observação e, com algo ligado (fora do patch panel), a configuração. Manda só o que o modo aceita. */
  protected salvar(): void {
    const m = this.modo();
    const base = { observacao: this.cfg.observacao, modo: 'access' as ModoPorta, vlan_nativa_id: null, vlans_tag: [], vlans_sem_tag: [], vlan_voz_id: null,
      ip_interface: '', velocidade_mbps: null, duplex: null };
    let dados: GravacaoPorta;
    if (!this.ligada()) dados = { ...base, status: this.passiva() ? (this.p()?.status === 'desativada' ? 'desativada' : 'down') : this.cfg.status };
    else if (this.passiva()) dados = { ...base, status: 'up' };
    else dados = {
      ...this.cfg, status: 'up', vlan_nativa_id: m.nativa ? this.cfg.vlan_nativa_id : null, vlans_tag: m.tag ? this.cfg.vlans_tag : [],
      vlans_sem_tag: m.semTag ? this.cfg.vlans_sem_tag : [], vlan_voz_id: m.voz ? this.cfg.vlan_voz_id : null, ip_interface: m.ip ? this.cfg.ip_interface.trim() : '',
    };
    this.executar(this.api.configurarPorta(this.id, dados), 'Não foi possível salvar a porta');
  }

  protected carregarPortasDe(chave: ChaveBloco, id: string | null): void {
    this.form(chave).outraPorta = null;
    this.form(chave).outroLado = null;
    this.portasOutro.update((m) => ({ ...m, [chave]: [] }));
    if (id) this.api.equipamento(id).subscribe({ next: (e) => this.portasOutro.update((m) => ({ ...m, [chave]: e.portas })), error: () => undefined });
  }

  protected portasDe(chave: ChaveBloco): Porta[] {
    return this.portasOutro()[chave] ?? [];
  }

  /** O equipamento escolhido do outro lado é patch panel (aí escolhe-se também o lado da porta dele). */
  protected outroEhPatch(chave: ChaveBloco): boolean {
    return this.equipamentos().find((e) => e.id === this.form(chave).outroEquipamento)?.tipo === 'patch_panel';
  }

  /** Porta do outro lado sem lugar: ligada (fora do patch panel) ou com os dois lados ligados (patch panel). */
  protected ocupada(chave: ChaveBloco, x: Porta): boolean {
    return this.outroEhPatch(chave) ? !!(x.fundo && x.frente) : !!x.conexao;
  }

  /** O que já ocupa aquele lado da porta de patch panel escolhida (vazio se o lado está livre). */
  protected ocupacaoLado(chave: ChaveBloco, lado: LadoPatch): string {
    const porta = this.portasDe(chave).find((x) => x.id === this.form(chave).outraPorta);
    return (lado === 'fundo' ? porta?.fundo : porta?.frente)?.texto ?? '';
  }

  protected ladoLivreDe(chave: ChaveBloco, lado: LadoPatch): boolean {
    const porta = this.portasDe(chave).find((x) => x.id === this.form(chave).outraPorta);
    return !porta || ladoLivre(porta, lado);
  }

  protected podeLigar(chave: ChaveBloco): boolean {
    const f = this.form(chave);
    if (f.tipo === 'bem') return !!f.bem;
    if (f.tipo === 'descricao') return !!f.descricao.trim();
    return !!f.outraPorta && (!this.outroEhPatch(chave) || !!f.outroLado);
  }

  protected ligar(chave: ChaveBloco): void {
    const f = this.form(chave);
    const lado = this.lado(chave);
    const dados = f.tipo === 'bem' ? { lado, bem_id: f.bem } : f.tipo === 'porta' ? { lado, porta_id: f.outraPorta, outro_lado: this.outroEhPatch(chave) ? f.outroLado : null }
      : { lado, descricao: f.descricao };
    this.executar(this.api.ligar(this.id, dados), 'Não foi possível ligar a porta');
  }

  protected podeAdicionarAtras(chave: ChaveBloco): boolean {
    const f = this.form(chave);
    return f.tipo === 'descricao' ? !!f.descricao.trim() : !!f.bem;
  }

  protected adicionarAtras(chave: ChaveBloco): void {
    const f = this.form(chave);
    const lado = this.lado(chave);
    const dados = f.tipo === 'descricao' ? { lado, descricao: f.descricao } : { lado, bem_id: f.bem };
    this.executar(this.api.adicionarAtras(this.id, dados), 'Não foi possível ligar o dispositivo');
  }

  protected removerAtras(dispositivoId: string): void {
    this.executar(this.api.removerAtras(this.id, dispositivoId), 'Não foi possível tirar o dispositivo');
  }

  /**
   * Desliga o que está na porta (no patch panel, naquele lado). Regras (decisões do usuário): a porta que fica sem nada ligado passa a
   * "Desligada" e em branco; o patch panel com o outro lado ainda ligado continua ligado. Se for o único cabo de um equipamento para
   * quem fica acima dele, o sistema recusa e explica.
   */
  protected async desligar(chave: ChaveBloco, c: Conexao): Promise<void> {
    const x = this.p();
    const lado = this.lado(chave);
    const outroLadoLigado = !!x && lado !== null && !!(lado === 'fundo' ? x.frente : x.fundo);
    const efeito = outroLadoLigado ? 'A porta continua ligada pelo outro lado.' : 'Sem nada ligado, a porta passa a "Desligada" e fica em branco (modo, VLANs, IP e velocidade são apagados).';
    const ok = await this.dialogos.confirmar({
      titulo: lado ? `Desligar o ${lado} da porta?` : 'Desligar a porta?',
      mensagem: `A ligação com ${c.texto} sai. ${efeito}` + (c.tipo !== 'porta' && c.atras?.length ? ' Os dispositivos ligados atrás saem junto.' : ''),
      rotuloConfirmar: 'Desligar', perigo: true,
    });
    if (!ok) return;
    this.executar(this.api.desligar(this.id, lado), 'Não foi possível desligar a porta');
  }

  protected rotuloStatus(p: Porta): string {
    return p.status ? ROTULOS_STATUS_PORTA[p.status] : '';
  }

  protected cor(p: Porta): string {
    return p.status ? COR_STATUS_PORTA[p.status] : 'neutro';
  }

  protected rotuloChamado(status: string): string {
    return ROTULOS_STATUS[status as keyof typeof ROTULOS_STATUS] ?? status;
  }
}
