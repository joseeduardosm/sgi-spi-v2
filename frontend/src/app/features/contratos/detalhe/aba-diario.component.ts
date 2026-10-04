// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a aba "Diário de bordo": registro de ocorrências (com glosa, anexos e impacto na avaliação) e lista em forma de chat.

import { DatePipe } from '@angular/common';
import { OpcaoEmailComponent } from '../compartilhado/opcao-email.component';
import { Component, computed, ElementRef, inject, input, OnInit, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { AnexoOcorrencia, DiarioContrato, OcorrenciaDiario } from '../compartilhado/contratos.models';
import { paraDecimalApi, ROTULOS_PAPEL } from '../compartilhado/rotulos';

/** Máximo de arquivos por ocorrência (mesmo limite da API). */
const MAXIMO_ANEXOS = 5;

interface LinhaGlosa {
  item_id: string;
  quantidade: string;
}

/** Aba "Diário de bordo": a equipe relata ocorrências; cada uma é enviada por e-mail à equipe e ao preposto. */
@Component({
  selector: 'app-aba-diario',
  imports: [FormsModule, DatePipe, OpcaoEmailComponent, ...PIPES_FORMATACAO],
  template: `
    <section class="cartao-dados" aria-labelledby="titulo-diario">
      <header>
        <div>
          <h2 id="titulo-diario">Diário de bordo</h2>
          <small>Ocorrências da execução relatadas pela equipe. Cada registro é enviado por e-mail (com os anexos) à equipe e ao preposto; as glosas limitam a medição da competência da data e o impacto pesa na avaliação da qualidade.</small>
        </div>
        <button type="button" class="acao-secundaria" [disabled]="!diario()?.ocorrencias?.length" (click)="baixarPdf()">Baixar PDF</button>
      </header>

      <div class="diario-chat" #chat>
        @for (o of diario()?.ocorrencias ?? []; track o.id) {
          <article class="balao-diario" [class.minha]="o.registrada_por_id === usuarioId()" [class.com-glosa]="o.possui_glosa" [class.com-impacto]="o.impacta_avaliacao">
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
            @if (o.impacta_avaliacao) {
              <!-- Itens do formulário de avaliação que a ocorrência impacta -->
              <div class="glosas-balao impacto-balao">
                <span class="rotulo-glosa">Impacta a avaliação</span>
                @for (i of o.itens_avaliacao; track i.item_id) { <span class="chip-glosa" [title]="i.grupo_nome">{{ i.item_nome }}</span> }
              </div>
            }
            @if (o.anexos.length) {
              <div class="anexos-balao">
                @for (a of o.anexos; track a.id) {
                  <button type="button" class="link-arquivo" [title]="'Baixar ' + a.nome" (click)="baixarAnexo(o, a)">{{ a.nome }} <small>({{ tamanhoLegivel(a.tamanho) }})</small></button>
                }
              </div>
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
          <div class="grade-formulario diario-campos">
            <div class="ocupa-duas">
              <span class="rotulo-campo" id="rotulo-impacto">Esta ocorrência impacta a avaliação da qualidade? *</span>
              <div class="seletor-segmentado" role="radiogroup" aria-labelledby="rotulo-impacto">
                <button type="button" role="radio" [attr.aria-checked]="!impactaAvaliacao" [class.ativo]="!impactaAvaliacao" (click)="impactaAvaliacao = false">Não</button>
                <button type="button" role="radio" [attr.aria-checked]="impactaAvaliacao" [class.ativo]="impactaAvaliacao"
                        [disabled]="!diario()?.itens_avaliacao?.length" (click)="impactaAvaliacao = true">Sim</button>
              </div>
              @if (!diario()?.itens_avaliacao?.length) { <small class="dica-formulario">O contrato não tem formulário de avaliação ativo.</small> }
            </div>
          </div>
          @if (impactaAvaliacao) {
            <p class="secao-formulario">Itens da avaliação impactados</p>
            <div class="itens-impacto">
              @for (g of gruposAvaliacao(); track g.grupo) {
                <fieldset>
                  <legend>{{ g.grupo }}</legend>
                  @for (i of g.itens; track i.id) {
                    <label class="opcao-marcar">
                      <input type="checkbox" [name]="'impacto-' + i.id" [checked]="itensMarcados().has(i.id)" (change)="alternarItem(i.id)" />
                      {{ i.nome }}
                    </label>
                  }
                </fieldset>
              }
            </div>
            <small class="dica-formulario">Na avaliação da competência da data, nota máxima nesses itens exigirá justificativa.</small>
          }
          <p class="secao-formulario">Anexos</p>
          <div class="anexos-formulario">
            <input #campoArquivos type="file" multiple hidden (change)="aoEscolherArquivos(campoArquivos)" />
            <button type="button" class="acao-secundaria acao-pequena" [disabled]="arquivos().length >= maximoAnexos" (click)="campoArquivos.click()">+ Anexar arquivos</button>
            <small class="dica-formulario">Até {{ maximoAnexos }} arquivos (fotos, PDF, planilhas…). Vão anexados ao e-mail da ocorrência.</small>
            @for (a of arquivos(); track $index) {
              <span class="chip-anexo">{{ a.name }} <small>({{ tamanhoLegivel(a.size) }})</small>
                <button type="button" class="link-arquivo" [attr.aria-label]="'Remover ' + a.name" (click)="removerArquivo($index)">remover</button>
              </span>
            }
          </div>
          @if (erro()) { <p class="aviso-formulario erro" role="alert">{{ erro() }}</p> }
          <div class="acoes-cartao">
            <app-opcao-email [(marcado)]="enviarEmail" [(selecionados)]="prepostosIds" [fonte]="fontePrepostos" rotuloLista="Prepostos" vazio="Nenhum preposto ativo com e-mail: só a equipe receberá." descricao="Registro e anexos à equipe e aos prepostos escolhidos" />
            <small class="dica-formulario">Ocorrências não podem ser editadas depois.</small>
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
  private readonly execucao = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly chat = viewChild<ElementRef<HTMLElement>>('chat');

  protected readonly diario = signal<DiarioContrato | null>(null);
  protected readonly salvando = signal(false);
  // "Enviar por e-mail" começa desmarcado: só envia quem marcar
  protected readonly enviarEmail = signal(false);
  protected readonly prepostosIds = signal<(string | number)[] | null>(null);
  protected readonly fontePrepostos = () => this.execucao.gruposPrepostos(this.contratoId());
  protected readonly reenviando = signal<string | null>(null);
  protected readonly erro = signal<string | null>(null);
  protected readonly glosas = signal<LinhaGlosa[]>([]);
  protected readonly hoje = new Date().toLocaleDateString('sv-SE');
  protected data = this.hoje;
  protected descricao = '';
  protected possuiGlosa = false;
  protected impactaAvaliacao = false;
  protected readonly maximoAnexos = MAXIMO_ANEXOS;
  protected readonly arquivos = signal<File[]>([]);
  protected readonly itensMarcados = signal<Set<string>>(new Set());
  /** Itens do formulário de avaliação ativo agrupados como no formulário. */
  protected readonly gruposAvaliacao = computed(() => {
    const grupos: { grupo: string; itens: { id: string; nome: string }[] }[] = [];
    for (const i of this.diario()?.itens_avaliacao ?? []) {
      let g = grupos.find((x) => x.grupo === i.grupo);
      if (!g) grupos.push((g = { grupo: i.grupo, itens: [] }));
      g.itens.push(i);
    }
    return grupos;
  });
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

  protected alternarItem(id: string): void {
    this.itensMarcados.update((s) => {
      const novo = new Set(s);
      if (!novo.delete(id)) novo.add(id);
      return novo;
    });
  }

  protected aoEscolherArquivos(campo: HTMLInputElement): void {
    const escolhidos = Array.from(campo.files ?? []);
    campo.value = '';
    const livres = MAXIMO_ANEXOS - this.arquivos().length;
    if (escolhidos.length > livres) this.erro.set(`No máximo ${MAXIMO_ANEXOS} arquivos por ocorrência.`);
    this.arquivos.update((l) => [...l, ...escolhidos.slice(0, livres)]);
  }

  protected removerArquivo(indice: number): void {
    this.arquivos.update((l) => l.filter((_, i) => i !== indice));
  }

  protected tamanhoLegivel(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${(bytes / 1024 / 1024).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB`;
  }

  protected baixarAnexo(ocorrencia: OcorrenciaDiario, anexo: AnexoOcorrencia): void {
    this.api.baixarAnexoOcorrencia(this.contratoId(), ocorrencia.id, anexo).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar o anexo') });
  }

  protected registrar(): void {
    const erro = this.validar();
    this.erro.set(erro);
    if (erro) return;
    this.salvando.set(true);
    const glosas = this.possuiGlosa ? this.glosas().map((g) => ({ item_id: g.item_id, quantidade: paraDecimalApi(g.quantidade) })) : [];
    const dados = {
      data_ocorrencia: this.data,
      descricao: this.descricao.trim(),
      possui_glosa: this.possuiGlosa,
      glosas,
      impacta_avaliacao: this.impactaAvaliacao,
      itens_avaliacao: this.impactaAvaliacao ? [...this.itensMarcados()] : [],
      enviar_email: this.enviarEmail(),
      prepostos_ids: this.enviarEmail() ? (this.prepostosIds() as string[] | null) : null,
    };
    this.api
      .registrarOcorrencia(this.contratoId(), dados, this.arquivos())
      .subscribe({
        next: () => {
          this.salvando.set(false);
          this.descricao = '';
          this.possuiGlosa = false;
          this.glosas.set([]);
          this.impactaAvaliacao = false;
          this.itensMarcados.set(new Set());
          this.arquivos.set([]);
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
    if (this.impactaAvaliacao && !this.itensMarcados().size) return 'Marque os itens da avaliação que a ocorrência impacta.';
    if (this.arquivos().length > MAXIMO_ANEXOS) return `No máximo ${MAXIMO_ANEXOS} arquivos por ocorrência.`;
    return null;
  }
}
