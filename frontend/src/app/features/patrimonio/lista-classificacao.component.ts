// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar, justificar, enviar e aprovar uma lista de inservíveis ou extraviados.
import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { classeMarcador } from '../tarefas/marcadores.paleta';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { FilaOfflineService } from './fila-offline.service';
import { LeitorCodigoComponent } from './leitor-codigo.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { BuscaBemComponent } from './busca-bem.component';
import { Bem, Classificacao, COR_STATUS, ROTULOS_STATUS } from './patrimonio.models';
import { RelacionarSalaComponent } from './relacionar-sala.component';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
/** `/patrimonio/inserviveis/:classificacaoId` ou `/patrimonio/extraviados/:classificacaoId` (conforme o tipo da lista). */
@Component({
  selector: 'app-lista-classificacao',
  imports: [EsqueletoComponent, FormsModule, RouterLink, CabecalhoPatrimonioComponent, LeitorCodigoComponent, RelacionarSalaComponent, BuscaBemComponent],
  template: `
    <app-cabecalho-patrimonio [titulo]="lista() ? (lista()!.tipo === 'inservivel' ? 'Lista de inservíveis' : 'Lista de extraviados') : 'Lista'" descricao="Só entram bens cadastrados e Ativos ou Em manutenção." />
    @if (lista(); as c) {
      <section class="painel-gestao patrimonio">
        <div class="pat-topo-bem">
          <span class="pat-marcadores"><b class="texto-codigo">#{{ c.numero }}</b><span [class]="marcador(cores[c.status])">{{ rotulos[c.status] }}</span><span [class]="marcador(0)">{{ c.solicitante_nome }}</span></span>
          <div class="pat-acoes">
            <button type="button" class="acao-secundaria" (click)="relatorio(c, 'pdf')" title="PDF consolidado: índice, relatório, fotos e anexos">Relatório PDF</button>
            <button type="button" class="acao-secundaria" (click)="relatorio(c, 'xlsx')">Relatório Excel</button>
            @if (rascunho()) { <button type="button" class="acao-recusar" (click)="descartar()">Descartar rascunho</button> }
          </div>
        </div>

        @if (rascunho()) {
          <div class="pat-linha-campo">
            <app-busca-bem [(texto)]="chapa" nome="chapa" [placeholder]="c.tipo === 'inservivel' ? 'Digite parte da chapa ou do nº de série' : 'Digite parte da chapa ou do nº de série do bem extraviado'" (escolhido)="incluirBem($event)" (enviar)="incluir($event)" />
            <button type="button" class="acao-secundaria" (click)="incluir(chapa)">Adicionar</button>
            <button type="button" class="acao-primaria" (click)="lendo.set(true)">Ler códigos</button>
          </div>
          <app-relacionar-sala modo="classificacao" (confirmado)="incluirVarios($event)" />
          @for (l of locais(); track l) { <p class="pat-aviso">Chapa {{ l }}: aguardando envio (sem conexão).</p> }
          @if (aviso()) { <p class="pat-aviso" role="alert">{{ aviso() }}</p> }
        }

        <ul class="pat-lista-itens">
          @for (i of c.itens; track i.id) {
            <li>
              @if (rascunho()) { <input type="checkbox" class="pat-selecao" [name]="'m' + i.id" [checked]="marcados().has(i.id)" (change)="alternar(i.id)" [attr.aria-label]="'Marcar ' + i.rotulo" /> }
              @else if (decidindo()) { <input type="checkbox" class="pat-selecao" [name]="'a' + i.id" [checked]="aprovados().has(i.id)" (change)="alternarAprovado(i.id)" [attr.aria-label]="'Aprovar ' + i.rotulo" /> }
              <div><strong class="texto-codigo">{{ i.rotulo }}</strong> <span>{{ i.descricao }}</span>@if (i.chapa && i.numero_serie) { <small>Série {{ i.numero_serie }}</small> }<small>{{ i.sala_rotulo }}</small>
                @if (i.justificativa) { <small class="pat-justificativa">“{{ i.justificativa }}”</small> }
                @if (i.anexo_nome) { <small><a href="javascript:void(0)" (click)="$event.preventDefault(); baixarAnexo(c.id, i.id)">{{ i.anexo_nome }}</a></small> }</div>
              <span class="pat-acoes">
                @if (i.resultado) { <span [class]="marcador(i.resultado === 'aprovado' ? 10 : 1)">{{ i.resultado === 'aprovado' ? 'Aprovado' : 'Recusado' }}</span> }
                @if (rascunho()) {
                  <label class="acao-secundaria acao-pequena pat-anexar">{{ c.tipo === 'inservivel' ? 'Foto' : 'Anexo' }}<input type="file" hidden [accept]="c.tipo === 'inservivel' ? 'image/*' : ''" (change)="anexar(c, i.id, $event)" /></label>
                  <button type="button" class="acao-recusar acao-pequena" (click)="tirar(c.id, i.id)">Tirar</button>
                }
              </span>
            </li>
          } @empty { <li class="estado-vazio">Nenhum bem na lista.</li> }
        </ul>

        @if (rascunho() && c.itens.length) {
          <div class="pat-painel-acao">
            <strong>Justificativa</strong>
            <small>Marque um ou vários bens e escreva a justificativa (mínimo de 10 caracteres): ela vale para todos os marcados.</small>
            <textarea name="justificativa" rows="3" placeholder="Ex.: baterias sem carga, conserto inviável" [(ngModel)]="justificativa"></textarea>
            <div class="pat-acoes">
              <button type="button" class="acao-secundaria" (click)="marcarTodos(c)">Marcar todos</button>
              <button type="button" class="acao-primaria" [disabled]="!marcados().size || justificativa.trim().length < 10" (click)="justificar(c)">Justificar {{ marcados().size }} marcado(s)</button>
            </div>
          </div>
          <div class="pat-barra-inferior">
            <button type="button" class="acao-primaria" [disabled]="semJustificar(c) > 0" (click)="enviar(c)">Enviar para aprovação</button>
          </div>
        }

        @if (decidindo()) {
          <div class="pat-painel-acao">
            <strong>Decisão</strong>
            <small>Os itens marcados serão aprovados; os demais, recusados. A recusa exige motivo.</small>
            <textarea name="motivo-recusa" rows="2" placeholder="Motivo da recusa (obrigatório ao recusar)" [(ngModel)]="motivoRecusa"></textarea>
            <div class="pat-acoes">
              <button type="button" class="acao-recusar" [disabled]="!motivoRecusa.trim()" (click)="recusarTudo(c)">Recusar tudo</button>
              <button type="button" class="acao-positiva" [disabled]="!aprovados().size || (aprovados().size < c.itens.length && !motivoRecusa.trim())" (click)="decidir(c)">
                {{ aprovados().size < c.itens.length ? 'Aprovar os ' + aprovados().size + ' marcado(s) e recusar os demais' : 'Aprovar tudo' }}</button>
            </div>
          </div>
        }
        @if (c.status === 'pendente' && estado.podeAdministrar() && souSolicitante(c)) { <p class="pat-aviso">Quem montou a lista não pode aprová-la: outra pessoa com controle total precisa decidir.</p> }
        @if (c.motivo_recusa) { <p class="pat-aviso">Motivo da recusa: {{ c.motivo_recusa }}</p> }
        <div class="pat-barra-inferior"><a class="acao-secundaria" [routerLink]="base()">Voltar</a></div>
      </section>
      @if (lendo()) { <app-leitor-codigo [continuo]="true" (lido)="incluir($event)" (fechar)="lendo.set(false)" /> }
    } @else { <app-esqueleto tipo="lista" [linhas]="4" /> }
  `,
})
export class ListaClassificacaoComponent implements OnInit {
  private readonly api = inject(PatrimonioApiService);
  private readonly fila = inject(FilaOfflineService);
  private readonly roteador = inject(Router);
  private readonly rota = inject(ActivatedRoute);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(PatrimonioEstadoService);

