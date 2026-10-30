// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a aba "Diário de bordo": registro de ocorrências (com glosa, anexos e impacto na avaliação) e lista em forma de chat.

import { DatePipe } from '@angular/common';
import { RascunhoServidorComponent } from '../compartilhado/rascunho-servidor.component';
import { OpcaoEmailComponent } from '../compartilhado/opcao-email.component';
import { Component, computed, DestroyRef, inject, input, OnInit, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { RascunhoGuardado, RascunhoService } from '../../../core/rascunho/rascunho.service';
import { AvisoRascunhoComponent } from '../../../shared/componentes/aviso-rascunho/aviso-rascunho.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { ParametrosContratosService } from '../compartilhado/parametros-contratos.service';
import { AnexoOcorrencia, DiarioContrato, OcorrenciaDiario } from '../compartilhado/contratos.models';
import { paraDecimalApi, ROTULOS_PAPEL } from '../compartilhado/rotulos';
import { EditorRicoComponent } from '../../contratacoes/editor-rico.component';
import { DescricaoTarefaPipe } from '../../tarefas/descricao-tarefa.pipe';

import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
/** Campos do formulário guardados como rascunho (os anexos não entram). */
interface RascunhoOcorrencia {
  data: string;
  competenciaAfetada: string;
  descricao: string;
  possuiGlosa: boolean;
  glosas: LinhaGlosa[];
  impactaAvaliacao: boolean;
  itensMarcados: string[];
  enviarEmail: boolean;
}

interface LinhaGlosa {
  item_id: string;
  quantidade: string;
}

/** Aba "Diário de bordo": a equipe relata ocorrências; cada uma é enviada por e-mail à equipe e ao preposto. */
@Component({
  selector: 'app-aba-diario',
  imports: [EsqueletoComponent, DescricaoTarefaPipe, EditorRicoComponent, FormsModule, DatePipe, OpcaoEmailComponent, ...PIPES_FORMATACAO, AvisoRascunhoComponent, RascunhoServidorComponent],
  template: `
    <section class="cartao-dados diario" aria-labelledby="titulo-diario">
      <header>
        <div>
          <h2 id="titulo-diario">Diário de bordo</h2>
          <small>Ocorrências da execução relatadas pela equipe. Cada registro é enviado por e-mail (com os anexos) à equipe e ao preposto; as glosas limitam a medição da competência da data e o impacto pesa na avaliação da qualidade.</small>
        </div>
        <div class="acoes-cartao">
          <button type="button" class="acao-secundaria" [disabled]="!diario()?.ocorrencias?.length" (click)="baixarPdf()">Baixar PDF</button>
          @if (diario()?.pode_registrar) {
            <button type="button" class="acao-primaria" [attr.aria-expanded]="formularioAberto()" aria-controls="diario-novo" (click)="alternarFormulario()">{{ formularioAberto() ? 'Fechar formulário' : '+ Nova ocorrência' }}</button>
          }
        </div>
      </header>

      @if (diario()?.pode_registrar && formularioAberto()) {
        <div id="diario-novo" class="diario-novo">
        <form class="diario-formulario" (ngSubmit)="registrar()">
          <p class="secao-formulario">Nova ocorrência</p>
          <app-rascunho-servidor #rascunhoServidor [contratoId]="contratoId()" tipo="diario" [editavel]="!!diario()?.pode_registrar" [obterDados]="dadosDoRascunho"
                                 observacao="Os anexos não são guardados." (carregar)="carregarRascunhoDaEquipe($event)" />
          @if (rascunhoRestaurado(); as r) { <app-aviso-rascunho [salvoEm]="r.salvoEm" observacao="Os anexos não são guardados: anexe de novo." (descartar)="descartarRascunho()" /> }
          <div class="grade-formulario diario-campos">
            <div>
              <label for="diario-data">Data da ocorrência *</label>
              <input id="diario-data" name="data" type="date" required [max]="hoje" [(ngModel)]="data" (ngModelChange)="aoMudarData()" />
            </div>
            <!-- Seletor segmentado Não | Sim (botões, no lugar de rádios desproporcionais) -->
            <div>
              <span class="rotulo-campo" id="rotulo-glosa">Esta ocorrência implicará glosa? *</span>
              <div class="seletor-segmentado" role="radiogroup" aria-labelledby="rotulo-glosa">
                <button type="button" role="radio" [attr.aria-checked]="!possuiGlosa" [class.ativo]="!possuiGlosa" (click)="possuiGlosa = false">Não</button>
                <button type="button" role="radio" [attr.aria-checked]="possuiGlosa" [class.ativo]="possuiGlosa" (click)="possuiGlosa = true; aoMarcarGlosa()">Sim</button>
              </div>
            </div>
            <div>
              <label for="diario-competencia">Competência afetada *</label>
              <select id="diario-competencia" name="competencia_afetada" required [(ngModel)]="competenciaAfetada" (ngModelChange)="competenciaEscolhida = true">
                @for (c of diario()?.competencias ?? []; track c.identificador) { <option [value]="c.identificador">{{ c.rotulo }}{{ c.medicao_concluida ? ' (medição concluída)' : '' }}</option> }
              </select>
              <small class="dica-formulario">A glosa e o impacto na avaliação valem nesta competência, mesmo que a data da ocorrência seja de outro mês.</small>
            </div>
            <div class="ocupa-duas">
              <label for="diario-texto">Ocorrência *</label>
              @defer (on idle) { <app-editor-rico [(html)]="descricao" [colarFormatado]="true" rotulo="Ocorrência" /> } @placeholder { <app-esqueleto tipo="formulario" [linhas]="3" /> }
              <small class="dica-formulario">Descreva o que aconteceu (ex.: posto descoberto das 8h às 12h). Aceita negrito, listas e links.</small>
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
                <button type="button" class="acao-perigo acao-pequena" [disabled]="glosas().length === 1" (click)="removerGlosa($index)">Remover</button>
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
                <button type="button" class="acao-perigo acao-pequena" [attr.aria-label]="'Remover ' + a.name" (click)="removerArquivo($index)">Remover</button>
              </span>
            }
          </div>
          @if (erro()) { <p class="aviso-formulario erro" role="alert">{{ erro() }}</p> }
          <app-opcao-email [(marcado)]="enviarEmail" [(selecionados)]="prepostosIds" [fonte]="fontePrepostos" rotuloLista="Prepostos" vazio="Nenhum preposto ativo com e-mail: só a equipe receberá." descricao="Registro e anexos à equipe e aos prepostos escolhidos" />
          <div class="barra-envio-nf barra-medicao">
            <div class="texto-envio"><span class="dica-formulario">Ocorrências não podem ser editadas depois.</span></div>
            <button type="button" class="acao-secundaria" [disabled]="rascunhoServidor.salvando()" (click)="rascunhoServidor.salvar()" title="Salva este rascunho para a equipe do contrato ver e continuar">Salvar rascunho</button>
            <button [class.carregando]="salvando()" type="submit" class="acao-primaria" [disabled]="salvando()">{{ salvando() ? 'Salvando…' : 'Registrar ocorrência' }}</button>
          </div>
        </form>
        </div>
      }

      @if (diario(); as dd) {
        <div class="resumo-diario" role="group" aria-label="Resumo do diário">
          <div><span>Ocorrências</span><strong>{{ dd.ocorrencias.length }}</strong></div>
          <div [class.perigo]="contar('glosa') > 0"><span>Com glosa</span><strong>{{ contar('glosa') }}</strong></div>
          <div [class.alerta]="contar('impacto') > 0"><span>Impactam a avaliação</span><strong>{{ contar('impacto') }}</strong></div>
          <div [class.alerta]="contar('email') > 0"><span>E-mail pendente</span><strong>{{ contar('email') }}</strong></div>
        </div>
        <div class="chips-filtro filtros-diario" role="group" aria-label="Filtrar ocorrências">
          @for (f of filtros; track f.chave) {
            <button type="button" [class.ativo]="filtro() === f.chave" [attr.aria-pressed]="filtro() === f.chave" (click)="filtro.set(f.chave); limite.set(20)">{{ f.rotulo }} ({{ contar(f.chave) }})</button>
          }
        </div>
      }

      <div class="diario-feed">
        @for (g of grupos(); track g.data) {
          <section class="dia-diario" [attr.aria-label]="'Ocorrências de ' + (g.data | dataBr)">
            <h3 class="dia-titulo"><span>{{ g.data | dataBr }}</span><small>{{ g.itens.length }} {{ g.itens.length === 1 ? 'ocorrência' : 'ocorrências' }}</small></h3>
            @for (o of g.itens; track o.id) {
              <article class="balao-diario" [class.com-glosa]="o.possui_glosa" [class.com-impacto]="o.impacta_avaliacao && !o.possui_glosa">
                <header class="cabeca-diario">
                  <span class="avatar-diario" aria-hidden="true">{{ iniciais(o.registrada_por_nome) }}</span>
                  <div class="autor-diario">
                    <strong>{{ o.registrada_por_nome }}@if (o.registrada_por_id === usuarioId()) { <span class="selo-diario">Você</span> }</strong>
                    @if (o.registrada_por_papel) { <small>{{ rotuloPapel(o.registrada_por_papel) }}</small> }
                  </div>
                  <div class="marcas-diario">
                    @if (o.competencia_rotulo) { <span class="selo-diario" title="Competência afetada pela ocorrência">Competência afetada {{ o.competencia_rotulo }}</span> }
                    <time [attr.datetime]="o.criado_em" title="Registrado em">Registrada em {{ o.criado_em | date: 'dd/MM/yyyy HH:mm' }}</time>
                  </div>
                </header>
                <div class="texto texto-rico" [class.recolhido]="longo(o) && !expandidas().has(o.id)" [innerHTML]="o.descricao | descricaoTarefa"></div>
                @if (longo(o)) {
                  <button type="button" class="link-arquivo ver-tudo" [attr.aria-expanded]="expandidas().has(o.id)" (click)="alternarTexto(o.id)">{{ expandidas().has(o.id) ? 'Recolher' : 'Ver tudo' }}</button>
                }
                @if (o.possui_glosa) {
                  <div class="status-diario perigo">
                    <span class="selo-situacao perigo">Haverá glosa</span>
                    <span class="itens-diario">@for (g of o.glosas; track g.item_id) { <span class="chip-diario">{{ g.descricao_item }} · <b>{{ g.quantidade | quantidade }}</b></span> }</span>
                  </div>
                  @if (o.medicao_ja_concluida) { <small class="texto-erro">A medição dessa competência já foi concluída: a glosa só vale se ela for reaberta.</small> }
                }
                @if (o.impacta_avaliacao) {
                  <div class="status-diario alerta">
                    <span class="selo-situacao alerta">Impacta a avaliação da qualidade</span>
                    <span class="itens-diario">@for (i of o.itens_avaliacao; track i.item_id) { <span class="chip-diario" [title]="i.grupo_nome">{{ i.item_nome }}</span> }</span>
                  </div>
                }
                <footer>
                  <div class="anexos-balao">
                    @for (a of o.anexos; track a.id) {
                      <button type="button" class="acao-secundaria acao-pequena" [title]="'Baixar ' + a.nome" (click)="baixarAnexo(o, a)">{{ a.nome }} <small>({{ tamanhoLegivel(a.tamanho) }})</small></button>
                    }
                  </div>
                  <div class="email-diario">
                    @if (o.email.enviado_em === null) {
                      <small>Enviando e-mail…</small>
                    } @else if (o.email.ok) {
                      <small [title]="o.email.destinatarios.join(', ')">✓ E-mail enviado a {{ o.email.destinatarios.length }} destinatário(s)</small>
                    } @else {
                      <small class="texto-erro">E-mail não enviado: {{ o.email.erro }}</small>
                      @if (diario()?.pode_registrar) {
                        <button type="button" class="acao-secundaria acao-pequena" [disabled]="reenviando() === o.id" (click)="reenviar(o)">{{ reenviando() === o.id ? 'Reenviando…' : 'Reenviar' }}</button>
                      }
                    }
                  </div>
                </footer>
              </article>
            }
          </section>
        } @empty {
          <div class="estado-vazio">@if (diario()) { {{ filtro() === 'todas' ? 'Nenhuma ocorrência registrada.' : 'Nenhuma ocorrência neste filtro.' }} } @else { <app-esqueleto tipo="lista" [linhas]="3" /> }</div>
        }
        @if (restantes() > 0) {
          <div class="mais-diario"><button type="button" class="acao-secundaria" (click)="limite.set(limite() + 20)">Carregar mais ({{ restantes() }})</button></div>
        }
      </div>
    </section>
  `,
})
export class AbaDiarioComponent implements OnInit {
  readonly contratoId = input.required<string>();
  /** Usuário logado (os próprios balões ficam à direita). */
  readonly usuarioId = input<number | null>(null);

  private readonly api = inject(ContratosApiService);
  private readonly parametros = inject(ParametrosContratosService);
  private readonly execucao = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rascunhos = inject(RascunhoService);
  private readonly destruir = inject(DestroyRef);

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
  /** Competência afetada (`AAAA-MM`): acompanha a data enquanto a pessoa não escolher outra. */
  protected competenciaAfetada = '';
  protected competenciaEscolhida = false;
  protected descricao = '';
  protected possuiGlosa = false;
  protected impactaAvaliacao = false;
  /** Máximo de arquivos por ocorrência (parâmetro de Contratos, o mesmo limite da API). */
  protected get maximoAnexos(): number { return this.parametros.valores().maximo_anexos_ocorrencia; }
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
  /** Filtro da lista de ocorrências. */
  protected readonly filtro = signal<'todas' | 'glosa' | 'impacto' | 'email' | 'minhas'>('todas');
  protected readonly filtros: { chave: 'todas' | 'glosa' | 'impacto' | 'email' | 'minhas'; rotulo: string }[] = [
    { chave: 'todas', rotulo: 'Todas' }, { chave: 'glosa', rotulo: 'Com glosa' }, { chave: 'impacto', rotulo: 'Impactam a avaliação' },
    { chave: 'email', rotulo: 'E-mail pendente' }, { chave: 'minhas', rotulo: 'Minhas' },
  ];
  /** Formulário "Nova ocorrência" (nasce fechado) e quantas ocorrências mostrar (carrega de 20 em 20). */
  protected readonly formularioAberto = signal(false);
  /** Rascunho restaurado ao abrir a aba (guardado no navegador enquanto se digita). */
  protected readonly rascunhoRestaurado = signal<RascunhoGuardado<RascunhoOcorrencia> | null>(null);
  protected readonly limite = signal(20);
  /** Ocorrências com o texto completo aberto. */
  protected readonly expandidas = signal<Set<string>>(new Set());
  /** Ocorrências que atendem ao filtro escolhido. */
  protected readonly visiveis = computed(() => (this.diario()?.ocorrencias ?? []).filter((o) => this.atende(o, this.filtro())));
  /** Mais recentes primeiro (data da ocorrência e, no mesmo dia, hora do registro), limitadas por `limite`. */
  private readonly ordenadas = computed(() => [...this.visiveis()].sort((a, b) => (b.data_ocorrencia + b.criado_em).localeCompare(a.data_ocorrencia + a.criado_em)));
  /** Ocorrências mostradas, agrupadas pelo dia da ocorrência. */
  protected readonly grupos = computed(() => {
    const dias: { data: string; itens: OcorrenciaDiario[] }[] = [];
    for (const o of this.ordenadas().slice(0, this.limite())) {
      const ultimo = dias.at(-1);
      if (ultimo && ultimo.data === o.data_ocorrencia) ultimo.itens.push(o);
      else dias.push({ data: o.data_ocorrencia, itens: [o] });
    }
    return dias;
  });
  protected readonly restantes = computed(() => Math.max(0, this.ordenadas().length - this.limite()));

  /** Troca a data: se a competência ainda não foi escolhida à mão, passa para a que contém o dia (ou o mês dele). */
  protected aoMudarData(): void {
    if (this.competenciaEscolhida || !this.data) return;
    this.sugerirCompetencia();
  }

  private sugerirCompetencia(): void {
    const lista = this.diario()?.competencias ?? [];
    const da_data = lista.find((c) => c.periodo_inicio <= this.data && this.data <= c.periodo_fim) ?? lista.find((c) => c.identificador === this.data.slice(0, 7));
    this.competenciaAfetada = da_data?.identificador ?? lista[0]?.identificador ?? '';
  }

  protected alternarFormulario(): void {
    this.formularioAberto.update((v) => !v);
    if (this.formularioAberto()) setTimeout(() => document.getElementById('diario-novo')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  }

  protected alternarTexto(id: string): void {
    this.expandidas.update((s) => { const n = new Set(s); if (!n.delete(id)) n.add(id); return n; });
  }

  /** Relato comprido (mais de ~420 caracteres ou muitos blocos): nasce recolhido, com "Ver tudo". */
  protected longo(o: OcorrenciaDiario): boolean {
    const texto = o.descricao.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    return texto.length > 420 || (o.descricao.match(/<(p|li)[ >]/gi) ?? []).length > 6;
  }

  /** Iniciais do autor para o avatar (primeira e última palavra do nome). */
  protected iniciais(nome: string): string {
    const partes = nome.trim().split(/\s+/).filter(Boolean);
    return ((partes[0]?.[0] ?? '') + (partes.length > 1 ? partes.at(-1)![0] : '')).toUpperCase();
  }

  protected atende(o: OcorrenciaDiario, f: string): boolean {
    return f === 'todas' || (f === 'glosa' && o.possui_glosa) || (f === 'impacto' && o.impacta_avaliacao)
      || (f === 'email' && (o.email.enviado_em === null || !o.email.ok)) || (f === 'minhas' && o.registrada_por_id === this.usuarioId());
  }
  protected contar(f: string): number {
    return (this.diario()?.ocorrencias ?? []).filter((o) => this.atende(o, f)).length;
  }

  /** Há envio em segundo plano ainda sem resultado: a lista é consultada de novo em instantes. */
  private readonly aguardandoEnvio = computed(() => this.diario()?.ocorrencias.some((o) => o.email.enviado_em === null) ?? false);

  ngOnInit(): void {
    this.carregar();
    this.restaurarRascunho();
    // Guarda o que está sendo digitado; formulário vazio (ou fechado sem nada) apaga o rascunho
    this.rascunhos.vigiar<RascunhoOcorrencia>(this.destruir, this.chaveRascunho(), () => this.estadoDoFormulario());
  }

  private chaveRascunho(): string {
    return `diario:${this.contratoId()}`;
  }

  /** Estado do formulário para o rascunho; `null` quando nada foi preenchido (não há o que guardar). */
  private estadoDoFormulario(): RascunhoOcorrencia | null {
    const texto = this.descricao.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim();
    const glosas = this.glosas().filter((g) => g.item_id || g.quantidade);
    const itens = [...this.itensMarcados()];
    if (!texto && !glosas.length && !itens.length && !this.possuiGlosa && !this.impactaAvaliacao) return null;
    return {
      data: this.data, competenciaAfetada: this.competenciaAfetada, descricao: this.descricao, possuiGlosa: this.possuiGlosa, glosas: this.glosas(),
      impactaAvaliacao: this.impactaAvaliacao, itensMarcados: itens, enviarEmail: this.enviarEmail(),
    };
  }

  /** Rascunho salvo no servidor (visível à equipe): o componente guarda e carrega; aqui só dizemos o que guardar e como aplicar. */
  private readonly rascunhoServidor = viewChild<RascunhoServidorComponent>('rascunhoServidor');
  protected readonly dadosDoRascunho = (): Record<string, unknown> | null => this.estadoDoFormulario() as Record<string, unknown> | null;

  /** Preenche o formulário com o rascunho salvo pela equipe. */
  protected carregarRascunhoDaEquipe(dados: Record<string, unknown>): void {
    this.aplicarRascunho(dados as unknown as RascunhoOcorrencia);
    this.rascunhoRestaurado.set(null);
  }

  private aplicarRascunho(r: RascunhoOcorrencia): void {
    this.data = r.data || this.hoje;
    this.competenciaAfetada = r.competenciaAfetada;
    this.competenciaEscolhida = !!r.competenciaAfetada;
    this.descricao = r.descricao;
    this.possuiGlosa = r.possuiGlosa;
    this.glosas.set(r.glosas ?? []);
    this.impactaAvaliacao = r.impactaAvaliacao;
    this.itensMarcados.set(new Set(r.itensMarcados ?? []));
    this.enviarEmail.set(!!r.enviarEmail);
    this.formularioAberto.set(true);
  }

  /** Se havia um rascunho (a sessão venceu, a aba fechou…), preenche o formulário de novo e o abre. */
  private restaurarRascunho(): void {
    const guardado = this.rascunhos.ler<RascunhoOcorrencia>(this.chaveRascunho());
    if (!guardado) return;
    this.aplicarRascunho(guardado.dados);
    this.rascunhoRestaurado.set(guardado);
  }

  /** Descarta o rascunho restaurado e limpa o formulário. */
  protected descartarRascunho(): void {
    this.rascunhos.limpar(this.chaveRascunho());
    this.rascunhoRestaurado.set(null);
    this.limparFormulario();
  }

  private limparFormulario(): void {
    this.descricao = '';
    this.possuiGlosa = false;
    this.glosas.set([]);
    this.impactaAvaliacao = false;
    this.itensMarcados.set(new Set());
    this.arquivos.set([]);
    this.data = this.hoje;
    this.competenciaEscolhida = false;
    this.enviarEmail.set(false);
    this.sugerirCompetencia();
  }

  /** Nome do papel na equipe (ou o código, se desconhecido). */
  protected rotuloPapel(papel: string): string {
    return (ROTULOS_PAPEL as Record<string, string>)[papel] ?? papel;
  }

  protected carregar(): void {
    this.api.diario(this.contratoId()).subscribe({
      next: (d) => {
        this.diario.set(d);
        if (!this.competenciaEscolhida) this.sugerirCompetencia();
        if (this.aguardandoEnvio()) setTimeout(() => this.carregar(), 2500);
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
    const livres = this.maximoAnexos - this.arquivos().length;
    if (escolhidos.length > livres) this.erro.set(`No máximo ${this.maximoAnexos} arquivos por ocorrência.`);
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
      competencia_afetada: this.competenciaAfetada || null,
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
          this.limparFormulario();
          // Registrada de verdade: o rascunho não serve mais (a vigilância o apagaria em 2 s; apaga já para não restaurar por engano)
          this.rascunhos.limpar(this.chaveRascunho());
          this.rascunhoRestaurado.set(null);
          this.rascunhoServidor()?.apagar();
          this.formularioAberto.set(false);
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
    if (!this.competenciaAfetada) return 'Escolha a competência afetada.';
    if (!this.descricao.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim()) return 'Descreva a ocorrência.';
    if (this.possuiGlosa) {
      if (!this.glosas().length) return 'Informe o item e a quantidade a glosar.';
      for (const g of this.glosas()) {
        if (!g.item_id) return 'Selecione o item de cada linha da glosa.';
        const quantidade = Number(paraDecimalApi(g.quantidade));
        if (!Number.isFinite(quantidade) || quantidade <= 0) return 'A quantidade a glosar deve ser maior que zero.';
      }
    }
    if (this.impactaAvaliacao && !this.itensMarcados().size) return 'Marque os itens da avaliação que a ocorrência impacta.';
    if (this.arquivos().length > this.maximoAnexos) return `No máximo ${this.maximoAnexos} arquivos por ocorrência.`;
    return null;
  }
}
