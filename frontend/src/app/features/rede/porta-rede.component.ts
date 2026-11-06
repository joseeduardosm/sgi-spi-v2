// Criado por José Eduardo Santana Martins
// Este arquivo serve para o painel de uma porta de rede: configuração lógica, o que está ligado, o ponto e os chamados da porta.

import { DatePipe } from '@angular/common';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

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
  COR_STATUS_PORTA, EquipamentoResumo, GravacaoPorta, MODOS_PORTA, ModoPorta, modoPorta, Porta, PortaDetalhe, ROTULOS_STATUS_PORTA, velocidade, Vlan,
} from './rede.models';

@Component({
  selector: 'app-porta-rede',
  imports: [DatePipe, FormsModule, RouterLink, BuscaBemRedeComponent, CabecalhoRedeComponent, CaminhoRedeComponent, EsqueletoComponent, SeletorVlansComponent],
  styles: [`
    /* "Última alteração" em linha própria no cabeçalho do cartão de configuração */
    .ultima-alteracao { flex-basis: 100%; }
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
        [descricao]="p()?.descricao || ''"
        [trilha]="p() ? [{ rotulo: p()!.equipamento_nome, rota: ['/rede/equipamentos', p()!.equipamento_id] }, { rotulo: 'Porta ' + (p()!.nome || p()!.numero_logico) }] : []" />
      @if (p(); as p) {
        <div class="detalhe-chamado">
          <div class="coluna-chamado">
            <section class="cartao-chamado" aria-labelledby="rp-config">
              <header><h2 id="rp-config">Configuração</h2>
                <small>É o cadastro do que está configurado no equipamento: o SGI não muda o switch.</small>
                <!-- Quem fez a última alteração da porta (configuração, ligação, ponto, carga LLDP...) -->
                <small class="ultima-alteracao">Última alteração: @if (p.alterado_em) { {{ p.alterado_por }} - <span class="texto-codigo">{{ p.alterado_em | date: 'dd/MM/yyyy HH:mm:ss' }}</span> } @else { nenhuma registrada }</small></header>
              <form class="grade-formulario" (ngSubmit)="salvar()">
                <div class="ocupa-duas"><label for="rp-desc">Descrição</label>
                  <!-- Regra: toda porta salva tem descrição -->
                  <input id="rp-desc" name="desc" maxlength="250" required placeholder="Ex.: Sala 504 - impressora" [disabled]="!papeis()?.editar" [(ngModel)]="cfg.descricao" /></div>
                @if (passiva()) {
                  <p class="ocupa-duas dica-formulario">Patch panel não tem configuração lógica (modo, VLANs, IP, velocidade): só a descrição e a situação.</p>
                } @else {
                <div class="ocupa-duas"><label for="rp-modo">Modo</label>
                  <select id="rp-modo" name="modo" [disabled]="!papeis()?.editar" [ngModel]="cfg.modo" (ngModelChange)="trocarModo($event)">
                    @for (m of modos; track m.valor) { <option [value]="m.valor">{{ m.rotulo }}</option> }
                  </select>
                  <small class="dica-formulario">{{ modo().dica }}</small></div>
                @if (modo().nativa) {
                  <div><label for="rp-nativa">{{ modo().nativa }}</label>
                    <select id="rp-nativa" name="nativa" [disabled]="!papeis()?.editar" [(ngModel)]="cfg.vlan_nativa_id">
                      <option [ngValue]="null">Nenhuma</option>
                      @for (v of vlans(); track v.id) { <option [ngValue]="v.id">{{ v.numero }} · {{ v.nome }}</option> }
                    </select></div>
                }
                @if (modo().ip) {
                  <div><label for="rp-ip">IP da interface</label>
                    <input id="rp-ip" name="ip" maxlength="49" class="texto-codigo" placeholder="Ex.: 10.23.0.1/30" [disabled]="!papeis()?.editar" [(ngModel)]="cfg.ip_interface" /></div>
                }
                @if (modo().semTag) {
                  <div class="ocupa-duas">
                    <app-seletor-vlans idCampo="rp-sem-tag" rotuloCampo="VLANs sem tag" detalheRotulo="(untagged, além da PVID)" prefixoResumo="Sem tag"
                      rotulo="Adicionar VLAN sem tag" [vlans]="vlans()" [valor]="cfg.vlans_sem_tag" [excluir]="cfg.vlans_tag" [desabilitado]="!papeis()?.editar"
                      [podeGerir]="!!papeis()?.administrar" (valorChange)="cfg.vlans_sem_tag = $event" (vlanAlterada)="atualizarVlan($event)" /></div>
                }
                @if (modo().tag) {
                  <div class="ocupa-duas">
                    <app-seletor-vlans idCampo="rp-tag" rotuloCampo="VLANs com tag" detalheRotulo="(tagged)" prefixoResumo="Com tag"
                      rotulo="Adicionar VLAN com tag" [vlans]="vlans()" [valor]="cfg.vlans_tag" [excluir]="cfg.vlans_sem_tag" [desabilitado]="!papeis()?.editar"
                      [podeGerir]="!!papeis()?.administrar" (valorChange)="cfg.vlans_tag = $event" (vlanAlterada)="atualizarVlan($event)" /></div>
                }
                }
                <div><label for="rp-status">Situação</label>
                  <!-- Porta com equipamento está necessariamente ligada: para mudar, primeiro se retira o que está nela -->
                  <select id="rp-status" name="status" [disabled]="!papeis()?.editar || !!p.conexao" [(ngModel)]="cfg.status">
                    <option [ngValue]="null">Não informada</option><option value="up">Ligada</option><option value="down">Desligada</option><option value="desativada">Desativada</option>
                  </select>
                  @if (p.conexao) { <small class="dica-formulario">Com equipamento ligado, a porta fica ligada. Para desligar ou desativar, retire o equipamento em "Ligado a".</small> }</div>
                @if (!passiva()) {
                  <div><label for="rp-vel">Velocidade (Mb/s)</label><input id="rp-vel" name="vel" type="number" min="1" [disabled]="!papeis()?.editar" [(ngModel)]="cfg.velocidade_mbps" /></div>
                }
                @if (papeis()?.editar) {
                  <div class="ocupa-duas acoes-formulario"><button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando()">Salvar configuração</button></div>
                }
              </form>
            </section>

            <section class="cartao-chamado" aria-labelledby="rp-ligado">
              <header><h2 id="rp-ligado">Ligado a</h2><small>O que está na outra ponta do cabo desta porta.</small></header>
              @if (p.conexao; as c) {
                @if (c.tipo === 'porta') {
                  <p><a [routerLink]="['/rede/equipamentos', c.equipamento_id]">{{ c.texto }}</a></p>
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
                  @if (papeis()?.editar) {
                    <form class="grade-formulario" (ngSubmit)="adicionarAtras()">
                      <div class="ocupa-duas"><label for="rp-tipo-atras">Ligar outro dispositivo atrás <small>(ex.: o PC ligado no telefone IP)</small></label>
                        <select id="rp-tipo-atras" name="tipo-atras" [(ngModel)]="tipoLigacao">
                          <option value="bem">Um bem do Patrimônio</option><option value="descricao">Outra coisa (descrever)</option>
                        </select></div>
                      @if (tipoLigacao === 'descricao') {
                        <div class="ocupa-duas"><label for="rp-texto-atras">Descrição</label>
                          <input id="rp-texto-atras" name="texto-atras" maxlength="250" placeholder="Ex.: Notebook do visitante" [(ngModel)]="descricaoLigacao" /></div>
                      } @else {
                        <div class="ocupa-duas"><label for="rp-bem-atras">Bem do Patrimônio</label>
                          <app-busca-bem-rede idCampo="rp-bem-atras" [(bemId)]="bemEscolhido" /></div>
                      }
                      <div class="ocupa-duas acoes-formulario">
                        <button type="button" class="acao-recusar" [disabled]="salvando()" (click)="desligar()">Desligar a porta</button>
                        <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando() || !podeAdicionarAtras()">Ligar atrás</button>
                      </div>
                    </form>
                  }
                }
                @if (c.tipo === 'porta' && papeis()?.editar) {
                  <footer class="acoes-formulario"><button type="button" class="acao-recusar" [disabled]="salvando()" (click)="desligar()">Desligar</button></footer>
                }
              } @else {
                <p class="estado-vazio-chamado">Nada ligado.</p>
                @if (papeis()?.editar) {
                  <form class="grade-formulario" (ngSubmit)="ligar()">
                    <div class="ocupa-duas"><label for="rp-tipo-ligacao">O que está ligado</label>
                      <select id="rp-tipo-ligacao" name="tipo-ligacao" [(ngModel)]="tipoLigacao">
                        <option value="bem">Um bem do Patrimônio (computador, impressora...)</option>
                        <option value="porta">Outro equipamento de rede</option>
                        <option value="descricao">Outra coisa (descrever)</option>
                      </select></div>
                    @switch (tipoLigacao) {
                      @case ('bem') {
                        <div class="ocupa-duas"><label for="rp-bem">Bem do Patrimônio</label>
                          <app-busca-bem-rede idCampo="rp-bem" [(bemId)]="bemEscolhido" /></div>
                      }
                      @case ('porta') {
                        <div><label for="rp-equip">Equipamento do outro lado</label>
                          <select id="rp-equip" name="equip" [(ngModel)]="outroEquipamento" (ngModelChange)="carregarPortasDe($event)">
                            <option [ngValue]="null">Escolha</option>
                            @for (e of equipamentos(); track e.id) { @if (e.id !== p.equipamento_id) { <option [ngValue]="e.id">{{ e.nome }}</option> } }
                          </select></div>
                        <div><label for="rp-outra">Porta</label>
                          <select id="rp-outra" name="outra" [disabled]="!outroEquipamento" [(ngModel)]="outraPorta">
                            <option [ngValue]="null">{{ outroEquipamento ? 'Escolha' : 'Escolha o equipamento antes' }}</option>
                            @for (x of portasOutro(); track x.id) { <option [ngValue]="x.id" [disabled]="!!x.conexao">{{ x.nome || x.numero_logico }}{{ x.conexao ? ' (ocupada)' : x.descricao ? ' (' + x.descricao + ')' : '' }}</option> }
                          </select></div>
                      }
                      @case ('descricao') {
                        <div class="ocupa-duas"><label for="rp-texto">Descrição</label>
                          <input id="rp-texto" name="texto" maxlength="250" placeholder="Ex.: Telefone da recepção" [(ngModel)]="descricaoLigacao" /></div>
                      }
                    }
                    <div class="ocupa-duas acoes-formulario">
                      <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando() || !podeLigar()">Ligar</button>
                    </div>
                  </form>
                }
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
                <div><dt>Velocidade</dt><dd>{{ vel(p.velocidade_mbps) }}{{ p.duplex ? ' · ' + p.duplex : '' }}</dd></div>
                @if (p.mac) { <div><dt>MAC</dt><dd class="texto-codigo">{{ p.mac }}</dd></div> }
                @if (p.ultima_mudanca) { <div><dt>Última mudança</dt><dd>{{ data(p.ultima_mudanca) }}</dd></div> }
                <div><dt>Erros (entrada / saída)</dt><dd>{{ p.erros_entrada }} / {{ p.erros_saida }}</dd></div>
                <div><dt>Ponto de rede</dt><dd>@if (p.ponto) { <span class="texto-codigo">{{ p.ponto }}</span> } @else { Nenhum }</dd></div>
              </dl>
            </section>
          </aside>
        </div>
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
  /** Porta de patch panel: sem parte lógica (só descrição e situação). */
  protected readonly passiva = computed(() => this.p()?.equipamento_tipo === 'patch_panel');
  protected readonly vlans = signal<Vlan[]>([]);
  protected readonly equipamentos = signal<EquipamentoResumo[]>([]);
  protected readonly portasOutro = signal<Porta[]>([]);
  protected readonly salvando = signal(false);
  protected cfg: GravacaoPorta = { descricao: '', modo: 'access', vlan_nativa_id: null, vlans_tag: [], vlans_sem_tag: [], vlan_voz_id: null, ip_interface: '',
    velocidade_mbps: null, duplex: null, status: null };
  protected readonly modos = MODOS_PORTA;
  /** O modo escolhido no formulário (atualizado em `trocarModo`): diz quais campos aparecem. */
  protected readonly modo = signal(modoPorta('access'));
  protected outroEquipamento: string | null = null;
  protected outraPorta: string | null = null;
  protected descricaoLigacao = '';
  protected tipoLigacao: 'bem' | 'porta' | 'descricao' = 'bem';
  protected bemEscolhido: string | null = null;
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
    this.cfg = { descricao: x.descricao, modo: x.modo, vlan_nativa_id: x.vlan_nativa_id, vlans_tag: [...x.vlans_tag_ids], vlans_sem_tag: [...(x.vlans_sem_tag_ids ?? [])],
      vlan_voz_id: x.vlan_voz_id ?? null, ip_interface: x.ip_interface ?? '', velocidade_mbps: x.velocidade_mbps, duplex: x.duplex, status: x.status };
    this.modo.set(modoPorta(x.modo));
    this.outroEquipamento = this.outraPorta = this.bemEscolhido = null;
    this.descricaoLigacao = '';
  }

  private executar(pedido: Observable<PortaDetalhe>, erro: string): void {
    this.salvando.set(true);
    pedido.subscribe({ next: (x) => this.aplicar(x), error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, erro); } });
  }

  /** Cor ou nome de VLAN trocados pelo selo: atualiza a lista (os dois campos e a VLAN nativa mostram o novo). */
  protected atualizarVlan(nova: Vlan): void {
    this.vlans.update((lista) => lista.map((v) => (v.id === nova.id ? nova : v)));
  }

  protected trocarModo(valor: ModoPorta): void {
    this.cfg.modo = valor;
    this.modo.set(modoPorta(valor));
  }

  /** Manda só o que o modo aceita (o que ficou marcado de outro modo é descartado, em vez de a API recusar). */
  protected salvar(): void {
    if (!this.cfg.descricao.trim()) {
      this.dialogos.avisar('Descrição obrigatória', 'Informe a descrição da porta antes de salvar.');
      return;
    }
    // Patch panel: só descrição e situação (a API recusa o resto)
    if (this.passiva()) {
      this.executar(this.api.configurarPorta(this.id, { descricao: this.cfg.descricao, modo: 'access', vlan_nativa_id: null, vlans_tag: [], vlans_sem_tag: [],
        vlan_voz_id: null, ip_interface: '', velocidade_mbps: null, duplex: null, status: this.cfg.status }), 'Não foi possível salvar a porta');
      return;
    }
    const m = this.modo();
    this.executar(this.api.configurarPorta(this.id, {
      ...this.cfg, vlan_nativa_id: m.nativa ? this.cfg.vlan_nativa_id : null, vlans_tag: m.tag ? this.cfg.vlans_tag : [], vlans_sem_tag: m.semTag ? this.cfg.vlans_sem_tag : [],
      // A VLAN de voz saiu da tela: a já gravada é mantida enquanto o modo aceitar
      vlan_voz_id: m.voz ? this.cfg.vlan_voz_id : null, ip_interface: m.ip ? this.cfg.ip_interface.trim() : '',
    }), 'Não foi possível salvar a porta');
  }

  protected carregarPortasDe(id: string | null): void {
    this.outraPorta = null;
    this.portasOutro.set([]);
    if (id) this.api.equipamento(id).subscribe({ next: (e) => this.portasOutro.set(e.portas), error: () => undefined });
  }

  protected podeAdicionarAtras(): boolean {
    return this.tipoLigacao === 'descricao' ? !!this.descricaoLigacao.trim() : !!this.bemEscolhido;
  }

  protected adicionarAtras(): void {
    const dados = this.tipoLigacao === 'descricao' ? { descricao: this.descricaoLigacao } : { bem_id: this.bemEscolhido };
    this.executar(this.api.adicionarAtras(this.id, dados), 'Não foi possível ligar o dispositivo');
  }

  protected removerAtras(dispositivoId: string): void {
    this.executar(this.api.removerAtras(this.id, dispositivoId), 'Não foi possível tirar o dispositivo');
  }

  protected podeLigar(): boolean {
    return this.tipoLigacao === 'bem' ? !!this.bemEscolhido : this.tipoLigacao === 'porta' ? !!this.outraPorta : !!this.descricaoLigacao.trim();
  }

  protected ligar(forcar = false): void {
    const dados = this.tipoLigacao === 'bem' ? { bem_id: this.bemEscolhido } : this.tipoLigacao === 'porta' ? { porta_id: this.outraPorta, forcar } : { descricao: this.descricaoLigacao };
    this.salvando.set(true);
    this.api.ligar(this.id, dados).subscribe({
      next: (x) => this.aplicar(x),
      error: async (e) => {
        this.salvando.set(false);
        // Porta descrita no switch (provável dispositivo): a API explica qual; só liga se a pessoa confirmar
        if (e?.error?.codigo === 'porta_com_dispositivo') {
          const ok = await this.dialogos.confirmar({ titulo: 'Porta com dispositivo?', mensagem: e.error.detalhe, rotuloConfirmar: 'Ligar e trocar a descrição' });
          if (ok) this.ligar(true);
          return;
        }
        this.dialogos.mostrarErro(e, 'Não foi possível ligar a porta');
      },
    });
  }

  protected desligar(): void {
    this.executar(this.api.desligar(this.id), 'Não foi possível desligar a porta');
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
