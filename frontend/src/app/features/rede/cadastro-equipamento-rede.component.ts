/**
 * =============================================================================
 * ARQUIVO: cadastro-equipamento-rede.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Página de cadastro (passo a passo) e de edição de um equipamento de rede.
 *
 * RESUMO TÉCNICO:
 * Componente standalone em duas rotas: /rede/equipamentos/novo (trilha
 * Dados → Conexão → Revisão, com app-trilha-etapas) e
 * /rede/equipamentos/:id/editar (só os dados; tipo, função e modelo travados,
 * e o botão Excluir). Nos Dados, rack e U são obrigatórios (menos no access
 * point): o rack escolhido é desenhado (app-rack-rede em modo escolha) e o U
 * é escolhido clicando num espaço livre, com confirmação Sim/Não. Na Conexão,
 * a porta deste equipamento e a do outro são escolhidas pela face
 * (app-seletor-porta-face); "Conectado em" só lista os elegíveis
 * (GET /rede/equipamentos/destinos-cadastro), e a face do outro só deixa
 * clicar nas portas que servem. As duas portas são configuradas no mesmo
 * bloco (ng-template), com a velocidade em fichas e o botão "Copiar da porta
 * …" para repetir a configuração da outra. Se Y for patch panel, escolhe o
 * lado (só os que levam acima) e vê o que está do outro lado daquela porta.
 *
 * FINALIDADE DE NEGÓCIO:
 * Força o desenho da rede de cima para baixo (decisão do usuário): todo
 * equipamento, menos o core primário e o patch panel, já entra ligado a quem
 * fica acima dele, com as duas portas configuradas na mesma tela.
 *
 * CONTEXTO NO SISTEMA:
 * Usa RedeApiService (POST/PUT/DELETE /api/rede/equipamentos), o
 * SeletorVlansComponent e a trilha compartilhada. As regras da cadeia são
 * conferidas no backend (app/services/rede/servico.py).
 *
 * =============================================================================
 */

import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectorRef, Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AcessoService } from '../../core/acesso/acesso.service';
import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { EtapaTrilha, TrilhaEtapasComponent } from '../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRedeComponent } from './cabecalho-rede.component';
import { RackRedeComponent } from './rack-rede.component';
import { RedeApiService } from './rede-api.service';
import { OpcaoPortaFace, posicoesDoModelo, SeletorPortaFaceComponent } from './seletor-porta-face.component';
import { SeletorVlansComponent } from './seletor-vlans.component';
import {
  DestinoCadastro, ehPassivo, EquipamentoDetalhe, rotuloLado, LEITURA_SSH_ATIVA, EquipamentoResumo, FuncaoEquipamento, GravacaoEquipamento, GravacaoPorta, LADOS_PATCH, LadoPatch, MODOS_PORTA,
  ModeloFace, modoPorta, Porta, portasDoModelo, Rack, ResultadoTesteLeitura, ROTULOS_FUNCAO_EQUIPAMENTO, ROTULOS_TIPO_EQUIPAMENTO, textoVlanPorta, TipoEquipamento, Vlan,
} from './rede.models';

type Passo = 'dados' | 'conexao' | 'revisao';

/** Velocidades da porta para escolher com um clique (Mb/s), no lugar de digitar (pedido do usuário, 17/11/2026). */
const VELOCIDADES: { valor: number; rotulo: string }[] = [
  { valor: 10, rotulo: '10 Mb' }, { valor: 100, rotulo: '100 Mb' }, { valor: 1000, rotulo: '1 Gb' }, { valor: 2500, rotulo: '2,5 Gb' },
  { valor: 10000, rotulo: '10 Gb' }, { valor: 25000, rotulo: '25 Gb' }, { valor: 40000, rotulo: '40 Gb' }, { valor: 100000, rotulo: '100 Gb' },
];

function dadosVazios(): GravacaoEquipamento {
  return { nome: '', tipo: 'switch', modelo_face_id: null, bem_id: null, localizacao_id: null, rack_id: null, posicao_u: null, ip_gerencia: '', funcao: null,
    numero_serie: '', observacao: '', ativo: true, acesso_usuario: '', acesso_porta: 22 };
}

function configVazia(): GravacaoPorta {
  return { observacao: '', modo: 'trunk', vlan_nativa_id: null, vlans_tag: [], vlans_sem_tag: [], vlan_voz_id: null, ip_interface: '', velocidade_mbps: null,
    duplex: null, status: 'up' };
}

/** Quem pode ficar acima do equipamento novo (a mesma regra do backend, para filtrar a lista): core secundário → primário; distribuição → core ou
 *  outra distribuição (cascata); acesso → distribuição, core ou outro acesso (cascata); access point, roteador e "outro" → switch de acesso. */
function podeFicarAcima(tipo: TipoEquipamento, funcao: FuncaoEquipamento | null, acima: EquipamentoResumo): boolean {
  if (acima.tipo !== 'switch') return false;
  if (tipo !== 'switch') return acima.funcao === 'acesso';
  const permitidas: Partial<Record<FuncaoEquipamento, FuncaoEquipamento[]>> = {
    core_secundario: ['core_primario'], distribuicao: ['core_primario', 'core_secundario', 'distribuicao'], acesso: ['core_primario', 'core_secundario', 'distribuicao', 'acesso'],
  };
  return !!acima.funcao && (permitidas[funcao ?? 'core_primario'] ?? []).includes(acima.funcao);
}

