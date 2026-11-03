// Criado por José Eduardo Santana Martins
// Este arquivo serve para os cadastros do plano de face em abas: pontos de rede, VLANs e modelos de face.

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { Observable } from 'rxjs';

import { AcessoService } from '../../core/acesso/acesso.service';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { CabecalhoRedeComponent } from './cabecalho-rede.component';
import { RedeApiService } from './rede-api.service';
import { GravacaoModelo, GravacaoPonto, ModeloFace, ParametrosRede, PontoRede, Vlan } from './rede.models';

type Aba = 'pontos' | 'vlans' | 'modelos' | 'monitoramento';

function modeloVazio(): GravacaoModelo {
  return { nome: '', fabricante: '', linhas: 2, colunas: 24, numeracao: 'coluna', portas_extras: [], altura_u: 1 };
}

@Component({
  selector: 'app-cadastros-rede',
  imports: [FormsModule, CabecalhoRedeComponent, EsqueletoComponent],
  template: `
    <div class="modulo-chamados">
      <app-cabecalho-rede titulo="Pontos, VLANs e modelos" descricao="Os pontos de rede das salas, as VLANs e o desenho da face de cada modelo de equipamento." />
      <section class="painel-gestao protocolo">
        <div class="abas abas-rolagem" role="tablist">
          @for (x of abas; track x[0]) {
            @if (x[0] !== 'monitoramento' || papeis()?.administrar) {
            <button type="button" role="tab" [class.ativa]="aba() === x[0]" [attr.aria-selected]="aba() === x[0]" (click)="aba.set(x[0]); x[0] === 'monitoramento' && carregarParametros()">{{ x[1] }}</button>
            }
          }
        </div>
        @switch (aba()) {
          @case ('pontos') {
            <p class="dica-formulario">O código é o que está escrito na tomada. A porta é a do patch panel em que o ponto chega; o caminho até o switch sai das conexões.</p>
            @if (papeis()?.editar) {
              <form class="grade-formulario" (ngSubmit)="salvarPonto(fp)" #fp="ngForm">
                <div><label for="pt-codigo">{{ editandoPonto() ? 'Alterar ponto' : 'Novo ponto' }}</label>
                  <input id="pt-codigo" name="codigo" required maxlength="40" placeholder="Ex.: 5A-12" [(ngModel)]="ponto.codigo" /></div>
                <div><label for="pt-obs">Observação <small>(opcional)</small></label><input id="pt-obs" name="obs" maxlength="2000" [(ngModel)]="ponto.observacao" /></div>
                <div class="ocupa-duas acoes-formulario">
                  @if (editandoPonto()) { <button type="button" class="acao-secundaria" (click)="novoPonto(fp)">Cancelar edição</button> }
                  <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fp.invalid || salvando()">{{ editandoPonto() ? 'Salvar ponto' : 'Cadastrar ponto' }}</button>
                </div>
              </form>
            }
            <div class="barra-protocolo">
              <div class="campo"><label for="pt-busca">Busca</label><input id="pt-busca" type="search" placeholder="Código do ponto" [(ngModel)]="buscaPonto" (keyup.enter)="carregarPontos()" /></div>
              <button type="button" class="acao-secundaria" (click)="carregarPontos()">Buscar</button>
            </div>
            <div class="tabela-gestao-envoltorio">
              <table class="tabela-gestao">
                <thead><tr><th scope="col">Ponto</th><th scope="col">Sala</th><th scope="col">Caminho até o switch</th><th scope="col"></th></tr></thead>
                <tbody>
                  @for (x of pontos(); track x.id) {
                    <tr><td data-rotulo="Ponto"><strong class="texto-codigo">{{ x.codigo }}</strong>@if (x.observacao) { <br /><small>{{ x.observacao }}</small> }</td>
                      <td data-rotulo="Sala">{{ x.sala || '—' }}</td>
                      <td data-rotulo="Caminho">{{ x.caminho.length ? x.caminho.join(' → ') : 'Sem porta' }}</td>
                      <td>@if (papeis()?.editar) { <div class="botoes-linha"><button type="button" class="acao-secundaria acao-pequena" (click)="editarPonto(x)">Editar</button>
                        <button type="button" class="acao-perigo acao-pequena" (click)="excluirPonto(x)">Excluir</button></div> }</td></tr>
                  } @empty { <tr><td colspan="4" class="estado-vazio">Nenhum ponto de rede cadastrado.</td></tr> }
                </tbody>
              </table>
            </div>
          }
          @case ('vlans') {
            @if (papeis()?.administrar) {
              <form class="grade-formulario" (ngSubmit)="salvarVlan(fv)" #fv="ngForm">
                <div><label for="vl-num">{{ editandoVlan() ? 'Alterar VLAN' : 'Nova VLAN' }}</label>
                  <input id="vl-num" name="numero" type="number" min="1" max="4094" required placeholder="Número (1 a 4094)" [(ngModel)]="vlan.numero" /></div>
                <div><label for="vl-nome">Nome</label><input id="vl-nome" name="nome" maxlength="120" placeholder="Ex.: Voz" [(ngModel)]="vlan.nome" /></div>
                <div class="ocupa-duas acoes-formulario">
                  @if (editandoVlan()) { <button type="button" class="acao-secundaria" (click)="novaVlan(fv)">Cancelar edição</button> }
                  <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fv.invalid || salvando()">{{ editandoVlan() ? 'Salvar VLAN' : 'Criar VLAN' }}</button>
                </div>
              </form>
            }
            <div class="tabela-gestao-envoltorio">
              <table class="tabela-gestao">
                <thead><tr><th scope="col">VLAN</th><th scope="col">Nome</th><th scope="col">Portas</th><th scope="col"></th></tr></thead>
                <tbody>
                  @for (x of vlans(); track x.id) {
                    <tr><td data-rotulo="VLAN" class="texto-codigo">{{ x.numero }}</td><td data-rotulo="Nome">{{ x.nome }}</td><td data-rotulo="Portas">{{ x.portas }}</td>
                      <td>@if (papeis()?.administrar) { <div class="botoes-linha"><button type="button" class="acao-secundaria acao-pequena" (click)="editarVlan(x)">Editar</button>
                        <button type="button" class="acao-perigo acao-pequena" (click)="excluirVlan(x)">Excluir</button></div> }</td></tr>
                  } @empty { <tr><td colspan="4" class="estado-vazio">Nenhuma VLAN cadastrada.</td></tr> }
                </tbody>
              </table>
            </div>
          }
          @case ('monitoramento') {
            <p class="dica-formulario">O SGI testa por ping o IP de gerência de cada equipamento (menos patch panel). Depois de 3 falhas seguidas, o equipamento
              aparece como fora do ar; se for o core primário, o secundário assume o topo da topologia.</p>
            @if (parametros(); as pr) {
              <form class="grade-formulario" (ngSubmit)="salvarParametros()">
                <div><label for="rp-intervalo">Intervalo entre os pings (minutos)</label>
                  <input id="rp-intervalo" name="intervalo" type="number" min="1" max="60" required [(ngModel)]="pr.ping_intervalo_min" />
                  <small class="dica-formulario">De 1 a 60. Com 3 falhas seguidas para dar fora do ar, a queda aparece em cerca de 3 intervalos.</small></div>
                <div class="ocupa-duas acoes-formulario">
                  <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando()">Salvar</button>
                </div>
              </form>
            } @else {
              <app-esqueleto tipo="formulario" [linhas]="2" />
            }
          }
          @case ('modelos') {
            <p class="dica-formulario">O desenho da face: quantas linhas e colunas de portas, como são numeradas e as portas extras (uplink, fibra), com número maior que as da grade.</p>
            @if (papeis()?.administrar) {
              <form class="grade-formulario" (ngSubmit)="salvarModelo(fm)" #fm="ngForm">
                <div><label for="md-nome">{{ editandoModelo() ? 'Alterar modelo' : 'Novo modelo' }}</label>
                  <input id="md-nome" name="nome" required minlength="2" maxlength="150" placeholder="Ex.: Switch 48 portas + 4 SFP" [(ngModel)]="modelo.nome" /></div>
                <div><label for="md-fab">Fabricante</label><input id="md-fab" name="fab" maxlength="120" [(ngModel)]="modelo.fabricante" /></div>
                <div><label for="md-lin">Linhas</label><input id="md-lin" name="lin" type="number" min="1" max="8" required [(ngModel)]="modelo.linhas" /></div>
                <div><label for="md-col">Colunas</label><input id="md-col" name="col" type="number" min="1" max="64" required [(ngModel)]="modelo.colunas" /></div>
                <div><label for="md-num">Numeração</label>
                  <select id="md-num" name="num" [(ngModel)]="modelo.numeracao">
                    <option value="coluna">Por coluna (1 em cima, 2 embaixo, 3 em cima...)</option><option value="linha">Por linha (1 a N na primeira linha)</option>
                  </select></div>
                <!-- Portas extras (uplink, fibra): uma linha por porta, como as faixas do Expediente nos Parâmetros dos Chamados -->
                <div class="ocupa-duas">
                  <span class="rotulo-campo">Portas extras <small>(uplink e fibra, com número maior que as da grade)</small></span>
                  @for (e of modelo.portas_extras; track $index) {
                    <div class="faixa-expediente">
                      <div><label [for]="'md-ex-num-' + $index">Número</label>
                        <input [id]="'md-ex-num-' + $index" [name]="'exnum' + $index" type="number" min="1" required [(ngModel)]="e.numero" /></div>
                      <div><label [for]="'md-ex-nome-' + $index">Nome da interface</label>
                        <input [id]="'md-ex-nome-' + $index" [name]="'exnome' + $index" maxlength="20" placeholder="Ex.: 25GE1/0/3" [(ngModel)]="e.rotulo" /></div>
                      <div><label [for]="'md-ex-tipo-' + $index">Tipo</label>
                        <select [id]="'md-ex-tipo-' + $index" [name]="'extipo' + $index" [(ngModel)]="e.tipo"><option value="fibra">Fibra</option><option value="cobre">Cobre</option></select></div>
                      <button type="button" class="acao-perigo acao-pequena" (click)="removerExtra($index)">Remover</button>
                    </div>
                  } @empty { <p class="dica-formulario">Nenhuma porta extra.</p> }
                  <button type="button" class="acao-secundaria acao-pequena" (click)="adicionarExtra()">Adicionar porta extra</button>
                </div>
                <div class="ocupa-duas acoes-formulario">
                  @if (editandoModelo()) { <button type="button" class="acao-secundaria" (click)="novoModelo(fm)">Cancelar edição</button> }
                  <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="fm.invalid || salvando()">{{ editandoModelo() ? 'Salvar modelo' : 'Criar modelo' }}</button>
                </div>
              </form>
            }
            <div class="tabela-gestao-envoltorio">
              <table class="tabela-gestao">
                <thead><tr><th scope="col">Modelo</th><th scope="col">Grade</th><th scope="col">Extras</th><th scope="col">Em uso</th><th scope="col"></th></tr></thead>
                <tbody>
                  @for (x of modelos(); track x.id) {
                    <tr><td data-rotulo="Modelo"><strong>{{ x.nome }}</strong>@if (x.fabricante) { <br /><small>{{ x.fabricante }}</small> }</td>
                      <td data-rotulo="Grade">{{ x.linhas }} × {{ x.colunas }} · por {{ x.numeracao }}</td>
                      <td data-rotulo="Extras">{{ x.portas_extras.length ? x.portas_extras.map(numeroExtra).join(', ') : '—' }}</td>
                      <td data-rotulo="Em uso">{{ x.equipamentos }}</td>
                      <td>@if (papeis()?.administrar) { <div class="botoes-linha"><button type="button" class="acao-secundaria acao-pequena" (click)="editarModelo(x)">Editar</button>
                        <button type="button" class="acao-perigo acao-pequena" (click)="excluirModelo(x)">Excluir</button></div> }</td></tr>
                  } @empty { <tr><td colspan="5" class="estado-vazio">Nenhum modelo de face.</td></tr> }
                </tbody>
              </table>
            </div>
          }
        }
      </section>
    </div>
  `,
})
export class CadastrosRedeComponent implements OnInit {
  private readonly api = inject(RedeApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  protected readonly papeis = inject(AcessoService).rede;

  protected readonly abas: [Aba, string][] = [['pontos', 'Pontos de rede'], ['vlans', 'VLANs'], ['modelos', 'Modelos de face'], ['monitoramento', 'Monitoramento']];
  protected readonly aba = signal<Aba>('pontos');
  protected readonly salvando = signal(false);
  protected readonly pontos = signal<PontoRede[]>([]);
  protected readonly vlans = signal<Vlan[]>([]);
  protected readonly modelos = signal<ModeloFace[]>([]);
  /** Parâmetros da Rede (intervalo do ping); só carrega ao abrir a aba, e só Controle total vê a aba. */
  protected readonly parametros = signal<ParametrosRede | null>(null);
  protected readonly editandoPonto = signal<string | null>(null);
  protected readonly editandoVlan = signal<string | null>(null);
  protected readonly editandoModelo = signal<string | null>(null);
  protected ponto: GravacaoPonto = { codigo: '', localizacao_id: null, porta_id: null, observacao: '' };
  protected vlan = { numero: null as number | null, nome: '', descricao: '' };
  protected modelo: GravacaoModelo = modeloVazio();
  protected buscaPonto = '';
  protected readonly numeroExtra = (e: { numero: number }) => e.numero;

  ngOnInit(): void {
    const aba = this.rota.snapshot.queryParamMap.get('aba') as Aba | null;
    if (aba && this.abas.some((x) => x[0] === aba)) this.aba.set(aba);
    if (this.aba() === 'monitoramento') this.carregarParametros();
    this.carregarPontos();
    this.api.vlans().subscribe({ next: (x) => this.vlans.set(x), error: () => undefined });
    this.api.modelos().subscribe({ next: (x) => this.modelos.set(x), error: () => undefined });
  }

  private salvar<T>(pedido: Observable<T>, depois: () => void): void {
    this.salvando.set(true);
    pedido.subscribe({ next: () => { this.salvando.set(false); depois(); }, error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível salvar'); } });
  }

  protected carregarParametros(): void {
    if (this.parametros()) return;
    this.api.parametros().subscribe({ next: (x) => this.parametros.set(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar os parâmetros') });
  }

  protected salvarParametros(): void {
    const pr = this.parametros();
    if (!pr) return;
    this.salvar(this.api.salvarParametros(pr), () => this.dialogos.avisar('Parâmetros salvos', `O ping roda a cada ${pr.ping_intervalo_min} minuto(s) a partir da próxima rodada.`));
  }

  protected carregarPontos(): void {
    this.api.pontos(this.buscaPonto).subscribe({ next: (x) => this.pontos.set(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar os pontos') });
  }

  protected novoPonto(form?: NgForm): void {
    this.editandoPonto.set(null);
    this.ponto = { codigo: '', localizacao_id: null, porta_id: null, observacao: '' };
    form?.resetForm({ codigo: '', obs: '' });
  }

  protected editarPonto(x: PontoRede): void {
    this.editandoPonto.set(x.id);
    this.ponto = { codigo: x.codigo, localizacao_id: x.localizacao_id, porta_id: x.porta_id, observacao: x.observacao };
  }

  protected salvarPonto(form: NgForm): void {
    this.salvar(this.api.salvarPonto(this.editandoPonto(), this.ponto), () => { this.novoPonto(form); this.carregarPontos(); });
  }

  protected async excluirPonto(x: PontoRede): Promise<void> {
    if (await this.dialogos.confirmar({ titulo: `Excluir o ponto ${x.codigo}?`, mensagem: 'Os chamados que apontavam o ponto ficam sem ele.', rotuloConfirmar: 'Excluir ponto', segundos: 3 })) {
      this.salvar(this.api.excluirPonto(x.id), () => this.carregarPontos());
    }
  }

  protected novaVlan(form?: NgForm): void {
    this.editandoVlan.set(null);
    this.vlan = { numero: null, nome: '', descricao: '' };
    form?.resetForm({ numero: null, nome: '' });
  }

  protected editarVlan(x: Vlan): void {
    this.editandoVlan.set(x.id);
    this.vlan = { numero: x.numero, nome: x.nome, descricao: x.descricao };
  }

  protected salvarVlan(form: NgForm): void {
    this.salvar(this.api.salvarVlan(this.editandoVlan(), { numero: this.vlan.numero ?? 0, nome: this.vlan.nome, descricao: this.vlan.descricao }), () => {
      this.novaVlan(form);
      this.api.vlans().subscribe((x) => this.vlans.set(x));
    });
  }

  protected async excluirVlan(x: Vlan): Promise<void> {
    if (await this.dialogos.confirmar({ titulo: `Excluir a VLAN ${x.numero}?`, mensagem: 'Só sai se nenhuma porta a usar.', rotuloConfirmar: 'Excluir VLAN', segundos: 3 })) {
      this.salvar(this.api.excluirVlan(x.id), () => this.api.vlans().subscribe((v) => this.vlans.set(v)));
    }
  }

  protected novoModelo(form?: NgForm): void {
    this.editandoModelo.set(null);
    this.modelo = modeloVazio();
    form?.resetForm({ nome: '', fab: '', lin: 2, col: 24, num: 'coluna' });
  }

  protected editarModelo(x: ModeloFace): void {
    this.editandoModelo.set(x.id);
    this.modelo = { nome: x.nome, fabricante: x.fabricante, linhas: x.linhas, colunas: x.colunas, numeracao: x.numeracao,
      portas_extras: x.portas_extras.map((e) => ({ ...e })), altura_u: x.altura_u };
  }

  /** Nova linha com o número seguinte (ao último extra ou ao fim da grade). */
  protected adicionarExtra(): void {
    const extras = this.modelo.portas_extras;
    const proximo = extras.length ? Math.max(...extras.map((e) => Number(e.numero) || 0)) + 1 : this.modelo.linhas * this.modelo.colunas + 1;
    extras.push({ numero: proximo, rotulo: '', tipo: 'fibra' });
  }

  protected removerExtra(indice: number): void {
    this.modelo.portas_extras.splice(indice, 1);
  }

  protected salvarModelo(form: NgForm): void {
    // Nome vazio vira o próprio número (o backend faz o mesmo)
    const extras = this.modelo.portas_extras.map((e) => ({ ...e, rotulo: e.rotulo.trim() || String(e.numero) }));
    this.salvar(this.api.salvarModelo(this.editandoModelo(), { ...this.modelo, portas_extras: extras }), () => {
      this.novoModelo(form);
      this.api.modelos().subscribe((x) => this.modelos.set(x));
    });
  }

  protected async excluirModelo(x: ModeloFace): Promise<void> {
    if (await this.dialogos.confirmar({ titulo: `Excluir o modelo ${x.nome}?`, mensagem: 'Só sai se nenhum equipamento o usar.', rotuloConfirmar: 'Excluir modelo', segundos: 3 })) {
      this.salvar(this.api.excluirModelo(x.id), () => this.api.modelos().subscribe((m) => this.modelos.set(m)));
    }
  }
}
