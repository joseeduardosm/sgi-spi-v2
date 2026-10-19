// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar, justificar, enviar e aprovar uma lista de inservíveis ou extraviados.
import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { EditorRicoComponent } from '../contratacoes/editor-rico.component';
import { DescricaoTarefaPipe } from '../tarefas/descricao-tarefa.pipe';
import { classeMarcador } from '../tarefas/marcadores.paleta';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { FilaOfflineService } from './fila-offline.service';
import { LeitorCodigoComponent } from './leitor-codigo.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { BuscaBemComponent } from './busca-bem.component';
import { Bem, CATEGORIAS_INSERVIVEL, CategoriaInservivel, Classificacao, ItemClassificacao, COR_STATUS, ROTULOS_STATUS, rotuloCategoria } from './patrimonio.models';
import { RelacionarSalaComponent } from './relacionar-sala.component';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
/** `/patrimonio/inserviveis/:classificacaoId` ou `/patrimonio/extraviados/:classificacaoId` (conforme o tipo da lista). */
@Component({
  selector: 'app-lista-classificacao',
  imports: [EsqueletoComponent, FormsModule, RouterLink, CabecalhoPatrimonioComponent, LeitorCodigoComponent, RelacionarSalaComponent, BuscaBemComponent, EditorRicoComponent, DescricaoTarefaPipe, SeletorUsuariosComponent],
  template: `
    <app-cabecalho-patrimonio [titulo]="lista() ? (lista()!.tipo === 'inservivel' ? 'Lista de inservíveis' : 'Lista de extraviados') : 'Lista'" descricao="Só entram bens cadastrados e Ativos ou Em manutenção." />
    @if (lista(); as c) {
      <section class="painel-gestao patrimonio">
        <div class="pat-topo-bem">
          <span class="pat-marcadores"><b class="texto-codigo">#{{ c.numero }}</b><span [class]="marcador(cores[c.status])">{{ rotulos[c.status] }}</span><span [class]="marcador(0)">{{ c.solicitante_nome }}</span></span>
          <div class="pat-acoes">
            <button type="button" class="acao-secundaria" (click)="relatorio(c, 'pdf')" title="PDF consolidado: índice, relatório, fotos e anexos">Relatório PDF</button>
            <button type="button" class="acao-secundaria" (click)="relatorio(c, 'xlsx')">Relatório Excel</button>
            @if (souDono()) { <button type="button" class="acao-secundaria" (click)="abrirCompartilhar(c)">Compartilhar{{ c.colaboradores?.length ? ' (' + c.colaboradores!.length + ')' : '' }}</button> }
            @if (rascunho()) { <button type="button" class="acao-recusar" (click)="descartar()">Descartar rascunho</button> }
          </div>
        </div>

        @if (rascunho()) {
          <div class="pat-linha-campo">
            <app-busca-bem [(texto)]="chapa" nome="chapa" [placeholder]="c.tipo === 'inservivel' ? 'Pesquise por chapa, série, descrição, marca, modelo, local…' : 'Pesquise por chapa, série, descrição, marca, modelo, local…'" (escolhido)="incluirBem($event)" (enviar)="incluir($event)" />
            <button type="button" class="acao-secundaria" (click)="incluir(chapa)">Adicionar</button>
            <button type="button" class="acao-primaria" (click)="lendo.set(true)">Ler códigos</button>
          </div>
          <app-relacionar-sala modo="classificacao" (confirmado)="incluirVarios($event)" />
          @for (l of locais(); track l) { <p class="pat-aviso">Chapa {{ l }}: aguardando envio (sem conexão).</p> }
          @if (aviso()) { <p class="pat-aviso" role="alert">{{ aviso() }}</p> }
        }

        @if (c.colaboradores?.length) {
          <p class="pat-aviso pat-colaboradores">Compartilhada com: <strong>{{ nomesColaboradores(c) }}</strong>@if (!souDono() && rascunho()) { · montada por {{ c.solicitante_nome }} }. Quem recebe faz tudo na lista, mas não pode aprová-la.</p>
        }

        <!-- Rascunho: seleção dos bens (todos os visíveis), pesquisa só dentro da lista e o botão que abre a justificativa -->
        @if (rascunho() && c.itens.length) {
          <div class="pat-barra-selecao">
            <label class="pat-selecionar-todos"><input type="checkbox" class="pat-selecao" name="selecionar-todos" [checked]="todosVisiveisMarcados()" [indeterminate]="algunsVisiveisMarcados()" (change)="alternarTodosVisiveis($any($event.target).checked)" aria-label="Selecionar todos os bens visíveis" /> Selecionar todos</label>
            <input type="search" class="pat-busca-lista" name="busca-lista" placeholder="Pesquisar nos bens da lista (chapa, série, descrição, marca, modelo, sala, grupo…)" aria-label="Pesquisar nos bens da lista" [(ngModel)]="buscaLista" autocomplete="off" />
            @if (salasDaLista().length > 1) {
              <select class="pat-selecionar-sala" name="selecionar-sala" aria-label="Selecionar todos os bens de uma sala" [ngModel]="''" (ngModelChange)="selecionarSala($event)">
                <option value="">Selecionar a sala…</option>
                @for (sala of salasDaLista(); track sala.rotulo) { <option [value]="sala.rotulo">{{ sala.rotulo }} ({{ sala.total }})</option> }
              </select>
            }
            <span class="pat-contagem-selecao">{{ marcados().size }} selecionado(s){{ visiveis().length !== c.itens.length ? ' · ' + visiveis().length + ' de ' + c.itens.length + ' visíveis' : '' }}</span>
            <button type="button" class="acao-primaria" [disabled]="!marcados().size" (click)="abrirJustificativa()">Criar justificativa</button>
            <button type="button" class="acao-secundaria" [disabled]="!selecionadosComJustificativa(c).length" (click)="excluirJustificativas(c, selecionadosComJustificativa(c))" title="Apaga a justificativa dos bens selecionados que já têm uma">Excluir justificativa</button>
          </div>
        }

        <ul class="pat-lista-itens">
          @for (i of visiveis(); track i.id) {
            <li>
              @if (rascunho()) { <input type="checkbox" class="pat-selecao" [name]="'m' + i.id" [checked]="marcados().has(i.id)" (change)="alternar(i.id)" [attr.aria-label]="'Marcar ' + i.rotulo" /> }
              @else if (decidindo()) { <input type="checkbox" class="pat-selecao" [name]="'a' + i.id" [checked]="aprovados().has(i.id)" (change)="alternarAprovado(i.id)" [attr.aria-label]="'Aprovar ' + i.rotulo" /> }
              <div><strong class="texto-codigo">{{ i.rotulo }}</strong> <span>{{ i.descricao }}</span>@if (i.chapa && i.numero_serie) { <small>Série {{ i.numero_serie }}</small> }@if (i.marca || i.modelo) { <small>{{ i.marca }}{{ i.marca && i.modelo ? ' · ' : '' }}{{ i.modelo }}</small> }<small>{{ i.sala_rotulo }}</small>
                @if (i.categoria) { <span [class]="marcador(i.resultado === 'aprovado' ? 1 : 4)" [attr.title]="'Categoria do bem inservível'">Inservível · {{ rotuloCategoria(i.categoria) }}</span> }
                @if (i.justificativa) { <div class="pat-justificativa" [innerHTML]="i.justificativa | descricaoTarefa"></div> } @else if (rascunho()) { <small class="pat-sem-justificativa">Sem justificativa</small> }
                @if (i.anexo_nome) { <small><a href="javascript:void(0)" (click)="$event.preventDefault(); baixarAnexo(c.id, i.id)">{{ i.anexo_nome }}</a></small> }</div>
              <span class="pat-acoes">
                @if (i.resultado) { <span [class]="marcador(i.resultado === 'aprovado' ? 10 : 1)">{{ i.resultado === 'aprovado' ? 'Aprovado' : 'Recusado' }}</span> }
                @if (rascunho()) {
                  <label class="acao-secundaria acao-pequena pat-anexar">{{ c.tipo === 'inservivel' ? 'Foto' : 'Anexo' }}<input type="file" hidden [accept]="c.tipo === 'inservivel' ? 'image/*' : ''" (change)="anexar(c, i.id, $event)" /></label>
                  @if (i.justificativa) {
                    <button type="button" class="acao-secundaria acao-pequena" (click)="abrirJustificativa(i)">Editar justificativa</button>
                    <button type="button" class="acao-secundaria acao-pequena" (click)="excluirJustificativas(c, [i])">Excluir justificativa</button>
                  }
                  <button type="button" class="acao-recusar acao-pequena" (click)="tirar(c.id, i.id)">Tirar</button>
                }
              </span>
            </li>
          } @empty { <li class="estado-vazio">{{ c.itens.length ? 'Nenhum bem encontrado na pesquisa.' : 'Nenhum bem na lista.' }}</li> }
        </ul>

        @if (rascunho() && c.itens.length) {
          <div class="pat-barra-inferior">
            <button type="button" class="acao-primaria" [disabled]="semJustificar(c) > 0" (click)="enviar(c)">Enviar para aprovação</button>
          </div>
        }

        @if (compartilhando()) {
          <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="compartilhando.set(false)"></div>
          <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-compartilhar-lista">
            <header>
              <div><span class="modal-sobretitulo">Lista #{{ c.numero }}</span><h2 id="titulo-compartilhar-lista">Compartilhar a lista</h2></div>
              <button type="button" aria-label="Fechar" (click)="compartilhando.set(false)">×</button>
            </header>
            <form (submit)="$event.preventDefault(); salvarCompartilhamento(c)">
              <p class="dica-formulario" style="margin-top: 0">Quem receber a lista faz <strong>tudo o que você faz nela</strong>: incluir e tirar bens, justificar, anexar fotos, enviar para aprovação e descartar. Só não pode aprová-la, nem você.</p>
              <div class="grade-formulario">
                <div class="ocupa-duas">
                  <label for="compartilhar-usuarios">Pessoas ({{ colaboradoresEscolhidos().length }})</label>
                  <app-seletor-usuarios idCampo="compartilhar-usuarios" [(selecionados)]="colaboradoresEscolhidos" [fonte]="fonteUsuarios" textoAjuda="Pesquisar por nome ou login" />
                </div>
              </div>
              <footer>
                <button type="button" class="acao-secundaria" (click)="compartilhando.set(false)">Cancelar</button>
                <button type="submit" class="acao-primaria">Salvar</button>
              </footer>
            </form>
          </section>
        }

        @if (justificando()) {
          <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="fecharJustificativa()"></div>
          <section animate.leave="mov-modal-sai" class="modal-portal modal-justificativa" role="dialog" aria-modal="true" aria-labelledby="titulo-justificativa-lista">
            <header>
              <div><span class="modal-sobretitulo">Lista #{{ c.numero }}</span><h2 id="titulo-justificativa-lista">{{ editandoItem() ? 'Editar justificativa' : 'Criar justificativa' }}</h2></div>
              <button type="button" aria-label="Fechar" (click)="fecharJustificativa()">×</button>
            </header>
            <form (submit)="$event.preventDefault(); aplicarJustificativa(c)">
              <p class="dica-formulario" style="margin-top: 0">@if (editandoItem(); as e) { Editando a justificativa do bem <strong>{{ e.rotulo }}</strong>. } @else { Esta justificativa será gravada em cada um dos <strong>{{ alvos().length }}</strong> bem(ns) selecionado(s), substituindo a que já tiver. }</p>
              <div class="grade-formulario">
                @if (c.tipo === 'inservivel') {
                  <!-- Categoria do bem inservível (classificação do desfazimento): vale para todos os bens selecionados -->
                  <fieldset class="ocupa-duas pat-categorias">
                    <legend>Categoria do bem *</legend>
                    @for (cat of categorias; track cat.codigo) {
                      <label class="pat-categoria" [class.selecionada]="categoria === cat.codigo">
                        <input type="radio" name="categoria-inservivel" [value]="cat.codigo" [(ngModel)]="categoria" />
                        <span><b>{{ cat.rotulo }}</b><small>{{ cat.descricao }}</small></span>
                      </label>
                    }
                  </fieldset>
                }
                <div class="ocupa-duas">
                  <label>Justificativa *</label>
                  @defer (on idle) { <app-editor-rico [(html)]="justificativa" [colarFormatado]="true" rotulo="Justificativa dos bens" /> } @placeholder { <app-esqueleto tipo="formulario" [linhas]="4" /> }
                  <small class="dica-formulario" [class.texto-erro]="tamanhoJustificativa() > maximoJustificativa">{{ tamanhoJustificativa() }} / {{ maximoJustificativa }} caracteres (mínimo {{ minimoJustificativa }})</small>
                </div>
              </div>
              <footer>
                <button type="button" class="acao-secundaria" (click)="fecharJustificativa()">Cancelar</button>
                <button type="submit" class="acao-primaria" [disabled]="!justificativaValida() || (c.tipo === 'inservivel' && !categoria)">{{ editandoItem() ? 'Salvar justificativa' : 'Aplicar a ' + alvos().length + ' bem(ns)' }}</button>
              </footer>
            </form>
          </section>
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
  // Edita a lista (rascunho) quem a montou e quem recebeu a lista compartilhada: os poderes são os mesmos
  protected readonly rascunho = computed(() => {
    const l = this.lista();
    const eu = this.estado.acesso()?.usuario_id;
    return l?.status === 'rascunho' && (l.solicitante_id === eu || !!l.colaboradores?.some((x) => x.id === eu));
  });
  /** Só quem montou a lista escolhe com quem compartilhá-la. */
  protected readonly souDono = computed(() => this.lista()?.status === 'rascunho' && this.lista()?.solicitante_id === this.estado.acesso()?.usuario_id);
  protected readonly compartilhando = signal(false);
  protected readonly colaboradoresEscolhidos = signal<OpcaoUsuario[]>([]);
  protected readonly fonteUsuarios = (busca: string) => this.api.opcoesUsuarios(busca);
  protected readonly decidindo = computed(() => this.lista()?.status === 'pendente' && this.estado.podeAdministrar() && !this.souSolicitante(this.lista()!));
  protected chapa = '';
  protected justificativa = '';
  /** Pesquisa só dentro dos bens já incluídos (ajuda a marcar bens iguais entre vários). */
  private readonly buscaListaSinal = signal('');
  protected get buscaLista(): string { return this.buscaListaSinal(); }
  protected set buscaLista(valor: string) { this.buscaListaSinal.set(valor ?? ''); }
  protected readonly justificando = signal(false);
  /** Categorias do inservível e a escolhida no modal. */
  protected readonly categorias = CATEGORIAS_INSERVIVEL;
  protected readonly rotuloCategoria = rotuloCategoria;
  protected categoria: CategoriaInservivel | '' = '';
  protected readonly minimoJustificativa = 10;
  protected readonly maximoJustificativa = 2000;
  /** Bens da lista que combinam com a pesquisa (sem acento nem maiúsculas); sem pesquisa, todos. */
  protected readonly visiveis = computed(() => {
    const itens = this.lista()?.itens ?? [];
    const termo = this.normalizar(this.buscaListaSinal());
    if (!termo) return itens;
    // Cada palavra digitada precisa aparecer em alguma informação do bem ("notebook dell 05A01")
    const palavras = termo.split(/\s+/).filter(Boolean);
    return itens.filter((i) => {
      const texto = this.normalizar([i.rotulo, i.chapa, i.numero_serie, i.descricao, i.marca, i.modelo, i.grupo_nome, i.responsavel_nome, i.nota_fiscal, i.fornecedor, i.observacoes, i.sala_rotulo, this.textoPuro(i.justificativa)].join(' '));
      return palavras.every((palavra) => texto.includes(palavra));
    });
  });
  /** Salas que têm bens na lista, com a quantidade (para selecionar todos os bens de uma sala de uma vez). */
  protected readonly salasDaLista = computed(() => {
    const contagem = new Map<string, number>();
    for (const i of this.lista()?.itens ?? []) contagem.set(i.sala_rotulo, (contagem.get(i.sala_rotulo) ?? 0) + 1);
    return [...contagem.entries()].sort((a, b) => a[0].localeCompare(b[0], 'pt-BR', { numeric: true })).map(([rotulo, total]) => ({ rotulo, total }));
  });
  protected readonly todosVisiveisMarcados = computed(() => this.visiveis().length > 0 && this.visiveis().every((i) => this.marcados().has(i.id)));
  protected readonly algunsVisiveisMarcados = computed(() => !this.todosVisiveisMarcados() && this.visiveis().some((i) => this.marcados().has(i.id)));
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

  /** Texto sem acento, em minúsculas (para a pesquisa dentro da lista). */
  private normalizar(texto: string): string {
    return (texto ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
  }

  /** Texto puro de um HTML do editor rico (a justificativa dos bens vem em HTML). */
  protected textoPuro(html: string | null | undefined): string {
    if (!html) return '';
    return new DOMParser().parseFromString(html, 'text/html').body.textContent?.replace(/\u00a0/g, ' ').trim() ?? '';
  }

  /** Caracteres da justificativa digitada (sem as tags), que valem para o mínimo e o máximo. */
  protected readonly tamanhoJustificativa = () => this.textoPuro(this.justificativa).length;
  protected justificativaValida(): boolean {
    const n = this.tamanhoJustificativa();
    return n >= this.minimoJustificativa && n <= this.maximoJustificativa;
  }

  /** Marca (ou desmarca) todos os bens **visíveis** pela pesquisa, sem mexer nos que a pesquisa esconde. */
  protected alternarTodosVisiveis(marcar: boolean): void {
    this.marcados.update((s) => {
      const novo = new Set(s);
      for (const i of this.visiveis()) marcar ? novo.add(i.id) : novo.delete(i.id);
      return novo;
    });
  }

  protected nomesColaboradores(c: Classificacao): string {
    return (c.colaboradores ?? []).map((x) => x.nome).join(', ');
  }

  protected abrirCompartilhar(c: Classificacao): void {
    this.colaboradoresEscolhidos.set((c.colaboradores ?? []).map((x) => ({ id: x.id, login: '', nome_completo: x.nome, cargo: '', ativo: true })));
    this.compartilhando.set(true);
  }

  protected salvarCompartilhamento(c: Classificacao): void {
    this.api.compartilharClassificacao(c.id, this.colaboradoresEscolhidos().map((u) => u.id)).subscribe({
      next: (x) => { this.definir(x); this.compartilhando.set(false); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível compartilhar a lista'),
    });
  }

  /** Marca todos os bens da sala escolhida (somam-se aos já marcados). */
  protected selecionarSala(rotulo: string): void {
    if (!rotulo) return;
    this.marcados.update((s) => {
      const novo = new Set(s);
      for (const i of this.lista()?.itens ?? []) if (i.sala_rotulo === rotulo) novo.add(i.id);
      return novo;
    });
  }

  /** Bem cuja justificativa está sendo editada (nulo = criando para os bens selecionados). */
  protected readonly editandoItem = signal<ItemClassificacao | null>(null);
  /** Bens que recebem a justificativa do modal: o item em edição ou os selecionados. */
  protected readonly alvos = computed(() => (this.editandoItem() ? [this.editandoItem()!.id] : [...this.marcados()]));

  /** Abre o modal: sem `item`, cria para os selecionados; com `item`, edita a justificativa e a categoria já gravadas dele. */
  protected abrirJustificativa(item?: ItemClassificacao): void {
    this.editandoItem.set(item ?? null);
    this.justificativa = item?.justificativa ?? '';
    this.categoria = (item?.categoria as CategoriaInservivel | null | undefined) ?? '';
    this.justificando.set(true);
  }

  /** Dos bens selecionados, os que já têm justificativa (a exclusão em lote só vale para eles). */
  protected selecionadosComJustificativa(c: Classificacao): ItemClassificacao[] {
    return c.itens.filter((i) => this.marcados().has(i.id) && !!i.justificativa);
  }

  /** Apaga a justificativa (e a categoria) dos bens, depois de confirmar; eles voltam a "sem justificativa". */
  protected async excluirJustificativas(c: Classificacao, itens: ItemClassificacao[]): Promise<void> {
    if (!itens.length) return;
    const ok = await this.dialogos.confirmar({
      titulo: 'Excluir a justificativa?',
      mensagem: itens.length === 1 ? `A justificativa de ${itens[0].rotulo} será apagada e o bem fica sem justificativa até receber outra.` : `A justificativa de ${itens.length} bens será apagada e eles ficam sem justificativa até receberem outra.`,
      rotuloConfirmar: 'Excluir',
      perigo: true,
    });
    if (!ok) return;
    this.api.removerJustificativa(c.id, itens.map((i) => i.id)).subscribe({
      next: (x) => this.definir(x),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir a justificativa'),
    });
  }

  protected fecharJustificativa(): void {
    this.editandoItem.set(null);
    this.justificando.set(false);
  }

  /** Grava a justificativa digitada em cada bem selecionado. */
  protected aplicarJustificativa(c: Classificacao): void {
    if (!this.justificativaValida()) return;
    this.justificar(c);
  }

  protected justificar(c: Classificacao): void {
    this.api.justificar(c.id, this.alvos(), this.justificativa.trim(), c.tipo === 'inservivel' ? (this.categoria || null) : null).subscribe({
      next: (x) => { this.definir(x); if (!this.editandoItem()) this.marcados.set(new Set()); this.justificativa = ''; this.editandoItem.set(null); this.justificando.set(false); }, error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível justificar'),
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
