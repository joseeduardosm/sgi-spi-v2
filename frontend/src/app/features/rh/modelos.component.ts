// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela RH > Modelos: textos editáveis (resolução, e-mail de nomeação, termo de posse, boas-vindas) e checklists de documentos por tipo de cargo.

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { EditorRicoComponent } from '../contratacoes/editor-rico.component';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { RhAdmissaoApiService } from './rh-admissao-api.service';
import { Checklist, ClassificacaoChecklist, GravacaoChecklist, ModeloRh, rotuloClassificacao } from './rh-admissao.models';

type Aba = 'modelos' | 'checklists';

/** RH > Modelos: o RH edita os textos que o sistema usa nas admissões e nas boas-vindas, e os documentos exigidos por tipo de cargo. */
@Component({
  selector: 'app-modelos-rh',
  imports: [FormsModule, CabecalhoRhComponent, EsqueletoComponent, EditorRicoComponent],
  host: { '(document:keydown.escape)': 'edicaoChecklist.set(null)' },
  template: `
    <app-cabecalho-rh titulo="Modelos" [trilha]="['Modelos']" descricao="Textos e documentos usados nas admissões. Nada fica fixo no código." />

    <div class="abas" role="tablist">
      <button type="button" role="tab" [class.ativa]="aba() === 'modelos'" [attr.aria-selected]="aba() === 'modelos'" (click)="aba.set('modelos')">Textos</button>
      <button type="button" role="tab" [class.ativa]="aba() === 'checklists'" [attr.aria-selected]="aba() === 'checklists'" (click)="aba.set('checklists')">Checklists de documentos <span class="contador-aba">{{ checklists().length }}</span></button>
    </div>

    @if (aba() === 'modelos') {
      @if (carregando()) { <app-esqueleto tipo="formulario" [linhas]="4" /> }
      <div class="parametros-rh"><div class="sem-borda">
        @for (m of modelos(); track m.tipo) {
          <section class="cartao-dados" [attr.aria-labelledby]="'mod-' + m.tipo">
            <header><div><h2 [id]="'mod-' + m.tipo">{{ m.nome }}</h2><small>Atualizado em {{ dataHora(m.atualizado_em) }}</small></div>
              <button type="button" class="acao-secundaria acao-pequena" (click)="alternar(m)">{{ aberto() === m.tipo ? 'Fechar' : 'Editar' }}</button></header>
            @if (aberto() === m.tipo) {
              <div class="corpo">
                @if (temAssunto(m)) { <div class="campo"><label [for]="'ass-' + m.tipo">Assunto do e-mail</label><input [id]="'ass-' + m.tipo" [name]="'ass-' + m.tipo" maxlength="300" [(ngModel)]="assunto" /></div> }
                @defer (on idle) { <app-editor-rico [(html)]="html" [rotulo]="'Texto de ' + m.nome" /> } @placeholder { <app-esqueleto tipo="formulario" [linhas]="4" /> }
                <details class="nota-explicativa">
                  <summary>Placeholders permitidos</summary>
                  <ul class="lista-simples">@for (p of placeholders(); track p[0]) { <li><span class="texto-codigo">#{{ p[0] }}</span>: {{ p[1] }}</li> }</ul>
                </details>
                <div class="acoes-formulario">
                  <button type="button" class="acao-secundaria" (click)="restaurar(m)">Restaurar o texto padrão</button>
                  <button type="button" class="acao-primaria" (click)="salvar(m)">Salvar</button>
                </div>
              </div>
            }
          </section>
        }
      </div></div>
    } @else {
      <section class="painel-gestao" aria-labelledby="titulo-checklists">
        <div class="barra-ferramentas">
          <div><h2 id="titulo-checklists">Checklists de documentos</h2><p>Cada checklist vale para uma ou várias classificações de cargo (grupo e nível, ex.: 1.15, 1.16, 1.17). O envio ao Portal de Indicações é externo: o RH só registra o envio.</p></div>
          <div class="acoes-formulario"><button type="button" class="acao-primaria" (click)="novoChecklist()"><span>+</span> Novo checklist</button></div>
        </div>
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <thead><tr><th>Checklist</th><th>Vale para</th><th>Documentos</th><th>Situação</th><th class="coluna-acoes">Ações</th></tr></thead>
            <tbody>
              @for (c of checklists(); track c.id) {
                <tr>
                  <td><strong>{{ c.nome }}</strong></td>
                  <td>{{ resumo(c) }}</td>
                  <td>{{ c.itens.length }}</td>
                  <td><span [class]="c.ativo ? 'selo-situacao' : 'selo-situacao inativo'">{{ c.ativo ? 'Ativo' : 'Inativo' }}</span></td>
                  <td class="coluna-acoes"><div class="acoes-linha">
                    <button type="button" class="acao-secundaria acao-pequena" (click)="editarChecklist(c)">Editar</button>
                    <button type="button" class="acao-secundaria acao-pequena" (click)="excluirChecklist(c)">Excluir</button>
                  </div></td>
                </tr>
              } @empty { <tr><td class="estado-vazio" colspan="5">Nenhum checklist cadastrado.</td></tr> }
            </tbody>
          </table>
        </div>
      </section>
    }

    @if (edicaoChecklist(); as e) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="edicaoChecklist.set(null)"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-checklist">
        <header>
          <div><span class="modal-sobretitulo">Checklists</span><h2 id="titulo-checklist">{{ idChecklist ? 'Editar checklist' : 'Novo checklist' }}</h2></div>
          <button type="button" aria-label="Fechar" (click)="edicaoChecklist.set(null)">×</button>
        </header>
        <form (ngSubmit)="salvarChecklist(e)">
          <div class="grade-formulario">
            <div class="ocupa-duas"><label for="ck-nome">Nome *</label><input id="ck-nome" name="nome" maxlength="200" [(ngModel)]="e.nome" /></div>
            <div class="ocupa-duas">
              <label>Vale para as classificações</label>
              @for (g of grupos; track g) {
                <div class="bloco-classificacao">
                  <div class="cabeca-classificacao">
                    <strong>Grupo {{ g }}</strong><small>{{ g === 1 ? 'direção e chefia' : 'assessoria' }}</small>
                    <span class="atalhos-classificacao">
                      <button type="button" class="acao-secundaria acao-pequena" (click)="marcarGrupo(e, g, true)">Todos</button>
                      <button type="button" class="acao-secundaria acao-pequena" (click)="marcarGrupo(e, g, false)">Nenhum</button>
                    </span>
                  </div>
                  <div class="chips-filtro chips-classificacao" role="group" [attr.aria-label]="'Níveis do grupo ' + g">
                    @for (n of niveis; track n) { <button type="button" [class.ativo]="marcada(e, g, n)" [attr.aria-pressed]="marcada(e, g, n)" (click)="alternarClassificacao(e, g, n)">{{ g }}.{{ n < 10 ? '0' + n : n }}</button> }
                  </div>
                </div>
              }
              <div class="linha-caixas"><label><input type="checkbox" name="ck-outros" [(ngModel)]="e.aplica_a_outros" /> Também vale para cargos sem classificação (Outros)</label></div>
            </div>
            <div class="ocupa-duas">
              <label>Documentos exigidos</label>
              @for (i of e.itens; track $index; let n = $index) {
                <div class="item-checklist">
                  <input [name]="'ck-item-' + n" maxlength="300" placeholder="Ex.: RG e CPF" [(ngModel)]="i.descricao" [attr.aria-label]="'Documento ' + (n + 1)" />
                  <div class="linha-caixas"><label><input type="checkbox" [name]="'ck-obr-' + n" [(ngModel)]="i.obrigatorio" /> Obrigatório</label></div>
                  <button type="button" class="acao-secundaria acao-pequena" (click)="e.itens.splice(n, 1)">Remover</button>
                </div>
              }
              <div><button type="button" class="acao-secundaria acao-pequena" (click)="e.itens.push({ descricao: '', obrigatorio: true })">+ Documento</button></div>
            </div>
          </div>
          <div class="linha-caixas"><label><input type="checkbox" name="ck-ativo" [(ngModel)]="e.ativo" /> Ativo</label></div>
          <footer>
            <button type="button" class="acao-secundaria" (click)="edicaoChecklist.set(null)">Cancelar</button>
            <button type="submit" class="acao-primaria" [disabled]="!e.nome.trim() || (!e.classificacoes.length && !e.aplica_a_outros)">Salvar</button>
          </footer>
        </form>
      </section>
    }
  `,
})
export class ModelosRhComponent implements OnInit {
  private readonly api = inject(RhAdmissaoApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly aba = signal<Aba>('modelos');
  protected readonly modelos = signal<ModeloRh[]>([]);
  protected readonly checklists = signal<Checklist[]>([]);
  protected readonly grupos: (1 | 2)[] = [1, 2];
  protected readonly niveis = Array.from({ length: 18 }, (_, i) => i + 1);
  protected readonly placeholders = signal<[string, string][]>([]);
  protected readonly carregando = signal(true);
  protected readonly aberto = signal<string | null>(null);
  protected readonly edicaoChecklist = signal<GravacaoChecklist | null>(null);
  protected idChecklist: number | null = null;
  protected assunto = '';
  protected html = '';

  ngOnInit(): void {
    this.carregar();
    this.api.placeholders().subscribe((p) => this.placeholders.set(Object.entries(p)));
    this.carregarChecklists();
  }

  private carregar(): void {
    this.api.modelos().subscribe({ next: (m) => { this.modelos.set(m); this.carregando.set(false); }, error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar os modelos'); } });
  }

  private carregarChecklists(): void {
    this.api.checklists().subscribe({ next: (c) => this.checklists.set(c), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar os checklists') });
  }

  protected dataHora(iso: string): string {
    const d = new Date(iso), p = (n: number) => String(n).padStart(2, '0');
    return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }

  protected temAssunto(m: ModeloRh): boolean {
    return m.tipo === 'email_nomeacao_publicada' || m.tipo === 'boas_vindas';
  }

  protected alternar(m: ModeloRh): void {
    if (this.aberto() === m.tipo) { this.aberto.set(null); return; }
    this.assunto = m.assunto;
    this.html = m.html;
    this.aberto.set(m.tipo);
  }

  protected salvar(m: ModeloRh): void {
    this.dialogos.executar(this.api.salvarModelo(m.tipo, this.assunto, this.html), 'Salvando…').subscribe({
      next: () => { this.dialogos.avisar('Modelo salvo', 'O novo texto vale a partir de agora.'); this.aberto.set(null); this.carregar(); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar o modelo'),
    });
  }

  protected async restaurar(m: ModeloRh): Promise<void> {
    if (!(await this.dialogos.confirmar({ titulo: 'Restaurar o texto padrão?', mensagem: 'O texto atual deste modelo será substituído pelo padrão do sistema.', rotuloConfirmar: 'Restaurar', perigo: true }))) return;
    this.dialogos.executar(this.api.restaurarModelo(m.tipo), 'Restaurando…').subscribe({
      next: (n) => { this.assunto = n.assunto; this.html = n.html; this.aberto.set(null); this.carregar(); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível restaurar o modelo'),
    });
  }

  // --- Checklists ---
  protected novoChecklist(): void {
    this.idChecklist = null;
    this.edicaoChecklist.set({ nome: '', ativo: true, classificacoes: [], aplica_a_outros: false, itens: [{ descricao: '', obrigatorio: true }] });
  }

  protected editarChecklist(c: Checklist): void {
    this.idChecklist = c.id;
    this.edicaoChecklist.set({ nome: c.nome, ativo: c.ativo, classificacoes: c.classificacoes.map((x) => ({ ...x })), aplica_a_outros: c.aplica_a_outros, itens: c.itens.map((i) => ({ ...i })) });
  }

  protected marcada(e: GravacaoChecklist, grupo: 1 | 2, nivel: number): boolean {
    return e.classificacoes.some((c) => c.grupo === grupo && c.nivel === nivel);
  }

  protected alternarClassificacao(e: GravacaoChecklist, grupo: 1 | 2, nivel: number): void {
    e.classificacoes = this.marcada(e, grupo, nivel) ? e.classificacoes.filter((c) => !(c.grupo === grupo && c.nivel === nivel)) : [...e.classificacoes, { grupo, nivel }];
  }

  /** Marca ou desmarca todos os níveis do grupo de uma vez. */
  protected marcarGrupo(e: GravacaoChecklist, grupo: 1 | 2, marcar: boolean): void {
    const outras = e.classificacoes.filter((c) => c.grupo !== grupo);
    e.classificacoes = marcar ? [...outras, ...this.niveis.map((nivel) => ({ grupo, nivel }))] : outras;
  }

  /** Resumo para a tabela: níveis seguidos viram faixa ("1.15–1.17"), o resto vai separado por vírgula. */
  protected resumo(c: Checklist): string {
    const partes: string[] = [];
    for (const g of this.grupos) {
      const niveis = c.classificacoes.filter((x) => x.grupo === g).map((x) => x.nivel).sort((a, b) => a - b);
      let i = 0;
      while (i < niveis.length) {
        let j = i;
        while (j + 1 < niveis.length && niveis[j + 1] === niveis[j] + 1) j++;
        const de = rotuloClassificacao({ grupo: g, nivel: niveis[i] }), ate = rotuloClassificacao({ grupo: g, nivel: niveis[j] });
        partes.push(j - i >= 2 ? `${de}–${ate}` : niveis.slice(i, j + 1).map((n) => rotuloClassificacao({ grupo: g, nivel: n })).join(', '));
        i = j + 1;
      }
    }
    if (c.aplica_a_outros) partes.push('Outros');
    return partes.join(', ') || '—';
  }

  protected salvarChecklist(e: GravacaoChecklist): void {
    const dados: GravacaoChecklist = { ...e, nome: e.nome.trim(), itens: e.itens.filter((i) => i.descricao.trim()).map((i) => ({ ...i, descricao: i.descricao.trim() })) };
    const chamada = this.idChecklist ? this.api.alterarChecklist(this.idChecklist, dados) : this.api.criarChecklist(dados);
    this.dialogos.executar(chamada, 'Salvando…').subscribe({
      next: () => { this.edicaoChecklist.set(null); this.carregarChecklists(); },
      error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível salvar o checklist'),
    });
  }

  protected async excluirChecklist(c: Checklist): Promise<void> {
    if (!(await this.dialogos.confirmar({ titulo: `Excluir o checklist "${c.nome}"?`, mensagem: 'Admissões já iniciadas guardam a própria cópia dos documentos e não são afetadas.', rotuloConfirmar: 'Excluir', perigo: true }))) return;
    this.api.excluirChecklist(c.id).subscribe({ next: () => this.carregarChecklists(), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir o checklist') });
  }
}