  readonly classificacaoId = input.required<string>();
  protected readonly lista = signal<Classificacao | null>(null);
  /** Tela de origem da lista: extraviados ou inservíveis (pelo tipo da lista; antes de carregar, pela rota). */
  protected readonly base = computed(() => ((this.lista()?.tipo ?? this.rota.snapshot.data['tipo']) === 'extraviado' ? '/patrimonio/extraviados' : '/patrimonio/inserviveis'));
  protected readonly lendo = signal(false);
  protected readonly aviso = signal('');
  protected readonly marcados = signal<Set<string>>(new Set());
  protected readonly aprovados = signal<Set<string>>(new Set());
  protected readonly locais = signal<string[]>([]);
  protected readonly rascunho = computed(() => this.lista()?.status === 'rascunho' && this.lista()?.solicitante_id === this.estado.acesso()?.usuario_id);
  protected readonly decidindo = computed(() => this.lista()?.status === 'pendente' && this.estado.podeAdministrar() && !this.souSolicitante(this.lista()!));
  protected chapa = '';
  protected justificativa = '';
  protected motivoRecusa = '';
  protected readonly marcador = classeMarcador;
  protected readonly cores = COR_STATUS;
  protected readonly rotulos = ROTULOS_STATUS;

  ngOnInit(): void {
    void this.estado.carregar();
    this.carregar();
  }

  private carregar(): void {
    this.api.classificacao(this.classificacaoId()).subscribe({
      next: (c) => { this.definir(c); this.aprovados.set(new Set(c.itens.map((i) => i.id))); },
      error: (e) => { this.dialogos.mostrarErro(e, 'Não foi possível carregar a lista'); void this.roteador.navigate([this.base()]); },
    });
  }

  private definir(c: Classificacao): void {
    this.lista.set(c);
    // Link antigo (/inserviveis/id) de uma lista de extraviados (ou o contrário): vai para a tela certa sem empilhar histórico
    if (this.rota.snapshot.data['tipo'] && this.rota.snapshot.data['tipo'] !== c.tipo) void this.roteador.navigate([this.base(), c.id], { replaceUrl: true });
    this.aviso.set('');
  }