@Component({
  selector: 'app-cadastro-equipamento-rede',
  imports: [FormsModule, NgTemplateOutlet, RouterLink, CabecalhoRedeComponent, EsqueletoComponent, RackRedeComponent, SeletorPortaFaceComponent, SeletorVlansComponent,
    TrilhaEtapasComponent],
  styles: [`
    /* A frase da conexão: "Este switch, na porta X, está conectado em Y, na porta Y" */
    .frase-conexao { margin: 0 0 var(--spi-espaco-16); color: var(--spi-texto); }
    /* As duas portas lado a lado (empilham no celular), cada uma num cartão com borda de 1px */
    .portas-conexao { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--spi-espaco-16); margin-top: var(--spi-espaco-16); }
    .portas-conexao > section { padding: var(--spi-espaco-16); border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-g); }
    .portas-conexao h3 { margin: 0; font-size: var(--spi-texto-compacto); font-weight: 700; }
    /* Cabeçalho do cartão: título à esquerda e "Copiar da porta…" no canto superior direito */
    .cabecalho-porta { display: flex; align-items: center; justify-content: space-between; gap: var(--spi-espaco-8); flex-wrap: wrap; margin-bottom: var(--spi-espaco-12); }
    /* Blocos de escolha da porta pela face (deste equipamento e do outro), um embaixo do outro */
    .bloco-face { margin-bottom: var(--spi-espaco-16); padding: var(--spi-espaco-16); border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-g); }
    .bloco-face h3 { margin: 0 0 var(--spi-espaco-12); font-size: var(--spi-texto-compacto); font-weight: 700; }
    .bloco-face .grade-formulario { margin-top: var(--spi-espaco-12); }
    /* O rack desenhado na largura de um rack (não a da tela inteira), alinhado à esquerda */
    .rack-escolha { max-width: 520px; margin-bottom: var(--spi-espaco-8); }
    /* Respiro entre o campo de VLANs e as fichas de velocidade */
    .campo-velocidade { margin-top: var(--spi-espaco-8); }
    .rack-escolha > small { display: block; margin-top: var(--spi-espaco-8); }
    .revisao dl { display: grid; grid-template-columns: max-content 1fr; gap: var(--spi-espaco-8) var(--spi-espaco-16); margin: 0; }
    .revisao dt { color: var(--spi-apagado); font-weight: 600; }
    .revisao dd { margin: 0; }
    /* Botão "Testar e ler" na altura dos campos; o resultado num quadro com borda de 1px */
    .alinhado-campo { align-items: flex-end; justify-content: flex-start; padding-bottom: 16px; }
    .resultado-teste { display: grid; gap: 4px; margin-bottom: 16px; padding: 12px; border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-m);
      background: var(--spi-superficie-alt); small { color: var(--spi-apagado); } .aviso-teste { color: var(--spi-alerta); } }
  `],
  template: `
    <div class="modulo-chamados">
      <app-cabecalho-rede [titulo]="editando() ? 'Editar ' + (original()?.nome || 'equipamento') : 'Novo equipamento'"
        [trilha]="editando() && original() ? [{ rotulo: original()!.nome, rota: ['/rede/equipamentos', original()!.id] }, { rotulo: 'Editar' }] : [{ rotulo: 'Novo equipamento' }]"
        [descricao]="editando() ? 'O tipo, a função e o modelo de face não mudam depois de criado: para trocar, exclua e cadastre de novo.' : 'A rede é cadastrada de cima para baixo: core, distribuição, acesso e, por último, APs e demais.'" />
      @if (pronto()) {
        <section class="painel-gestao protocolo">
          @if (!editando()) { <app-trilha-etapas [etapas]="etapas()" ariaLabel="Etapas do cadastro do equipamento" /> }

          @if (passo() === 'dados') {
            <form class="grade-formulario" (ngSubmit)="avancar()" #fd="ngForm">
              <div><label for="ce-nome">Nome *</label>
                <input id="ce-nome" name="nome" required minlength="2" maxlength="150" placeholder="Ex.: SPI-SWAC-05A" [(ngModel)]="dados.nome" /></div>
              <div><label for="ce-tipo">Tipo *</label>
                <select id="ce-tipo" name="tipo" [disabled]="editando()" [(ngModel)]="dados.tipo" (ngModelChange)="trocouTipo()">
                  @for (t of tipos; track t[0]) { <option [value]="t[0]">{{ t[1] }}</option> }
                </select></div>
              @if (dados.tipo === 'switch') {
                <div><label for="ce-funcao">Função na topologia *</label>
                  <select id="ce-funcao" name="funcao" required [disabled]="editando()" [(ngModel)]="dados.funcao">
                    <option [ngValue]="null" disabled>Escolha</option>
                    @for (f of funcoes; track f[0]) { <option [ngValue]="f[0]">{{ f[1] }}</option> }
                  </select>
                  <small class="dica-formulario">Core no topo, depois distribuição e acesso. AP, roteador e "outro" ficam abaixo do acesso.</small></div>
              }
              <div><label for="ce-modelo">Modelo de face *</label>
                <select id="ce-modelo" name="modelo" required [disabled]="editando()" [(ngModel)]="dados.modelo_face_id" (ngModelChange)="ligacao.porta = null">
                  <option [ngValue]="null" disabled>Escolha</option>
                  @for (m of modelos(); track m.id) { <option [ngValue]="m.id">{{ m.nome }} ({{ m.linhas * m.colunas + m.portas_extras.length }} portas, {{ m.altura_u }}U)</option> }
                </select>
                <small class="dica-formulario">As portas são criadas pelo modelo, todas desligadas, menos a da conexão.</small></div>
              @if (!passivo(dados.tipo)) {
                <div><label for="ce-ip">IP de gerência</label>
                  <input id="ce-ip" name="ip" required maxlength="45" class="texto-codigo" placeholder="Ex.: 10.23.5.2" [(ngModel)]="dados.ip_gerencia" /></div>
              }
              @if (leituraAtiva && !passivo(dados.tipo)) {
                <!-- Acesso SSH só leitura (decisão do usuário: por equipamento): o SGI lê o equipamento e faz a carga -->
                <div class="ocupa-duas"><span class="rotulo-cartao">Acesso para leitura (SSH, só consulta)</span>
                  <small class="dica-formulario">Use uma conta só leitura do equipamento. O SGI envia apenas comandos de consulta (display/show) e guarda a senha cifrada.</small></div>
                <div><label for="ce-usuario">Usuário</label>
                  <input id="ce-usuario" name="usuario" maxlength="120" autocomplete="off" [(ngModel)]="dados.acesso_usuario" /></div>
                <div><label for="ce-senha">Senha</label>
                  <input id="ce-senha" name="senha" type="password" maxlength="200" autocomplete="new-password"
                    [placeholder]="editando() && original()?.tem_acesso ? 'Deixe em branco para manter a senha gravada' : ''" [(ngModel)]="senha" /></div>
                <div><label for="ce-porta-ssh">Porta SSH</label>
                  <input id="ce-porta-ssh" name="porta-ssh" type="number" min="1" max="65535" [(ngModel)]="dados.acesso_porta" /></div>
                @if (!editando()) {
                  <div class="acoes-formulario alinhado-campo">
                    <button type="button" class="acao-secundaria" [class.carregando]="testando()" [disabled]="testando() || !podeTestar()" (click)="testar()">Testar e ler o equipamento</button>
                  </div>
                  @if (teste(); as t) {
                    <!-- O que foi lido (nada gravado ainda): confere o equipamento e já sugere a conexão -->
                    <div class="ocupa-duas resultado-teste">
                      <strong>{{ t.nome || 'Equipamento' }}</strong> · {{ t.modelo || 'modelo não lido' }}{{ t.versao ? ' · versão ' + t.versao : '' }}
                      <small>Série {{ t.serie || '—' }} · {{ t.portas }} portas · {{ t.vlans }} VLANs · {{ t.vizinhos.length }} vizinho(s) LLDP</small>
                      @if (t.sugestao) { <small>Conexão sugerida pelo LLDP: {{ t.sugestao.texto }} (já preenchida no passo Conexão).</small> }
                      @for (a of t.avisos; track $index) { <small class="aviso-teste">{{ a }}</small> }
                    </div>
                  }
                }
              }
              <!-- Rack e U obrigatórios, menos no access point (decisão do usuário, 17/11/2026) -->
              <div><label for="ce-rack">Rack{{ rackObrigatorio() ? ' *' : '' }}</label>
                <select id="ce-rack" name="rack" [required]="rackObrigatorio()" [(ngModel)]="dados.rack_id" (ngModelChange)="trocouRack()">
                  <option [ngValue]="null" [disabled]="rackObrigatorio()">{{ rackObrigatorio() ? 'Escolha' : 'Fora de rack' }}</option>
                  @for (r of racks(); track r.id) { <option [ngValue]="r.id">{{ r.nome }} ({{ r.altura_u }}U)</option> }
                </select></div>
              <div><label for="ce-u">Posição no rack (U){{ rackObrigatorio() ? ' *' : '' }}</label>
                <input id="ce-u" name="u" type="number" min="1" max="60" [required]="!!dados.rack_id" [disabled]="!dados.rack_id" placeholder="Clique num U livre no rack abaixo" [(ngModel)]="dados.posicao_u" /></div>
              @if (rackEscolhido(); as r) {
                <!-- O rack escolhido, com o que já está montado: clicar num U livre pergunta Sim/Não e preenche a posição -->
                <div class="ocupa-duas rack-escolha">
                  <app-rack-rede [rack]="r" [equipamentos]="doRack(r.id)" [escolha]="true" [alturaNova]="alturaModelo()" [uEscolhido]="dados.posicao_u"
                    [nomeNovo]="dados.nome" [ignorarId]="idEditado" (pedirU)="pedirU($event)" />
                  <small class="dica-formulario">Clique num U livre para colocar o equipamento ({{ alturaModelo() }}U{{ dados.modelo_face_id ? ', pelo modelo' : '; escolha o modelo para saber a altura' }}).</small>
                </div>
              }
              <div><label for="ce-serie">Número de série</label><input id="ce-serie" name="serie" maxlength="120" [(ngModel)]="dados.numero_serie" /></div>
              @if (editando()) { <div><label class="linha-caixa"><input type="checkbox" name="ativo" [(ngModel)]="dados.ativo" /> Ativo</label></div> }
              <div class="ocupa-duas"><label for="ce-obs">Observação <small>(opcional)</small></label>
                <textarea id="ce-obs" name="obs" rows="2" maxlength="4000" [(ngModel)]="dados.observacao"></textarea></div>
              <div class="ocupa-duas acoes-formulario">
                @if (editando()) {
                  <button type="button" class="acao-perigo" (click)="excluir()">Excluir equipamento</button>
                  <a class="acao-secundaria" [routerLink]="['/rede/equipamentos', original()!.id]">Cancelar</a>
                  <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fd.invalid || salvando()">Salvar</button>
                } @else {
                  <a class="acao-secundaria" routerLink="/rede">Cancelar</a>
                  <button type="submit" class="acao-primaria" [disabled]="fd.invalid">Avançar</button>
                }
              </div>
            </form>
          }

          @if (passo() === 'conexao') {
            @if (!precisaLigacao()) {
              <p class="dica-formulario">{{ passivo(dados.tipo) ? 'O patch panel não precisa de conexão no cadastro: os cabos do Terminal Punch Down e do Conector RJ45 de cada porta são ligados depois, na tela da porta.' : 'O core primário é o topo da rede: não fica ligado a ninguém acima dele.' }}</p>
              <div class="acoes-formulario">
                <button type="button" class="acao-secundaria" (click)="passo.set('dados')">Voltar</button>
                <button type="button" class="acao-primaria" (click)="passo.set('revisao')">Avançar</button>
              </div>
            } @else {
              <form (ngSubmit)="avancar()" #fc="ngForm">
                <p class="frase-conexao">Este {{ rotuloTipo(dados.tipo).toLowerCase() }} <strong>{{ dados.nome }}</strong>, na porta escolhida abaixo, está conectado
                  em {{ rotuloAcima() }} (direto ou passando por um patch panel).</p>
                <!-- Porta deste equipamento: escolhida na face (desenhada pelo modelo; todas livres, o equipamento ainda não existe) -->
                <section class="bloco-face" aria-labelledby="cc-face-propria">
                  <h3 id="cc-face-propria">Porta deste equipamento ({{ dados.nome }}) *</h3>
                  <app-seletor-porta-face nome="cc-porta" rotulo="Porta deste equipamento" [modelo]="modeloEscolhido()" [posicoes]="posicoesProprias()"
                    [opcoes]="opcoesProprias()" [valor]="ligacao.porta === null ? null : '' + ligacao.porta" (valorChange)="ligacao.porta = +$event" />
                </section>
                <div class="grade-formulario">
                  <div class="ocupa-duas"><label for="cc-equip">Conectado em *</label>
                    <select id="cc-equip" name="equip" required [(ngModel)]="ligacao.equipamento" (ngModelChange)="escolheuDestino($event)">
                      <option [ngValue]="null" disabled>Escolha</option>
                      @for (e of candidatos(); track e.id) { <option [ngValue]="e.id">{{ e.nome }} · {{ e.tipo === 'patch_panel' ? 'Patch panel' : rotuloFuncao(e.funcao) }}</option> }
                    </select>
                    @if (destinos() !== null && !candidatos().length) { <small class="dica-formulario">Nenhum equipamento com porta livre que leve a {{ rotuloAcima() }}: cadastre ou ligue antes {{ rotuloAcima() }}.</small> }
                    @else { <small class="dica-formulario">Só aparecem os equipamentos com porta livre que serve: {{ rotuloAcima() }}, ou um patch panel cuja porta leva até ele.</small> }</div>
                </div>
                @if (destinoDetalhe(); as d) {
                  <!-- Porta do outro equipamento: a face dele; só as portas que servem ficam clicáveis -->
                  <section class="bloco-face" aria-labelledby="cc-face-destino">
                    <h3 id="cc-face-destino">{{ d.nome }} · {{ d.tipo === 'patch_panel' ? 'Patch panel' : rotuloFuncao(d.funcao) }}: porta *</h3>
                    <app-seletor-porta-face nome="cc-destino" [rotulo]="'Porta de ' + d.nome" [modelo]="d.modelo" [posicoes]="d.posicoes"
                      [opcoes]="opcoesDestino()" [valor]="ligacao.destino" (valorChange)="ligacao.destino = $event; escolheuPortaDestino()" />
                    @if (destinoEhPatch() && ligacao.destino) {
                      <div class="grade-formulario">
                        <div><label for="cc-lado">Lado da porta do patch panel *</label>
                          <select id="cc-lado" name="lado" required [(ngModel)]="ligacao.lado">
                            <option [ngValue]="null" disabled>Escolha</option>
                            @for (l of lados; track l.valor) { <option [ngValue]="l.valor" [disabled]="!ladoElegivel(l.valor)">{{ l.rotulo }}{{ ladoElegivel(l.valor) ? '' : ' (ocupado ou não leva acima)' }}</option> }
                          </select>
                          @if (ligacao.lado) {
                            <small class="dica-formulario">Do outro lado desta porta: {{ outroLadoTexto() || 'nada ligado' }}</small>
                          }</div>
                      </div>
                    }
                  </section>
                }
                <div class="portas-conexao">
                  <section aria-labelledby="cc-cfg-propria">
                    <header class="cabecalho-porta"><h3 id="cc-cfg-propria">Porta {{ nomePortaPropria() || '—' }} (este equipamento)</h3>
                      @if (ligacao.destino && !destinoEhPatch() && podeCopiar(cfgDestino, cfgPropria)) {
                        <button type="button" class="acao-secundaria acao-pequena" (click)="cfgPropria = copiaConfig(cfgDestino)">Copiar da porta {{ nomePortaDestino() }}</button>
                      }
                    </header>
                    <ng-container *ngTemplateOutlet="configPorta; context: { $implicit: cfgPropria, chave: 'propria' }" /></section>
                  @if (ligacao.destino && !destinoEhPatch()) {
                    <section aria-labelledby="cc-cfg-destino">
                      <header class="cabecalho-porta"><h3 id="cc-cfg-destino">Porta {{ nomePortaDestino() }} ({{ nomeDestino() }})</h3>
                        @if (podeCopiar(cfgPropria, cfgDestino)) {
                          <button type="button" class="acao-secundaria acao-pequena" (click)="cfgDestino = copiaConfig(cfgPropria)">Copiar da porta {{ nomePortaPropria() || 'deste equipamento' }}</button>
                        }
                      </header>
                      @if (destinoConfigurado()) { <p class="dica-formulario">Esta porta já tinha configuração: ela aparece abaixo e pode ser ajustada.</p> }
                      <ng-container *ngTemplateOutlet="configPorta; context: { $implicit: cfgDestino, chave: 'destino' }" /></section>
                  }
                </div>
                <div class="acoes-formulario">
                  <button type="button" class="acao-secundaria" (click)="passo.set('dados')">Voltar</button>
                  <button type="submit" class="acao-primaria" [disabled]="fc.invalid || !conexaoCompleta()">Avançar</button>
                </div>
              </form>
            }
          }

          @if (passo() === 'revisao') {
            <div class="revisao">
              <dl>
                <dt>Nome</dt><dd>{{ dados.nome }}</dd>
                <dt>Tipo</dt><dd>{{ rotuloTipo(dados.tipo) }}{{ dados.funcao ? ' · ' + rotuloFuncao(dados.funcao) : '' }}</dd>
                <dt>Modelo de face</dt><dd>{{ nomeModelo() }}</dd>
                @if (dados.ip_gerencia) { <dt>IP de gerência</dt><dd class="texto-codigo">{{ dados.ip_gerencia }}</dd> }
                @if (leituraAtiva && dados.acesso_usuario) { <dt>Acesso SSH</dt><dd>{{ dados.acesso_usuario }} · porta {{ dados.acesso_porta }} (o equipamento é lido logo depois de cadastrado)</dd> }
                @if (precisaLigacao()) {
                  <dt>Conexão</dt>
                  <dd>Porta <span class="texto-codigo">{{ nomePortaPropria() }}</span> ({{ resumoConfig(cfgPropria) }}) ligada em {{ nomeDestino() }},
                    porta <span class="texto-codigo">{{ nomePortaDestino() }}</span>{{ ligacao.lado ? ' (' + ligacao.lado + ')' : '' }}{{ !destinoEhPatch() ? ' (' + resumoConfig(cfgDestino) + ')' : '' }}</dd>
                }
                <dt>Demais portas</dt><dd>Desligadas e em branco, até alguém ligar algo nelas.</dd>
              </dl>
            </div>
            <div class="acoes-formulario">
              <button type="button" class="acao-secundaria" (click)="passo.set('conexao')">Voltar</button>
              <button type="button" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando()" (click)="salvar()">Cadastrar equipamento</button>
            </div>
          }
        </section>

        <!-- Configuração de uma porta (a deste equipamento ou a do outro): o que o modo aceita aparece -->
        <ng-template #configPorta let-cfg let-chave="chave">
          <div class="grade-formulario">
            <div class="ocupa-duas"><label [for]="'cfg-modo-' + chave">Modo</label>
              <select [id]="'cfg-modo-' + chave" [name]="'modo-' + chave" [(ngModel)]="cfg.modo">
                @for (m of modos; track m.valor) { <option [value]="m.valor">{{ m.rotulo }}</option> }
              </select></div>
            @if (modo(cfg).nativa) {
              <div><label [for]="'cfg-nativa-' + chave">{{ modo(cfg).nativa }}</label>
                <select [id]="'cfg-nativa-' + chave" [name]="'nativa-' + chave" [(ngModel)]="cfg.vlan_nativa_id">
                  <option [ngValue]="null">Nenhuma</option>
                  @for (v of vlans(); track v.id) { <option [ngValue]="v.id">{{ v.numero }} · {{ v.nome }}</option> }
                </select></div>
            }
            @if (modo(cfg).ip) {
              <div><label [for]="'cfg-ip-' + chave">IP da interface</label>
                <input [id]="'cfg-ip-' + chave" [name]="'ip-' + chave" maxlength="49" class="texto-codigo" placeholder="Ex.: 10.23.0.1/30" [(ngModel)]="cfg.ip_interface" /></div>
            }
            @if (modo(cfg).semTag) {
              <div class="ocupa-duas">
                <app-seletor-vlans [idCampo]="'cfg-sem-tag-' + chave" rotuloCampo="VLANs sem tag" detalheRotulo="(untagged, além da PVID)" prefixoResumo="Sem tag"
                  rotulo="Adicionar VLAN sem tag" [vlans]="vlans()" [valor]="cfg.vlans_sem_tag" [excluir]="cfg.vlans_tag" [podeGerir]="!!papeis()?.administrar"
                  (valorChange)="cfg.vlans_sem_tag = $event" (vlanAlterada)="atualizarVlan($event)" /></div>
            }
            @if (modo(cfg).tag) {
              <div class="ocupa-duas">
                <app-seletor-vlans [idCampo]="'cfg-tag-' + chave" rotuloCampo="VLANs com tag" detalheRotulo="(tagged)" prefixoResumo="Com tag"
                  rotulo="Adicionar VLAN com tag" [vlans]="vlans()" [valor]="cfg.vlans_tag" [excluir]="cfg.vlans_sem_tag" [podeGerir]="!!papeis()?.administrar"
                  (valorChange)="cfg.vlans_tag = $event" (vlanAlterada)="atualizarVlan($event)" /></div>
            }
            <!-- Velocidade com um clique (clicar de novo na escolhida desmarca) -->
            <div class="ocupa-duas campo-velocidade"><label [id]="'cfg-vel-' + chave">Velocidade</label>
              <div class="chips-filtro" role="group" [attr.aria-labelledby]="'cfg-vel-' + chave">
                @for (v of velocidades; track v.valor) {
                  <button type="button" [class.ativo]="cfg.velocidade_mbps === v.valor" [attr.aria-pressed]="cfg.velocidade_mbps === v.valor"
                    (click)="cfg.velocidade_mbps = cfg.velocidade_mbps === v.valor ? null : v.valor">{{ v.rotulo }}</button>
                }
              </div></div>
          </div>
        </ng-template>
      } @else {
        <app-esqueleto tipo="painel" />
      }
    </div>
  `,
})
export class CadastroEquipamentoRedeComponent implements OnInit {
  private readonly api = inject(RedeApiService);
  private readonly dialogos = inject(DialogosService);
  /** O app roda sem zone.js: depois de uma resposta assíncrona (a confirmação Sim/Não) é preciso avisar que a tela mudou. */
  private readonly deteccao = inject(ChangeDetectorRef);
  private readonly roteador = inject(Router);
  protected readonly idEditado = inject(ActivatedRoute).snapshot.paramMap.get('id');
  protected readonly papeis = inject(AcessoService).rede;

