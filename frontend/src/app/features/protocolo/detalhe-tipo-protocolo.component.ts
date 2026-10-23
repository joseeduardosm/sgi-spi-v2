// Criado por José Eduardo Santana Martins
// Este arquivo serve para a página de detalhe de um tipo de documento do Protocolo: renomear, faixa do exercício, "liberar a partir de" e exclusão.

import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoProtocoloComponent } from './cabecalho-protocolo.component';
import { ProtocoloApiService } from './protocolo-api.service';
import { SequenciaProtocolo, TipoProtocolo } from './protocolo.models';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
/**
 * `/protocolo/administracao/tipos/:tipoId?sequencia=<id>`: o clique no cartão da administração abre esta página (só CONTROLE_TOTAL).
 * Sem `sequencia`, mostra o primeiro exercício do tipo (ou só as ações do tipo, se ele ainda não tem nenhum).
 */
@Component({
  selector: 'app-detalhe-tipo-protocolo',
  imports: [EsqueletoComponent, FormsModule, RouterLink, CabecalhoProtocoloComponent],
  template: `
    <app-cabecalho-protocolo [titulo]="tipo()?.nome ?? 'Tipo de documento'" descricao="Faixa de números do exercício, ponto de liberação para todos e ações do tipo." />
    @if (tipo(); as t) {
      <section class="painel-gestao pagina-tipo-protocolo">
        <div class="cartao-dados">
          @if (t.sequencias.length > 1) {
            <nav class="exercicios-tipo" aria-label="Exercícios do tipo">
              @for (x of t.sequencias; track x.id) {
                <a class="acao-secundaria acao-pequena" [class.ativo]="x.id === sequencia()?.id" [routerLink]="[]" [queryParams]="{ sequencia: x.id }">{{ x.exercicio }}</a>
              }
            </nav>
          }
          @if (sequencia(); as s) {
            <h2>Exercício {{ s.exercicio }}</h2>
            <div class="grade-formulario">
              <div><label for="dt-inicio">Início da faixa</label><input id="dt-inicio" name="inicio" type="number" min="0" [(ngModel)]="inicio" /></div>
              <div><label for="dt-fim">Fim da faixa</label><input id="dt-fim" name="fim" type="number" min="0" [(ngModel)]="fim" /></div>
              <div class="ocupa-duas"><label for="dt-liberar">Liberar a partir de</label><input id="dt-liberar" name="liberar" type="number" min="0" placeholder="—" [(ngModel)]="liberar" />
                <small class="dica">Atual: {{ s.inicio }} a {{ s.fim }}@if (s.liberar_a_partir_de) { · <b>Reservado CGI</b>: {{ s.inicio }} a {{ s.liberar_a_partir_de - 1 }} }. Diminuir o início ou aumentar o fim <b>amplia</b> a faixa.</small></div>
            </div>
            <div class="acoes-formulario"><button type="button" class="acao-recusar" (click)="excluirExercicio(s)">Excluir exercício {{ s.exercicio }}</button><button type="button" class="acao-primaria" [disabled]="!mudou()" (click)="salvarFaixa(s)">Salvar faixa</button></div>
          } @else { <p class="estado-vazio">Este tipo ainda não tem sequência.</p> }
        </div>
        <footer class="acoes-formulario rodape-detalhe">
          <a class="acao-secundaria" routerLink="/protocolo/administracao">Voltar</a>
          <button type="button" class="acao-recusar" (click)="excluir(t)">Excluir tipo</button>
          <button type="button" class="acao-secundaria" (click)="renomear(t)">Renomear</button>
          <a class="acao-secundaria" [routerLink]="['/protocolo/administracao/tipos', t.id, 'exercicio']">+ Novo exercício</a>
        </footer>
      </section>
    } @else { <app-esqueleto tipo="formulario" [linhas]="5" /> }
  `,
  styles: `
    .pagina-tipo-protocolo { max-width: 860px; }
    .cartao-dados { padding: 18px 20px; }
    .cartao-dados h2 { margin: 0 0 14px; font-size: 18px; }
    .exercicios-tipo { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
    .dica { display: block; margin-top: 4px; color: var(--spi-apagado); }
    .cartao-dados > .acoes-formulario { margin-top: 14px; }
    footer.rodape-detalhe { padding: 16px 20px; }
  `,
})
export class DetalheTipoProtocoloComponent implements OnInit {
  private readonly api = inject(ProtocoloApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);

  /** Parâmetros da rota (`:tipoId`) e da consulta (`?sequencia=`), ligados por `withComponentInputBinding`. */
  readonly tipoId = input.required<string>();
  readonly sequenciaId = input<string | undefined>(undefined, { alias: 'sequencia' });

  protected readonly tipo = signal<TipoProtocolo | null>(null);
  protected readonly sequencia = computed<SequenciaProtocolo | null>(() => {
    const t = this.tipo();
    return t?.sequencias.find((s) => s.id === this.sequenciaId()) ?? t?.sequencias[0] ?? null;
  });
  protected inicio = 0;
  protected fim = 0;
  protected liberar: number | null = null;

  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    this.api.tipos().subscribe({
      next: (r) => {
        const t = r.itens.find((x) => x.id === this.tipoId());
        if (!t) { void this.roteador.navigate(['/protocolo/administracao']); return; }
        this.tipo.set(t);
        this.preencher();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o tipo'),
    });
  }

  private preencher(): void {
    const s = this.sequencia();
    if (s) { this.inicio = s.inicio; this.fim = s.fim; this.liberar = s.liberar_a_partir_de; }
  }

  protected mudou(): boolean {
    const s = this.sequencia();
    return !!s && (this.inicio !== s.inicio || this.fim !== s.fim || (this.liberar || null) !== s.liberar_a_partir_de);
  }

  protected salvarFaixa(s: SequenciaProtocolo): void {
    this.api.alterarFaixa(s.id, { inicio: this.inicio, fim: this.fim, liberar_a_partir_de: this.liberar || null }).subscribe({
      next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível alterar a faixa'),
    });
  }

  protected async excluirExercicio(s: SequenciaProtocolo): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Excluir o exercício ${s.exercicio}?`, mensagem: `A faixa ${s.inicio} a ${s.fim} e os seus números serão apagados. Só é possível se nenhum número foi reservado, utilizado ou anulado.`,
      rotuloConfirmar: 'Excluir', segundos: 3,
    });
    if (!ok) return;
    this.api.excluirSequencia(s.id).subscribe({
      // Sem outro exercício a mostrar, a consulta volta ao primeiro que restar
      next: () => { void this.roteador.navigate([], { queryParams: { sequencia: null }, queryParamsHandling: 'merge' }); this.carregar(); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir o exercício'),
    });
  }

  protected renomear(t: TipoProtocolo): void {
    const nome = window.prompt('Novo nome do tipo de documento:', t.nome)?.trim();
    if (!nome || nome === t.nome) return;
    this.api.renomearTipo(t.id, nome).subscribe({ next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível renomear') });
  }

  protected async excluir(t: TipoProtocolo): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Excluir este tipo?', mensagem: `"${t.nome}" e as suas sequências serão apagados. Só é possível se nenhum número foi reservado, utilizado ou anulado.`,
      rotuloConfirmar: 'Excluir', segundos: 3,
    });
    if (ok) this.api.excluirTipo(t.id).subscribe({ next: () => void this.roteador.navigate(['/protocolo/administracao']), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir') });
  }
}