  protected souSolicitante(c: Classificacao): boolean {
    return c.solicitante_id === this.estado.acesso()?.usuario_id;
  }

  protected semJustificar(c: Classificacao): number {
    return c.itens.filter((i) => !i.justificativa).length;
  }

  /** Inclui a chapa lida ou digitada. Recusas (bem inativo, já pendente…) viram aviso sem interromper a leitura; sem sinal, a chapa fica na fila do aparelho. */
  protected incluir(chapa: string): void {
    const c = chapa.trim();
    this.chapa = '';
    if (!c) return;
    const guardar = () => { void this.fila.enfileirar({ tipo: 'incluir_classificacao', corpo: { lista: { id: this.classificacaoId() }, chapa: c } }, `Chapa ${c} na lista de ${this.lista()?.tipo}`); this.locais.update((l) => [...l, c]); };
    if (!this.fila.online()) { guardar(); return; }
    this.api.incluirNaClassificacao(this.classificacaoId(), { chapa: c }).subscribe({
      next: (x) => this.definir(x),
      error: (e) => (e?.status === 0 ? guardar() : this.aviso.set(e?.error?.detalhe ?? `Não foi possível incluir ${c}.`)),
    });
  }

  protected relatorio(c: Classificacao, formato: 'pdf' | 'xlsx'): void {
    this.dialogos.executar(this.api.relatorioClassificacao(c.id, formato, c.tipo === 'extraviado' ? 'extraviados' : 'inserviveis'), 'Gerando o relatório…')
      .subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar o relatório') });
  }

  protected incluirBem(b: Bem): void {
    this.api.incluirNaClassificacao(this.classificacaoId(), { bem_id: b.id }).subscribe({ next: (x) => this.definir(x), error: (e) => this.aviso.set(e?.error?.detalhe ?? `Não foi possível incluir ${b.chapa}.`) });
  }

  /** Inclui os bens de uma sala, um a um; os que a API recusar (já em outra lista etc.) viram um aviso único. */
  protected async incluirVarios(bens: Bem[]): Promise<void> {
    let recusados = 0;
    for (const b of bens) {
      try { this.definir(await firstValueFrom(this.api.incluirNaClassificacao(this.classificacaoId(), { bem_id: b.id }))); } catch { recusados++; }
    }
    this.aviso.set(recusados ? `${bens.length - recusados} de ${bens.length} bem(ns) incluídos; ${recusados} não puderam entrar (já em outra lista ou situação inválida).` : '');
  }

  protected tirar(id: string, itemId: string): void {
    this.api.tirarDaClassificacao(id, itemId).subscribe({ next: (x) => this.definir(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível tirar o bem') });
  }

  protected alternar(id: string): void {
    this.marcados.update((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  protected alternarAprovado(id: string): void {
    this.aprovados.update((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  protected marcarTodos(c: Classificacao): void {
    this.marcados.set(new Set(c.itens.map((i) => i.id)));
  }

  protected justificar(c: Classificacao): void {
    this.api.justificar(c.id, [...this.marcados()], this.justificativa.trim()).subscribe({
      next: (x) => { this.definir(x); this.marcados.set(new Set()); this.justificativa = ''; }, error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível justificar'),
    });
  }

  protected anexar(c: Classificacao, itemId: string, evento: Event): void {
    const arquivo = (evento.target as HTMLInputElement).files?.[0];
    (evento.target as HTMLInputElement).value = '';
    if (arquivo) this.api.anexarNaClassificacao(c.id, itemId, arquivo).subscribe({ next: (x) => this.definir(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível anexar') });
  }

  protected baixarAnexo(id: string, itemId: string): void {
    this.api.baixarAnexoClassificacao(id, itemId).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar o anexo') });
  }

  protected enviar(c: Classificacao): void {
    this.api.enviarClassificacao(c.id).subscribe({ next: (x) => this.definir(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível enviar') });
  }

  protected async descartar(): Promise<void> {
    if (!(await this.dialogos.confirmar({ titulo: 'Descartar o rascunho?', mensagem: 'A lista e as justificativas serão apagadas.', rotuloConfirmar: 'Descartar', segundos: 2 }))) return;
    this.api.descartarClassificacao(this.classificacaoId()).subscribe({ next: () => void this.roteador.navigate([this.base()]), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível descartar') });
  }

  /** Recusa a lista inteira (nenhum item aprovado), com o motivo informado. */
  protected recusarTudo(c: Classificacao): void {
    this.api.decidirClassificacao(c.id, [], this.motivoRecusa.trim()).subscribe({ next: (x) => this.definir(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível recusar') });
  }

  protected decidir(c: Classificacao): void {
    this.api.decidirClassificacao(c.id, [...this.aprovados()], this.motivoRecusa.trim() || undefined).subscribe({ next: (x) => this.definir(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível decidir') });
  }
}