  protected readonly editando = signal(!!this.idEditado);
  protected readonly original = signal<EquipamentoDetalhe | null>(null);
  protected readonly modelos = signal<ModeloFace[]>([]);
  protected readonly racks = signal<Rack[]>([]);
  protected readonly vlans = signal<Vlan[]>([]);
  protected readonly equipamentos = signal<EquipamentoResumo[]>([]);
  /** Portas do equipamento escolhido em "Conectado em" (com o que já está ligado nelas). */
  protected readonly portasDestino = signal<Porta[]>([]);
  /** O equipamento escolhido em "Conectado em", com o modelo e as posições (para desenhar a face). */
  protected readonly destinoDetalhe = signal<EquipamentoDetalhe | null>(null);
  /** Equipamentos e portas elegíveis para a ligação (null = ainda carregando). */
  protected readonly destinos = signal<DestinoCadastro[] | null>(null);
  protected readonly velocidades = VELOCIDADES;
  protected readonly salvando = signal(false);
  protected readonly pronto = signal(!this.idEditado);
  /** Senha SSH digitada (só vai na gravação; em branco na edição mantém a gravada). */
  protected senha = '';
  /** Leitura por SSH ligada? (desligada por enquanto: o cadastro não pede usuário e senha) */
  protected readonly leituraAtiva = LEITURA_SSH_ATIVA;
  protected readonly testando = signal(false);
  protected readonly teste = signal<ResultadoTesteLeitura | null>(null);
  protected readonly passo = signal<Passo>('dados');

