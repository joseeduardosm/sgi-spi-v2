// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de Administração › Menu (ordem, grupos, nomes, links e itens ocultos da barra lateral).

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { aplicarConfiguracao, NoMenu } from '../../../core/navegacao/menu-config';
import { MenuConfigService } from '../../../core/navegacao/menu-config.service';
import { NAVEGACAO } from '../../../core/navegacao/navegacao';
import { ItemNavegacao } from '../../../core/navegacao/navegacao.model';
import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
import { TrilhaComponent } from '../../../shared/componentes/trilha/trilha.component';
import { erroExibivel } from '../../../shared/utilitarios/erros-api';

/** Uma linha do editor: um módulo do código, um grupo ou um link criado pelo administrador. */
interface Linha {
  id: string;
  tipo: 'modulo' | 'grupo' | 'link';
  /** Nome padrão do módulo no código (null em grupos e links). */
  rotuloPadrao: string | null;
  rotulo: string;
  paiId: string | null;
  oculto: boolean;
  url: string;
  novaAba: boolean | null;
  /** Grupo do próprio código (não recebe grupos nem pode ser movido para dentro de outro). */
  grupoDoCodigo: boolean;
}

/** Itens da seção configurável do menu padrão, por id (módulos e grupos do código). */
function itensDoCodigo(): ItemNavegacao[] {
  return NAVEGACAO.find((s) => s.configuravel)?.itens ?? [];
}

/** Administração do menu lateral: ordenar, agrupar, renomear e ocultar módulos, e criar grupos e links para todos. */
@Component({
  selector: 'app-gestao-menu',
  imports: [FormsModule, TrilhaComponent, EsqueletoComponent],
  template: `
    <div class="cabecalho-pagina">
      <div>
        <app-trilha [itens]="[{ rotulo: 'Administração' }, { rotulo: 'Menu' }]" />
        <h1>Menu</h1>
        <small>Ordem, grupos, nomes e itens ocultos da barra lateral, para todos os usuários. Ocultar tira o item do menu e da busca, mas não muda quem tem acesso.</small>
      </div>
    </div>

    @if (aviso(); as a) { <p class="aviso-admin" [class.erro]="a.erro" role="status">{{ a.texto }}</p> }

    <section class="painel-gestao" aria-labelledby="titulo-novo">
      <div class="barra-ferramentas"><div><h2 id="titulo-novo">Novo grupo ou link</h2>
        <p>Grupo reúne itens sob um nome dobrável. Link leva a uma tela do SGI (<code>/ramais</code>) ou a um endereço externo (<code>https://…</code>).</p></div></div>
      <form class="grade-formulario" style="grid-template-columns: 1fr 1fr" (ngSubmit)="adicionar()">
        <div><label for="novo-tipo">Tipo</label>
          <select id="novo-tipo" name="tipo" class="form-control" [(ngModel)]="novoTipo">
            <option value="grupo">Grupo</option>
            <option value="link">Link</option>
          </select></div>
        <div><label for="novo-nome">Nome *</label>
          <input id="novo-nome" name="nome" class="form-control" required maxlength="80" [(ngModel)]="novoNome" /></div>
        @if (novoTipo === 'link') {
          <div><label for="novo-url">Destino *</label>
            <input id="novo-url" name="url" class="form-control" required maxlength="500" placeholder="/ramais ou https://exemplo.gov.br" [(ngModel)]="novoUrl" /></div>
          <div><label for="novo-aba">Abrir em</label>
            <select id="novo-aba" name="aba" class="form-control" [(ngModel)]="novoAba">
              <option value="auto">Automático (externos em nova aba)</option>
              <option value="nova">Nova aba</option>
              <option value="mesma">Mesma aba</option>
            </select></div>
        }
        <div class="ocupa-duas acoes-formulario" style="grid-column: 1 / -1">
          <button type="submit" class="acao-secundaria" [disabled]="!novoNome.trim() || (novoTipo === 'link' && !novoUrl.trim())">Adicionar</button>
        </div>
      </form>
    </section>

    <section class="painel-gestao" aria-labelledby="titulo-itens">
      <div class="barra-ferramentas"><div><h2 id="titulo-itens">Itens do menu</h2>
        <p>Use as setas para ordenar e escolha o grupo de cada item. As mudanças só valem para todos depois de <strong>Salvar menu</strong>.</p></div></div>
      @if (carregando()) {
        <app-esqueleto [linhas]="6" />
      } @else {
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <thead><tr><th>Nome exibido</th><th>Grupo</th><th>Ordem</th><th>Visibilidade</th><th></th></tr></thead>
            <tbody>
              @for (l of ordenadas(); track l.id) {
                <tr [style.opacity]="l.oculto ? 0.55 : 1">
                  <td [style.padding-left.px]="l.paiId ? 36 : 15">
                    <input class="form-control" [attr.aria-label]="'Nome de ' + (l.rotuloPadrao ?? l.rotulo)" maxlength="80"
                           [placeholder]="l.rotuloPadrao ?? ''" [ngModel]="l.rotulo" (ngModelChange)="renomear(l, $event)" />
                    @if (l.tipo !== 'modulo' || l.grupoDoCodigo) { <small>{{ descricao(l) }}</small> }
                  </td>
                  <td>
                    @if (podeMudarDeGrupo(l)) {
                      <select class="form-control" [attr.aria-label]="'Grupo de ' + l.rotulo" [ngModel]="l.paiId ?? ''" (ngModelChange)="mudarGrupo(l, $event)">
                        <option value="">Primeiro nível</option>
                        @for (g of grupos(); track g.id) { @if (g.id !== l.id) { <option [value]="g.id">{{ g.rotulo }}</option> } }
                      </select>
                    } @else { <span>—</span> }
                  </td>
                  <td>
                    <button type="button" class="acao-secundaria acao-pequena" [attr.aria-label]="'Subir ' + l.rotulo" (click)="mover(l, -1)">↑</button>
                    <button type="button" class="acao-secundaria acao-pequena" [attr.aria-label]="'Descer ' + l.rotulo" (click)="mover(l, 1)">↓</button>
                  </td>
                  <td>
                    <button type="button" class="acao-secundaria acao-pequena" [attr.aria-label]="(l.oculto ? 'Mostrar ' : 'Ocultar ') + l.rotulo" (click)="l.oculto = !l.oculto; linhas.set([...linhas()])">{{ l.oculto ? 'Mostrar' : 'Ocultar' }}</button>
                  </td>
                  <td>
                    @if (l.tipo !== 'modulo') { <button type="button" class="acao-perigo acao-pequena" (click)="remover(l)">Excluir</button> }
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
        <footer class="acoes-formulario">
          <button type="button" class="acao-secundaria" (click)="restaurar()">Restaurar padrão</button>
          <button type="button" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando()" (click)="salvar()">Salvar menu</button>
        </footer>
      }
    </section>
  `,
  // O painel não tem margem interna própria: o conteúdo abaixo do cabeçalho recebe o mesmo recuo (24px) do cabeçalho (padrão da Integração GLPI)
  styles: `
    .painel-gestao > :not(.barra-ferramentas):not(.tabela-gestao-envoltorio) { margin-inline: 24px; }
    .painel-gestao > .barra-ferramentas + :not(.tabela-gestao-envoltorio) { margin-top: 20px; }
    .painel-gestao > :last-child { margin-bottom: 22px; }
    .tabela-gestao td small { display: block; margin-top: 4px; }
    .tabela-gestao td .acao-pequena + .acao-pequena { margin-left: 4px; }
  `,
})
export class GestaoMenuComponent implements OnInit {
  private readonly servico = inject(MenuConfigService);

