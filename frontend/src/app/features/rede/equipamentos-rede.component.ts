// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela principal da rede: os racks (com os equipamentos na posição) e a lista, com o cadastro de racks e equipamentos.

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AcessoService } from '../../core/acesso/acesso.service';
import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRedeComponent } from './cabecalho-rede.component';
import { OpcaoSala } from '../patrimonio/patrimonio-estado.service';
import { SeletorSalaComponent } from '../patrimonio/seletor-sala.component';
import { RackRedeComponent } from './rack-rede.component';
import { RedeApiService } from './rede-api.service';
import {
  CORES_RACK, ehPassivo, EquipamentoResumo, FuncaoEquipamento, GravacaoEquipamento, GravacaoRack, ModeloFace, Rack, ROTULOS_FUNCAO_EQUIPAMENTO, ROTULOS_PING,
  ROTULOS_TIPO_EQUIPAMENTO, TipoEquipamento,
} from './rede.models';

function equipamentoVazio(): GravacaoEquipamento {
  return { nome: '', tipo: 'switch', modelo_face_id: null, bem_id: null, localizacao_id: null, rack_id: null, posicao_u: null, ip_gerencia: '', funcao: null, numero_serie: '',
    observacao: '', ativo: true };
}

function rackVazio(): GravacaoRack {
  return { nome: '', cor: 'preto', localizacao_id: null, altura_u: 42, observacao: '' };
}