  protected readonly tipos = Object.entries(ROTULOS_TIPO_EQUIPAMENTO) as [TipoEquipamento, string][];
  protected readonly funcoes = Object.entries(ROTULOS_FUNCAO_EQUIPAMENTO) as [FuncaoEquipamento, string][];
  protected readonly modos = MODOS_PORTA;
  protected readonly lados = LADOS_PATCH;
  protected readonly passivo = ehPassivo;
  protected dados = dadosVazios();
  protected ligacao: { porta: number | null; equipamento: string | null; destino: string | null; lado: LadoPatch | null } =
    { porta: null, equipamento: null, destino: null, lado: null };
  protected cfgPropria = configVazia();
  protected cfgDestino = configVazia();

  /** Trilha do cadastro: Dados → Conexão → Revisão (a atual em vermelho, as anteriores concluídas). */
  protected readonly etapas = computed<EtapaTrilha[]>(() => {
    const ordem: Passo[] = ['dados', 'conexao', 'revisao'];
    const atual = ordem.indexOf(this.passo());
    const rotulos: Record<Passo, string> = { dados: 'Dados', conexao: 'Conexão', revisao: 'Revisão' };
    return ordem.map((p, i) => ({ id: p, rotulo: rotulos[p], estado: i < atual ? 'concluida' : i === atual ? 'atual' : 'aguardando' }));
  });