  protected readonly linhas = signal<Linha[]>([]);
  protected readonly carregando = signal(true);
  protected readonly salvando = signal(false);
  protected readonly aviso = signal<{ texto: string; erro: boolean } | null>(null);

  // Formulário de novo grupo/link
  protected novoTipo: 'grupo' | 'link' = 'grupo';
  protected novoNome = '';
  protected novoUrl = '';
  protected novoAba: 'auto' | 'nova' | 'mesma' = 'auto';

  /** Primeiro nível na ordem, cada um seguido dos itens do seu grupo. */
  protected readonly ordenadas = computed(() => {
    const todas = this.linhas();
    const ids = new Set(todas.map((l) => l.id));
    return todas.filter((l) => !l.paiId || !ids.has(l.paiId)).flatMap((l) => [l, ...todas.filter((f) => f.paiId === l.id)]);
  });

  /** Grupos que aceitam itens: os criados aqui e o grupo "Módulos" do código. */
  protected readonly grupos = computed(() => this.linhas().filter((l) => l.tipo === 'grupo' || l.id === 'modulos'));

  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    this.carregando.set(true);
    this.servico.ler().subscribe({
      next: (r) => {
        this.linhas.set(this.montar(r.itens));
        this.carregando.set(false);
      },
      error: (e) => {
        this.avisar(erroExibivel(e).mensagem, true);
        this.carregando.set(false);
      },
    });
  }

  /** Junta o menu do código com a configuração (ocultos incluídos) numa lista plana editável. */
  private montar(nos: NoMenu[]): Linha[] {
    const codigo = new Map<string, ItemNavegacao>();
    const guardar = (itens: ItemNavegacao[]): void => itens.forEach((i) => { codigo.set(i.id, i); guardar(i.filhos ?? []); });
    guardar(itensDoCodigo());
    const configurados = new Map(nos.map((n) => [n.id, n]));
    const linha = (i: ItemNavegacao, paiId: string | null): Linha => {
      const padrao = codigo.get(i.id);
      const no = configurados.get(i.id);
      return {
        id: i.id, tipo: padrao ? 'modulo' : (no?.tipo ?? 'link') === 'grupo' ? 'grupo' : 'link', rotuloPadrao: padrao?.rotulo ?? null, rotulo: i.rotulo, paiId,
        oculto: !!i.oculto, url: no?.url ?? '', novaAba: no?.nova_aba ?? null, grupoDoCodigo: !!padrao?.filhos,
      };
    };
    return aplicarConfiguracao(itensDoCodigo(), nos, true).flatMap((i) => [linha(i, null), ...(i.filhos ?? []).map((f) => linha(f, i.id))]);
  }

  protected descricao(l: Linha): string {
    if (l.tipo === 'grupo') return 'Grupo criado por você';
    if (l.tipo === 'link') return `Link: ${l.url}`;
    return l.grupoDoCodigo ? 'Grupo do sistema' : 'Módulo do sistema';
  }

  /** Grupos ficam no primeiro nível (o menu aceita só dois níveis); itens de um grupo do sistema que não é "Módulos" (ex.: a documentação da API) não saem dele. */
  protected podeMudarDeGrupo(l: Linha): boolean {
    const pai = this.linhas().find((x) => x.id === l.paiId);
    return l.tipo !== 'grupo' && !l.grupoDoCodigo && !(pai?.grupoDoCodigo && pai.id !== 'modulos');
  }

  protected renomear(l: Linha, texto: string): void {
    l.rotulo = texto;
  }

  protected mudarGrupo(l: Linha, paiId: string): void {
    // O item vai para o fim do grupo escolhido
    this.linhas.set([...this.linhas().filter((x) => x.id !== l.id), { ...l, paiId: paiId || null }]);
  }

  /** Troca o item de lugar com o vizinho do mesmo grupo (acima ou abaixo). */
  protected mover(l: Linha, passo: -1 | 1): void {
    const todas = [...this.linhas()];
    const irmaos = todas.filter((x) => x.paiId === l.paiId);
    const outro = irmaos[irmaos.indexOf(l) + passo];
    if (!outro) return;
    const a = todas.indexOf(l);
    const b = todas.indexOf(outro);
    [todas[a], todas[b]] = [todas[b], todas[a]];
    this.linhas.set(todas);
  }

  protected adicionar(): void {
    const ehLink = this.novoTipo === 'link';
    const id = `${ehLink ? 'l' : 'g'}-${Date.now().toString(36)}`;
    const novaAba = this.novoAba === 'auto' ? null : this.novoAba === 'nova';
    this.linhas.set([...this.linhas(), { id, tipo: this.novoTipo, rotuloPadrao: null, rotulo: this.novoNome.trim(), paiId: null, oculto: false, url: ehLink ? this.novoUrl.trim() : '', novaAba, grupoDoCodigo: false }]);
    this.novoNome = this.novoUrl = '';
    this.novoAba = 'auto';
  }

  /** Exclui o grupo ou link; os itens de um grupo excluído sobem para o primeiro nível. */
  protected remover(l: Linha): void {
    if (!confirm(`Excluir "${l.rotulo}" do menu?`)) return;
    this.linhas.set(this.linhas().filter((x) => x.id !== l.id).map((x) => (x.paiId === l.id ? { ...x, paiId: null } : x)));
  }

  protected salvar(): void {
    const itens: NoMenu[] = this.linhas().map((l) => {
      const no: NoMenu = { id: l.id, tipo: l.tipo };
      const nome = l.rotulo.trim();
      if (l.tipo !== 'modulo' || (nome && nome !== l.rotuloPadrao)) no.rotulo = nome;
      if (l.paiId) no.pai_id = l.paiId;
      if (l.oculto) no.oculto = true;
      if (l.tipo === 'link') {
        no.url = l.url;
        if (l.novaAba !== null) no.nova_aba = l.novaAba;
      }
      return no;
    });
    this.salvando.set(true);
    this.servico.gravar(itens).subscribe({
      next: () => {
        this.salvando.set(false);
        this.avisar('Menu salvo. Já vale para todos (quem está com o sistema aberto vê ao recarregar).');
      },
      error: (e) => {
        this.salvando.set(false);
        this.avisar(erroExibivel(e).mensagem, true);
      },
    });
  }

  protected restaurar(): void {
    if (!confirm('Voltar ao menu padrão? A ordem, os grupos, os links e os itens ocultos que você definiu serão apagados.')) return;
    this.servico.restaurar().subscribe({
      next: () => {
        this.avisar('Menu padrão restaurado.');
        this.carregar();
      },
      error: (e) => this.avisar(erroExibivel(e).mensagem, true),
    });
  }

  private avisar(texto: string, erro = false): void {
    this.aviso.set({ texto, erro });
  }
}
