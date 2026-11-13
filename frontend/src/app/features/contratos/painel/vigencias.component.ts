/**
 * =============================================================================
 * ARQUIVO: vigencias.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Tela "Vigências" do módulo Contratos: uma linha do tempo por contrato
 * vigente, do que vence primeiro ao último, com prorrogações, marcas de
 * reajuste e a cor de urgência do vencimento.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template embutido e detecção de mudanças OnPush
 * (só redesenha quando signals ou entradas mudam). Busca o painel de vigências
 * na API e, num computed, transforma cada contrato em LinhaPrazo pela função
 * exportada montarLinha (posições em % do trilho). Os limites de dias crítico
 * e de atenção vêm do ParametrosContratosService (90 e 180 por padrão).
 *
 * FINALIDADE DE NEGÓCIO:
 * Mostra de relance quais contratos estão perto de expirar e quanto ainda
 * podem ser prorrogados, para que a SPI inicie a prorrogação ou uma nova
 * contratação a tempo, sem deixar serviço essencial descoberto.
 *
 * CONTEXTO NO SISTEMA:
 * Rota do módulo Contratos. Usa ContratosApiService.painelVigencias,
 * ParametrosContratosService, formatarData e os tipos PainelVigencias e
 * VigenciaContratoPainel. Os limites são os mesmos editados em
 * parametros.component.ts.
 *
 * =============================================================================
 */

import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { formatarData } from '../../../shared/utilitarios/formatadores';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { ParametrosContratosService } from '../compartilhado/parametros-contratos.service';
import { PainelVigencias, VigenciaContratoPainel } from '../compartilhado/contratos.models';

import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
/** Até quantos dias o vencimento fica vermelho (mesmo critério de "a vencer") e âmbar: parâmetros de Contratos (90 e 180 de início). */
interface Limites { critico: number; atencao: number }
const LIMITES_DE_FABRICA: Limites = { critico: 90, atencao: 180 };
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
  imports: [EsqueletoComponent, FormsModule, RouterLink, CabecalhoModuloComponent],
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
            <span><i class="critico"></i>Até {{ limites().critico }} dias</span><span><i class="atencao"></i>Até {{ limites().atencao }} dias</span>
            <span><i class="normal"></i>Mais de {{ limites().atencao }} dias</span><span><i class="reajuste"></i>Reajuste</span>
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
      <app-esqueleto tipo="painel" [linhas]="4" />
    }
  `,
})
export class VigenciasComponent implements OnInit {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly painel = signal<PainelVigencias | null>(null);
  protected empresaId = '';
  protected readonly data = formatarData;
  private readonly parametros = inject(ParametrosContratosService);
  // Limites vêm dos parâmetros de Contratos (tela Parâmetros), não fixos no código
  protected readonly limites = computed<Limites>(() => ({ critico: this.parametros.valores().dias_vigencia_a_vencer, atencao: this.parametros.valores().dias_vigencia_atencao }));

  /** Linhas calculadas a partir do painel e dos limites (refaz sozinha quando os parâmetros chegam). */
  protected readonly linhas = computed<LinhaPrazo[]>(() => {
    const p = this.painel();
    return p ? p.contratos.map((c) => montarLinha(c, p.hoje, this.limites())) : [];
  });

  /** Pede os parâmetros do módulo (limites de dias) e carrega as vigências. */
  ngOnInit(): void {
    this.parametros.carregar();
    this.carregar();
  }

  /** Busca as vigências (com o filtro de empresa) e calcula as posições de cada linha. */
  protected carregar(): void {
    this.api.painelVigencias(this.empresaId).subscribe({
      next: (p) => {
        this.painel.set(p);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o painel de vigências'),
    });
  }
}

/** Data AAAA-MM-DD em milissegundos (UTC, sem fuso). */
function dia(texto: string): number {
  return Date.parse(`${texto}T00:00:00Z`);
}

/**
 * Posições da linha na escala do próprio contrato: do início ao fim da vigência atual (inclusive).
 * - `total` soma um dia ao fim para que o último dia conte inteiro no trilho.
 * - `posicao` converte uma data em % do trilho, com uma casa decimal, presa entre 0 e 100.
 * - Cada vigência (inicial e prorrogações) vira um segmento; a sequência 1 é a vigência inicial.
 * - A urgência compara os dias restantes com os limites (vermelho, âmbar ou normal).
 * Exportada para poder ser testada sem montar o componente.
 * @param c contrato vigente como veio da API.
 * @param hoje data de hoje (AAAA-MM-DD) informada pelo servidor, para não depender do relógio do navegador.
 * @param limites cortes de dias; sem parâmetros carregados usa 90 e 180.
 */
export function montarLinha(c: VigenciaContratoPainel, hoje: string, limites: Limites = LIMITES_DE_FABRICA): LinhaPrazo {
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
  const urgencia = c.dias_restantes <= limites.critico ? 'critico' : c.dias_restantes <= limites.atencao ? 'atencao' : 'normal';
  return {
    contrato: c, segmentos, decorrido: posicao(dia(hoje)), urgencia,
    reajustes: c.reajustes.map((r) => ({ posicao: posicao(dia(r)), titulo: `Reajuste a partir de ${formatarData(r).slice(3)}` })),
    descricao: `Contrato ${c.numero}: ${segmentos.map((s) => s.titulo).join('; ')}. Vence em ${formatarData(c.data_fim)} (${c.dias_restantes} dias).`,
  };
}