  ngOnInit(): void {
    this.api.modelos().subscribe({ next: (x) => this.modelos.set(x), error: () => undefined });
    this.api.racks().subscribe({ next: (x) => this.racks.set(x), error: () => undefined });
    this.api.vlans().subscribe({ next: (x) => this.vlans.set(x), error: () => undefined });
    this.api.equipamentos().subscribe({ next: (x) => this.equipamentos.set(x), error: () => undefined });
    if (this.idEditado) {
      this.api.equipamento(this.idEditado).subscribe({
        next: (e) => {
          this.original.set(e);
          this.dados = { nome: e.nome, tipo: e.tipo, modelo_face_id: e.modelo_face_id, bem_id: e.bem_id, localizacao_id: e.localizacao_id, rack_id: e.rack_id,
            posicao_u: e.posicao_u, ip_gerencia: e.ip_gerencia, numero_serie: e.numero_serie, observacao: e.observacao, ativo: e.ativo, funcao: e.funcao,
            acesso_usuario: e.acesso_usuario ?? '', acesso_porta: e.acesso_porta ?? 22 };
          this.pronto.set(true);
        },
        error: (x) => this.dialogos.mostrarErro(x, 'Não foi possível abrir o equipamento'),
      });
    }
  }

  protected podeTestar(): boolean {
    return !!this.dados.ip_gerencia.trim() && !!this.dados.acesso_usuario?.trim() && !!this.senha;
  }

