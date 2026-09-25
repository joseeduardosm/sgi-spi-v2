import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { Previsao, VigenciaPrevisao } from '../compartilhado/contratos.models';
import { paraDecimalApi, paraDecimalTela, ROTULOS_TIPO_ITEM } from '../compartilhado/rotulos';

/** Aba "Previsão orçamentária": grade sob demanda por vigência (selada ao salvar) e tabela mensal. */
@Component({
  selector: 'app-aba-previsao',
  imports: [FormsModule, ...PIPES_FORMATACAO],
  templateUrl: './aba-previsao.component.html',
})
export class AbaPrevisaoComponent implements OnInit {
  readonly contratoId = input.required<string>();

  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly autenticacao = inject(AutenticacaoService);
  protected readonly superRoot = computed(() => this.autenticacao.possuiPapel('SuperRoot'));

  protected readonly previsao = signal<Previsao | null>(null);
  /** Grade em edição por vigência: item → mês → quantidade digitada. */
  protected grades: Record<number, Record<string, Record<string, string>>> = {};
  protected readonly editandoSelada = signal<Set<number>>(new Set());
  protected readonly expandidos = signal<Set<string>>(new Set());
  protected readonly rotulosTipo = ROTULOS_TIPO_ITEM;

  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    this.api.previsao(this.contratoId()).subscribe({
      next: (p) => this.aplicar(p),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a previsão'),
    });
  }

  private aplicar(previsao: Previsao): void {
    this.previsao.set(previsao);
    this.grades = {};
    for (const v of previsao.vigencias) {
      this.grades[v.sequencia] = Object.fromEntries(
        v.itens_sob_demanda.map((i) => [i.item_id, Object.fromEntries(v.meses.map((m) => [m, paraDecimalTela(i.apontamentos[m] ?? '0') || '']))]),
      );
    }
    this.editandoSelada.set(new Set());
  }

  protected mesesDaVigencia(sequencia: number) {
    return (this.previsao()?.meses ?? []).filter((m) => m.sequencia_vigencia === sequencia);
  }

  protected editavel(v: VigenciaPrevisao): boolean {
    return v.pode_editar && (!v.salva || this.editandoSelada().has(v.sequencia));
  }

  protected saldo(v: VigenciaPrevisao, itemId: string, limite: string): number {
    const grade = this.grades[v.sequencia]?.[itemId] ?? {};
    return Number(limite) - Object.values(grade).reduce((t, q) => t + (Number(paraDecimalApi(q)) || 0), 0);
  }

  protected temSaldoNegativo(v: VigenciaPrevisao): boolean {
    return v.itens_sob_demanda.some((i) => this.saldo(v, i.item_id, i.limite) < 0);
  }

  protected alternarEdicaoSelada(sequencia: number): void {
    const conjunto = new Set(this.editandoSelada());
    if (conjunto.has(sequencia)) conjunto.delete(sequencia);
    else conjunto.add(sequencia);
    this.editandoSelada.set(conjunto);
  }

  protected async salvar(v: VigenciaPrevisao): Promise<void> {
    if (!v.salva) {
      const ok = await this.dialogos.confirmar({
        titulo: `Salvar a previsão da ${v.sequencia}ª vigência?`,
        mensagem: 'Depois de salva, a previsão fica selada: somente o SuperRoot poderá alterá-la.',
        rotuloConfirmar: 'Salvar previsão',
        segundos: 3,
      });
      if (!ok) return;
    }
    const apontamentos = Object.entries(this.grades[v.sequencia] ?? {}).flatMap(([item_id, meses]) =>
      Object.entries(meses).map(([competencia, quantidade]) => ({ item_id, competencia, quantidade: paraDecimalApi(quantidade) })),
    );
    this.api.salvarPrevisao(this.contratoId(), v.sequencia, apontamentos).subscribe({
      next: (p) => this.aplicar(p),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar a previsão'),
    });
  }

  protected exportar(sequencia: number): void {
    this.dialogos.executar(this.api.exportarPrevisao(this.contratoId(), sequencia), 'Gerando a planilha…').subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected alternarMes(chave: string): void {
    const conjunto = new Set(this.expandidos());
    if (conjunto.has(chave)) conjunto.delete(chave);
    else conjunto.add(chave);
    this.expandidos.set(conjunto);
  }
}