@Component({
  selector: 'app-equipamentos-rede',
  imports: [FormsModule, RouterLink, CabecalhoRedeComponent, EsqueletoComponent, RackRedeComponent, SeletorSalaComponent],
  styles: ['.grade-racks { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; align-items: start; margin-bottom: 16px; }'],
  template: `
    <div class="modulo-chamados">
      <app-cabecalho-rede titulo="Rede" descricao="Os racks, a face de cada switch e patch panel, a configuração das portas e o que está ligado." />
      <section class="painel-gestao protocolo">
        <div class="barra-protocolo">
          <div class="chips-filtro" role="group" aria-label="Visão">
            <button type="button" [class.ativo]="visao() === 'racks'" [attr.aria-pressed]="visao() === 'racks'" (click)="verRacks()">Racks</button>
            <button type="button" [class.ativo]="visao() === 'lista'" [attr.aria-pressed]="visao() === 'lista'" (click)="visao.set('lista')">Lista</button>
          </div>
          <span class="espacador"></span>
          @if (papeis()?.administrar) {
            <button type="button" class="acao-secundaria" (click)="abrirRack(null)">Novo rack</button>
            <button type="button" class="acao-primaria" (click)="formulario.set(formulario() === 'equipamento' ? null : 'equipamento')">Novo equipamento</button>
          }
        </div>

        @if (formulario() === 'rack') {
          <form class="grade-formulario" (ngSubmit)="salvarRack(fr)" #fr="ngForm">
            <div><label for="rk-nome">{{ editandoRack() ? 'Alterar rack' : 'Novo rack' }}</label>
              <input id="rk-nome" name="nome" required maxlength="80" placeholder="Ex.: Rack do 5º andar" [(ngModel)]="rack.nome" /></div>
            <div><label for="rk-cor">Cor</label>
              <select id="rk-cor" name="cor" [(ngModel)]="rack.cor">@for (c of cores; track c[0]) { <option [value]="c[0]">{{ c[1] }}</option> }</select></div>
            <div><label for="rk-altura">Quantidade de U</label>
              <input id="rk-altura" name="altura" type="number" min="1" max="60" required [(ngModel)]="rack.altura_u" /></div>
            <div><label for="rk-sala">Localização (sala do Patrimônio)</label>
              <!-- Um campo só: digitar filtra a lista de salas (agrupada por andar); o mesmo campo de sala do Patrimônio -->
              <app-seletor-sala idCampo="rk-sala" nome="sala" rotulo="Localização do rack" placeholder="Digite o código ou o nome da sala (ex.: 05A03)"
                [opcoes]="salas()" [valor]="rack.localizacao_id ?? ''" (valorChange)="rack.localizacao_id = $event || null" /></div>
            <div class="ocupa-duas acoes-formulario">
              <button type="button" class="acao-secundaria" (click)="fecharFormulario(fr)">Cancelar</button>
              <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fr.invalid || salvando()">{{ editandoRack() ? 'Salvar rack' : 'Cadastrar rack' }}</button>
            </div>
          </form>
        }

        @if (formulario() === 'equipamento') {
          <form class="grade-formulario" (ngSubmit)="criar(fe)" #fe="ngForm">
            <div><label for="re-nome">Novo equipamento</label>
              <input id="re-nome" name="nome" required minlength="2" maxlength="150" placeholder="Ex.: SW-5A" [(ngModel)]="novo.nome" /></div>
            <div><label for="re-tipo">Tipo</label>
              <select id="re-tipo" name="tipo" [(ngModel)]="novo.tipo">@for (t of tipos; track t[0]) { <option [value]="t[0]">{{ t[1] }}</option> }</select></div>
            @if (!passivo(novo.tipo)) {
              <div><label for="re-funcao">Função na topologia</label>
                <select id="re-funcao" name="funcao" required [(ngModel)]="novo.funcao">
                  <option [ngValue]="null" disabled>Escolha</option>
                  @for (f of funcoes; track f[0]) { <option [ngValue]="f[0]">{{ f[1] }}</option> }
                </select></div>
            }
            <div><label for="re-modelo">Modelo de face</label>
              <select id="re-modelo" name="modelo" [(ngModel)]="novo.modelo_face_id">
                <option [ngValue]="null">Sem modelo (cadastro as portas depois)</option>
                @for (m of modelos(); track m.id) { <option [ngValue]="m.id">{{ m.nome }} ({{ m.linhas * m.colunas + m.portas_extras.length }} portas, {{ m.altura_u }}U)</option> }
              </select></div>
            <div><label for="re-ip">IP de gerência @if (passivo(novo.tipo)) { <small>(opcional)</small> }</label>
              <input id="re-ip" name="ip" maxlength="45" placeholder="Ex.: 10.23.5.2" [required]="!passivo(novo.tipo)" [(ngModel)]="novo.ip_gerencia" /></div>
            <div><label for="re-rack">Rack</label>
              <select id="re-rack" name="rack" [(ngModel)]="novo.rack_id">
                <option [ngValue]="null">Fora de rack</option>
                @for (r of racks(); track r.id) { <option [ngValue]="r.id">{{ r.nome }} ({{ r.altura_u }}U)</option> }
              </select></div>
            <div><label for="re-u">Posição no rack (U)</label>
              <input id="re-u" name="u" type="number" min="1" max="60" [disabled]="!novo.rack_id" placeholder="U mais baixo que ocupa (U1 = embaixo)" [(ngModel)]="novo.posicao_u" /></div>
            <div class="ocupa-duas acoes-formulario">
              <button type="button" class="acao-secundaria" (click)="fecharFormulario(fe)">Cancelar</button>
              <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fe.invalid || salvando()">Cadastrar equipamento</button>
            </div>
          </form>
        }

        @if (carregando()) {
          <app-esqueleto tipo="tabela" [linhas]="6" [colunas]="5" />
        } @else if (visao() === 'racks') {
          <!-- Rack → clica no equipamento → face → clica na porta → detalhe da porta -->
          <div class="grade-racks">
            @for (r of racks(); track r.id) {
              <app-rack-rede [rack]="r" [equipamentos]="doRack(r.id)">
                @if (papeis()?.administrar) {
                  <div class="botoes-linha"><button type="button" class="acao-secundaria acao-pequena" (click)="abrirRack(r)">Editar</button>
                    <button type="button" class="acao-perigo acao-pequena" (click)="excluirRack(r)">Excluir</button></div>
                }
              </app-rack-rede>
            }
          </div>
          @if (foraDeRack().length) {
            <p class="dica-formulario">Fora de rack:
              @for (e of foraDeRack(); track e.id) { <a [routerLink]="['/rede/equipamentos', e.id]">{{ e.nome }}</a>{{ $last ? '' : ', ' }} }</p>
          }
          @if (!racks().length) { <p class="estado-vazio">Nenhum rack cadastrado. {{ papeis()?.administrar ? 'Use "Novo rack" para começar.' : '' }}</p> }
        } @else {
          <div class="chips-filtro" role="group" aria-label="Tipo de equipamento">
            @for (t of filtros; track t[0]) {
              <button type="button" [class.ativo]="tipo() === t[0]" [attr.aria-pressed]="tipo() === t[0]" (click)="tipo.set(t[0]); carregar()">{{ t[1] }}</button>
            }
          </div>
          <div class="barra-protocolo">
            <div class="campo"><label for="re-busca">Busca</label>
              <input id="re-busca" type="search" placeholder="Nome, IP ou rack" [(ngModel)]="busca" (keyup.enter)="carregar()" /></div>
            <button type="button" class="acao-secundaria" (click)="carregar()">Buscar</button>
          </div>
          <div class="tabela-gestao-envoltorio">
            <table class="tabela-gestao">
              <thead><tr><th scope="col">Equipamento</th><th scope="col">Tipo</th><th scope="col">Ping</th><th scope="col">Modelo</th><th scope="col">Rack</th><th scope="col">Portas</th></tr></thead>
              <tbody>
                @for (e of itens(); track e.id) {
                  <tr>
                    <td data-rotulo="Equipamento"><a [routerLink]="['/rede/equipamentos', e.id]"><strong>{{ e.nome }}</strong></a>
                      @if (e.ip_gerencia) { <br /><small class="texto-codigo">{{ e.ip_gerencia }}</small> }
                      @if (!e.ativo) { <span class="selo-status" data-chamado="neutro">Inativo</span> }
                      @if (e.cadastro_incompleto) { <span class="selo-status" data-chamado="alerta">Cadastro incompleto</span> }</td>
                    <td data-rotulo="Tipo">{{ rotuloTipo(e.tipo) }}@if (e.funcao) { <br /><small>{{ rotulosFuncao[e.funcao] }}</small> }</td>
                    <td data-rotulo="Ping">@if (e.ping_situacao) {
                        <span class="selo-status" [attr.data-chamado]="e.ping_situacao === 'no_ar' ? 'sucesso' : 'perigo'">{{ rotulosPing[e.ping_situacao] }}</span>
                      } @else { — }</td>
                    <td data-rotulo="Modelo">{{ e.modelo_nome || '—' }}</td>
                    <td data-rotulo="Rack">{{ e.rack_nome || 'Fora de rack' }}{{ e.posicao_u ? ' · U' + e.posicao_u : '' }}</td>
                    <td data-rotulo="Portas">{{ e.portas_total }}
                      @if (e.portas_up) { <span class="selo-status" data-chamado="sucesso">{{ e.portas_up }} ligadas</span> }
                      @if (e.portas_down) { <span class="selo-status" data-chamado="perigo">{{ e.portas_down }} desligadas</span> }</td>
                  </tr>
                } @empty { <tr><td colspan="6" class="estado-vazio">Nenhum equipamento. A carga inicial vem do GLPI (scripts/migrar-rede-glpi.py) ou cadastre em "Novo equipamento".</td></tr> }
              </tbody>
            </table>
          </div>
        }
      </section>
    </div>
  `,
})
export class EquipamentosRedeComponent implements OnInit {
  private readonly api = inject(RedeApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly papeis = inject(AcessoService).rede;

  protected readonly filtros: [string, string][] = [['', 'Todos'], ['switch', 'Switches'], ['patch_panel', 'Patch panels'], ['roteador', 'Roteadores'], ['outro', 'Outros']];
  protected readonly tipos = Object.entries(ROTULOS_TIPO_EQUIPAMENTO) as [TipoEquipamento, string][];
  protected readonly funcoes = Object.entries(ROTULOS_FUNCAO_EQUIPAMENTO) as [FuncaoEquipamento, string][];
  protected readonly passivo = ehPassivo;
  protected readonly rotulosFuncao = ROTULOS_FUNCAO_EQUIPAMENTO;
  protected readonly rotulosPing = ROTULOS_PING;
  protected readonly cores = CORES_RACK;
  protected readonly tipo = signal('');
  protected readonly itens = signal<EquipamentoResumo[]>([]);
  protected readonly racks = signal<Rack[]>([]);
  protected readonly modelos = signal<ModeloFace[]>([]);
  /** Todas as salas ativas, no formato do campo de sala (carregadas uma vez, ao abrir o formulário do rack). */
  protected readonly salas = signal<OpcaoSala[]>([]);
  protected readonly carregando = signal(true);
  protected readonly salvando = signal(false);
  /** Visão padrão: os racks (decisão do usuário); a lista continua para busca e filtro. */
  protected readonly visao = signal<'racks' | 'lista'>('racks');
  protected readonly formulario = signal<'rack' | 'equipamento' | null>(null);
  protected readonly editandoRack = signal<Rack | null>(null);
  protected readonly foraDeRack = computed(() => this.itens().filter((x) => !x.rack_id));
  protected busca = '';
  protected novo = equipamentoVazio();
  protected rack = rackVazio();

  ngOnInit(): void {
    this.carregar();
    this.api.modelos().subscribe({ next: (x) => this.modelos.set(x), error: () => undefined });
  }

  protected carregar(): void {
    this.carregando.set(true);
    this.api.racks().subscribe({ next: (x) => this.racks.set(x), error: () => undefined });
    this.api.equipamentos(this.busca, this.tipo()).subscribe({
      next: (x) => { this.itens.set(x); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar os equipamentos'); },
    });
  }

  protected doRack(id: string): EquipamentoResumo[] {
    return this.itens().filter((e) => e.rack_id === id);
  }

  /** Os racks mostram tudo: a busca e o filtro de tipo são da lista. */
  protected verRacks(): void {
    this.visao.set('racks');
    if (this.tipo() || this.busca) {
      this.tipo.set('');
      this.busca = '';
      this.carregar();
    }
  }

  protected abrirRack(r: Rack | null): void {
    this.editandoRack.set(r);
    this.rack = r ? { nome: r.nome, cor: r.cor, localizacao_id: r.localizacao_id, altura_u: r.altura_u, observacao: r.observacao } : rackVazio();
    if (!this.salas().length) {
      this.api.salas('', true).subscribe({
        next: (x) => this.salas.set(x.map((l) => ({ id: l.id, codigo: l.codigo || null, rotulo: l.rotulo || `${l.codigo} · ${l.nome}`, andar: l.andar, ativo: true,
          deposito: false, semResponsavel: false }))),
        error: () => undefined,
      });
    }
    this.formulario.set('rack');
  }

  protected fecharFormulario(form?: NgForm): void {
    form?.resetForm();
    this.novo = equipamentoVazio();
    this.rack = rackVazio();
    this.editandoRack.set(null);
    this.formulario.set(null);
  }

  protected salvarRack(form: NgForm): void {
    this.salvando.set(true);
    this.api.salvarRack(this.editandoRack()?.id ?? null, this.rack).subscribe({
      next: () => { this.salvando.set(false); this.fecharFormulario(form); this.carregar(); },
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível salvar o rack'); },
    });
  }

  protected async excluirRack(r: Rack): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir o rack ${r.nome}?`, mensagem: 'Só sai se não tiver equipamento.', rotuloConfirmar: 'Excluir rack', segundos: 3 });
    if (!ok) return;
    this.api.excluirRack(r.id).subscribe({ next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir o rack') });
  }

  protected criar(form: NgForm): void {
    this.salvando.set(true);
    this.api.salvarEquipamento(null, { ...this.novo, posicao_u: this.novo.rack_id ? this.novo.posicao_u : null }).subscribe({
      next: () => { this.salvando.set(false); this.fecharFormulario(form); this.carregar(); },
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível cadastrar o equipamento'); },
    });
  }

  protected rotuloTipo(t: TipoEquipamento): string {
    return ROTULOS_TIPO_EQUIPAMENTO[t];
  }
}
