// Criado por José Eduardo Santana Martins
// Este arquivo serve para mostrar um equipamento de rede: dados, portas (configuração, o que está ligado, ponto e chamados) e a leitura por SSH; a edição tem página própria.

import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { AcessoService } from '../../core/acesso/acesso.service';
import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRedeComponent } from './cabecalho-rede.component';
import { FaceRedeComponent } from './face-rede.component';
import { RedeApiService } from './rede-api.service';
import {
  AplicacaoLeitura, COR_STATUS_PORTA, ehPassivo, EquipamentoDetalhe, LEITURA_SSH_ATIVA, Porta, ResumoLeitura, ROTULOS_FUNCAO_EQUIPAMENTO, ROTULOS_PING, ROTULOS_STATUS_PORTA, ROTULOS_TIPO_EQUIPAMENTO, textoVlanPorta,
  TipoEquipamento, velocidade,
} from './rede.models';

@Component({
  selector: 'app-equipamento-rede',
  imports: [DatePipe, NgTemplateOutlet, RouterLink, CabecalhoRedeComponent, EsqueletoComponent, FaceRedeComponent],
  styles: [`
    .titulo-lista-portas { margin: 8px 0 10px; font-size: var(--spi-texto-destaque); font-weight: 700; }
    /* Dados do equipamento: pares rótulo/valor em colunas que se ajustam à largura (empilham no celular) */
    .dados-equipamento { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--spi-espaco-12) var(--spi-espaco-24);
      margin: var(--spi-espaco-16) 0; padding: var(--spi-espaco-16); border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-g);
      dt { color: var(--spi-apagado); font-size: var(--spi-texto-legenda); font-weight: 600; }
      dd { display: flex; flex-wrap: wrap; align-items: center; gap: var(--spi-espaco-8); margin: var(--spi-espaco-4) 0 0; }
      dd small { color: var(--spi-apagado); }
      .ocupa-largo { grid-column: span 2; } }
    @media (max-width: 600px) { .dados-equipamento .ocupa-largo { grid-column: auto; } }
    /* "Ligado a": o botão (ou o texto) na linha; no patch panel, uma linha por lado, com o rótulo do lado em cinza */
    .ligado-celula { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
    .ligado-celula + .ligado-celula { margin-top: 6px; }
    .ligado-celula small { min-width: 44px; color: var(--spi-apagado); }
    /* Resumo da leitura: grupos com título, uma linha por item; item que não se aplica fica apagado */
    .resumo-leitura { display: grid; gap: var(--spi-espaco-8); margin: var(--spi-espaco-12) 0; }
    .resumo-leitura .rotulo-cartao { margin-top: var(--spi-espaco-8); }
    .lista-leitura { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none;
      li { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; } small { color: var(--spi-apagado); } }
    .apagada { opacity: .55; }
    .aviso-leitura { color: var(--spi-alerta); margin: 0; }
  `],
  template: `
    <div class="modulo-chamados">
      <app-cabecalho-rede [titulo]="e()?.nome || 'Equipamento'" [trilha]="[{ rotulo: e()?.nome || 'Equipamento' }]" [descricao]="e() ? rotuloTipo(e()!.tipo) + (e()!.modelo_nome ? ' · ' + e()!.modelo_nome : '') : ''" />
      @if (e(); as e) {
        <section class="painel-gestao protocolo">
          @if (papeis()?.administrar) {
            <!-- Edição em página própria (decisão do usuário), com o botão principal vermelho -->
            <div class="barra-protocolo"><span class="espacador"></span>
              @if (leituraAtiva && !passivo(e.tipo)) {
                <!-- Carga por SSH só leitura (decisão do usuário): lê de novo o equipamento e mostra o resumo para aplicar -->
                <button type="button" class="acao-secundaria" [class.carregando]="lendo()" [disabled]="lendo() || !e.tem_acesso"
                  [title]="e.tem_acesso ? '' : 'Cadastre o usuário e a senha SSH em Editar'" (click)="ler()">Recarregar do equipamento</button>
              }
              <a class="acao-primaria" [routerLink]="['/rede/equipamentos', e.id, 'editar']">Editar</a></div>
          }
          @if (!leituraAtiva) {
            <!-- Leitura por SSH desligada por enquanto (decisão do usuário): resumo e última leitura escondidos -->
          } @else if (resumo(); as r) {
            <!-- Resumo da leitura: o que o equipamento tem de diferente do cadastro; a pessoa marca o que aplicar -->
            <section class="cartao-chamado resumo-leitura" aria-labelledby="re-leitura">
              <header><h2 id="re-leitura">Lido do equipamento</h2>
                <small>em <span class="texto-codigo">{{ r.lido_em | date: 'dd/MM/yyyy HH:mm' }}</span> por {{ r.lido_por }}@if (r.aplicada_em) { · aplicado em <span class="texto-codigo">{{ r.aplicada_em | date: 'dd/MM/yyyy HH:mm' }}</span> }</small></header>
              @if (r.lldp.length) {
                <h3 class="rotulo-cartao">Ligações pelos vizinhos LLDP (feitas sozinhas)</h3>
                <ul class="lista-leitura">
                  @for (v of r.lldp; track $index) {
                    <li><span class="texto-codigo">{{ v.interface_local }}</span> → {{ v.vizinho_nome }} · <span class="texto-codigo">{{ v.vizinho_interface }}</span>
                      <span class="selo-status" [attr.data-chamado]="v.situacao === 'ligada' ? 'sucesso' : v.situacao === 'ja_estava' ? 'neutro' : 'alerta'">{{ v.situacao === 'ligada' ? 'Ligada agora' : v.situacao === 'ja_estava' ? 'Já estava ligada' : 'Não ligada' }}</span>
                      @if (v.motivo) { <small>{{ v.motivo }}</small> }</li>
                  }
                </ul>
              }
              @if (!r.aplicada_em && papeis()?.administrar) {
                @if (r.equipamento.serie_lida && r.equipamento.serie_lida !== r.equipamento.serie_cadastro) {
                  <h3 class="rotulo-cartao">Equipamento</h3>
                  <label class="linha-caixa"><input type="checkbox" [checked]="escolhas.equipamento" (change)="escolhas.equipamento = !escolhas.equipamento" />
                    Gravar o número de série <span class="texto-codigo">{{ r.equipamento.serie_lida }}</span> (hoje: {{ r.equipamento.serie_cadastro || '—' }}) e o modelo {{ r.equipamento.modelo }}, versão {{ r.equipamento.versao }}, na observação</label>
                }
                @if (r.vlans_novas.length) {
                  <h3 class="rotulo-cartao">VLANs do equipamento que o SGI não tem</h3>
                  @for (v of r.vlans_novas; track v.numero) {
                    <label class="linha-caixa"><input type="checkbox" [checked]="escolhas.vlans.includes(v.numero)" (change)="alternar(escolhas.vlans, v.numero)" />
                      Cadastrar a VLAN <span class="texto-codigo">{{ v.numero }}</span> {{ v.nome }}</label>
                  }
                }
                @if (r.descricoes.length) {
                  <h3 class="rotulo-cartao">Portas com algo ligado no switch e nada em "Ligado a"</h3>
                  @for (d of r.descricoes; track d.interface) {
                    <label class="linha-caixa"><input type="checkbox" [checked]="escolhas.descricoes.includes(d.interface)" (change)="alternar(escolhas.descricoes, d.interface)" />
                      Porta <span class="texto-codigo">{{ d.porta }}</span>: ligar como "{{ d.descricao }}"</label>
                  }
                }
                @if (r.configuracao.length) {
                  <h3 class="rotulo-cartao">Configuração das portas</h3>
                  <small class="dica-formulario">Portas ligadas no SGI, ou marcadas acima para ligar pela descrição do switch.</small>
                  @for (c of r.configuracao; track c.interface) {
                    <label class="linha-caixa" [class.apagada]="!podeConfigurar(c)"><input type="checkbox" [disabled]="!podeConfigurar(c)"
                      [checked]="podeConfigurar(c) && escolhas.configuracao.includes(c.interface)" (change)="alternar(escolhas.configuracao, c.interface)" />
                      Porta <span class="texto-codigo">{{ c.porta }}</span>: {{ c.atual }} → <strong>{{ c.lida }}</strong></label>
                  }
                }
                @if (r.portas_sem_ligacao) {
                  <p class="dica-formulario">{{ r.portas_sem_ligacao }} porta(s) sem nada ligado no SGI ficaram de fora: configuração só vale em porta ligada. Ligue a porta em "Ligado a" e leia de novo para trazer a configuração dela.</p>
                }
                @for (a of r.avisos; track $index) { <p class="dica-formulario aviso-leitura">{{ a }}</p> }
                <footer class="acoes-formulario">
                  <button type="button" class="acao-secundaria" (click)="resumo.set(null)">Fechar</button>
                  <button type="button" class="acao-primaria" [class.carregando]="aplicando()" [disabled]="aplicando() || !temEscolha()" (click)="aplicar()">Aplicar selecionados</button>
                </footer>
              } @else {
                <footer class="acoes-formulario"><button type="button" class="acao-secundaria" (click)="resumo.set(null)">Fechar</button></footer>
              }
            </section>
          } @else if (ultima(); as u) {
            <p class="dica-formulario">Última leitura do equipamento em <span class="texto-codigo">{{ u.lido_em | date: 'dd/MM/yyyy HH:mm' }}</span>.
              <button type="button" class="acao-secundaria acao-pequena" (click)="abrirResumo(u)">Ver o resumo</button></p>
          }
          <!-- Mesmos indicadores da tela de Desempenho das Tarefas -->
          <section class="desempenho"><div class="indicadores-desempenho" role="group" aria-label="Portas do equipamento">
            <div><b>{{ e.portas_total }}</b><small>portas</small></div>
            <div><b>{{ e.portas_up }}</b><small>ligadas</small></div>
            <div><b>{{ e.portas_down }}</b><small>desligadas</small></div>
            <div><b>{{ e.portas_desativadas }}</b><small>desativadas</small></div>
          </div></section>
          <!-- Dados do equipamento em pares rótulo/valor (como a lateral "Situação" da porta): cada selo no seu campo, nada de texto corrido -->
          <dl class="dados-equipamento">
            @if (e.funcao) { <div><dt>Função</dt><dd><span class="selo-status" data-chamado="info">{{ rotulosFuncao[e.funcao] }}</span></dd></div> }
            @if (!passivo(e.tipo)) {
              <div><dt>Ping</dt><dd>
                @if (e.ping_situacao) {
                  <span class="selo-status" [attr.data-chamado]="e.ping_situacao === 'no_ar' ? 'sucesso' : 'perigo'">{{ rotulosPing[e.ping_situacao] }}</span>
                  @if (e.ping_mudou_em) { <small>desde <span class="texto-codigo">{{ e.ping_mudou_em | date: 'dd/MM/yyyy HH:mm' }}</span></small> }
                } @else { <span class="selo-status" data-chamado="neutro">Ainda não testado</span> }
              </dd></div>
              <div><dt>IP de gerência</dt><dd>@if (e.ip_gerencia) { <span class="texto-codigo">{{ e.ip_gerencia }}</span> } @else { — }</dd></div>
            }
            <div><dt>Número de série</dt><dd>@if (e.numero_serie) { <span class="texto-codigo">{{ e.numero_serie }}</span> } @else { — }</dd></div>
            @if (e.rack_nome) { <div><dt>Rack</dt><dd>{{ e.rack_nome }}@if (e.posicao_u) { · U<span class="texto-codigo">{{ e.posicao_u }}</span> }</dd></div> }
            @if (e.sala) { <div><dt>Sala</dt><dd>{{ e.sala }}</dd></div> }
            @if (e.cadastro_incompleto) { <div><dt>Cadastro</dt><dd><span class="selo-status" data-chamado="alerta">Incompleto: falta {{ !e.ip_gerencia ? 'IP de gerência' : 'função' }}</span></dd></div> }
            <!-- A alteração mais recente entre as portas deste equipamento: quem, quando e a porta (botão que abre a porta) -->
            <div class="ocupa-largo"><dt>Última alteração em porta</dt><dd>
              @if (e.alterado_em) {
                <span>{{ e.alterado_por }} · <span class="texto-codigo">{{ e.alterado_em | date: 'dd/MM/yyyy HH:mm:ss' }}</span></span>
                <a class="acao-secundaria acao-pequena" [routerLink]="['/rede/portas', e.alterado_porta_id]">Porta {{ e.alterado_porta }}</a>
              } @else { Nenhuma registrada }
            </dd></div>
          </dl>
          <app-face-rede [e]="e" />
          <h2 class="titulo-lista-portas">Lista de portas</h2>
          <div class="tabela-gestao-envoltorio">
            <table class="tabela-gestao">
              <thead><tr><th scope="col">Porta</th><th scope="col">Situação</th><th scope="col">VLAN</th><th scope="col">Ligado a</th><th scope="col">Observação</th><th scope="col">Ponto</th><th scope="col">Chamados</th></tr></thead>
              <tbody>
                @for (p of e.portas; track p.id) {
                  <tr>
                    <!-- A porta é um botão pequeno (ação, não link sublinhado) que abre o detalhe dela -->
                    <td data-rotulo="Porta"><a class="acao-secundaria acao-pequena texto-codigo" [routerLink]="['/rede/portas', p.id]" [attr.aria-label]="'Abrir a porta ' + (p.nome || p.numero_logico)">{{ p.nome || p.numero_logico }}</a>
                      @if (p.velocidade_mbps) { <br /><small>{{ vel(p.velocidade_mbps) }}{{ p.duplex ? ' ' + p.duplex : '' }}</small> }</td>
                    <td data-rotulo="Situação">@if (p.status) { <span class="selo-status" [attr.data-chamado]="cor(p)">{{ rotuloStatus(p) }}</span> } @else { — }</td>
                    <td data-rotulo="VLAN">{{ passivo(e.tipo) ? '—' : textoVlan(p) }}</td>
                    <td data-rotulo="Ligado a">
                      <!-- O que está ligado: outra porta vira botão (abre a porta de lá), sem link solto. No patch panel, fundo e frente -->
                      @if (passivo(e.tipo)) {
                        @if (p.fundo; as c) { <ng-container *ngTemplateOutlet="ligado; context: { $implicit: c, lado: 'Fundo' }" /> }
                        @if (p.frente; as c) { <ng-container *ngTemplateOutlet="ligado; context: { $implicit: c, lado: 'Frente' }" /> }
                        @if (!p.fundo && !p.frente) { — }
                      } @else if (p.conexao; as c) { <ng-container *ngTemplateOutlet="ligado; context: { $implicit: c, lado: '' }" /> }
                      @else { — }</td>
                    <td data-rotulo="Observação">{{ p.observacao || '—' }}</td>
                    <td data-rotulo="Ponto">@if (p.ponto) { <span class="texto-codigo">{{ p.ponto }}</span> } @else { — }</td>
                    <td data-rotulo="Chamados">@if (p.chamados_abertos) { <span class="selo-status" data-chamado="alerta">{{ p.chamados_abertos }} aberto(s)</span> } @else { — }</td>
                  </tr>
                } @empty { <tr><td colspan="7" class="estado-vazio">Sem portas. Escolha um modelo de face ao editar o equipamento: as portas são criadas por ele.</td></tr> }
              </tbody>
            </table>
          </div>
          <ng-template #ligado let-c let-lado="lado">
            <!-- Outra porta: o próprio nome é o botão que abre a porta do outro lado; bem ou descrição: só o texto -->
            <div class="ligado-celula">@if (lado) { <small>{{ lado }}</small> }
              @if (c.porta_id) { <a class="acao-secundaria acao-pequena" [routerLink]="['/rede/portas', c.porta_id]" [attr.aria-label]="'Abrir a porta ' + c.texto">{{ c.texto }}</a> }
              @else { <span>{{ c.texto }}</span> }</div>
          </ng-template>
        </section>

      } @else {
        <app-esqueleto tipo="painel" />
      }
    </div>
  `,
})
export class EquipamentoRedeComponent implements OnInit {
  private readonly api = inject(RedeApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly destruir = inject(DestroyRef);
  /** Equipamento aberto. Muda sem recriar a tela quando um link leva a outro equipamento (ex.: "Ligado a" → PATCH PANEL A-1). */
  private id = this.rota.snapshot.paramMap.get('id')!;
  protected readonly papeis = inject(AcessoService).rede;

  protected readonly e = signal<EquipamentoDetalhe | null>(null);
  /** Leitura por SSH ligada? (desligada por enquanto, decisão do usuário) */
  protected readonly leituraAtiva = LEITURA_SSH_ATIVA;
  /** Resumo da leitura aberto (depois de ler, ou ao clicar em "Ver o resumo") e a última leitura gravada. */
  protected readonly resumo = signal<ResumoLeitura | null>(null);
  protected readonly ultima = signal<ResumoLeitura | null>(null);
  protected readonly lendo = signal(false);
  protected readonly aplicando = signal(false);
  protected escolhas: AplicacaoLeitura = { equipamento: false, vlans: [], descricoes: [], configuracao: [] };
  protected readonly passivo = ehPassivo;
  protected readonly rotulosFuncao = ROTULOS_FUNCAO_EQUIPAMENTO;
  protected readonly rotulosPing = ROTULOS_PING;
  protected readonly vel = velocidade;

  ngOnInit(): void {
    // A mesma tela é reaproveitada entre equipamentos: a cada id novo, mostra o esqueleto e carrega o outro
    this.rota.paramMap.pipe(takeUntilDestroyed(this.destruir)).subscribe((p) => {
      const id = p.get('id')!;
      if (id === this.id && this.e()) return;
      this.id = id;
      this.e.set(null);
      this.resumo.set(null);
      this.api.equipamento(this.id).subscribe({ next: (e) => this.e.set(e), error: (x) => this.dialogos.mostrarErro(x, 'Não foi possível abrir o equipamento') });
      if (this.leituraAtiva) {
        this.api.ultimaLeitura(this.id).subscribe({ next: (u) => this.ultima.set(u), error: () => undefined });
        // Vindo do cadastro com acesso SSH (?ler=1): já faz a carga
        if (this.rota.snapshot.queryParamMap.get('ler') === '1') this.ler();
      }
    });
  }

  /** Lê o equipamento por SSH (só consulta): liga sozinho os vizinhos LLDP e abre o resumo do resto, já marcado. */
  protected ler(): void {
    this.lendo.set(true);
    this.dialogos.executar(this.api.lerEquipamento(this.id), 'Lendo o equipamento…').subscribe({
      next: (r) => {
        this.lendo.set(false);
        this.ultima.set(r);
        this.abrirResumo(r);
        // As ligações feitas pelo LLDP já mudaram as portas: recarrega a face
        this.api.equipamento(this.id).subscribe({ next: (e) => this.e.set(e), error: () => undefined });
      },
      error: (x) => { this.lendo.set(false); this.dialogos.mostrarErro(x, 'Não foi possível ler o equipamento'); },
    });
  }

  /** Abre o resumo com tudo o que dá para aplicar já marcado (a pessoa desmarca o que não quiser). */
  protected abrirResumo(r: ResumoLeitura): void {
    this.escolhas = {
      equipamento: !!r.equipamento.serie_lida && r.equipamento.serie_lida !== r.equipamento.serie_cadastro,
      vlans: r.vlans_novas.map((v) => v.numero), descricoes: r.descricoes.map((d) => d.interface),
      configuracao: r.configuracao.map((c) => c.interface),
    };
    this.resumo.set(r);
  }

  protected alternar<T>(lista: T[], valor: T): void {
    const i = lista.indexOf(valor);
    if (i >= 0) lista.splice(i, 1);
    else lista.push(valor);
  }

  /** A configuração só vale em porta ligada, ou que vai ser ligada pela descrição marcada acima. */
  protected podeConfigurar(c: ResumoLeitura['configuracao'][number]): boolean {
    return c.ligada || this.escolhas.descricoes.includes(c.interface);
  }

  protected temEscolha(): boolean {
    const e = this.escolhas;
    return e.equipamento || e.vlans.length > 0 || e.descricoes.length > 0 || e.configuracao.length > 0;
  }

  protected aplicar(): void {
    const r = this.resumo();
    if (!r) return;
    const dados = { ...this.escolhas, configuracao: this.escolhas.configuracao.filter((i) => this.podeConfigurar(r.configuracao.find((c) => c.interface === i)!)) };
    this.aplicando.set(true);
    this.api.aplicarLeitura(this.id, dados).subscribe({
      next: (e) => {
        this.aplicando.set(false);
        this.e.set(e);
        this.resumo.set(null);
        this.api.ultimaLeitura(this.id).subscribe({ next: (u) => this.ultima.set(u), error: () => undefined });
      },
      error: (x) => { this.aplicando.set(false); this.dialogos.mostrarErro(x, 'Não foi possível aplicar a leitura'); },
    });
  }

  protected rotuloTipo(t: TipoEquipamento): string {
    return ROTULOS_TIPO_EQUIPAMENTO[t];
  }

  protected rotuloStatus(p: Porta): string {
    return p.status ? ROTULOS_STATUS_PORTA[p.status] : '';
  }

  protected cor(p: Porta): string {
    return p.status ? COR_STATUS_PORTA[p.status] : 'neutro';
  }

  protected textoVlan(p: Porta): string {
    return textoVlanPorta(p);
  }
}
