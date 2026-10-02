// Criado por José Eduardo Santana Martins
// Este arquivo serve para a administração do Protocolo: tipos de documento, sequências por exercício e ampliação de faixa.

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoProtocoloComponent } from './cabecalho-protocolo.component';
import { ProtocoloApiService } from './protocolo-api.service';
import { SequenciaProtocolo, TipoProtocolo } from './protocolo.models';

/** Só CONTROLE_TOTAL (a API confere em cada chamada). */
@Component({
  selector: 'app-administracao-protocolo',
  imports: [FormsModule, CabecalhoProtocoloComponent],
  template: `
    <app-cabecalho-protocolo titulo="Administração do Protocolo" descricao="Tipos de documento, sequências por exercício e ampliação das faixas." />
    <section class="painel-gestao protocolo">
      <form class="barra-protocolo" (ngSubmit)="criarTipo()">
        <div class="campo"><label for="ad-nome">Novo tipo de documento</label><input id="ad-nome" name="nome" maxlength="200" placeholder="Ex.: Ofício" [(ngModel)]="novoTipo" /></div>
        <button type="submit" class="acao-primaria" [disabled]="!novoTipo.trim()">Adicionar tipo</button>
      </form>

      @for (t of tipos(); track t.id) {
        <article class="cartao-dados tipo-protocolo">
          <header>
            <div><h2>{{ t.nome }}</h2><small>{{ t.sequencias.length }} exercício(s) cadastrado(s)</small></div>
            <div class="acoes-formulario">
              <button type="button" class="acao-secundaria acao-pequena" (click)="renomear(t)">Renomear</button>
              <button type="button" class="acao-recusar acao-pequena" (click)="excluir(t)">Excluir</button>
            </div>
          </header>
          <div class="corpo">
            @for (s of t.sequencias; track s.id) {
              <div class="linha-sequencia">
                <strong>{{ s.exercicio }}</strong>
                <span class="faixa">de <input type="number" min="0" [(ngModel)]="faixas[s.id].inicio" [name]="'i' + s.id" aria-label="Início da faixa" />
                  até <input type="number" min="0" [(ngModel)]="faixas[s.id].fim" [name]="'f' + s.id" aria-label="Fim da faixa" /></span>
                <small>Atual: {{ s.inicio }} a {{ s.fim }}. Diminuir o início ou aumentar o fim <b>amplia</b> a faixa.</small>
                <button type="button" class="acao-secundaria acao-pequena" [disabled]="!mudou(s)" (click)="alterarFaixa(s)">Salvar faixa</button>
              </div>
            } @empty { <p class="estado-vazio">Nenhuma sequência ainda.</p> }
            <form class="linha-sequencia nova" (ngSubmit)="criarSequencia(t)">
              <strong>Novo exercício</strong>
              <span class="faixa"><input type="number" min="2000" max="2200" [(ngModel)]="novas[t.id].exercicio" [name]="'e' + t.id" aria-label="Exercício" />
                de <input type="number" min="0" [(ngModel)]="novas[t.id].inicio" [name]="'a' + t.id" aria-label="Primeiro número" />
                até <input type="number" min="0" [(ngModel)]="novas[t.id].fim" [name]="'b' + t.id" aria-label="Último número" /></span>
              <button type="submit" class="acao-secundaria acao-pequena">Criar sequência</button>
            </form>
          </div>
        </article>
      } @empty { <p class="estado-vazio">Nenhum tipo cadastrado.</p> }
    </section>
  `,
})
export class AdministracaoProtocoloComponent implements OnInit {
  private readonly api = inject(ProtocoloApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly tipos = signal<TipoProtocolo[]>([]);
  protected novoTipo = '';
  protected faixas: Record<string, { inicio: number; fim: number }> = {};
  protected novas: Record<string, { exercicio: number; inicio: number; fim: number }> = {};

  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    this.api.tipos().subscribe({
      next: (r) => {
        this.tipos.set(r.itens);
        for (const t of r.itens) {
          this.novas[t.id] ??= { exercicio: new Date().getFullYear() + 1, inicio: 1, fim: 100 };
          for (const s of t.sequencias) this.faixas[s.id] = { inicio: s.inicio, fim: s.fim };
        }
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a administração'),
    });
  }

  private erro(titulo: string) {
    return (e: unknown) => this.dialogos.mostrarErro(e, titulo);
  }

  protected criarTipo(): void {
    this.api.criarTipo(this.novoTipo.trim()).subscribe({ next: () => { this.novoTipo = ''; this.carregar(); }, error: this.erro('Não foi possível criar o tipo') });
  }

  protected renomear(t: TipoProtocolo): void {
    const nome = window.prompt('Novo nome do tipo de documento:', t.nome)?.trim();
    if (!nome || nome === t.nome) return;
    this.api.renomearTipo(t.id, nome).subscribe({ next: () => this.carregar(), error: this.erro('Não foi possível renomear') });
  }

  protected async excluir(t: TipoProtocolo): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Excluir este tipo?', mensagem: `"${t.nome}" e as suas sequências serão apagados. Só é possível se nenhum número foi reservado, utilizado ou anulado.`,
      rotuloConfirmar: 'Excluir', segundos: 3,
    });
    if (ok) this.api.excluirTipo(t.id).subscribe({ next: () => this.carregar(), error: this.erro('Não foi possível excluir') });
  }

  protected mudou(s: SequenciaProtocolo): boolean {
    const f = this.faixas[s.id];
    return !!f && (f.inicio !== s.inicio || f.fim !== s.fim);
  }

  protected alterarFaixa(s: SequenciaProtocolo): void {
    this.api.alterarFaixa(s.id, this.faixas[s.id]).subscribe({ next: () => this.carregar(), error: this.erro('Não foi possível alterar a faixa') });
  }

  protected criarSequencia(t: TipoProtocolo): void {
    this.api.criarSequencia(t.id, this.novas[t.id]).subscribe({ next: () => this.carregar(), error: this.erro('Não foi possível criar a sequência') });
  }
}
