import { DatePipe } from '@angular/common';
import { Component, computed, inject, input, OnChanges, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { DetalheCompetencia, NotaSelecionada } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { paraDecimalApi, paraDecimalTela, ROTULOS_PAPEL } from '../compartilhado/rotulos';

/** Etapa 1: medição, NEs em ordem de consumo, ciências (mínimo 2) e memória de cálculo. */
@Component({
  selector: 'app-etapa-medicao',
  imports: [FormsModule, DatePipe, ...PIPES_FORMATACAO],
  templateUrl: './etapa-medicao.component.html',
})
export class EtapaMedicaoComponent implements OnChanges {
  readonly detalhe = input.required<DetalheCompetencia>();
  readonly editavel = input(false);
  readonly atualizado = output<DetalheCompetencia>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly autenticacao = inject(AutenticacaoService);
  protected readonly papeis = ROTULOS_PAPEL;
  protected readonly jaRegistrei = computed(() => this.detalhe().ciencias.some((c) => c.usuario_id === this.autenticacao.usuario()?.id));

  protected medidas: Record<string, string> = {};
  protected readonly notas = signal<NotaSelecionada[]>([]);
  protected notaParaAdicionar = '';
  protected readonly alterado = signal(false);

  ngOnChanges(): void {
    const d = this.detalhe();
    this.medidas = Object.fromEntries(d.itens.map((i) => [i.id, paraDecimalTela(i.quantidade_medida)]));
    this.notas.set(d.notas_selecionadas);
    this.alterado.set(false);
  }

  protected readonly disponiveis = computed(() => {
    const escolhidas = new Set(this.notas().map((n) => n.id));
    return this.detalhe().notas_disponiveis.filter((n) => !escolhidas.has(n.id));
  });
  protected readonly saldoNotas = computed(() => this.notas().reduce((t, n) => t + Number(n.saldo_livre), 0));

  protected subtotal(itemId: string, preco: string): number {
    return (Number(paraDecimalApi(this.medidas[itemId])) || 0) * Number(preco);
  }

  protected total(): number {
    return this.detalhe().itens.reduce((t, i) => t + this.subtotal(i.id, i.valor_unitario), 0);
  }

  protected usarPrevista(): void {
    for (const i of this.detalhe().itens) this.medidas[i.id] = paraDecimalTela(i.quantidade_prevista);
    this.alterado.set(true);
  }

  protected adicionarNota(): void {
    const nota = this.detalhe().notas_disponiveis.find((n) => n.id === this.notaParaAdicionar);
    if (nota) this.notas.update((l) => [...l, nota]);
    this.notaParaAdicionar = '';
    this.alterado.set(true);
  }

  protected moverNota(indice: number, deslocamento: number): void {
    const lista = [...this.notas()];
    const destino = indice + deslocamento;
    if (destino < 0 || destino >= lista.length) return;
    [lista[indice], lista[destino]] = [lista[destino], lista[indice]];
    this.notas.set(lista);
    this.alterado.set(true);
  }

  protected removerNota(indice: number): void {
    this.notas.update((l) => l.filter((_, i) => i !== indice));
    this.alterado.set(true);
  }

  protected async salvar(): Promise<void> {
    const d = this.detalhe();
    if (d.ciencias.length) {
      const ok = await this.dialogos.confirmar({
        titulo: 'Salvar a medição?',
        mensagem: `Alterar a medição apaga as ${d.ciencias.length} ciência(s) já registrada(s).`,
        rotuloConfirmar: 'Salvar',
      });
      if (!ok) return;
    }
    const itens = d.itens.map((i) => ({ id: i.id, quantidade_medida: paraDecimalApi(this.medidas[i.id]) }));
    this.api.salvarMedicao(d.contrato_id, d.id, itens, this.notas().map((n) => n.id)).subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar a medição'),
    });
  }

  protected ciencia(): void {
    const d = this.detalhe();
    this.api.cienciaMedicao(d.contrato_id, d.id).subscribe({ next: (novo) => this.atualizado.emit(novo), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected async concluir(): Promise<void> {
    const d = this.detalhe();
    const ok = await this.dialogos.confirmar({
      titulo: 'Concluir a medição?',
      mensagem: 'A medição fica somente leitura, a quantidade medida soma no executado dos itens e a memória de cálculo em PDF é gerada.',
      rotuloConfirmar: 'Concluir medição',
      segundos: 5,
    });
    if (!ok) return;
    this.dialogos.executar(this.api.concluirMedicao(d.contrato_id, d.id, d.notas_selecionadas.map((n) => n.id)), 'Gerando a memória de cálculo…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível concluir a medição'),
    });
  }

  protected baixar(anexoId: string): void {
    const d = this.detalhe();
    this.api.baixar(d.contrato_id, d.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
