// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a etapa 1 (medição): quantidades medidas, NEs em ordem, ciências e memória de cálculo.

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
  // Entradas vindas da tela da competência; `atualizado` devolve a competência depois de cada gravação
  readonly detalhe = input.required<DetalheCompetencia>();
  readonly editavel = input(false);
  readonly atualizado = output<DetalheCompetencia>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly autenticacao = inject(AutenticacaoService);
  // O usuário logado já deu ciência nesta medição?
  protected readonly papeis = ROTULOS_PAPEL;
  protected readonly jaRegistrei = computed(() => this.detalhe().ciencias.some((c) => c.usuario_id === this.autenticacao.usuario()?.id));

  // Campos editáveis: quantidade medida por item e a lista ordenada de NEs escolhidas
  protected medidas: Record<string, string> = {};
  protected readonly notas = signal<NotaSelecionada[]>([]);
  protected notaParaAdicionar = '';
  // Houve alteração não salva (mostra o aviso para salvar)
  protected readonly alterado = signal(false);
  protected readonly reenviando = signal(false);

  /** Sempre que a competência muda (entrada nova), recarrega os campos a partir dela. */
  ngOnChanges(): void {
    const d = this.detalhe();
    this.medidas = Object.fromEntries(d.itens.map((i) => [i.id, paraDecimalTela(i.quantidade_medida)]));
    this.notas.set(d.notas_selecionadas);
    this.alterado.set(false);
  }

  // NEs que ainda podem ser acrescentadas (as já escolhidas saem da lista)
  protected readonly disponiveis = computed(() => {
    const escolhidas = new Set(this.notas().map((n) => n.id));
    return this.detalhe().notas_disponiveis.filter((n) => !escolhidas.has(n.id));
  });
  // Soma do saldo livre das NEs escolhidas, comparada ao total medido
  protected readonly saldoNotas = computed(() => this.notas().reduce((t, n) => t + Number(n.saldo_livre), 0));

  /** Subtotal do item com a quantidade digitada. */
  protected subtotal(itemId: string, preco: string): number {
    return (Number(paraDecimalApi(this.medidas[itemId])) || 0) * Number(preco);
  }

  /** Total medido com as quantidades digitadas. */
  protected total(): number {
    return this.detalhe().itens.reduce((t, i) => t + this.subtotal(i.id, i.valor_unitario), 0);
  }

  /** Preenche todas as quantidades com o previsto. */
  protected usarPrevista(): void {
    // Preenche com o máximo permitido: o saldo líquido (saldo − glosas)
    for (const i of this.detalhe().itens) this.medidas[i.id] = paraDecimalTela(i.saldo_liquido);
    this.alterado.set(true);
  }

  /** Acrescenta a NE escolhida no fim da ordem de consumo. */
  protected adicionarNota(): void {
    const nota = this.detalhe().notas_disponiveis.find((n) => n.id === this.notaParaAdicionar);
    if (nota) this.notas.update((l) => [...l, nota]);
    this.notaParaAdicionar = '';
    this.alterado.set(true);
  }

  /** Sobe (−1) ou desce (+1) uma NE na ordem de consumo, trocando-a de lugar com a vizinha. */
  protected moverNota(indice: number, deslocamento: number): void {
    const lista = [...this.notas()];
    const destino = indice + deslocamento;
    if (destino < 0 || destino >= lista.length) return;
    [lista[indice], lista[destino]] = [lista[destino], lista[indice]];
    this.notas.set(lista);
    this.alterado.set(true);
  }

  /** Tira uma NE da lista. */
  protected removerNota(indice: number): void {
    this.notas.update((l) => l.filter((_, i) => i !== indice));
    this.alterado.set(true);
  }

  /** A medição digitada passa do saldo líquido do item? */
  protected acimaDoSaldo(itemId: string, saldoLiquido: string): boolean {
    const medida = Number(paraDecimalApi(this.medidas[itemId]));
    return Number.isFinite(medida) && medida > Number(saldoLiquido) + 1e-9;
  }

  /** Itens digitados acima do saldo líquido (a API também recusa). */
  protected excedentes(): string[] {
    return this.detalhe().itens.filter((i) => this.acimaDoSaldo(i.id, i.saldo_liquido)).map((i) => i.descricao);
  }

  /** Reenvia o e-mail da medição concluída. */
  protected reenviarEmail(): void {
    const d = this.detalhe();
    this.reenviando.set(true);
    this.api.reenviarEmailMedicao(d.contrato_id, d.id).subscribe({
      next: (novo) => {
        this.reenviando.set(false);
        this.atualizado.emit(novo);
      },
      error: (e) => {
        this.reenviando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível reenviar o e-mail');
      },
    });
  }

  /** Salva a medição; se já houver ciências, avisa que elas serão apagadas. */
  protected async salvar(): Promise<void> {
    const d = this.detalhe();
    if (this.excedentes().length) {
      this.dialogos.avisar('Medição acima do saldo líquido', `Ajuste: ${this.excedentes().join(', ')}. Nenhum item pode ser medido acima do saldo líquido (saldo − glosas).`);
      return;
    }
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

  /** Registra a ciência do usuário logado. */
  protected ciencia(): void {
    const d = this.detalhe();
    this.api.cienciaMedicao(d.contrato_id, d.id).subscribe({ next: (novo) => this.atualizado.emit(novo), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Conclui a medição (gera a memória de cálculo em PDF). */
  protected async concluir(): Promise<void> {
    const d = this.detalhe();
    const ok = await this.dialogos.confirmar({
      titulo: 'Concluir a medição?',
      mensagem: 'A medição fica somente leitura, a quantidade medida soma no executado dos itens e a memória de cálculo em PDF é gerada. Em seguida, a memória e o diário de bordo do período são enviados por e-mail à equipe e ao preposto, pedindo a nota fiscal em até 48 horas.',
      rotuloConfirmar: 'Concluir medição',
      segundos: 5,
    });
    if (!ok) return;
    this.dialogos.executar(this.api.concluirMedicao(d.contrato_id, d.id, d.notas_selecionadas.map((n) => n.id)), 'Gerando a memória de cálculo…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível concluir a medição'),
    });
  }

  /** Baixa um PDF da competência (ex.: memória de cálculo). */
  protected baixar(anexoId: string): void {
    const d = this.detalhe();
    this.api.baixar(d.contrato_id, d.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
