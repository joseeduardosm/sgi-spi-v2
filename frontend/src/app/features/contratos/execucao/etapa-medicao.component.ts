// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a etapa 1 (medição): quantidades medidas, NEs em ordem, ciências e memória de cálculo.

import { DatePipe } from '@angular/common';
import { Component, computed, DestroyRef, inject, input, OnChanges, output, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { RascunhoGuardado, RascunhoService } from '../../../core/rascunho/rascunho.service';
import { AvisoRascunhoComponent } from '../../../shared/componentes/aviso-rascunho/aviso-rascunho.component';
import { BotaoCopiarComponent } from '../../../shared/componentes/botao-copiar/botao-copiar.component';
import { valorPorExtenso } from '../../../shared/utilitarios/extenso';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { DetalheCompetencia, NotaSelecionada } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { RascunhoServidorComponent } from '../compartilhado/rascunho-servidor.component';
import { OpcaoEmailComponent } from '../compartilhado/opcao-email.component';
import { paraDecimalApi, paraDecimalTela, ROTULOS_PAPEL } from '../compartilhado/rotulos';

/** Etapa 1: medição, NEs em ordem de consumo, ciências (uma já basta) e memória de cálculo. */
/** Medição digitada e ainda não salva, guardada como rascunho; `base` identifica a medição gravada a que ela se refere. */
interface RascunhoMedicao {
  base: string;
  medidas: Record<string, string>;
  acertos: Record<string, string>;
  marcadas: Record<string, boolean>;
  notasIds: string[];
}

@Component({
  selector: 'app-etapa-medicao',
  imports: [RascunhoServidorComponent, AvisoRascunhoComponent, FormsModule, DatePipe, BotaoCopiarComponent, OpcaoEmailComponent, ...PIPES_FORMATACAO],
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
  private readonly rascunhos = inject(RascunhoService);
  private readonly destruir = inject(DestroyRef);
  // O usuário logado já deu ciência nesta medição?
  protected readonly papeis = ROTULOS_PAPEL;
  protected readonly jaRegistrei = computed(() => this.detalhe().ciencias.some((c) => c.usuario_id === this.autenticacao.usuario()?.id));

  // Campos editáveis: quantidade medida por item e a lista ordenada de NEs escolhidas
  protected medidas: Record<string, string> = {};
  /** Itens marcados como despesa variável (por item da competência). */
  protected marcadas: Record<string, boolean> = {};
  protected readonly notas = signal<NotaSelecionada[]>([]);
  protected notaParaAdicionar = '';
  // Houve alteração não salva (mostra o aviso para salvar)
  protected readonly alterado = signal(false);
  protected readonly reenviando = signal(false);
  protected readonly prepostosIds = signal<(string | number)[] | null>(null);
  // Prazo de contestação da contratada (dias úteis), obrigatório com o e-mail; na reemissão, vazio = igual ao anterior
  protected readonly prazoContestacao = signal<number | null>(3);
  protected readonly prazoReemissao = signal<number | null>(null);
  protected readonly fontePrepostos = () => this.api.gruposPrepostos(this.detalhe().contrato_id);

  /** Sempre que a competência muda (entrada nova), recarrega os campos a partir dela. */
  ngOnChanges(): void {
    const d = this.detalhe();
    this.medidas = Object.fromEntries(d.itens.map((i) => [i.id, paraDecimalTela(i.quantidade_medida)]));
    this.acertos = Object.fromEntries(d.itens.map((i) => [i.id, Number(i.acerto) ? paraDecimalTela(i.acerto) : '']));
    this.marcadas = Object.fromEntries(d.itens.map((i) => [i.id, !!i.despesa_variavel]));
    this.notas.set(d.notas_selecionadas);
    this.alterado.set(false);
    this.base = this.retratoDaMedicao();
    this.restaurarRascunho();
    if (!this.vigiando) {
      this.vigiando = true;
      // Guarda as quantidades, acertos e NEs digitados e ainda não salvos (some ao salvar; não vale se a medição mudou no servidor)
      this.rascunhos.vigiar<RascunhoMedicao>(this.destruir, this.chaveRascunho(), () => this.estadoDoRascunho());
    }
  }

  // Medição como veio do servidor (para saber se há algo digitado e não salvo) e controle do rascunho
  private base = '';
  private vigiando = false;
  protected readonly rascunhoRestaurado = signal<RascunhoGuardado<RascunhoMedicao> | null>(null);

  private chaveRascunho(): string {
    return `medicao:${this.detalhe().id}`;
  }

  private retratoDaMedicao(): string {
    return JSON.stringify([this.medidas, this.acertos, this.marcadas, this.notas().map((n) => n.id)]);
  }

  /** Só há rascunho quando se pode editar e algo difere do que está salvo. */
  private estadoDoRascunho(): RascunhoMedicao | null {
    if (!this.editavel() || this.detalhe().medicao_concluida_em || this.retratoDaMedicao() === this.base) return null;
    return { base: this.base, medidas: this.medidas, acertos: this.acertos, marcadas: this.marcadas, notasIds: this.notas().map((n) => n.id) };
  }

  /** Preenche de novo o que foi digitado e não salvo, se a medição gravada continua a mesma; senão descarta o rascunho velho. */
  private restaurarRascunho(): void {
    this.rascunhoRestaurado.set(null);
    const guardado = this.rascunhos.ler<RascunhoMedicao>(this.chaveRascunho());
    if (!guardado) return;
    if (guardado.dados.base !== this.base || !this.editavel() || this.detalhe().medicao_concluida_em) {
      this.rascunhos.limpar(this.chaveRascunho());
      return;
    }
    const d = this.detalhe();
    this.medidas = { ...this.medidas, ...guardado.dados.medidas };
    this.acertos = { ...this.acertos, ...guardado.dados.acertos };
    this.marcadas = { ...this.marcadas, ...guardado.dados.marcadas };
    // As NEs voltam na ordem guardada, só as que continuam disponíveis
    const conhecidas = new Map([...d.notas_selecionadas, ...d.notas_disponiveis].map((n) => [n.id, n]));
    this.notas.set(guardado.dados.notasIds.map((id) => conhecidas.get(id)).filter((n): n is NotaSelecionada => !!n));
    this.alterado.set(true);
    this.rascunhoRestaurado.set(guardado);
  }

  private readonly rascunhoDaEquipe = viewChild<RascunhoServidorComponent>('rascunhoServidor');

  /** Campos para o rascunho salvo no servidor (visível à equipe): o que está na tela agora. */
  protected readonly dadosDoRascunhoServidor = (): Record<string, unknown> | null => ({
    medidas: this.medidas, acertos: this.acertos, marcadas: this.marcadas, notasIds: this.notas().map((n) => n.id),
  });

  /** Preenche a medição com o rascunho salvo pela equipe. */
  protected carregarRascunhoDaEquipe(dados: Record<string, unknown>): void {
    const d = this.detalhe();
    this.medidas = { ...this.medidas, ...(dados['medidas'] as Record<string, string>) };
    this.acertos = { ...this.acertos, ...(dados['acertos'] as Record<string, string>) };
    this.marcadas = { ...this.marcadas, ...(dados['marcadas'] as Record<string, boolean>) };
    const conhecidas = new Map([...d.notas_selecionadas, ...d.notas_disponiveis].map((n) => [n.id, n]));
    this.notas.set(((dados['notasIds'] as string[]) ?? []).map((id) => conhecidas.get(id)).filter((n): n is NotaSelecionada => !!n));
    this.alterado.set(true);
    this.rascunhoRestaurado.set(null);
  }

  /** Descarta o rascunho e volta à medição salva. */
  protected descartarRascunho(): void {
    this.rascunhos.limpar(this.chaveRascunho());
    this.rascunhoRestaurado.set(null);
    this.ngOnChanges();
  }

  // NEs que ainda podem ser acrescentadas (as já escolhidas saem da lista)
  protected readonly disponiveis = computed(() => {
    const escolhidas = new Set(this.notas().map((n) => n.id));
    return this.detalhe().notas_disponiveis.filter((n) => !escolhidas.has(n.id));
  });
  // Soma do saldo livre das NEs escolhidas, comparada ao total medido
  protected readonly saldoNotas = computed(() => this.notas().reduce((t, n) => t + Number(n.saldo_livre), 0));

  /** Acertos de centavos digitados por item (ex.: "0,01", "-0,02"); vazio = sem acerto. */
  protected acertos: Record<string, string> = {};

  /** Acerto do item como número (aceita "+0,01", "-0,02"; texto inválido vale zero). */
  protected acertoDe(itemId: string): number {
    const n = Number(paraDecimalApi((this.acertos[itemId] ?? '').replace(/^\+/, '')));
    return Number.isFinite(n) ? n : 0;
  }

  /** Acerto fora dos limites (mais de R$ 1,00, mais de duas casas) ou sem quantidade medida. */
  protected acertoInvalido(itemId: string): boolean {
    const a = this.acertoDe(itemId);
    if (!a) return false;
    const semMedicao = !(Number(paraDecimalApi(this.medidas[itemId])) > 0);
    return Math.abs(a) > 1 || Math.abs(Math.round(a * 100) - a * 100) > 1e-6 || semMedicao;
  }

  /** Acerto com sinal para leitura ("+R$ 0,01", "-R$ 0,02"); sem acerto, um traço. */
  protected acertoTexto(valor: string | number): string {
    const n = Number(valor);
    if (!n) return '—';
    return `${n > 0 ? '+' : '−'}R$ ${Math.abs(n).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  /** Subtotal do item: quantidade digitada × preço, arredondado em centavos, mais o acerto. */
  protected subtotal(itemId: string, preco: string): number {
    const bruto = (Number(paraDecimalApi(this.medidas[itemId])) || 0) * Number(preco);
    return Math.round(bruto * 100) / 100 + this.acertoDe(itemId);
  }

  /** Há item marcado como despesa variável (mostra os subtotais separados). */
  protected temDespesasVariaveis(): boolean {
    return this.detalhe().itens.some((i) => this.marcadas[i.id]);
  }

  /** Subtotal dos itens que não são despesas variáveis. */
  protected subtotalMedicao(): number {
    return this.detalhe().itens.filter((i) => !this.marcadas[i.id]).reduce((t, i) => t + this.subtotal(i.id, i.valor_unitario), 0);
  }

  /** Subtotal dos itens marcados como despesas variáveis. */
  protected subtotalDespesas(): number {
    return this.detalhe().itens.filter((i) => this.marcadas[i.id]).reduce((t, i) => t + this.subtotal(i.id, i.valor_unitario), 0);
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

  /** As quantidades podem ser digitadas: competência regular ou medição adicional (a diferença de reajuste tem quantidades fixas). */
  protected medivel(): boolean {
    return this.detalhe().tipo === 'regular' || this.detalhe().tipo === 'adicional';
  }

  /** A medição digitada passa do saldo líquido do item? Na medição adicional, o item contínuo não tem teto (o servidor só avisa). */
  protected acimaDoSaldo(itemId: string, saldoLiquido: string): boolean {
    if (this.detalhe().tipo === 'adicional' && this.detalhe().itens.find((i) => i.id === itemId)?.tipo === 'continuo') return false;
    const medida = Number(paraDecimalApi(this.medidas[itemId]));
    return Number.isFinite(medida) && medida > Number(saldoLiquido) + 1e-9;
  }

  /** Itens digitados acima do saldo líquido (a API também recusa). */
  protected excedentes(): string[] {
    return this.detalhe().itens.filter((i) => this.acimaDoSaldo(i.id, i.saldo_liquido)).map((i) => i.descricao);
  }

  /** Valor por extenso (ex.: "Quatrocentos e Noventa e Sete Mil, … Reais e Sessenta e Oito Centavos"), para copiar. */
  protected extenso(valor: number): string {
    return valorPorExtenso(valor);
  }

  /** Algum acerto de centavos inválido (bloqueia o salvar). */
  protected acertosInvalidos(): boolean {
    return this.detalhe().itens.some((i) => this.acertoInvalido(i.id));
  }

  /** O que ainda impede de salvar ou concluir (aparece na barra de ações). */
  protected pendencias(): string[] {
    const d = this.detalhe();
    const falta: string[] = [];
    if (!this.notas().length) falta.push('Selecione ao menos uma NE');
    if (this.excedentes().length) falta.push('Há item medido acima do saldo líquido');
    if (this.acertosInvalidos()) falta.push('Há acerto de centavos inválido');
    if (!this.temAvaliacao() && !this.retroativa() && !this.prepostosIds()?.length) falta.push('Escolha ao menos um preposto para receber a medição');
    if (!this.temAvaliacao() && !this.retroativa() && !this.prazoValido(this.prazoContestacao())) falta.push('Informe o prazo de contestação (1 a 60 dias úteis)');
    if (this.alterado()) falta.push('Salve a medição antes de registrar ciência ou concluir');
    else if (d.ciencias.length < d.ciencias_minimas) falta.push('Falta ao menos uma ciência');
    return falta;
  }

  /** Envio obrigatório: ao menos um preposto escolhido e o prazo de contestação válido. */
  protected envioValido(): boolean {
    return this.temAvaliacao() || this.retroativa() || (!!this.prepostosIds()?.length && this.prazoValido(this.prazoContestacao()));
  }

  /** Prazo em dias úteis: inteiro de 1 a 60. */
  private prazoValido(prazo: number | null): boolean {
    return prazo !== null && Number.isInteger(Number(prazo)) && Number(prazo) >= 1 && Number(prazo) <= 60;
  }

  /** Reemite o documento executivo e o e-mail único (contestação aceita) e reinicia o prazo. */
  protected async reemitir(): Promise<void> {
    const d = this.detalhe();
    const novoPrazo = this.prazoReemissao();
    if (novoPrazo !== null && !this.prazoValido(novoPrazo)) {
      this.dialogos.avisar('Prazo inválido', 'Informe de 1 a 60 dias úteis, ou deixe vazio para manter o prazo anterior.');
      return;
    }
    const refazer = !!d.email_medicao.ok;
    const ok = await this.dialogos.confirmar({
      titulo: refazer ? 'Reemitir a comunicação?' : 'Repetir o envio?',
      mensagem: refazer
        ? 'O sistema gera uma nova versão do documento executivo com o valor atual, reenvia o e-mail único à equipe e aos prepostos e reinicia o prazo de contestação.'
        : 'O e-mail anterior não foi entregue. O sistema envia de novo o pacote e abre o prazo de contestação.',
      rotuloConfirmar: refazer ? 'Reemitir' : 'Enviar de novo',
    });
    if (!ok) return;
    this.reenviando.set(true);
    this.api.reemitirMedicao(d.contrato_id, d.id, novoPrazo === null ? null : Number(novoPrazo)).subscribe({
      next: (novo) => {
        this.reenviando.set(false);
        this.prazoReemissao.set(null);
        this.atualizado.emit(novo);
      },
      error: (e) => {
        this.reenviando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível reemitir a comunicação');
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
    const invalidos = d.itens.filter((i) => this.acertoInvalido(i.id)).map((i) => i.descricao);
    if (invalidos.length) {
      this.dialogos.avisar('Acerto inválido', `Confira o acerto de: ${invalidos.join(', ')}. O acerto é em centavos (até R$ 1,00 para mais ou para menos) e só vale em item medido.`);
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
    const itens = d.itens.map((i) => ({ id: i.id, quantidade_medida: paraDecimalApi(this.medidas[i.id]), acerto: this.acertoDe(i.id).toFixed(2), despesa_variavel: !!this.marcadas[i.id] }));
    this.api.salvarMedicao(d.contrato_id, d.id, itens, this.notas().map((n) => n.id)).subscribe({
      next: (novo) => {
        // Medição gravada de verdade: o rascunho da equipe não serve mais
        this.rascunhoDaEquipe()?.apagar();
        this.atualizado.emit(novo);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar a medição'),
    });
  }

  /** Registra a ciência do usuário logado. */
  protected ciencia(): void {
    const d = this.detalhe();
    this.api.cienciaMedicao(d.contrato_id, d.id).subscribe({ next: (novo) => this.atualizado.emit(novo), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Competência anterior ao corte de alertas: não envia e-mail à contratada, então não pede preposto nem prazo. */
  protected retroativa(): boolean {
    return this.detalhe().retroativa;
  }

  /** Com avaliação de qualidade, os prepostos e o prazo do e-mail único são escolhidos ao concluir a avaliação, não aqui. */
  protected temAvaliacao(): boolean {
    return this.detalhe().etapas.includes('avaliacao');
  }

  /** Explica, na confirmação, quando o e-mail único sai: com avaliação de qualidade, só depois de concluí-la; sem ela, logo em seguida. */
  private avisoDoEnvio(): string {
    if (this.retroativa()) return 'Esta competência é anterior ao corte de alertas: não é enviado e-mail à contratada nem aviso à equipe.';
    const prepostos = this.prepostosIds()?.length ?? 0;
    const quem = `à equipe e a ${prepostos} preposto(s) escolhido(s)`;
    const prazo = `abre o prazo de ${this.prazoContestacao()} dia(s) útil(eis) para a contratada contestar`;
    if (this.detalhe().etapas.includes('avaliacao')) {
      return 'O e-mail único à contratada NÃO sai agora: ele só é enviado quando você finalizar a avaliação de qualidade, clicando em "Enviar Medição e Avaliação" na etapa de avaliação: um e-mail só, com a medição e a avaliação anexas. Lá você escolherá os prepostos que recebem e o prazo.';
    }
    return `Como este contrato não tem avaliação de qualidade, o e-mail único sai logo em seguida ${quem} (com a medição anexa) e ${prazo}.`;
  }

  /** Conclui a medição (gera a memória de cálculo em PDF). */
  protected async concluir(): Promise<void> {
    const d = this.detalhe();
    const ok = await this.dialogos.confirmar({
      titulo: 'Concluir a medição?',
      mensagem: 'A medição fica somente leitura, a quantidade medida soma no executado dos itens e a memória de cálculo em PDF é gerada. ' + this.avisoDoEnvio(),
      rotuloConfirmar: 'Concluir medição',
      segundos: 5,
    });
    if (!ok) return;
    this.dialogos.executar(this.api.concluirMedicao(d.contrato_id, d.id, d.notas_selecionadas.map((n) => n.id), this.temAvaliacao() || this.retroativa() ? null : (this.prepostosIds() as string[]), this.temAvaliacao() || this.retroativa() ? null : Number(this.prazoContestacao())), 'Gerando a memória de cálculo…').subscribe({
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