  /**
   * "Testar e ler o equipamento": entra por SSH só leitura (nada é gravado), confere o acesso e preenche o que der: nome e série (se vazios)
   * e o passo Conexão, pela porta de subida vista no LLDP.
   */
  protected testar(): void {
    this.testando.set(true);
    this.teste.set(null);
    this.api.testarLeitura({ ip: this.dados.ip_gerencia.trim(), usuario: this.dados.acesso_usuario!.trim(), senha: this.senha, porta: this.dados.acesso_porta || 22,
      modelo_face_id: this.dados.modelo_face_id, tipo: this.dados.tipo, funcao: this.dados.funcao }).subscribe({
      next: (t) => {
        this.testando.set(false);
        this.teste.set(t);
        if (!this.dados.nome.trim() && t.nome) this.dados.nome = t.nome;
        if (!this.dados.numero_serie.trim() && t.serie) this.dados.numero_serie = t.serie;
        if (t.sugestao) {
          this.ligacao.porta = t.sugestao.porta_numero;
          this.ligacao.equipamento = t.sugestao.destino_equipamento_id;
          // As portas do equipamento de cima chegam depois: a porta sugerida fica pendente e é marcada quando elas chegarem
          this.escolheuDestino(t.sugestao.destino_equipamento_id, t.sugestao.destino_porta_id);
        }
      },
      error: (e) => { this.testando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível ler o equipamento'); },
    });
  }

  protected trocouTipo(): void {
    if (this.dados.tipo !== 'switch') this.dados.funcao = null;
    if (ehPassivo(this.dados.tipo)) this.dados.ip_gerencia = '';
  }

  /** Todo equipamento entra ligado a quem fica acima dele, menos o core primário (o topo) e o patch panel. */
  protected precisaLigacao(): boolean {
    return !ehPassivo(this.dados.tipo) && !(this.dados.tipo === 'switch' && this.dados.funcao === 'core_primario');
  }

  protected rotuloAcima(): string {
    if (this.dados.tipo !== 'switch') return 'um switch de acesso';
    const rotulos: Partial<Record<FuncaoEquipamento, string>> = { core_secundario: 'o core primário', distribuicao: 'um core', acesso: 'uma distribuição, um core ou outro switch de acesso' };
    return (this.dados.funcao && rotulos[this.dados.funcao]) || 'quem fica acima';
  }

  /**
   * Lista de "Conectado em" (pedido do usuário, 17/11/2026): só os elegíveis, que a API calcula com as regras da cadeia (switch que pode
   * ficar acima e chega ao core, com porta livre; patch panel com uma porta cujo outro lado leva a ele). Antes de a API responder, usa a
   * regra local (sem os patch panels) para a lista não ficar vazia.
   */
  protected candidatos(): EquipamentoResumo[] {
    const destinos = this.destinos();
    if (destinos === null) return this.equipamentos().filter((e) => podeFicarAcima(this.dados.tipo, this.dados.funcao, e));
    const ids = new Set(destinos.map((d) => d.equipamento_id));
    return this.equipamentos().filter((e) => ids.has(e.id));
  }

  /** Portas (e lados) que servem no equipamento escolhido em "Conectado em". */
  private elegiveisDoDestino(): { porta_id: string; lado: LadoPatch | null }[] {
    return this.destinos()?.find((d) => d.equipamento_id === this.ligacao.equipamento)?.portas ?? [];
  }

  // ----- Rack e U (passo Dados) -----

  /** Rack e U obrigatórios em todo equipamento, menos no access point (decisão do usuário, 17/11/2026). */
  protected rackObrigatorio(): boolean {
    return this.dados.tipo !== 'access_point';
  }

  protected rackEscolhido(): Rack | null {
    return this.racks().find((r) => r.id === this.dados.rack_id) ?? null;
  }

  protected doRack(rackId: string): EquipamentoResumo[] {
    return this.equipamentos().filter((e) => e.rack_id === rackId);
  }

  protected modeloEscolhido(): ModeloFace | null {
    return this.modelos().find((m) => m.id === this.dados.modelo_face_id) ?? null;
  }

  /** Quantos U o equipamento ocupa (do modelo; 1 enquanto não há modelo). */
  protected alturaModelo(): number {
    return Math.max(1, this.modeloEscolhido()?.altura_u ?? 1);
  }

  /** Trocou o rack: a posição de antes era de outro rack (na edição, voltar ao rack original devolve a posição original). */
  protected trocouRack(): void {
    this.dados.posicao_u = this.idEditado && this.dados.rack_id === this.original()?.rack_id ? this.original()!.posicao_u : null;
  }

  /** Clicou num U livre do desenho do rack: pergunta Sim/Não e, se sim, preenche a posição. */
  protected async pedirU(u: number): Promise<void> {
    const altura = this.alturaModelo();
    const ok = await this.dialogos.confirmar({ titulo: `Colocar no U${u}?`, simNao: true,
      mensagem: `${this.dados.nome || 'O equipamento'} vai ocupar ${altura > 1 ? `do U${u} ao U${u + altura - 1}` : `o U${u}`} do rack ${this.rackEscolhido()?.nome ?? ''}.` });
    if (!ok) return;
    this.dados.posicao_u = u;
    this.deteccao.markForCheck();
  }

  // ----- Portas pela face (passo Conexão) -----

  /** Posições das portas do equipamento novo (ele ainda não existe: vêm do modelo). */
  protected posicoesProprias(): Record<string, [number, number]> {
    return posicoesDoModelo(this.modeloEscolhido());
  }

  /** Portas deste equipamento: todas livres (as portas nascem no cadastro). */
  protected opcoesProprias(): OpcaoPortaFace[] {
    return this.portasDoModelo().map((x) => ({ id: String(x.numero), numero: x.numero, nome: x.nome, livre: true, dica: `Porta ${x.nome}` }));
  }

  /** Portas do outro equipamento: clicáveis só as que servem; nas outras, o que está ligado (ou por que não serve). */
  protected opcoesDestino(): OpcaoPortaFace[] {
    const elegiveis = this.elegiveisDoDestino();
    return this.portasDestino().map((p) => {
      const lados = elegiveis.filter((x) => x.porta_id === p.id);
      const nome = p.nome || String(p.numero_logico);
      const dica = lados.length ? (this.destinoEhPatch() ? `Livre: ${lados.map((x) => rotuloLado(x.lado)).join(' ou ')}` : 'Livre')
        : p.conexao?.texto || (this.destinoEhPatch() ? 'O outro lado desta porta não leva acima' : 'Não serve');
      return { id: p.id, numero: p.numero_logico, nome, livre: lados.length > 0, dica };
    });
  }

  /** O lado da porta do patch panel serve? (livre e o outro lado da mesma porta leva acima) */
  protected ladoElegivel(lado: LadoPatch): boolean {
    return this.elegiveisDoDestino().some((x) => x.porta_id === this.ligacao.destino && x.lado === lado);
  }

  // ----- Copiar a configuração de uma porta para a outra -----

  /** "Copiar da porta…" aparece quando a outra porta já tem algo preenchido e é diferente desta. */
  protected podeCopiar(origem: GravacaoPorta, alvo: GravacaoPorta): boolean {
    const preenchida = !!origem.vlan_nativa_id || origem.vlans_tag.length > 0 || origem.vlans_sem_tag.length > 0 || !!origem.vlan_voz_id
      || !!origem.ip_interface.trim() || origem.velocidade_mbps !== null || origem.modo !== configVazia().modo;
    return preenchida && JSON.stringify(this.copiaConfig(origem)) !== JSON.stringify(this.copiaConfig(alvo));
  }

  /** Cópia da configuração (modo, VLANs, IP e velocidade), com listas novas para uma não mexer na outra. */
  protected copiaConfig(c: GravacaoPorta): GravacaoPorta {
    return { observacao: '', modo: c.modo, vlan_nativa_id: c.vlan_nativa_id, vlans_tag: [...c.vlans_tag], vlans_sem_tag: [...c.vlans_sem_tag], vlan_voz_id: c.vlan_voz_id,
      ip_interface: c.ip_interface, velocidade_mbps: c.velocidade_mbps, duplex: c.duplex, status: 'up' };
  }

  protected portasDoModelo(): { numero: number; nome: string }[] {
    return portasDoModelo(this.modelos().find((m) => m.id === this.dados.modelo_face_id));
  }

  /** Escolheu o equipamento de cima: carrega as portas dele; `portaPendente` (sugestão do LLDP) é marcada quando elas chegam. */
  protected escolheuDestino(id: string | null, portaPendente: string | null = null): void {
    this.ligacao.destino = null;
    this.ligacao.lado = null;
    this.portasDestino.set([]);
    this.destinoDetalhe.set(null);
    if (!id) return;
    this.api.equipamento(id).subscribe({
      next: (e) => {
        this.portasDestino.set(e.portas);
        this.destinoDetalhe.set(e);
        if (portaPendente && e.portas.some((x) => x.id === portaPendente)) {
          this.ligacao.destino = portaPendente;
          this.escolheuPortaDestino();
        }
      },
      error: () => undefined,
    });
  }

  /** Porta de switch já usada: se ela tinha configuração (cadastro antigo), começa por ela; senão, pela configuração desta porta. */
  protected escolheuPortaDestino(): void {
    this.ligacao.lado = null;
    // Patch panel com um só lado que serve: já fica escolhido
    const lados = this.elegiveisDoDestino().filter((x) => x.porta_id === this.ligacao.destino);
    if (this.destinoEhPatch() && lados.length === 1) this.ligacao.lado = lados[0].lado;
    const p = this.portaDestino();
    if (!p || this.destinoEhPatch()) return;
    this.cfgDestino = this.destinoConfigurado()
      ? { observacao: '', modo: p.modo, vlan_nativa_id: p.vlan_nativa_id, vlans_tag: [...p.vlans_tag_ids], vlans_sem_tag: [...(p.vlans_sem_tag_ids ?? [])],
        vlan_voz_id: p.vlan_voz_id, ip_interface: p.ip_interface, velocidade_mbps: p.velocidade_mbps, duplex: p.duplex, status: 'up' }
      : { ...this.cfgPropria, vlans_tag: [...this.cfgPropria.vlans_tag], vlans_sem_tag: [...this.cfgPropria.vlans_sem_tag] };
  }

  private portaDestino(): Porta | undefined {
    return this.portasDestino().find((x) => x.id === this.ligacao.destino);
  }

  protected destinoEhPatch(): boolean {
    return this.equipamentos().find((e) => e.id === this.ligacao.equipamento)?.tipo === 'patch_panel';
  }



  /** O que está do outro lado da porta do patch panel escolhida (é o que vale para a regra da cadeia). */
  protected outroLadoTexto(): string {
    const p = this.portaDestino();
    if (!p || !this.ligacao.lado) return '';
    return (this.ligacao.lado === 'fundo' ? p.frente : p.fundo)?.texto ?? '';
  }

  protected destinoConfigurado(): boolean {
    const p = this.portaDestino();
    return !!p && (p.modo !== 'access' || !!p.vlan_nativa_id || p.vlans_tag_ids.length > 0);
  }

  protected conexaoCompleta(): boolean {
    return this.ligacao.porta !== null && !!this.ligacao.destino && (!this.destinoEhPatch() || !!this.ligacao.lado);
  }

  protected avancar(): void {
    if (this.editando()) {
      this.salvarEdicao();
      return;
    }
    if (this.passo() === 'dados') {
      this.passo.set('conexao');
      this.carregarDestinos();
    } else {
      this.passo.set('revisao');
    }
  }

  /** Busca os elegíveis para o tipo e a função do passo Dados (podem ter mudado ao voltar). */
  private carregarDestinos(): void {
    if (!this.precisaLigacao()) return;
    this.destinos.set(null);
    this.api.destinosCadastro(this.dados.tipo, this.dados.funcao).subscribe({
      next: (d) => {
        this.destinos.set(d);
        // O que estava escolhido deixou de servir (voltou e trocou a função): limpa
        if (this.ligacao.equipamento && !d.some((x) => x.equipamento_id === this.ligacao.equipamento)) {
          this.ligacao.equipamento = null;
          this.escolheuDestino(null);
        }
      },
      error: (e) => { this.destinos.set([]); this.dialogos.mostrarErro(e, 'Não foi possível listar onde o equipamento pode ser ligado'); },
    });
  }

  /** Só o que o modo aceita vai para a API (o que ficou marcado de outro modo é descartado). */
  private limpa(cfg: GravacaoPorta): GravacaoPorta {
    const m = modoPorta(cfg.modo);
    return { ...cfg, status: 'up', vlan_nativa_id: m.nativa ? cfg.vlan_nativa_id : null, vlans_tag: m.tag ? cfg.vlans_tag : [], vlans_sem_tag: m.semTag ? cfg.vlans_sem_tag : [],
      vlan_voz_id: m.voz ? cfg.vlan_voz_id : null, ip_interface: m.ip ? cfg.ip_interface.trim() : '' };
  }

  protected salvar(): void {
    const ligacao = this.precisaLigacao() ? {
      porta_numero: this.ligacao.porta!, destino_porta_id: this.ligacao.destino!, destino_lado: this.destinoEhPatch() ? this.ligacao.lado : null,
      config: this.limpa(this.cfgPropria), config_destino: this.destinoEhPatch() ? null : this.limpa(this.cfgDestino),
    } : null;
    this.salvando.set(true);
    this.api.salvarEquipamento(null, { ...this.dados, posicao_u: this.dados.rack_id ? this.dados.posicao_u : null, ligacao, acesso_senha: this.leituraAtiva ? this.senha || null : null }).subscribe({
      // Com acesso SSH, a tela do equipamento já abre lendo o equipamento (a carga) e mostra o resumo para aplicar
      next: (e) => void this.roteador.navigate(['/rede/equipamentos', e.id], { queryParams: this.leituraAtiva && this.dados.acesso_usuario && this.senha ? { ler: 1 } : {} }),
      error: (x) => { this.salvando.set(false); this.dialogos.mostrarErro(x, 'Não foi possível cadastrar o equipamento'); },
    });
  }

  private salvarEdicao(): void {
    this.salvando.set(true);
    this.api.salvarEquipamento(this.idEditado, { ...this.dados, posicao_u: this.dados.rack_id ? this.dados.posicao_u : null, acesso_senha: this.leituraAtiva ? this.senha || null : null }).subscribe({
      next: (e) => void this.roteador.navigate(['/rede/equipamentos', e.id]),
      error: (x) => { this.salvando.set(false); this.dialogos.mostrarErro(x, 'Não foi possível salvar'); },
    });
  }

  protected async excluir(): Promise<void> {
    const e = this.original();
    if (!e) return;
    const ok = await this.dialogos.confirmar({ titulo: `Excluir ${e.nome}?`, mensagem: 'As portas e as ligações dele vão junto, e as portas do outro lado ficam desligadas. '
      + 'Não sai se algum equipamento depender só dele para chegar ao core.', rotuloConfirmar: 'Excluir equipamento', segundos: 3, perigo: true });
    if (!ok) return;
    this.api.excluirEquipamento(e.id).subscribe({ next: () => void this.roteador.navigate(['/rede']), error: (x) => this.dialogos.mostrarErro(x, 'Não foi possível excluir') });
  }

  protected atualizarVlan(nova: Vlan): void {
    this.vlans.update((lista) => lista.map((v) => (v.id === nova.id ? nova : v)));
  }

  protected modo(cfg: GravacaoPorta) {
    return modoPorta(cfg.modo);
  }

  protected resumoConfig(cfg: GravacaoPorta): string {
    const c = this.limpa(cfg);
    const numero = (id: string | null) => this.vlans().find((v) => v.id === id)?.numero ?? null;
    return textoVlanPorta({ modo: c.modo, vlan_nativa: numero(c.vlan_nativa_id), vlans_tag: c.vlans_tag.map((i) => numero(i)!).filter((n) => n !== null),
      vlans_sem_tag: c.vlans_sem_tag.map((i) => numero(i)!).filter((n) => n !== null), vlan_voz: numero(c.vlan_voz_id), ip_interface: c.ip_interface } as Porta);
  }

  protected nomeModelo(): string {
    return this.modelos().find((m) => m.id === this.dados.modelo_face_id)?.nome ?? '—';
  }

  protected nomePortaPropria(): string {
    return this.portasDoModelo().find((x) => x.numero === this.ligacao.porta)?.nome ?? '';
  }

  protected nomeDestino(): string {
    return this.equipamentos().find((e) => e.id === this.ligacao.equipamento)?.nome ?? '';
  }

  protected nomePortaDestino(): string {
    const p = this.portaDestino();
    return p ? p.nome || String(p.numero_logico) : '';
  }

  protected rotuloTipo(t: TipoEquipamento): string {
    return ROTULOS_TIPO_EQUIPAMENTO[t];
  }

  protected rotuloFuncao(f: FuncaoEquipamento | null): string {
    return f ? ROTULOS_FUNCAO_EQUIPAMENTO[f] : 'sem função';
  }
}
