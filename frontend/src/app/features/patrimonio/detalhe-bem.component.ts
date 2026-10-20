// Criado por José Eduardo Santana Martins
// Este arquivo serve para a página do bem: dados, edição, fotos, histórico por campo, linha do tempo, trajeto e ações (movimentar, ajustar local, devolver a Ativo).
import { DatePipe } from '@angular/common';
import { Component, inject, input, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { classeMarcador } from '../tarefas/marcadores.paleta';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { montarChapa, separarChapa } from './chapa-prefixo';
import { LeitorCodigoComponent } from './leitor-codigo.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { Bem, COR_SITUACAO, DadosBem, Evento, ROTULOS_CONSERVACAO, ROTULOS_GARANTIA, ROTULOS_SITUACAO, rotuloCategoria } from './patrimonio.models';
import { SeletorSalaComponent } from './seletor-sala.component';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
type Aba = 'dados' | 'linha' | 'trajeto';

const ROTULOS_CAMPO: Record<string, string> = {
  chapa: 'Chapa', descricao: 'Descrição', conservacao: 'Conservação', situacao: 'Situação', origem: 'Origem', grupo_id: 'Grupo', uge: 'UGE', ua: 'UA', divisao: 'Divisão',
  valor_aquisicao: 'Valor de aquisição', valor_atual: 'Valor atual', data_aquisicao: 'Data de aquisição', garantia_meses: 'Meses de garantia', marca: 'Marca', modelo: 'Modelo',
  numero_serie: 'Número de série', nota_fiscal: 'Nota fiscal', fornecedor: 'Fornecedor', observacoes: 'Observações', localizacao: 'Sala', responsavel: 'Responsável', fotos: 'Fotos',
};
const ROTULOS_EVENTO: Record<string, string> = {
  cadastrou: 'Cadastrado', alterou: 'Alterado', moveu: 'Movimentado', ajustou_local: 'Local ajustado', localizou: 'Localizado', responsavel: 'Responsável', classificou: 'Classificado', classificacao_pendente: 'Classificação pendente',
  classificacao_recusada: 'Classificação recusada', reverteu: 'Devolvido a Ativo', baixou: 'Baixado', baixa_recusada: 'Baixa recusada', nao_chegou: 'Não chegou ao destino',
};
const CAMPOS_EDITAVEIS = ['chapa', 'descricao', 'conservacao', 'situacao', 'origem', 'grupo_id', 'uge', 'ua', 'divisao', 'valor_aquisicao', 'valor_atual', 'data_aquisicao', 'garantia_meses', 'marca', 'modelo', 'numero_serie', 'nota_fiscal', 'fornecedor', 'observacoes'] as const;

/** `/patrimonio/bens/:bemId`. */
@Component({
  selector: 'app-detalhe-bem',
  imports: [EsqueletoComponent, FormsModule, RouterLink, DatePipe, CabecalhoPatrimonioComponent, SeletorSalaComponent, LeitorCodigoComponent],
  template: `
    <app-cabecalho-patrimonio [titulo]="bem() ? 'Bem ' + bem()!.rotulo : 'Bem'" [descricao]="bem()?.descricao ?? ''" />
    @if (bem(); as b) {
      <section class="painel-gestao patrimonio" [class.pat-compacto]="editando()" [class.pat-formulario]="editando()">
        <div class="pat-topo-bem">
          <span class="pat-marcadores">
            <span [class]="marcador(cores[b.situacao])">{{ situacoes[b.situacao] }}@if (b.categoria_inservivel) { · {{ rotuloCategoria(b.categoria_inservivel) }} }</span>
            @if (b.classificacao_pendente) { <span [class]="marcador(3)">Classificação pendente</span> }
            @if (b.em_movimentacao) { <span [class]="marcador(4)">Em movimentação</span> }
            @if (b.dados_contabeis_pendentes) { <span [class]="marcador(0)">Dados contábeis pendentes</span> }
          </span>
          <div class="pat-acoes">
            @if (b.situacao !== 'baixado') {
              @if (estado.podeOperar()) {
                <button type="button" class="acao-secundaria" (click)="editando() ? cancelarEdicao() : editar(b)">{{ editando() ? 'Cancelar edição' : 'Editar' }}</button>
                <a class="acao-primaria" [routerLink]="['/patrimonio/movimentacoes/nova']" [queryParams]="{ bem: b.id }">Movimentar</a>
              }
              @if (estado.podeAdministrar()) { <button type="button" class="acao-secundaria" (click)="ajustando.set(!ajustando())">Ajustar local</button> }
              @if (estado.podeAdministrar() && (b.situacao === 'inservivel' || b.situacao === 'extraviado')) {
                <button type="button" class="acao-secundaria" (click)="revertendo.set(!revertendo())">Devolver a Ativo</button>
              }
            }
          </div>
        </div>
        @for (a of b.avisos; track a) { <p class="pat-aviso">{{ a }}</p> }

        @if (ajustando()) {
          <div class="pat-painel-acao">
            <strong>Ajustar o local sem movimentação</strong>
            <app-seletor-sala nome="ajuste" [leitor]="true" [valor]="novaSala" (valorChange)="novaSala = $event" [excluir]="[b.localizacao_id]" [soDeposito]="b.situacao === 'inservivel'" />
            <label for="aj-motivo">Motivo (obrigatório; fica no histórico)</label>
            <input id="aj-motivo" name="motivo-ajuste" [(ngModel)]="motivoAjuste" />
            <button type="button" class="acao-primaria" [disabled]="!novaSala || !motivoAjuste.trim()" (click)="ajustarLocal(b)">Ajustar local</button>
          </div>
        }
        @if (revertendo()) {
          <div class="pat-painel-acao">
            <strong>Devolver o bem a Ativo</strong>
            @if (b.situacao === 'extraviado') { <label>Sala onde foi encontrado *</label><app-seletor-sala nome="achado" [leitor]="true" [valor]="novaSala" (valorChange)="novaSala = $event" /> }
            <label for="rv-just">Justificativa (mínimo de 10 caracteres)</label>
            <textarea id="rv-just" name="justificativa-reversao" rows="3" [(ngModel)]="justificativa"></textarea>
            <button type="button" class="acao-primaria" [disabled]="justificativa.trim().length < 10 || (b.situacao === 'extraviado' && !novaSala)" (click)="reverter(b)">Devolver a Ativo</button>
          </div>
        }

        <nav class="pat-abas" aria-label="Seções do bem">
          <button type="button" [class.ativa]="aba() === 'dados'" (click)="aba.set('dados')">Dados</button>
          <button type="button" [class.ativa]="aba() === 'linha'" (click)="abrirAba('linha')">Linha do tempo</button>
          <button type="button" [class.ativa]="aba() === 'trajeto'" (click)="abrirAba('trajeto')">Trajeto</button>
        </nav>

        @if (aba() === 'dados') {
          @if (editando()) {
            <!-- Mesmo desenho da tela de adicionar: identificação com prefixo e leitor, botões de escolha e "Mais dados" -->
            <div class="grade-formulario pat-edicao">
              <fieldset class="ocupa-duas pat-identificacao">
                <legend>Identificação * <small>(chapa <b>ou</b> série)</small></legend>
                <div class="pat-identificacao-campos">
                  <div><label for="e-chapa">Chapa</label>
                    <div class="pat-entrada-com-acao">
                      <select name="prefixo" aria-label="Prefixo da chapa" class="pat-prefixo" [(ngModel)]="prefixo">
                        <option value="">Sem prefixo</option>
                        @for (p of estado.prefixos(); track p.id) { <option [value]="p.codigo">{{ p.codigo }}</option> }
                      </select>
                      <input id="e-chapa" name="chapa" maxlength="60" autocomplete="off" inputmode="text" placeholder="Número (ex.: 231)" [(ngModel)]="numero" />
                      <button type="button" class="pat-leitor" aria-label="Ler o código da chapa com a câmera" title="Ler código com a câmera" (click)="lendo.set('chapa')">
                        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10" /></svg></button>
                    </div>
                    @if (chapaFinal() && chapaFinal() !== numero.trim()) { <small class="dica">A chapa ficará <b>{{ chapaFinal() }}</b>.</small> }</div>
                  <div><label for="e-serie">Número de série</label>
                    <div class="pat-entrada-com-acao">
                      <input id="e-serie" name="numero_serie" maxlength="80" autocomplete="off" placeholder="Digite ou leia o código" [(ngModel)]="e['numero_serie']" />
                      <button type="button" class="pat-leitor" aria-label="Ler o código do número de série com a câmera" title="Ler código com a câmera" (click)="lendo.set('serie')">
                        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10" /></svg></button>
                    </div></div>
                </div>
              </fieldset>
              <div class="ocupa-duas"><label for="e-descricao">Descrição do material *</label><input id="e-descricao" name="descricao" maxlength="300" autocomplete="off" [(ngModel)]="e['descricao']" required /></div>
              <div class="ocupa-duas"><label id="e-conservacao-rotulo">Estado de conservação *</label>
                <div class="pat-segmentado cinco" role="radiogroup" aria-labelledby="e-conservacao-rotulo">
                  @for (c of conservacoes; track c[0]) {
                    <button type="button" role="radio" [class.ativo]="e['conservacao'] === +c[0]" [attr.aria-checked]="e['conservacao'] === +c[0]" (click)="e['conservacao'] = +c[0]"><b>{{ c[0] }}</b><small>{{ c[1] }}</small></button>
                  }
                </div></div>
              <div><label id="e-situacao-rotulo">Situação *</label>
                <div class="pat-segmentado" role="radiogroup" aria-labelledby="e-situacao-rotulo">
                  <button type="button" role="radio" [disabled]="!situacaoEditavel(b)" [class.ativo]="e['situacao'] === 'ativo'" [attr.aria-checked]="e['situacao'] === 'ativo'" (click)="e['situacao'] = 'ativo'">Ativo</button>
                  <button type="button" role="radio" [disabled]="!situacaoEditavel(b)" [class.ativo]="e['situacao'] === 'em_manutencao'" [attr.aria-checked]="e['situacao'] === 'em_manutencao'" (click)="e['situacao'] = 'em_manutencao'">Manutenção</button>
                </div></div>
              <div><label id="e-origem-rotulo">Origem *</label>
                <div class="pat-segmentado" role="radiogroup" aria-labelledby="e-origem-rotulo">
                  <button type="button" role="radio" [class.ativo]="e['origem'] === 'proprio'" [attr.aria-checked]="e['origem'] === 'proprio'" (click)="e['origem'] = 'proprio'">Próprio</button>
                  <button type="button" role="radio" [class.ativo]="e['origem'] === 'terceiros'" [attr.aria-checked]="e['origem'] === 'terceiros'" (click)="e['origem'] = 'terceiros'">Terceiros</button>
                </div></div>
            </div>
            <details class="pat-mais-dados" open>
              <summary>Mais dados (opcionais)</summary>
              <div class="grade-formulario">
                <div><label for="e-grupo">Grupo de material</label>
                  <select id="e-grupo" name="grupo" [(ngModel)]="e['grupo_id']"><option [ngValue]="null">Sem grupo</option>@for (g of estado.grupos(); track g.id) { <option [value]="g.id">{{ g.nome }}</option> }</select></div>
                <div><label for="e-uge">UGE</label><input id="e-uge" name="uge" maxlength="40" [(ngModel)]="e['uge']" /></div>
                <div><label for="e-ua">UA</label><input id="e-ua" name="ua" maxlength="40" [(ngModel)]="e['ua']" /></div>
                <div><label for="e-divisao">Divisão</label><input id="e-divisao" name="divisao" maxlength="80" [(ngModel)]="e['divisao']" /></div>
                <div><label for="e-aquisicao">Valor de aquisição (R$)</label><input id="e-aquisicao" name="valor_aquisicao" inputmode="decimal" placeholder="0,00" [(ngModel)]="e['valor_aquisicao']" /></div>
                <div><label for="e-atual">Valor atual (R$)</label><input id="e-atual" name="valor_atual" inputmode="decimal" placeholder="0,00" [(ngModel)]="e['valor_atual']" /></div>
                <div><label for="e-data">Data de aquisição</label><input id="e-data" name="data_aquisicao" type="date" [(ngModel)]="e['data_aquisicao']" /></div>
                <div><label for="e-garantia">Meses de garantia</label><input id="e-garantia" name="garantia_meses" type="number" inputmode="numeric" min="0" [(ngModel)]="e['garantia_meses']" /></div>
                <div><label for="e-marca">Marca</label><input id="e-marca" name="marca" maxlength="80" [(ngModel)]="e['marca']" /></div>
                <div><label for="e-modelo">Modelo</label><input id="e-modelo" name="modelo" maxlength="80" [(ngModel)]="e['modelo']" /></div>
                <div><label for="e-nf">Nota fiscal</label><input id="e-nf" name="nota_fiscal" maxlength="60" [(ngModel)]="e['nota_fiscal']" /></div>
                <div class="ocupa-duas"><label for="e-fornecedor">Fornecedor</label><input id="e-fornecedor" name="fornecedor" maxlength="200" [(ngModel)]="e['fornecedor']" /></div>
                <div class="ocupa-duas"><label for="e-obs">Observações</label><textarea id="e-obs" name="observacoes" rows="3" [(ngModel)]="e['observacoes']"></textarea></div>
              </div>
            </details>
            <div class="pat-barra-inferior"><button type="button" class="acao-secundaria" (click)="cancelarEdicao()">Cancelar</button><button type="button" class="acao-primaria" [disabled]="!edicaoValida()" (click)="salvarEdicao(b)">Salvar alterações</button></div>
            @if (lendo(); as campo) {
              <app-leitor-codigo [mensagem]="campo === 'serie' ? 'Aponte a câmera para o código de barras do número de série' : 'Aponte a câmera para o QR code ou código de barras da chapa'"
                                 (lido)="lerCodigo(campo, $event)" (fechar)="lendo.set(null)" />
            }
          } @else {
            <dl class="pat-dados">
              @for (d of dadosVisiveis(b); track d.campo) {
                <div><dt>{{ d.rotulo }}@if (d.campo) { <button type="button" class="pat-historico-campo" [attr.aria-label]="'Histórico de ' + d.rotulo" title="Histórico deste campo" (click)="historicoDoCampo(b, d.campo)">⟲</button> }</dt><dd>{{ d.valor || '—' }}</dd></div>
              }
            </dl>
            @if (dadosSam(b); as linhas) {
              <h3 class="pat-subtitulo">Dados do SAM</h3>
              <dl class="pat-dados">
                @for (d of linhas; track d.rotulo) { <div><dt>{{ d.rotulo }}</dt><dd>{{ d.valor || '—' }}</dd></div> }
              </dl>
            }
            @if (campoAberto(); as c) {
              <div class="pat-painel-acao">
                <strong>Histórico: {{ rotulosCampo[c] ?? c }}</strong>
                @for (ev of historicoCampo(); track ev.id) { <p class="pat-evento-curto">{{ ev.ocorrido_em | date: 'dd/MM/yyyy HH:mm' }} · {{ ev.autor_nome }}: <s>{{ ev.valor_anterior || '—' }}</s> → <b>{{ ev.valor_novo || '—' }}</b></p> }
                @empty { <p class="estado-vazio">Este campo ainda não foi alterado.</p> }
              </div>
            }
          }

          <h3 class="pat-subtitulo">Fotos ({{ b.fotos.length }}/3)</h3>
          <div class="pat-fotos">
            @for (f of b.fotos; track f.id) {
              <figure>
                @if (urlsFotos()[f.id]; as u) { <img loading="lazy" decoding="async" [src]="u" [alt]="'Foto de ' + b.rotulo" /> } @else { <app-esqueleto tipo="formulario" [linhas]="5" /> }
                @if (estado.podeOperar() && b.situacao !== 'baixado') { <button type="button" class="acao-recusar acao-pequena" (click)="removerFoto(b, f.id)">Remover</button> }
              </figure>
            }
            @if (estado.podeOperar() && b.fotos.length < 3 && b.situacao !== 'baixado') {
              <label class="pat-adicionar-foto">+ Foto<input type="file" accept="image/*" capture="environment" hidden (change)="enviarFoto(b, $event)" /></label>
            }
          </div>
        }

        @if (aba() === 'linha') {
          <ol class="pat-linha-tempo">
            @for (ev of eventos(); track ev.id) {
              <li><strong>{{ rotulosEvento[ev.tipo] ?? ev.tipo }}</strong><span>{{ ev.ocorrido_em | date: 'dd/MM/yyyy HH:mm' }} · {{ ev.autor_nome }}{{ ev.origem ? ' · ' + ev.origem : '' }}</span>
                @if (ev.campo) { <p>{{ rotulosCampo[ev.campo] ?? ev.campo }}: <s>{{ ev.valor_anterior || '—' }}</s> → <b>{{ ev.valor_novo || '—' }}</b></p> }
                @if (ev.texto) { <p>{{ ev.texto }}</p> }</li>
            } @empty { <p class="estado-vazio">Nenhum evento.</p> }
          </ol>
        }
        @if (aba() === 'trajeto') {
          <ol class="pat-linha-tempo">
            @for (ev of trajeto(); track ev.id) {
              <li><strong>{{ ev.tipo === 'cadastrou' ? 'Cadastrado em ' + (ev.dados?.['sala'] ?? '') : (ev.dados?.['de'] ?? '') + ' → ' + (ev.dados?.['para'] ?? '') }}</strong>
                <span>{{ ev.ocorrido_em | date: 'dd/MM/yyyy HH:mm' }}</span>
                @if (ev.dados?.['solicitante']) { <p>Pediu: {{ ev.dados?.['solicitante'] }} · Autorizou: {{ ev.dados?.['autorizador'] }}@if (ev.dados?.['recebedor']) { · Recebeu: {{ ev.dados?.['recebedor'] }} }</p> }
                @else if (ev.dados?.['autorizador']) { <p>Autorizou: {{ ev.dados?.['autorizador'] }}</p> }
                @if (ev.texto) { <p>{{ ev.texto }}</p> }</li>
            } @empty { <p class="estado-vazio">Nenhum deslocamento.</p> }
          </ol>
        }
      </section>
    } @else { <app-esqueleto tipo="formulario" [linhas]="5" /> }
  `,
})
export class DetalheBemComponent implements OnInit, OnDestroy {
  private readonly api = inject(PatrimonioApiService);
  private readonly roteador = inject(Router);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(PatrimonioEstadoService);

  readonly bemId = input.required<string>();
  protected readonly bem = signal<Bem | null>(null);
  protected readonly aba = signal<Aba>('dados');
  protected readonly eventos = signal<Evento[]>([]);
  protected readonly trajeto = signal<Evento[]>([]);
  protected readonly editando = signal(false);
  protected readonly ajustando = signal(false);
  protected readonly revertendo = signal(false);
  protected readonly campoAberto = signal<string | null>(null);
  protected readonly historicoCampo = signal<Evento[]>([]);
  protected readonly urlsFotos = signal<Record<string, string>>({});
  protected e: Record<string, unknown> = {};
  /** Chapa em edição: prefixo e número separados (o servidor junta ao salvar). */
  protected prefixo = '';
  protected numero = '';
  /** Campo cuja leitura de código (câmera) está aberta. */
  protected readonly lendo = signal<'chapa' | 'serie' | null>(null);
  protected novaSala = '';
  protected motivoAjuste = '';
  protected justificativa = '';

  protected readonly marcador = classeMarcador;
  protected readonly cores = COR_SITUACAO;
  protected readonly situacoes = ROTULOS_SITUACAO;
  protected readonly rotuloCategoria = rotuloCategoria;
  protected readonly conservacoes = Object.entries(ROTULOS_CONSERVACAO);
  protected readonly rotulosCampo = ROTULOS_CAMPO;
  protected readonly rotulosEvento = ROTULOS_EVENTO;

  ngOnInit(): void {
    void this.estado.carregar();
    this.carregar();
  }

  ngOnDestroy(): void {
    Object.values(this.urlsFotos()).forEach((u) => URL.revokeObjectURL(u));
  }

  private carregar(): void {
    this.api.bem(this.bemId()).subscribe({
      next: (b) => { this.bem.set(b); this.carregarFotos(b); },
      error: (e) => { this.dialogos.mostrarErro(e, 'Não foi possível carregar o bem'); void this.roteador.navigate(['/patrimonio']); },
    });
  }

  private carregarFotos(b: Bem): void {
    const atuais = this.urlsFotos();
    for (const f of b.fotos) {
      if (atuais[f.id]) continue;
      this.api.fotoBlob(b.id, f.id).subscribe((blob) => this.urlsFotos.update((m) => ({ ...m, [f.id]: URL.createObjectURL(blob) })));
    }
  }

  protected abrirAba(aba: Aba): void {
    this.aba.set(aba);
    if (aba === 'linha') this.api.historico(this.bemId()).subscribe((x) => this.eventos.set(x));
    if (aba === 'trajeto') this.api.trajeto(this.bemId()).subscribe((x) => this.trajeto.set(x));
  }

  protected historicoDoCampo(b: Bem, campo: string): void {
    if (this.campoAberto() === campo) { this.campoAberto.set(null); return; }
    this.campoAberto.set(campo);
    this.api.historico(b.id, campo).subscribe((x) => this.historicoCampo.set(x));
  }

  /** Linhas da aba Dados; `campo` liga o ícone de histórico daquele campo. */
  protected dadosVisiveis(b: Bem): { rotulo: string; valor: string; campo?: string }[] {
    const real = (v: string | null) => (v === null ? '' : Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }));
    const data = (v: string | null) => (v ? new Date(v + 'T00:00:00').toLocaleDateString('pt-BR') : '');
    return [
      { rotulo: 'Chapa', valor: b.chapa ?? 'Sem patrimônio', campo: 'chapa' }, { rotulo: 'Descrição', valor: b.descricao, campo: 'descricao' },
      { rotulo: 'Sala', valor: b.sala_rotulo, campo: 'localizacao' }, { rotulo: 'Responsável', valor: b.responsavel_nome ?? '', campo: 'responsavel' },
      { rotulo: 'Conservação', valor: `${b.conservacao} · ${ROTULOS_CONSERVACAO[b.conservacao]}`, campo: 'conservacao' }, { rotulo: 'Situação', valor: ROTULOS_SITUACAO[b.situacao], campo: 'situacao' },
      { rotulo: 'Origem', valor: b.origem === 'proprio' ? 'Próprio' : 'De terceiros', campo: 'origem' }, { rotulo: 'Grupo de material', valor: b.grupo_nome ?? '', campo: 'grupo_id' },
      { rotulo: 'UGE', valor: b.uge ?? '', campo: 'uge' }, { rotulo: 'UA', valor: b.ua ?? '', campo: 'ua' }, { rotulo: 'Divisão', valor: b.divisao ?? '', campo: 'divisao' },
      { rotulo: 'Valor de aquisição', valor: real(b.valor_aquisicao), campo: 'valor_aquisicao' }, { rotulo: 'Valor atual', valor: real(b.valor_atual), campo: 'valor_atual' },
      { rotulo: 'Valor considerado nos painéis', valor: real(b.valor_efetivo) },
      { rotulo: 'Data de aquisição', valor: data(b.data_aquisicao), campo: 'data_aquisicao' }, { rotulo: 'Meses de garantia', valor: b.garantia_meses === null ? '' : String(b.garantia_meses), campo: 'garantia_meses' },
      { rotulo: 'Fim da garantia', valor: b.garantia_fim ? data(b.garantia_fim) : 'Indefinida' }, { rotulo: 'Garantia', valor: ROTULOS_GARANTIA[b.situacao_garantia] },
      { rotulo: 'Marca', valor: b.marca ?? '', campo: 'marca' }, { rotulo: 'Modelo', valor: b.modelo ?? '', campo: 'modelo' }, { rotulo: 'Número de série', valor: b.numero_serie ?? '', campo: 'numero_serie' },
      { rotulo: 'Nota fiscal', valor: b.nota_fiscal ?? '', campo: 'nota_fiscal' }, { rotulo: 'Fornecedor', valor: b.fornecedor ?? '', campo: 'fornecedor' }, { rotulo: 'Observações', valor: b.observacoes ?? '', campo: 'observacoes' },
    ];
  }

  /** Linhas da seção "Dados do SAM" (só leitura, vêm da importação da Visão Geral); `null` quando o bem não tem nenhum dado do SAM. */
  protected dadosSam(b: Bem): { rotulo: string; valor: string }[] | null {
    const s = b.sam;
    if (!s) return null;
    const real = (v: string | null) => (v === null ? '' : Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }));
    const data = (v: string | null) => (v ? new Date(v + 'T00:00:00').toLocaleDateString('pt-BR') : '');
    const ref = (v: string | null) => (v ? `${v.slice(4, 6)}/${v.slice(0, 4)}` : '');
    return [
      { rotulo: 'Código do item', valor: s.item_codigo ?? '' }, { rotulo: 'Estado no SAM', valor: s.estado_sam ?? '' }, { rotulo: 'Responsável no SAM', valor: s.responsavel_sam ?? '' },
      { rotulo: 'UO', valor: s.uo ?? '' }, { rotulo: 'Destino UGE', valor: s.destino_uge ?? '' },
      { rotulo: 'Conta contábil', valor: s.conta_contabil ?? '' }, { rotulo: 'Conta de depreciação', valor: s.conta_depreciacao ?? '' },
      { rotulo: 'Depreciação acumulada', valor: real(s.depreciacao_acumulada) }, { rotulo: 'Depreciação mensal', valor: real(s.depreciacao_mensal) },
      { rotulo: 'Vida útil', valor: s.vida_util_meses === null ? '' : `${s.meses_depreciados ?? 0} de ${s.vida_util_meses} meses depreciados` },
      { rotulo: 'Última depreciação', valor: ref(s.ultima_depreciacao_ref) }, { rotulo: 'Data de incorporação', valor: data(s.data_incorporacao) },
      { rotulo: 'Empenho', valor: s.empenho ?? '' }, { rotulo: 'Número do documento', valor: s.numero_documento ?? '' },
      { rotulo: 'Último histórico', valor: s.ultimo_historico ? `${s.ultimo_historico}${s.data_ultimo_historico ? ' · ' + data(s.data_ultimo_historico) : ''}` : '' },
    ];
  }

  protected editar(b: Bem): void {
    this.e = {};
    for (const c of CAMPOS_EDITAVEIS) if (c !== 'chapa') this.e[c] = (b as unknown as Record<string, unknown>)[c] ?? null;
    // A chapa vira prefixo + número; chapa antiga, sem prefixo conhecido, fica inteira no número e "Sem prefixo"
    const partes = b.chapa ? separarChapa(b.chapa, this.estado.prefixos()) : null;
    this.prefixo = partes?.prefixo ?? '';
    this.numero = partes ? partes.numero : (b.chapa ?? '');
    this.editando.set(true);
  }

  protected cancelarEdicao(): void {
    this.editando.set(false);
    this.lendo.set(null);
  }

  /** A chapa como o servidor vai gravar (prefixo + número com 6 dígitos). */
  protected chapaFinal(): string {
    return montarChapa(this.prefixo, this.numero);
  }

  /** Inservível e extraviado só mudam de situação pela reversão; os demais alternam entre Ativo e Em manutenção. */
  protected situacaoEditavel(b: Bem): boolean {
    return b.situacao === 'ativo' || b.situacao === 'em_manutencao';
  }

  /** Descrição obrigatória e, como no cadastro, chapa ou número de série. */
  protected edicaoValida(): boolean {
    return !!String(this.e['descricao'] ?? '').trim() && !!(this.numero.trim() || String(this.e['numero_serie'] ?? '').trim());
  }

  /** Código lido pela câmera: vai para a chapa (separando o prefixo, se vier junto) ou para o número de série. */
  protected lerCodigo(campo: 'chapa' | 'serie', codigo: string): void {
    const valor = codigo.trim();
    if (campo === 'serie') { this.e['numero_serie'] = valor; return; }
    const partes = separarChapa(valor, this.estado.prefixos());
    if (partes) { this.prefixo = partes.prefixo; this.numero = partes.numero; } else this.numero = valor;
  }

  protected salvarEdicao(b: Bem): void {
    const alteracoes: Record<string, unknown> = {};
    const atual = b as unknown as Record<string, unknown>;
    for (const c of CAMPOS_EDITAVEIS) {
      if (c === 'chapa') continue;
      let novo = this.e[c];
      if (typeof novo === 'string') novo = novo.trim() === '' ? null : novo.trim().replace(/^(\d+),(\d+)$/, '$1.$2');
      if (c === 'garantia_meses' && novo !== null) novo = Number(novo);
      if (c === 'situacao' && (b.situacao === 'inservivel' || b.situacao === 'extraviado')) continue;
      if (novo !== (atual[c] ?? null) && String(novo ?? '') !== String(atual[c] ?? '')) alteracoes[c] = novo;
    }
    // Chapa: só vai se mudou; o servidor junta o prefixo ao número (e completa com zeros)
    if (this.chapaFinal() !== (b.chapa ?? '')) {
      alteracoes['chapa'] = this.numero.trim() || null;
      if (this.numero.trim() && this.prefixo) alteracoes['prefixo'] = this.prefixo;
    }
    if (!Object.keys(alteracoes).length) { this.editando.set(false); return; }
    this.api.alterarBem(b.id, alteracoes as Partial<DadosBem>).subscribe({
      next: (n) => { this.bem.set(n); this.editando.set(false); this.lendo.set(null); this.campoAberto.set(null); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar'),
    });
  }

  protected ajustarLocal(b: Bem): void {
    this.api.ajustarLocal(b.id, this.novaSala, this.motivoAjuste.trim()).subscribe({
      next: (n) => { this.bem.set(n); this.ajustando.set(false); this.novaSala = ''; this.motivoAjuste = ''; void this.estado.carregar(true); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível ajustar o local'),
    });
  }

  protected reverter(b: Bem): void {
    this.api.reverter(b.id, this.justificativa.trim(), b.situacao === 'extraviado' ? this.novaSala : undefined).subscribe({
      next: (n) => { this.bem.set(n); this.revertendo.set(false); this.justificativa = ''; this.novaSala = ''; },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível devolver o bem a Ativo'),
    });
  }

  /** A foto do celular pode ter vários MB: reduz para até 1.280 px e JPEG antes de enviar. */
  protected async enviarFoto(b: Bem, evento: Event): Promise<void> {
    const arquivo = (evento.target as HTMLInputElement).files?.[0];
    (evento.target as HTMLInputElement).value = '';
    if (!arquivo) return;
    const reduzida = await this.reduzir(arquivo);
    this.api.adicionarFoto(b.id, reduzida, 'foto.jpg').subscribe({
      next: (n) => { this.bem.set(n); this.carregarFotos(n); },
      error: (e) => { this.dialogos.mostrarErro(e, 'Não foi possível enviar a foto'); },
    });
  }

  private async reduzir(arquivo: File): Promise<Blob> {
    try {
      const imagem = await createImageBitmap(arquivo);
      const escala = Math.min(1, 1280 / Math.max(imagem.width, imagem.height));
      const tela = document.createElement('canvas');
      tela.width = Math.round(imagem.width * escala);
      tela.height = Math.round(imagem.height * escala);
      tela.getContext('2d')?.drawImage(imagem, 0, 0, tela.width, tela.height);
      return await new Promise<Blob>((resolver) => tela.toBlob((x) => resolver(x ?? arquivo), 'image/jpeg', 0.82));
    } catch {
      return arquivo;
    }
  }

  protected removerFoto(b: Bem, fotoId: string): void {
    this.api.removerFoto(b.id, fotoId).subscribe({ next: (n) => this.bem.set(n), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível remover a foto') });
  }
}
