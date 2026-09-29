// Criado por José Eduardo Santana Martins
// Este arquivo serve para o painel de férias e licença-prêmio da CGP e dos autorizadores (calendário, filtros, alertas e aprovação).

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { LancamentoAfastamentoComponent } from './lancamento-afastamento.component';
import { FiltrosPainel, RhApiService } from './rh-api.service';
import { Afastamento, PainelAfastamentos, ROTULOS_STATUS, ROTULOS_TIPO, SIGLAS_TIPO } from './rh.models';

const DIA_MS = 86_400_000;
const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

function dia(texto: string): number {
  return Date.parse(`${texto}T00:00:00Z`);
}

function dataBr(texto: string): string {
  return texto.split('-').reverse().join('/');
}

/**
 * Painel de afastamentos: uma faixa por período ("[F] Nome – Setor"), amarela quando aguarda aprovação e verde
 * quando aprovada; visão mensal (dias) ou anual (meses); filtros por pessoa, setor (com os filhos) e tipo.
 * A CGP vê todos; o autorizador vê os autorizados e a si mesmo.
 */
@Component({
  selector: 'app-painel-afastamentos',
  imports: [FormsModule, DatePipe, CabecalhoRhComponent, LancamentoAfastamentoComponent],
  templateUrl: './painel-afastamentos.component.html',
  // Esc fecha o detalhe do período e a janela de recusa
  host: { '(document:keydown.escape)': 'detalhe.set(null); recusando.set(null)' },
})
export class PainelAfastamentosComponent implements OnInit {
  private readonly api = inject(RhApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly tipos = ROTULOS_TIPO;
  protected readonly siglas = SIGLAS_TIPO;
  protected readonly status = ROTULOS_STATUS;
  protected readonly meses = MESES;
  protected filtros: FiltrosPainel = { visao: 'mensal', ano: new Date().getFullYear(), mes: new Date().getMonth() + 1, pessoa_id: null, setor_id: null, tipo: '' };
  protected readonly painel = signal<PainelAfastamentos | null>(null);
  protected readonly aprovacoes = signal<Afastamento[]>([]);
  protected readonly hoje = new Date().toISOString().slice(0, 10);
  protected readonly anos = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - 1 + i);

  /** Marcas do eixo: dias do mês (visão mensal) ou meses (visão anual), em % da largura. */
  protected readonly eixo = computed(() => {
    const p = this.painel();
    if (!p) return [];
    const inicio = dia(p.inicio);
    const total = dia(p.fim) + DIA_MS - inicio;
    if (p.visao === 'anual') {
      return MESES.map((rotulo, m) => ({ rotulo, posicao: ((Date.UTC(this.filtros.ano, m, 1) - inicio) / total) * 100, fimDeSemana: false, feriado: null as string | null }));
    }
    // Feriados e pontos facultativos da janela (marcados como os fins de semana, com a descrição no título)
    const feriados = new Map(p.feriados.map((f) => [f.data, f]));
    const dias = Math.round(total / DIA_MS);
    return Array.from({ length: dias }, (_, i) => {
      const d = new Date(inicio + i * DIA_MS);
      const feriado = feriados.get(d.toISOString().slice(0, 10));
      return { rotulo: String(d.getUTCDate()), posicao: (i / dias) * 100, fimDeSemana: d.getUTCDay() === 0 || d.getUTCDay() === 6, feriado: feriado?.descricao ?? null };
    });
  });

  ngOnInit(): void {
    this.carregar();
  }

  protected carregar(): void {
    this.api.painel(this.filtros).subscribe({
      next: (p) => this.painel.set(p),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o painel'),
    });
    this.api.aprovacoes().subscribe({ next: (a) => this.aprovacoes.set(a), error: () => undefined });
  }

  /** Posição e largura (%) do período dentro da janela exibida. */
  protected barra(a: Afastamento): { esquerda: number; largura: number } {
    const p = this.painel()!;
    const inicio = dia(p.inicio);
    const total = dia(p.fim) + DIA_MS - inicio;
    const de = Math.max(dia(a.inicio), inicio);
    const ate = Math.min(dia(a.fim) + DIA_MS, dia(p.fim) + DIA_MS);
    return { esquerda: ((de - inicio) / total) * 100, largura: Math.max(((ate - de) / total) * 100, 0.6) };
  }

  protected data(texto: string): string {
    return dataBr(texto);
  }

  protected readonly lancando = signal(false);

  /** CGP: relatório de saldos de férias e LP de todos os servidores. */
  protected saldos(formato: 'pdf' | 'xlsx'): void {
    this.dialogos.executar(this.api.relatorioSaldos(formato), 'Gerando o relatório de saldos…').subscribe({
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar o relatório'),
    });
  }

  protected exportar(formato: 'pdf' | 'xlsx'): void {
    this.dialogos.executar(this.api.exportar(this.filtros, formato), 'Gerando o arquivo…').subscribe({
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível exportar'),
    });
  }

  protected async aprovar(a: Afastamento): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Aprovar pedido?',
      mensagem: `${ROTULOS_TIPO[a.tipo]} de ${a.nome} (${a.setor}), de ${dataBr(a.inicio)} a ${dataBr(a.fim)} (${a.dias} dias).`,
      rotuloConfirmar: 'Aprovar',
    });
    if (!ok) return;
    this.dialogos.executar(this.api.aprovar(a.id), 'Aprovando…').subscribe({
      next: () => this.carregar(),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível aprovar'),
    });
  }

  // Detalhe do período clicado no gráfico
  protected readonly detalhe = signal<Afastamento | null>(null);

  /** Aprovar a partir do detalhe: a própria janela já é a confirmação. */
  protected aprovarDoDetalhe(a: Afastamento): void {
    this.dialogos.executar(this.api.aprovar(a.id), 'Aprovando…').subscribe({
      next: () => {
        this.detalhe.set(null);
        this.carregar();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível aprovar'),
    });
  }

  // Recusa: janela com a justificativa (obrigatória)
  protected readonly recusando = signal<Afastamento | null>(null);
  protected justificativa = '';

  protected recusar(): void {
    const a = this.recusando();
    if (!a || !this.justificativa.trim()) return;
    this.dialogos.executar(this.api.recusarAfastamento(a.id, this.justificativa.trim()), 'Recusando…').subscribe({
      next: () => {
        this.recusando.set(null);
        this.justificativa = '';
        this.carregar();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível recusar'),
    });
  }
}
