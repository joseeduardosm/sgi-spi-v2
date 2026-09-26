// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a aba "Diário de bordo": registro de ocorrências (com glosa) e lista em forma de chat.

import { DatePipe } from '@angular/common';
import { Component, computed, ElementRef, inject, input, OnInit, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { DiarioContrato, OcorrenciaDiario } from '../compartilhado/contratos.models';
import { paraDecimalApi, ROTULOS_PAPEL } from '../compartilhado/rotulos';

interface LinhaGlosa {
  item_id: string;
  quantidade: string;
}

/** Aba "Diário de bordo": a equipe relata ocorrências; cada uma é enviada por e-mail à equipe e ao preposto. */
@Component({
  selector: 'app-aba-diario',
  imports: [FormsModule, DatePipe, ...PIPES_FORMATACAO],
  template: `
    <section class="cartao-dados" aria-labelledby="titulo-diario">
      <header>
        <div>
          <h2 id="titulo-diario">Diário de bordo</h2>
          <small>Ocorrências da execução relatadas pela equipe. Cada registro é enviado por e-mail à equipe e ao preposto; as glosas limitam a medição da competência da data.</small>
        </div>
        <button type="button" class="acao-secundaria" [disabled]="!diario()?.ocorrencias?.length" (click)="baixarPdf()">Baixar PDF</button>
      </header>

      <div class="diario-chat" #chat>
        @for (o of diario()?.ocorrencias ?? []; track o.id) {
          <article class="balao-diario" [class.minha]="o.registrada_por_id === usuarioId()" [class.com-glosa]="o.possui_glosa">
            <!-- Cabeçalho numa linha: autor, papel, data da ocorrência e competência (selos) e hora do registro -->
            <header>
              <strong>{{ o.registrada_por_nome }}</strong>
              @if (o.registrada_por_papel) { <span class="papel">{{ rotuloPapel(o.registrada_por_papel) }}</span> }
              <span class="selo-diario">Ocorrência {{ o.data_ocorrencia | dataBr }}</span>
              @if (o.competencia_rotulo) { <span class="selo-diario">Competência {{ o.competencia_rotulo }}</span> }
              <time [attr.datetime]="o.criado_em" title="Registrado em">{{ o.criado_em | date: 'dd/MM/yyyy HH:mm' }}</time>
            </header>
            <p class="texto">{{ o.descricao }}</p>
            @if (o.possui_glosa) {
              <!-- Glosas como chips: item e quantidade, sem ocupar um bloco inteiro -->
              <div class="glosas-balao">
                <span class="rotulo-glosa">Glosa</span>
                @for (g of o.glosas; track g.item_id) { <span class="chip-glosa">{{ g.descricao_item }} · <b>{{ g.quantidade | quantidade }}</b></span> }
              </div>
              @if (o.medicao_ja_concluida) { <small class="texto-erro">A medição dessa competência já foi concluída: a glosa só vale se ela for reaberta.</small> }
            }
            <footer>
              @if (o.email.enviado_em === null) {
                <small>Enviando e-mail…</small>
              } @else if (o.email.ok) {
                <small [title]="o.email.destinatarios.join(', ')">✓ E-mail enviado a {{ o.email.destinatarios.length }} destinatário(s)</small>
              } @else {
                <small class="texto-erro">E-mail não enviado: {{ o.email.erro }}</small>
                @if (diario()?.pode_registrar) {
                  <button type="button" class="link-arquivo" [disabled]="reenviando() === o.id" (click)="reenviar(o)">{{ reenviando() === o.id ? 'Reenviando…' : 'Reenviar' }}</button>
                }
              }
            </footer>
          </article>
        } @empty {
          <p class="estado-vazio">{{ diario() ? 'Nenhuma ocorrência registrada.' : 'Carregando…' }}</p>
        }
      </div>

      @if (diario()?.pode_registrar) {
        <form class="diario-formulario" (ngSubmit)="registrar()">
          <p class="secao-formulario">Nova ocorrência</p>
          <div class="grade-formulario diario-campos">
            <div>
              <label for="diario-data">Data da ocorrência *</label>
              <input id="diario-data" name="data" type="date" required [max]="hoje" [(ngModel)]="data" />
            </div>
            <!-- Seletor segmentado Não | Sim (botões, no lugar de rádios desproporcionais) -->
            <div>
              <span class="rotulo-campo" id="rotulo-glosa">Esta ocorrência implicará glosa? *</span>
              <div class="seletor-segmentado" role="radiogroup" aria-labelledby="rotulo-glosa">
                <button type="button" role="radio" [attr.aria-checked]="!possuiGlosa" [class.ativo]="!possuiGlosa" (click)="possuiGlosa = false">Não</button>
                <button type="button" role="radio" [attr.aria-checked]="possuiGlosa" [class.ativo]="possuiGlosa" (click)="possuiGlosa = true; aoMarcarGlosa()">Sim</button>
              </div>
            </div>
            <div class="ocupa-duas">
              <label for="diario-texto">Ocorrência *</label>
              <textarea id="diario-texto" name="descricao" required maxlength="4000" rows="3" [(ngModel)]="descricao"
                        placeholder="Descreva o que aconteceu (ex.: posto descoberto das 8h às 12h)."></textarea>
            </div>
          </div>
          @if (possuiGlosa) {
            <p class="secao-formulario">Itens a glosar</p>
            @for (g of glosas(); track $index) {
              <div class="linha-glosa">
                <select [name]="'item' + $index" [attr.aria-label]="'Item da glosa ' + ($index + 1)" [(ngModel)]="g.item_id">
                  <option value="" disabled>Selecione o item</option>
                  @for (i of diario()?.itens ?? []; track i.id) {
                    <option [value]="i.id" [disabled]="usado(i.id, $index)">{{ i.ordem }}. {{ i.descricao }}</option>
                  }
                </select>
                <input [name]="'qtd' + $index" inputmode="decimal" placeholder="Quantidade" [attr.aria-label]="'Quantidade da glosa ' + ($index + 1)" [(ngModel)]="g.quantidade" />
                <button type="button" class="link-arquivo" [disabled]="glosas().length === 1" (click)="removerGlosa($index)">remover</button>
              </div>
            }
            <button type="button" class="acao-secundaria acao-pequena" [disabled]="glosas().length >= (diario()?.itens?.length ?? 0)" (click)="adicionarGlosa()">+ Item</button>
          }
          @if (erro()) { <p class="aviso-formulario erro" role="alert">{{ erro() }}</p> }
          <div class="acoes-cartao">
            <small class="dica-formulario">Ao salvar, o registro é enviado por e-mail à equipe e aos prepostos. Ocorrências não podem ser editadas depois.</small>
            <button type="submit" class="acao-primaria" [disabled]="salvando()">{{ salvando() ? 'Salvando…' : 'Registrar ocorrência' }}</button>
          </div>
        </form>
      }
    </section>
  `,
})
export class AbaDiarioComponent implements OnInit {
  readonly contratoId = input.required<string>();
  /** Usuário logado (os próprios balões ficam à direita). */
  readonly usuarioId = input<number | null>(null);

  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly chat = viewChild<ElementRef<HTMLElement>>('chat');

  protected readonly diario = signal<DiarioContrato | null>(null);
  protected readonly salvando = signal(false);
  protected readonly reenviando = signal<string | null>(null);
  protected readonly erro = signal<string | null>(null);
  protected readonly glosas = signal<LinhaGlosa[]>([]);
  protected readonly hoje = new Date().toLocaleDateString('sv-SE');
  protected data = this.hoje;
  protected descricao = '';
  protected possuiGlosa = false;
  /** Há envio em segundo plano ainda sem resultado: a lista é consultada de novo em instantes. */
  private readonly aguardandoEnvio = computed(() => this.diario()?.ocorrencias.some((o) => o.email.enviado_em === null) ?? false);

  ngOnInit(): void {
    this.carregar();
  }

  /** Nome do papel na equipe (ou o código, se desconhecido). */
  protected rotuloPapel(papel: string): string {
    return (ROTULOS_PAPEL as Record<string, string>)[papel] ?? papel;
  }

  protected carregar(rolar = true): void {
    this.api.diario(this.contratoId()).subscribe({
      next: (d) => {
        this.diario.set(d);
        if (rolar) setTimeout(() => this.chat()?.nativeElement.scrollTo({ top: 1e9 }));
        if (this.aguardandoEnvio()) setTimeout(() => this.carregar(false), 2500);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o diário de bordo'),
    });
  }

  protected aoMarcarGlosa(): void {
    if (!this.glosas().length) this.adicionarGlosa();
  }

  protected adicionarGlosa(): void {
    this.glosas.update((l) => [...l, { item_id: '', quantidade: '' }]);
  }

  protected removerGlosa(indice: number): void {
    this.glosas.update((l) => l.filter((_, i) => i !== indice));
  }

  /** O item já escolhido em outra linha fica indisponível. */
  protected usado(itemId: string, linha: number): boolean {
    return this.glosas().some((g, i) => i !== linha && g.item_id === itemId);
  }

  protected registrar(): void {
    const erro = this.validar();
    this.erro.set(erro);
    if (erro) return;
    this.salvando.set(true);
    const glosas = this.possuiGlosa ? this.glosas().map((g) => ({ item_id: g.item_id, quantidade: paraDecimalApi(g.quantidade) })) : [];
    this.api
      .registrarOcorrencia(this.contratoId(), { data_ocorrencia: this.data, descricao: this.descricao.trim(), possui_glosa: this.possuiGlosa, glosas })
      .subscribe({
        next: () => {
          this.salvando.set(false);
          this.descricao = '';
          this.possuiGlosa = false;
          this.glosas.set([]);
          this.data = this.hoje;
          this.carregar();
        },
        error: (e) => {
          this.salvando.set(false);
          this.dialogos.mostrarErro(e, 'Não foi possível registrar a ocorrência');
        },
      });
  }

  protected reenviar(ocorrencia: OcorrenciaDiario): void {
    this.reenviando.set(ocorrencia.id);
    this.api.reenviarOcorrencia(this.contratoId(), ocorrencia.id).subscribe({
      next: (nova) => {
        this.reenviando.set(null);
        this.diario.update((d) => (d ? { ...d, ocorrencias: d.ocorrencias.map((o) => (o.id === nova.id ? nova : o)) } : d));
      },
      error: (e) => {
        this.reenviando.set(null);
        this.dialogos.mostrarErro(e, 'Não foi possível reenviar o e-mail');
      },
    });
  }

  protected baixarPdf(): void {
    this.dialogos.executar(this.api.diarioPdf(this.contratoId()), 'Gerando o diário de bordo…').subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Mesmas regras da API, para avisar antes de enviar. */
  private validar(): string | null {
    if (!this.data) return 'Informe a data da ocorrência.';
    if (this.data > this.hoje) return 'A data da ocorrência não pode ser futura.';
    if (!this.descricao.trim()) return 'Descreva a ocorrência.';
    if (this.possuiGlosa) {
      if (!this.glosas().length) return 'Informe o item e a quantidade a glosar.';
      for (const g of this.glosas()) {
        if (!g.item_id) return 'Selecione o item de cada linha da glosa.';
        const quantidade = Number(paraDecimalApi(g.quantidade));
        if (!Number.isFinite(quantidade) || quantidade <= 0) return 'A quantidade a glosar deve ser maior que zero.';
      }
    }
    return null;
  }
}
