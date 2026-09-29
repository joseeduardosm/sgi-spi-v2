// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir a aba "Vigências": uma linha do tempo de vigência por contrato vigente.

import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { formatarData } from '../../../shared/utilitarios/formatadores';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { PainelVigencias, VigenciaContratoPainel } from '../compartilhado/contratos.models';

/** Até quantos dias o vencimento fica vermelho (mesmo critério de "a vencer") e âmbar. */
const DIAS_CRITICO = 90;
const DIAS_ATENCAO = 180;
const DIA_MS = 86_400_000;

/** Linha já calculada para o template: posições em % do trilho (escala própria de cada contrato). */
interface LinhaPrazo {
  contrato: VigenciaContratoPainel;
  segmentos: { sequencia: number; inicio: number; largura: number; titulo: string }[];
  decorrido: number;
  reajustes: { posicao: number; titulo: string }[];
  urgencia: 'critico' | 'atencao' | 'normal';
  descricao: string;
}

/**
 * Painel de vigências: um contrato vigente por linha, do que vence primeiro ao último. Todos os trilhos têm
 * a mesma largura e cada um vai do início do contrato ao fim da vigência atual; assim, a parte decorrida
 * mostra de relance quem está mais perto de expirar, seja o contrato de 12, 15 ou 30 meses.
 */
@Component({
  selector: 'app-vigencias',
  imports: [FormsModule, RouterLink, CabecalhoModuloComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-cabecalho-modulo titulo="Vigências" [trilha]="['Vigências']"
                          descricao="Vigência dos contratos vigentes, do que vence primeiro ao último." />

    @if (painel(); as p) {
      <form class="filtros-gestao painel-gestao" style="margin-bottom: 18px; border-bottom: 0">
        <select name="empresa" aria-label="Empresa" [(ngModel)]="empresaId" (change)="carregar()">
          <option value="">Todas as empresas</option>
          @for (e of p.empresas; track e.id) { <option [value]="e.id">{{ e.rotulo }}</option> }
        </select>
      </form>

      <section class="cartao-dados" aria-labelledby="titulo-prazos">
        <header>
          <div><h2 id="titulo-prazos">Vigências ({{ linhas().length }})</h2></div>
          <div class="legenda-grafico legenda-prazos">
            <span><i class="critico"></i>Até {{ DIAS_CRITICO }} dias</span><span><i class="atencao"></i>Até {{ DIAS_ATENCAO }} dias</span>
            <span><i class="normal"></i>Mais de {{ DIAS_ATENCAO }} dias</span><span><i class="reajuste"></i>Reajuste</span>
          </div>
        </header>
        <ol class="lista-prazos">
          @for (l of linhas(); track l.contrato.contrato_id) {
            <li [class]="'linha-prazo ' + l.urgencia">
              <div class="identificacao-prazo">
                <a [routerLink]="['/contratos', l.contrato.contrato_id]"><strong>{{ l.contrato.numero }}</strong></a>
                <span [title]="l.contrato.rotulo">{{ l.contrato.rotulo }}</span>
                @if (l.contrato.rotulo !== l.contrato.empresa) { <small [title]="l.contrato.empresa">{{ l.contrato.empresa }}</small> }
              </div>
              <div class="trilho-prazo-area">
                <div class="trilho-prazo" role="img" [attr.aria-label]="l.descricao" [title]="l.descricao">
                  @for (s of l.segmentos; track s.sequencia) {
                    <span class="segmento" [class.prorrogacao]="s.sequencia > 1" [style.left.%]="s.inicio" [style.width.%]="s.largura" [title]="s.titulo"></span>
                  }
                  <span class="decorrido-prazo" [style.width.%]="l.decorrido"></span>
                  @for (r of l.reajustes; track $index) { <i class="marca-reajuste" [style.left.%]="r.posicao" [title]="r.titulo"></i> }
                  <i class="marca-hoje" [style.left.%]="l.decorrido" title="Hoje"></i>
                </div>
                <div class="datas-prazo"><span>{{ data(l.contrato.data_inicio) }}</span>
                  @if (l.segmentos.length > 1) { <span>{{ l.segmentos.length - 1 }} prorrogação(ões)</span> }
                  <span>{{ data(l.contrato.data_fim) }}</span></div>
              </div>
              <div class="vencimento-prazo">
                <strong>{{ l.contrato.dias_restantes === 0 ? 'Vence hoje' : l.contrato.dias_restantes + ' dia(s)' }}</strong>
                <span>vence em {{ data(l.contrato.data_fim) }}</span>
                <small>{{ l.contrato.meses_prorrogaveis ? 'pode prorrogar +' + l.contrato.meses_prorrogaveis + ' meses' : 'no limite máximo' }}</small>
              </div>
            </li>
          } @empty {
            <li class="estado-vazio">Nenhum contrato vigente.</li>
          }
        </ol>
      </section>
    } @else {
      <p class="estado-vazio">Carregando…</p>
    }
  `,
})
export class VigenciasComponent implements OnInit {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly painel = signal<PainelVigencias | null>(null);
  protected readonly linhas = signal<LinhaPrazo[]>([]);
  protected empresaId = '';
  protected readonly data = formatarData;
  protected readonly DIAS_CRITICO = DIAS_CRITICO;
  protected readonly DIAS_ATENCAO = DIAS_ATENCAO;

  ngOnInit(): void {
    this.carregar();
  }

  /** Busca as vigências (com o filtro de empresa) e calcula as posições de cada linha. */
  protected carregar(): void {
    this.api.painelVigencias(this.empresaId).subscribe({
      next: (p) => {
        this.painel.set(p);
        this.linhas.set(p.contratos.map((c) => montarLinha(c, p.hoje)));
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o painel de vigências'),
    });
  }
}

/** Data AAAA-MM-DD em milissegundos (UTC, sem fuso). */
function dia(texto: string): number {
  return Date.parse(`${texto}T00:00:00Z`);
}

/** Posições da linha na escala do próprio contrato: do início ao fim da vigência atual (inclusive). */
export function montarLinha(c: VigenciaContratoPainel, hoje: string): LinhaPrazo {
  const inicio = dia(c.data_inicio);
  const total = dia(c.data_fim) + DIA_MS - inicio;
  const posicao = (ms: number) => Math.min(100, Math.max(0, Math.round(((ms - inicio) / total) * 1000) / 10));
  const segmentos = c.vigencias.map((v) => {
    const de = posicao(dia(v.inicio));
    return {
      sequencia: v.sequencia, inicio: de, largura: posicao(dia(v.fim) + DIA_MS) - de,
      titulo: `${v.sequencia === 1 ? 'Vigência inicial' : `${v.sequencia - 1}ª prorrogação`}: ${formatarData(v.inicio)} a ${formatarData(v.fim)}`,
    };
  });
  const urgencia = c.dias_restantes <= DIAS_CRITICO ? 'critico' : c.dias_restantes <= DIAS_ATENCAO ? 'atencao' : 'normal';
  return {
    contrato: c, segmentos, decorrido: posicao(dia(hoje)), urgencia,
    reajustes: c.reajustes.map((r) => ({ posicao: posicao(dia(r)), titulo: `Reajuste a partir de ${formatarData(r).slice(3)}` })),
    descricao: `Contrato ${c.numero}: ${segmentos.map((s) => s.titulo).join('; ')}. Vence em ${formatarData(c.data_fim)} (${c.dias_restantes} dias).`,
  };
}
