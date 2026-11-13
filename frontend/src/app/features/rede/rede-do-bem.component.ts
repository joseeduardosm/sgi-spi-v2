// Criado por José Eduardo Santana Martins
// Este arquivo serve para mostrar, no cadastro do bem (Patrimônio), em qual switch e porta ele está ligado, e ligar ou desligar dali mesmo.

import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AcessoService } from '../../core/acesso/acesso.service';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CaminhoRedeComponent } from './caminho-rede.component';
import { RedeApiService } from './rede-api.service';
import { EquipamentoResumo, LADOS_PATCH, LadoPatch, ladoLivre, Porta, PortaDoBem } from './rede.models';

/** É a mesma ligação da tela da porta (Rede › switch › porta): o que se faz num lugar aparece no outro. Só para quem tem acesso à Rede. */
@Component({
  selector: 'app-rede-do-bem',
  imports: [FormsModule, RouterLink, CaminhoRedeComponent],
  template: `
    @if (papeis()?.ver) {
      <h3 class="pat-subtitulo">Rede</h3>
      @for (p of portas(); track p.porta_id) {
        <p class="rede-do-bem-linha">Ligado em <a [routerLink]="['/rede/equipamentos', p.equipamento_id]">{{ p.equipamento_nome }}</a> ·
          <a [routerLink]="['/rede/portas', p.porta_id]">porta {{ p.porta_nome }}{{ p.lado ? ' (' + p.lado + ')' : '' }}</a>@if (p.atras_de) { <span>, atrás de {{ p.atras_de }}</span> }
          @if (papeis()?.editar) { <button type="button" class="acao-recusar acao-pequena" [disabled]="salvando()" (click)="desligar(p)">Desligar</button> }</p>
        <app-caminho-rede [portaId]="p.porta_id" />
      } @empty {
        <p class="estado-vazio">Este bem não está ligado em nenhuma porta de rede.</p>
      }
      @if (papeis()?.editar && !portas().length) {
        <div class="grade-formulario rede-do-bem-form">
          <div><label for="rb-equip">Switch ou patch panel</label>
            <select id="rb-equip" name="rb-equip" [(ngModel)]="equipamento" (ngModelChange)="carregarPortas($event)">
              <option [ngValue]="null">Escolha</option>
              @for (e of equipamentos(); track e.id) { <option [ngValue]="e.id">{{ e.nome }}{{ e.rack_nome ? ' (' + e.rack_nome + ')' : '' }}</option> }
            </select></div>
          <div><label for="rb-porta">Porta</label>
            <select id="rb-porta" name="rb-porta" [disabled]="!equipamento" [(ngModel)]="porta" (ngModelChange)="lado = null">
              <option [ngValue]="null">Escolha</option>
              @for (x of portasDoEquipamento(); track x.id) { <option [ngValue]="x.id" [disabled]="ocupada(x)">{{ x.nome || x.numero_logico }}{{ ocupada(x) ? ' (ocupada)' : '' }}</option> }
            </select></div>
          @if (ehPatch()) {
            <!-- Patch panel: o bem fica num dos lados da porta (normalmente o fundo, o cabo que vai até a sala) -->
            <div><label for="rb-lado">Lado da porta</label>
              <select id="rb-lado" name="rb-lado" [disabled]="!porta" [(ngModel)]="lado">
                <option [ngValue]="null">Escolha</option>
                @for (l of lados; track l.valor) { <option [ngValue]="l.valor" [disabled]="!livre(l.valor)">{{ l.rotulo }}{{ livre(l.valor) ? '' : ' (ocupado)' }}</option> }
              </select></div>
          }
          <div class="ocupa-duas acoes-formulario">
            <button type="button" class="acao-primaria acao-pequena" [class.carregando]="salvando()" [disabled]="salvando() || !porta || (ehPatch() && !lado)" (click)="ligar()">Ligar na porta</button>
          </div>
        </div>
      }
    }
  `,
  styles: ['.rede-do-bem-linha { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 0 0 8px; } .rede-do-bem-form { margin-bottom: 12px; }'],
})
export class RedeDoBemComponent implements OnInit {
  readonly bemId = input.required<string>();
  private readonly api = inject(RedeApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly papeis = inject(AcessoService).rede;

  protected readonly portas = signal<PortaDoBem[]>([]);
  protected readonly equipamentos = signal<EquipamentoResumo[]>([]);
  protected readonly portasDoEquipamento = signal<Porta[]>([]);
  protected readonly salvando = signal(false);
  protected equipamento: string | null = null;
  protected porta: string | null = null;
  /** Lado da porta quando o equipamento escolhido é patch panel. */
  protected lado: LadoPatch | null = null;
  protected readonly lados = LADOS_PATCH;

  ngOnInit(): void {
    if (!this.papeis()?.ver) return;
    this.carregar();
    if (this.papeis()?.editar) this.api.equipamentos().subscribe({ next: (x) => this.equipamentos.set(x), error: () => undefined });
  }

  private carregar(): void {
    this.api.portasDoBem(this.bemId()).subscribe({ next: (x) => this.portas.set(x), error: () => undefined });
  }

  protected carregarPortas(id: string | null): void {
    this.porta = null;
    this.portasDoEquipamento.set([]);
    if (id) this.api.equipamento(id).subscribe({ next: (e) => this.portasDoEquipamento.set(e.portas), error: () => undefined });
  }

  protected ehPatch(): boolean {
    return this.equipamentos().find((e) => e.id === this.equipamento)?.tipo === 'patch_panel';
  }

  /** Porta sem lugar: ligada (switch) ou com os dois lados ligados (patch panel). */
  protected ocupada(x: Porta): boolean {
    return this.ehPatch() ? !!(x.fundo && x.frente) : !!x.conexao;
  }

  protected livre(lado: LadoPatch): boolean {
    const x = this.portasDoEquipamento().find((p) => p.id === this.porta);
    return !x || ladoLivre(x, lado);
  }

  protected ligar(): void {
    if (!this.porta) return;
    this.salvando.set(true);
    this.api.ligar(this.porta, { bem_id: this.bemId(), lado: this.ehPatch() ? this.lado : null }).subscribe({
      next: () => { this.salvando.set(false); this.equipamento = this.porta = null; this.lado = null; this.carregar(); },
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível ligar o bem na porta'); },
    });
  }

  /** Atrás de outro dispositivo: tira só este bem (o da frente continua). Direto na porta: a porta fica livre (e os de trás saem junto). */
  protected async desligar(p: PortaDoBem): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Desligar o bem da porta?', rotuloConfirmar: 'Desligar',
      mensagem: p.dispositivo_id ? `Sai de trás de ${p.atras_de}; o resto da ligação continua.`
        : `${p.equipamento_nome} · porta ${p.porta_nome}${p.lado ? ' (' + p.lado + ')' : ''} fica livre (os dispositivos ligados atrás dele saem junto). `
          + 'Sem nada ligado, a porta passa a "Desligada" e fica em branco (modo, VLANs, IP e velocidade são apagados).',
    });
    if (!ok) return;
    this.salvando.set(true);
    (p.dispositivo_id ? this.api.removerAtras(p.porta_id, p.dispositivo_id) : this.api.desligar(p.porta_id, p.lado ?? null)).subscribe({
      next: () => { this.salvando.set(false); this.carregar(); },
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível desligar'); },
    });
  }
}
