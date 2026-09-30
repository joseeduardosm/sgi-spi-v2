// Criado por José Eduardo Santana Martins
// Este arquivo serve para os aprovadores configurarem a página inicial: slider, curadoria, atalhos e categorias.

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { NoticiasApiService } from '../noticias-api.service';
import { Atalho, Categoria, ConfiguracaoPortal, dataCurta, NoticiaCartao } from '../noticias.models';
import { SliderNoticiasComponent } from '../publico/slider-noticias.component';
import { CabecalhoNoticiasComponent } from './cabecalho-noticias.component';

@Component({
  selector: 'app-configuracao-portal',
  imports: [FormsModule, CabecalhoNoticiasComponent, SliderNoticiasComponent],
  template: `
    <app-cabecalho-noticias titulo="Configurar portal" [trilha]="[{ rotulo: 'Configurar portal' }]"
                            descricao="Como a página inicial do sistema mostra as notícias e os atalhos." />
    @if (config(); as c) {
      <div class="colunas-configuracao">
        <section class="cartao-dados">
          <header><h2>Slider e página inicial</h2></header>
          <form class="corpo grade-formulario" (submit)="$event.preventDefault(); salvar()">
            <div><label for="cp-titulo">Título da página</label><input id="cp-titulo" name="titulo" maxlength="120" [(ngModel)]="c.titulo" /></div>
            <div><label for="cp-sub">Subtítulo</label><input id="cp-sub" name="subtitulo" maxlength="200" [(ngModel)]="c.subtitulo" /></div>
            <div><label for="cp-qtd">Notícias no slider</label><input id="cp-qtd" type="number" min="1" max="10" name="qtd" [(ngModel)]="c.quantidade_slides" /></div>
            <div><label for="cp-seg">Segundos por notícia</label><input id="cp-seg" type="number" min="3" max="60" name="seg" [(ngModel)]="c.segundos_por_slide" /></div>
            <div><label for="cp-cartoes">Cartões abaixo do slider</label><input id="cp-cartoes" type="number" min="0" max="12" name="cartoes" [(ngModel)]="c.quantidade_cartoes" /></div>
            <div><label for="cp-criterio">Quais notícias vão para o slider</label>
              <select id="cp-criterio" name="criterio" [(ngModel)]="c.criterio_slider">
                <option value="automatico">Automático: fixadas e mais recentes</option>
                <option value="curadoria">Curadoria: escolho a lista e a ordem</option>
              </select></div>
            <div class="ocupa-duas linha-caixas">
              <label><input type="checkbox" name="auto" [(ngModel)]="c.passagem_automatica" /> Passar sozinho</label>
              <label><input type="checkbox" name="sobre" [(ngModel)]="c.titulo_sobreposto" /> Título sobre a imagem</label>
              <label><input type="checkbox" name="atalhos" [(ngModel)]="c.exibir_atalhos" /> Mostrar atalhos</label>
              <label><input type="checkbox" name="todas" [(ngModel)]="c.exibir_todas" /> Mostrar "Ver todas as notícias"</label>
            </div>
            @if (c.criterio_slider === 'curadoria') {
              <div class="ocupa-duas">
                <p class="secao-formulario">Curadoria ({{ curadoria().length }} de {{ c.quantidade_slides }} no slider)</p>
                <ol class="lista-curadoria">
                  @for (n of curadoria(); track n.id; let i = $index) {
                    <li><span>{{ i + 1 }}. {{ n.titulo }}</span>
                      <span class="acoes-linha">
                        <button type="button" [disabled]="i === 0" aria-label="Subir" (click)="moverCuradoria(i, -1)">↑</button>
                        <button type="button" [disabled]="i === curadoria().length - 1" aria-label="Descer" (click)="moverCuradoria(i, 1)">↓</button>
                        <button type="button" (click)="tirar(n)">Tirar</button>
                      </span></li>
                  } @empty { <li class="dica-formulario">Nenhuma escolhida: o slider fica vazio.</li> }
                </ol>
                <label for="cp-add">Incluir notícia publicada</label>
                <select id="cp-add" name="add" [ngModel]="''" (ngModelChange)="incluir($event)">
                  <option value="">Escolha…</option>
                  @for (n of candidatasLivres(); track n.id) { <option [value]="n.id">{{ n.titulo }} ({{ data(n.publicada_em) }})</option> }
                </select>
              </div>
            }
            <div class="ocupa-duas acoes-formulario">
              <span class="dica-formulario">@if (c.atualizado_por_nome) { Última alteração: {{ c.atualizado_por_nome }} }</span>
              <button type="submit" class="acao-primaria">Salvar configuração</button>
            </div>
          </form>
        </section>
        <section class="cartao-dados">
          <header><h2>Prévia do slider</h2></header>
          <div class="corpo">
            <app-slider-noticias [slides]="previa()" [segundos]="c.segundos_por_slide" [automatico]="c.passagem_automatica" [tituloSobreposto]="c.titulo_sobreposto" />
            @if (!previa().length) { <p class="dica-formulario">Sem notícias para mostrar.</p> }
          </div>
        </section>
      </div>
    }

    <section class="cartao-dados">
      <header><div><h2>Atalhos</h2><small>Aparecem ao lado das notícias. Imagem JPG, PNG ou WebP (é reduzida para 480 px).</small></div>
        <button type="button" class="acao-primaria" (click)="novoAtalho()"><span>+</span> Novo atalho</button></header>
      <div class="corpo">
        <div class="grade-atalhos-gestao">
          @for (a of atalhos(); track a.id; let i = $index) {
            <div class="atalho-gestao" [class.inativo]="!a.ativo">
              @if (a.imagem) { <img [src]="a.imagem" alt="" /> } @else { <span class="sem-capa">sem imagem</span> }
              <strong>{{ a.titulo }}</strong><small>{{ a.url }}</small>
              <span class="acoes-linha">
                <button type="button" [disabled]="i === 0" aria-label="Mover para a esquerda" (click)="moverAtalho(i, -1)">←</button>
                <button type="button" [disabled]="i === atalhos().length - 1" aria-label="Mover para a direita" (click)="moverAtalho(i, 1)">→</button>
                <button type="button" (click)="editarAtalho(a)">Editar</button>
                <button type="button" (click)="excluirAtalho(a)">Excluir</button>
              </span>
            </div>
          } @empty { <p class="dica-formulario">Nenhum atalho.</p> }
        </div>
      </div>
    </section>

    <section class="cartao-dados">
      <header><h2>Categorias</h2></header>
      <div class="corpo">
        <div class="lista-categorias">
          @for (c of categorias(); track c.id) {
            <form class="linha-categoria" (submit)="$event.preventDefault(); salvarCategoria(c)">
              <input type="color" [name]="'cor' + c.id" [(ngModel)]="c.cor" aria-label="Cor" />
              <input [name]="'nome' + c.id" maxlength="60" [(ngModel)]="c.nome" aria-label="Nome" />
              <label><input type="checkbox" [name]="'ativa' + c.id" [(ngModel)]="c.ativa" /> ativa</label>
              <button type="submit" class="acao-secundaria acao-pequena">Salvar</button>
            </form>
          }
          <form class="linha-categoria" (submit)="$event.preventDefault(); novaCategoria()">
            <input type="color" name="corNova" [(ngModel)]="corNova" aria-label="Cor" />
            <input name="nomeNova" maxlength="60" [(ngModel)]="nomeNova" placeholder="Nova categoria" aria-label="Nova categoria" />
            <button type="submit" class="acao-secundaria acao-pequena" [disabled]="!nomeNova.trim()">Incluir</button>
          </form>
        </div>
      </div>
    </section>

    @if (atalhoAberto(); as a) {
      <div class="fundo-modal" role="presentation" (click)="atalhoAberto.set(null)"></div>
      <section class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-atalho">
        <header><div><span class="modal-sobretitulo">Atalho</span><h2 id="titulo-atalho">{{ a.id ? 'Editar atalho' : 'Novo atalho' }}</h2></div>
          <button type="button" aria-label="Fechar" (click)="atalhoAberto.set(null)">×</button></header>
        <form (submit)="$event.preventDefault(); salvarAtalho()">
          <div class="grade-formulario uma-coluna">
            <div><label for="at-titulo">Título *</label><input id="at-titulo" name="titulo" maxlength="80" [(ngModel)]="a.titulo" /></div>
            <div><label for="at-url">Endereço *</label><input id="at-url" name="url" maxlength="500" placeholder="https://…" [(ngModel)]="a.url" /></div>
            <div><label for="at-img">Imagem</label><input id="at-img" type="file" accept="image/jpeg,image/png,image/webp" (change)="imagemAtalho = $any($event.target).files?.[0] ?? null" /></div>
          </div>
          <div class="linha-caixas">
            <label><input type="checkbox" name="ativo" [(ngModel)]="a.ativo" /> Ativo</label>
            <label><input type="checkbox" name="aba" [(ngModel)]="a.nova_aba" /> Abrir em nova aba</label>
          </div>
          <footer><button type="button" class="acao-secundaria" (click)="atalhoAberto.set(null)">Cancelar</button>
            <button type="submit" class="acao-primaria" [disabled]="!a.titulo.trim() || !a.url.trim()">Salvar</button></footer>
        </form>
      </section>
    }
  `,
})
export class ConfiguracaoPortalComponent implements OnInit {
  private readonly api = inject(NoticiasApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly config = signal<ConfiguracaoPortal | null>(null);
  protected readonly curadoria = signal<NoticiaCartao[]>([]);
  protected readonly candidatas = signal<NoticiaCartao[]>([]);
  protected readonly atalhos = signal<Atalho[]>([]);
  protected readonly categorias = signal<Categoria[]>([]);
  protected readonly atalhoAberto = signal<(Partial<Atalho> & { titulo: string; url: string; ativo: boolean; nova_aba: boolean }) | null>(null);
  protected imagemAtalho: File | null = null;
  protected nomeNova = '';
  protected corNova = '#2f6fb5';
  protected readonly data = dataCurta;

  ngOnInit(): void {
    this.carregarConfiguracao();
    this.carregarAtalhos();
    this.api.categorias().subscribe({ next: (c) => this.categorias.set(c), error: () => undefined });
  }

  private carregarConfiguracao(): void {
    this.api.configuracao().subscribe({
      next: (g) => { this.config.set({ ...g.configuracao }); this.curadoria.set(g.curadoria); this.candidatas.set(g.candidatas); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível abrir a configuração'),
    });
  }

  private carregarAtalhos(): void {
    this.api.atalhos().subscribe({ next: (a) => this.atalhos.set(a), error: () => undefined });
  }

  /** Prévia do slider com a configuração da tela (automático: fixadas e mais recentes). */
  protected previa(): NoticiaCartao[] {
    const c = this.config();
    if (!c) return [];
    const base = c.criterio_slider === 'curadoria' ? this.curadoria()
      : [...this.candidatas()].sort((a, b) => Number(b.fixada) - Number(a.fixada));
    return base.slice(0, c.quantidade_slides);
  }

  protected candidatasLivres(): NoticiaCartao[] {
    const usados = new Set(this.curadoria().map((n) => n.id));
    return this.candidatas().filter((n) => !usados.has(n.id));
  }

  protected incluir(id: string): void {
    const n = this.candidatas().find((x) => x.id === id);
    if (n) this.curadoria.update((l) => [...l, n]);
  }

  protected tirar(n: NoticiaCartao): void { this.curadoria.update((l) => l.filter((x) => x.id !== n.id)); }

  protected moverCuradoria(i: number, passo: number): void {
    this.curadoria.update((l) => { const c = [...l]; [c[i], c[i + passo]] = [c[i + passo], c[i]]; return c; });
  }

  protected salvar(): void {
    const c = this.config()!;
    this.dialogos.executar(this.api.salvarConfiguracao({ ...c, curadoria: c.criterio_slider === 'curadoria' ? this.curadoria().map((n) => n.id) : null })).subscribe({
      next: (g) => { this.config.set({ ...g.configuracao }); this.curadoria.set(g.curadoria); this.dialogos.avisar('Configuração salva', 'A página inicial já mostra as mudanças.'); },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected novoAtalho(): void { this.imagemAtalho = null; this.atalhoAberto.set({ titulo: '', url: 'https://', ativo: true, nova_aba: true }); }

  protected editarAtalho(a: Atalho): void { this.imagemAtalho = null; this.atalhoAberto.set({ ...a }); }

  protected salvarAtalho(): void {
    const a = this.atalhoAberto()!;
    this.dialogos.executar(this.api.salvarAtalho({ titulo: a.titulo, url: a.url, ativo: a.ativo, nova_aba: a.nova_aba }, this.imagemAtalho, a.id)).subscribe({
      next: () => { this.atalhoAberto.set(null); this.carregarAtalhos(); }, error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected async excluirAtalho(a: Atalho): Promise<void> {
    if (!(await this.dialogos.confirmar({ titulo: 'Excluir atalho', mensagem: `"${a.titulo}" sai da página inicial.`, rotuloConfirmar: 'Excluir' }))) return;
    this.api.excluirAtalho(a.id).subscribe({ next: () => this.carregarAtalhos(), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected moverAtalho(i: number, passo: number): void {
    const l = [...this.atalhos()];
    [l[i], l[i + passo]] = [l[i + passo], l[i]];
    this.atalhos.set(l);
    this.api.ordenarAtalhos(l.map((a) => a.id)).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected salvarCategoria(c: Categoria): void {
    this.api.salvarCategoria({ nome: c.nome, cor: c.cor, ordem: c.ordem, ativa: c.ativa }, c.id).subscribe({
      next: () => undefined, error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected novaCategoria(): void {
    this.api.salvarCategoria({ nome: this.nomeNova.trim(), cor: this.corNova, ordem: this.categorias().length, ativa: true }).subscribe({
      next: (c) => { this.categorias.update((l) => [...l, c]); this.nomeNova = ''; }, error: (e) => this.dialogos.mostrarErro(e),
    });
  }
}
