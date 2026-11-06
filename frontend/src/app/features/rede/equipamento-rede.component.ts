// Criado por José Eduardo Santana Martins
// Este arquivo serve para mostrar um equipamento de rede: dados, portas (configuração, o que está ligado, ponto e chamados) e edição.

import { DatePipe } from '@angular/common';
import { Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AcessoService } from '../../core/acesso/acesso.service';
import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRedeComponent } from './cabecalho-rede.component';
import { FaceRedeComponent } from './face-rede.component';
import { RedeApiService } from './rede-api.service';
import {
  COR_STATUS_PORTA, ehPassivo, EquipamentoDetalhe, FuncaoEquipamento, GravacaoEquipamento, ModeloFace, Porta, Rack, ROTULOS_FUNCAO_EQUIPAMENTO, ROTULOS_PING,
  ROTULOS_STATUS_PORTA, ROTULOS_TIPO_EQUIPAMENTO, textoVlanPorta, TipoEquipamento, velocidade,
} from './rede.models';

@Component({
  selector: 'app-equipamento-rede',
  imports: [DatePipe, FormsModule, RouterLink, CabecalhoRedeComponent, EsqueletoComponent, FaceRedeComponent],
  styles: ['.titulo-lista-portas { margin: 8px 0 10px; font-size: var(--spi-texto-destaque); font-weight: 700; }'],
  template: `
    <div class="modulo-chamados">
      <app-cabecalho-rede [titulo]="e()?.nome || 'Equipamento'" [trilha]="[{ rotulo: e()?.nome || 'Equipamento' }]" [descricao]="e() ? rotuloTipo(e()!.tipo) + (e()!.modelo_nome ? ' · ' + e()!.modelo_nome : '') : ''" />
      @if (e(); as e) {
        <section class="painel-gestao protocolo">
          <!-- Mesmos indicadores da tela de Desempenho das Tarefas -->
          <section class="desempenho"><div class="indicadores-desempenho" role="group" aria-label="Portas do equipamento">
            <div><b>{{ e.portas_total }}</b><small>portas</small></div>
            <div><b>{{ e.portas_up }}</b><small>ligadas</small></div>
            <div><b>{{ e.portas_down }}</b><small>desligadas</small></div>
            <div><b>{{ e.portas_desativadas }}</b><small>desativadas</small></div>
          </div></section>
          <p class="dica-formulario" style="margin: 12px 0">
            @if (e.funcao) { <span class="selo-status" data-chamado="info">{{ rotulosFuncao[e.funcao] }}</span> }
            @if (e.ping_situacao) {
              <span class="selo-status" [attr.data-chamado]="e.ping_situacao === 'no_ar' ? 'sucesso' : 'perigo'"
                    [title]="e.ping_mudou_em ? 'Desde ' + (e.ping_mudou_em | date: 'dd/MM/yyyy HH:mm') : ''">{{ rotulosPing[e.ping_situacao] }}</span>
            } @else if (e.ip_gerencia && !passivo(e.tipo)) { <span class="selo-status" data-chamado="neutro">Ping ainda não testado</span> }
            @if (e.cadastro_incompleto) { <span class="selo-status" data-chamado="alerta">Cadastro incompleto: falta {{ !e.ip_gerencia ? 'IP de gerência' : '' }}{{ !e.ip_gerencia && !e.funcao ? ' e ' : '' }}{{ !e.funcao ? 'função' : '' }}</span> }
            {{ dadosTexto(e) }}
            <!-- A alteração mais recente entre as portas deste equipamento (quem, quando e qual porta) -->
            <br />Última alteração em porta: @if (e.alterado_em) {
              {{ e.alterado_por }} - <span class="texto-codigo">{{ e.alterado_em | date: 'dd/MM/yyyy HH:mm:ss' }}</span>
              (<a [routerLink]="['/rede/portas', e.alterado_porta_id]">porta <span class="texto-codigo">{{ e.alterado_porta }}</span></a>)
            } @else { nenhuma registrada }
          </p>
          <app-face-rede [e]="e" />
          <h2 class="titulo-lista-portas">Lista de portas</h2>
          <div class="tabela-gestao-envoltorio">
            <table class="tabela-gestao">
              <thead><tr><th scope="col">Porta</th><th scope="col">Situação</th><th scope="col">VLAN</th><th scope="col">Descrição</th><th scope="col">Ligado a</th><th scope="col">Ponto</th><th scope="col">Chamados</th></tr></thead>
              <tbody>
                @for (p of e.portas; track p.id) {
                  <tr>
                    <td data-rotulo="Porta"><a [routerLink]="['/rede/portas', p.id]"><strong class="texto-codigo">{{ p.nome || p.numero_logico }}</strong></a>
                      @if (p.velocidade_mbps) { <br /><small>{{ vel(p.velocidade_mbps) }}{{ p.duplex ? ' ' + p.duplex : '' }}</small> }</td>
                    <td data-rotulo="Situação">@if (p.status) { <span class="selo-status" [attr.data-chamado]="cor(p)">{{ rotuloStatus(p) }}</span> } @else { — }</td>
                    <td data-rotulo="VLAN">{{ passivo(e.tipo) ? '—' : textoVlan(p) }}</td>
                    <td data-rotulo="Descrição">{{ p.descricao || '—' }}</td>
                    <td data-rotulo="Ligado a">
                      @if (p.conexao?.equipamento_id) { <a [routerLink]="['/rede/equipamentos', p.conexao!.equipamento_id]">{{ p.conexao!.texto }}</a> }
                      @else { {{ p.conexao?.texto || '—' }} }</td>
                    <td data-rotulo="Ponto">@if (p.ponto) { <span class="texto-codigo">{{ p.ponto }}</span> } @else { — }</td>
                    <td data-rotulo="Chamados">@if (p.chamados_abertos) { <span class="selo-status" data-chamado="alerta">{{ p.chamados_abertos }} aberto(s)</span> } @else { — }</td>
                  </tr>
                } @empty { <tr><td colspan="7" class="estado-vazio">Sem portas. Escolha um modelo de face ao editar o equipamento: as portas são criadas por ele.</td></tr> }
              </tbody>
            </table>
          </div>
        </section>

        @if (papeis()?.administrar) {
          <section class="cartao-dados" aria-labelledby="re-editar" style="margin-top: 16px">
            <header><div><h2 id="re-editar">Dados do equipamento</h2><small>O modelo de face e o tipo (patch panel ou não) não mudam depois de criado: para trocar, exclua e cadastre de novo.</small></div></header>
            <div class="corpo">
            <form class="grade-formulario" (ngSubmit)="salvar()">
              <div><label for="ed-nome">Nome</label><input id="ed-nome" name="nome" required minlength="2" maxlength="150" [(ngModel)]="dados.nome" /></div>
              <div><label for="ed-tipo">Tipo</label>
                <!-- Patch panel não vira switch (nem o contrário): só os tipos do mesmo grupo aparecem -->
                <select id="ed-tipo" name="tipo" [(ngModel)]="dados.tipo">@for (t of tiposPermitidos(e); track t[0]) { <option [value]="t[0]">{{ t[1] }}</option> }</select></div>
              @if (!passivo(dados.tipo)) {
                <div><label for="ed-funcao">Função na topologia</label>
                  <select id="ed-funcao" name="funcao" required [(ngModel)]="dados.funcao">
                    <option [ngValue]="null" disabled>Escolha</option>
                    @for (f of funcoes; track f[0]) { <option [ngValue]="f[0]">{{ f[1] }}</option> }
                  </select>
                  <small class="dica-formulario">Os cores ficam no topo da topologia; se o primário cair (ping), o secundário assume.</small></div>
              }
              <div><label for="ed-modelo">Modelo de face</label>
                @if (e.modelo_face_id) {
                  <!-- Regra: o modelo é escolhido na criação e não muda mais -->
                  <input id="ed-modelo" name="modelo" [value]="e.modelo_nome" disabled />
                  <small class="dica-formulario">Para trocar o modelo, exclua o equipamento e cadastre de novo.</small>
                } @else {
                  <!-- Equipamento antigo sem modelo: recebe o modelo uma vez (as portas são criadas por ele) -->
                  <select id="ed-modelo" name="modelo" [(ngModel)]="dados.modelo_face_id">
                    <option [ngValue]="null">Sem modelo</option>
                    @for (m of modelos(); track m.id) { <option [ngValue]="m.id">{{ m.nome }}</option> }
                  </select>
                  <small class="dica-formulario">Escolha com cuidado: depois de salvo, o modelo não muda.</small>
                }</div>
              <div><label for="ed-ip">IP de gerência @if (passivo(dados.tipo)) { <small>(opcional)</small> }</label>
                <input id="ed-ip" name="ip" maxlength="45" [required]="!passivo(dados.tipo)" [(ngModel)]="dados.ip_gerencia" /></div>
              <div><label for="ed-rack">Rack</label>
                <select id="ed-rack" name="rack" [(ngModel)]="dados.rack_id">
                  <option [ngValue]="null">Fora de rack</option>
                  @for (r of racks(); track r.id) { <option [ngValue]="r.id">{{ r.nome }} ({{ r.altura_u }}U)</option> }
                </select></div>
              <div><label for="ed-u">Posição no rack (U)</label><input id="ed-u" name="u" type="number" min="1" max="60" [disabled]="!dados.rack_id" [(ngModel)]="dados.posicao_u" /></div>
              <div><label for="ed-serie">Número de série</label><input id="ed-serie" name="serie" maxlength="120" [(ngModel)]="dados.numero_serie" /></div>
              <div><label class="linha-caixa"><input type="checkbox" name="ativo" [(ngModel)]="dados.ativo" /> Ativo</label></div>
              <div class="ocupa-duas"><label for="ed-obs">Observação</label><textarea id="ed-obs" name="obs" rows="2" maxlength="4000" [(ngModel)]="dados.observacao"></textarea></div>
              <div class="ocupa-duas acoes-formulario">
                <button type="button" class="acao-perigo" (click)="excluir(e)">Excluir equipamento</button>
                <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando()">Salvar</button>
              </div>
            </form>
            </div>
          </section>
        }
      } @else {
        <app-esqueleto tipo="painel" />
      }
    </div>
  `,
})
export class EquipamentoRedeComponent implements OnInit {
  private readonly api = inject(RedeApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  private readonly rota = inject(ActivatedRoute);
  private readonly destruir = inject(DestroyRef);
  /** Equipamento aberto. Muda sem recriar a tela quando um link leva a outro equipamento (ex.: "Ligado a" → PATCH PANEL A-1). */
  private id = this.rota.snapshot.paramMap.get('id')!;
  protected readonly papeis = inject(AcessoService).rede;

  protected readonly e = signal<EquipamentoDetalhe | null>(null);
  protected readonly modelos = signal<ModeloFace[]>([]);
  protected readonly racks = signal<Rack[]>([]);
  protected readonly salvando = signal(false);
  protected readonly tipos = Object.entries(ROTULOS_TIPO_EQUIPAMENTO) as [TipoEquipamento, string][];
  protected readonly funcoes = Object.entries(ROTULOS_FUNCAO_EQUIPAMENTO) as [FuncaoEquipamento, string][];
  protected readonly passivo = ehPassivo;
  protected readonly rotulosFuncao = ROTULOS_FUNCAO_EQUIPAMENTO;
  protected readonly rotulosPing = ROTULOS_PING;
  protected dados!: GravacaoEquipamento;
  protected readonly vel = velocidade;

  ngOnInit(): void {
    // A mesma tela é reaproveitada entre equipamentos: a cada id novo, mostra o esqueleto e carrega o outro
    this.rota.paramMap.pipe(takeUntilDestroyed(this.destruir)).subscribe((p) => {
      const id = p.get('id')!;
      if (id === this.id && this.e()) return;
      this.id = id;
      this.e.set(null);
      this.carregar();
    });
    this.api.modelos().subscribe({ next: (x) => this.modelos.set(x), error: () => undefined });
    this.api.racks().subscribe({ next: (x) => this.racks.set(x), error: () => undefined });
  }

  private aplicar(e: EquipamentoDetalhe): void {
    this.e.set(e);
    this.dados = { nome: e.nome, tipo: e.tipo, modelo_face_id: e.modelo_face_id, bem_id: e.bem_id, localizacao_id: e.localizacao_id, rack_id: e.rack_id,
      posicao_u: e.posicao_u, ip_gerencia: e.ip_gerencia, numero_serie: e.numero_serie, observacao: e.observacao, ativo: e.ativo, funcao: e.funcao };
  }

  private carregar(): void {
    this.api.equipamento(this.id).subscribe({ next: (e) => this.aplicar(e), error: (x) => this.dialogos.mostrarErro(x, 'Não foi possível abrir o equipamento') });
  }

  protected salvar(): void {
    this.salvando.set(true);
    this.api.salvarEquipamento(this.id, { ...this.dados, posicao_u: this.dados.rack_id ? this.dados.posicao_u : null }).subscribe({
      next: (e) => { this.salvando.set(false); this.aplicar(e); },
      error: (x) => { this.salvando.set(false); this.dialogos.mostrarErro(x, 'Não foi possível salvar'); },
    });
  }

  protected async excluir(e: EquipamentoDetalhe): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir ${e.nome}?`, mensagem: 'As portas e as conexões dele vão junto. Os chamados ficam sem a porta.',
      rotuloConfirmar: 'Excluir equipamento', segundos: 3 });
    if (!ok) return;
    this.api.excluirEquipamento(e.id).subscribe({ next: () => void this.roteador.navigate(['/rede']), error: (x) => this.dialogos.mostrarErro(x, 'Não foi possível excluir') });
  }

  /** "IP de gerência 10.23.5.2 · Sala 504 · Rack 5A, 12U · Série ABC" (só o que existir). */
  protected dadosTexto(e: EquipamentoDetalhe): string {
    return [e.ip_gerencia && `IP de gerência ${e.ip_gerencia}`, e.sala, e.rack_nome && `${e.rack_nome}${e.posicao_u ? ', U' + e.posicao_u : ''}`,
      e.numero_serie && `Série ${e.numero_serie}`].filter(Boolean).join(' · ');
  }

  /** Tipos que o equipamento pode assumir: patch panel continua patch panel; os demais não viram patch panel. */
  protected tiposPermitidos(e: EquipamentoDetalhe): [TipoEquipamento, string][] {
    return this.tipos.filter(([t]) => ehPassivo(t) === ehPassivo(e.tipo));
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
