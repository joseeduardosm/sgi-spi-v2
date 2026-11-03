// Criado por José Eduardo Santana Martins
// Este arquivo serve para abrir um chamado: escolher a categoria em cartões e preencher título, descrição e anexos.

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { EditorRicoComponent } from '../contratacoes/editor-rico.component';
import { CabecalhoChamadosComponent } from './cabecalho-chamados.component';
import { RedeApiService } from '../rede/rede-api.service';
import { ChamadoService } from '../../core/chamados/chamado.service';
import { ChamadosApiService } from './chamados-api.service';
import { OpcaoSala } from '../patrimonio/patrimonio-estado.service';
import { SeletorSalaComponent } from '../patrimonio/seletor-sala.component';
import { campoVisivel, CategoriaCatalogo, ChamadoRelacionavel, LocalResumo, SetorResumo, tamanhoLegivel, TipoChamado } from './chamados.models';

// Formatos aceitos pelos anexos gerais do SGI
const FORMATOS = '.pdf,.docx,.xlsx,.pptx,.odt,.ods,.odp,.doc,.xls,.ppt,.png,.jpg,.jpeg,.txt,.csv';

@Component({
  selector: 'app-novo-chamado',
  imports: [FormsModule, RouterLink, CabecalhoChamadosComponent, EditorRicoComponent, EsqueletoComponent, SeletorSalaComponent],
  template: `
    <div class="modulo-chamados">
      <app-cabecalho-chamados titulo="Abrir chamado" descricao="Escolha o assunto e conte o que aconteceu. A equipe certa recebe na hora." />
      @if (redePorta) {
        <p class="aviso-formulario" role="status">Chamado da porta <strong>{{ nomePorta() || 'de rede escolhida' }}</strong>: escolha o assunto (ex.: Rede e Internet) e conte o que acontece. O chamado já vai ligado à porta.</p>
      }
      @if (aPartirDe(); as data) {
        <!-- "A partir de": antes da data, só quem administra abre aqui; os demais seguem no GLPI -->
        <p class="aviso-formulario" role="status">Os chamados passam a ser abertos aqui a partir de <strong>{{ data }}</strong>. Até lá, abra pelo GLPI.
          <button type="button" class="acao-primaria acao-pequena" (click)="abrirNoGlpi()">Abrir chamado no GLPI</button></p>
      }
      <section class="painel-gestao protocolo">
        @if (carregando()) {
          <app-esqueleto tipo="cartao" [linhas]="2" />
        } @else if (!escolhida()) {
          <div class="barra-protocolo">
            <div class="campo"><label for="nc-busca">Buscar assunto</label>
              <input id="nc-busca" type="search" placeholder="Ex.: senha, impressora, crachá" [ngModel]="busca()" (ngModelChange)="busca.set($event)" /></div>
            @if (pai(); as p) {
              <span class="espacador"></span>
              <button type="button" class="acao-secundaria" (click)="subir()">Voltar para {{ p.pai_id ? nomeDe(p.pai_id) : 'todos os assuntos' }}</button>
            }
          </div>
          @if (pai(); as p) { <p class="dica-formulario">{{ p.caminho }}: escolha um item abaixo ou use a própria categoria.</p> }
          <ul class="catalogo-chamados" aria-label="Categorias">
            @if (pai(); as p) {
              <li><button type="button" class="cartao-categoria" (click)="escolher(p)"><strong>{{ p.nome }}</strong><small>Usar esta categoria · {{ p.setor_nome }}</small></button></li>
            }
            @for (c of visiveis(); track c.id) {
              <li><button type="button" class="cartao-categoria" (click)="abrirNo(c)">
                <strong>{{ busca() ? c.caminho : c.nome }}</strong>
                <small>{{ temFilhas(c) ? 'Ver opções' : c.setor_nome }}</small>
              </button></li>
            } @empty {
              <li class="estado-vazio">{{ busca() ? 'Nenhum assunto encontrado com essa busca.' : 'Nenhuma categoria disponível. Avise a administração dos Chamados.' }}</li>
            }
          </ul>
        } @else {
          <form class="grade-formulario" (ngSubmit)="enviar()" #f="ngForm">
            <div class="ocupa-duas categoria-escolhida">
              <span>{{ escolhida()!.caminho }}<small>{{ escolhida()!.setor_nome }}</small></span>
              <button type="button" class="acao-secundaria acao-pequena" (click)="trocar()">Trocar assunto</button>
            </div>
            <div class="ocupa-duas"><label for="nc-titulo">Título</label>
              <input id="nc-titulo" name="titulo" required minlength="3" maxlength="250" placeholder="Resuma em uma frase" [(ngModel)]="titulo" /></div>
            <div class="ocupa-duas"><label for="nc-local">Onde podemos te encontrar? <small>(sala)</small></label>
              <app-seletor-sala idCampo="nc-local" nome="local" rotulo="Onde podemos te encontrar?" placeholder="Digite o código ou o nome da sala (ex.: 05A03)"
                [opcoes]="salas()" [(valor)]="localId" />
              <small class="dica-formulario">@if (sugerido() && localId === sugerido()!.id) { Já veio com a sua sala pelo Patrimônio; troque se estiver em outro lugar. }
                @else { A equipe usa a sala para ir até você. }</small>
            </div>
            <div class="ocupa-duas editor-chamado"><label for="nc-descricao">Descrição</label>
              @defer (on viewport) { <app-editor-rico id="nc-descricao" [(html)]="descricao" rotulo="Descrição do chamado" [colarFormatado]="true" /> }
              @placeholder { <app-esqueleto tipo="formulario" [linhas]="3" /> }
            </div>
            <!-- Campos adicionais da categoria (os herdados primeiro); o que tem condição só aparece com a resposta certa -->
            @for (campo of camposVisiveis(); track campo.id) {
              <div [class.ocupa-duas]="campo.tipo === 'texto_longo'">
                <label [for]="'nc-campo-' + campo.id">{{ campo.rotulo }}@if (!campo.obrigatorio) { <small> (opcional)</small> }</label>
                @switch (campo.tipo) {
                  @case ('texto_longo') {
                    <textarea [id]="'nc-campo-' + campo.id" [name]="'campo-' + campo.id" rows="3" maxlength="4000" [required]="campo.obrigatorio"
                      [ngModel]="respostas()[campo.id] ?? ''" (ngModelChange)="responder(campo.id, $event)"></textarea>
                  }
                  @case ('lista') {
                    <select [id]="'nc-campo-' + campo.id" [name]="'campo-' + campo.id" [required]="campo.obrigatorio"
                      [ngModel]="respostas()[campo.id] ?? ''" (ngModelChange)="responder(campo.id, $event)">
                      <option value="">Escolha</option>
                      @for (o of campo.opcoes ?? []; track o) { <option [value]="o">{{ o }}</option> }
                    </select>
                  }
                  @case ('sim_nao') {
                    <select [id]="'nc-campo-' + campo.id" [name]="'campo-' + campo.id" [required]="campo.obrigatorio"
                      [ngModel]="respostas()[campo.id] ?? ''" (ngModelChange)="responder(campo.id, $event)">
                      <option value="">Escolha</option><option value="Sim">Sim</option><option value="Não">Não</option>
                    </select>
                  }
                  @default {
                    <input [id]="'nc-campo-' + campo.id" [name]="'campo-' + campo.id" [required]="campo.obrigatorio"
                      [type]="campo.tipo === 'numero' ? 'number' : campo.tipo === 'data' ? 'date' : 'text'" [maxlength]="campo.tipo === 'texto' ? 300 : 4000"
                      [ngModel]="respostas()[campo.id] ?? ''" (ngModelChange)="responder(campo.id, $event)" />
                  }
                }
                @if (campo.ajuda || campo.dado_pessoal) {
                  <small class="dica-formulario">{{ campo.ajuda }}@if (campo.dado_pessoal) { {{ campo.ajuda ? ' · ' : '' }}Dado pessoal: aparece mascarado para os outros. }</small>
                }
              </div>
            }
            <div><label for="nc-relacionado">Chamado relacionado <small>(opcional)</small></label>
              <select id="nc-relacionado" name="relacionado" [(ngModel)]="relacionadoId">
                <option [ngValue]="null">Nenhum</option>
                @for (r of relacionaveis(); track r.id) { <option [ngValue]="r.id">#{{ r.numero }} · {{ r.titulo }}</option> }
              </select>
              @if (!relacionaveis().length) { <small class="dica-formulario">Você ainda não tem chamados.</small> }
            </div>
            @if (escolhida()!.perguntar_impedindo) {
              <fieldset class="ocupa-duas"><legend class="rotulo-campo">Isso está impedindo você de trabalhar?</legend>
                <div class="opcoes-sim-nao">
                  <label><input type="radio" name="impedindo" [value]="true" [(ngModel)]="impedindo" /> Sim</label>
                  <label><input type="radio" name="impedindo" [value]="false" [(ngModel)]="impedindo" /> Não</label>
                </div></fieldset>
            }
            @if (setores().length) {
              <div class="ocupa-duas"><label for="nc-setor">Em nome de um setor (opcional)</label>
                <select id="nc-setor" name="setor" [(ngModel)]="setorSolicitante">
                  <option [ngValue]="null">Só em meu nome</option>
                  @for (s of setores(); track s.id) { <option [ngValue]="s.id">{{ s.caminho }}</option> }
                </select>
                <small class="dica-formulario">Todos do setor recebem os avisos do chamado, inclusive por e-mail.</small></div>
            }
            <div class="ocupa-duas">
              @if (arquivos().length) {
                <ul class="arquivos-chamado">
                  @for (a of arquivos(); track $index) {
                    <li>{{ a.name }} <small>{{ tamanho(a.size) }}</small>
                      <button type="button" class="acao-secundaria acao-pequena" [attr.aria-label]="'Remover ' + a.name" (click)="remover($index)">Remover</button></li>
                  }
                </ul>
              }
            </div>
            <div class="ocupa-duas acoes-formulario">
              <label class="acao-secundaria botao-arquivo">Anexar arquivos
                <input type="file" multiple [accept]="formatos" (change)="escolherArquivos($event)" /></label>
              <a class="acao-secundaria" routerLink="/chamados/meus">Cancelar</a>
              <button type="submit" class="acao-primaria" [class.carregando]="enviando()" [disabled]="f.invalid || enviando() || !temTexto()">Abrir chamado</button>
            </div>
          </form>
        }
      </section>
    </div>
  `,
})
export class NovoChamadoComponent implements OnInit {
  private readonly api = inject(ChamadosApiService);
  private readonly chamadoGlpi = inject(ChamadoService);
  /** Data "a partir de" (dd/mm/aaaa) quando ainda não chegou e a pessoa não administra: a tela avisa e oferece o GLPI. */
  protected readonly aPartirDe = signal<string | null>(null);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  /** Aberto pelo "Abrir chamado desta porta" do plano de face: a porta vai junto (`?rede_porta=`). */
  protected readonly redePorta = inject(ActivatedRoute).snapshot.queryParamMap.get('rede_porta');
  /** "SW-05A · porta 5", lido do plano de face (só quem tem acesso à Rede chega por esse link). */
  protected readonly nomePorta = signal('');
  private readonly rede = inject(RedeApiService);

  protected readonly formatos = FORMATOS;
  protected readonly carregando = signal(true);
  protected readonly enviando = signal(false);
  protected readonly categorias = signal<CategoriaCatalogo[]>([]);
  protected readonly setores = signal<SetorResumo[]>([]);
  protected readonly pai = signal<CategoriaCatalogo | null>(null);
  protected readonly escolhida = signal<CategoriaCatalogo | null>(null);
  protected readonly busca = signal('');
  protected readonly arquivos = signal<File[]>([]);

  protected readonly respostas = signal<Record<string, string>>({});
  /** Todas as salas ativas do Patrimônio, no formato do seletor de sala (agrupadas por andar). */
  protected readonly salas = signal<OpcaoSala[]>([]);
  protected readonly sugerido = signal<LocalResumo | null>(null);
  protected readonly relacionaveis = signal<ChamadoRelacionavel[]>([]);
  /** Sala escolhida ('' = não informada). */
  protected localId = '';
  protected relacionadoId: string | null = null;

  /** Campos da categoria escolhida que aparecem com as respostas atuais (condição "mostrar se"). */
  protected readonly camposVisiveis = computed(() => (this.escolhida()?.campos ?? []).filter((c) => campoVisivel(c, this.respostas())));

    protected titulo = '';
  protected descricao = '';
  protected tipo: TipoChamado = 'incidente';
  protected impedindo: boolean | null = null;
  protected setorSolicitante: number | null = null;
  protected tamanho = tamanhoLegivel;

  /** Categorias do nível atual, ou todas as que batem com a busca (pelo caminho). */
  protected readonly visiveis = computed(() => {
    const termo = normalizar(this.busca());
    if (termo) return this.categorias().filter((c) => normalizar(c.caminho).includes(termo)).slice(0, 30);
    const paiId = this.pai()?.id ?? null;
    return this.categorias().filter((c) => c.pai_id === paiId);
  });

  /** Antes da data: abre o formulário do GLPI (o mesmo do "Abrir chamado" do sistema). */
  protected abrirNoGlpi(): void {
    this.chamadoGlpi.modalAberto.set(true);
  }

  ngOnInit(): void {
    if (this.redePorta) this.rede.porta(this.redePorta).subscribe({ next: (p) => this.nomePorta.set(`${p.equipamento_nome} · porta ${p.nome || p.numero_logico}`), error: () => undefined });
    this.api.contexto().subscribe({
      next: (c) => {
        this.setores.set(c.setores_do_usuario);
        if (c.inicio_atendimento && !c.atendimento_aberto && !c.papeis.administrar) {
          this.aPartirDe.set(c.inicio_atendimento.split('-').reverse().join('/'));
        }
      },
    });
    // Sala sugerida pelo Patrimônio (já vem escolhida) e os chamados do próprio solicitante, para o relacionado
    this.api.contextoAbertura().subscribe({
      next: (c) => {
        this.relacionaveis.set(c.relacionaveis);
        this.sugerido.set(c.local_sugerido);
        if (c.local_sugerido) this.localId = c.local_sugerido.id;
      },
    });
    this.api.locais('', 2000).subscribe({
      next: (lista) => this.salas.set(lista.map((l) => ({ id: l.id, codigo: l.codigo ?? null, rotulo: l.rotulo, andar: l.andar ?? null, ativo: true, deposito: false, semResponsavel: false }))),
    });
    this.api.catalogo().subscribe({
      next: (c) => {
        this.categorias.set(c);
        this.carregando.set(false);
      },
      error: (e) => {
        this.carregando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível carregar as categorias');
      },
    });
  }

  protected temFilhas(c: CategoriaCatalogo): boolean {
    return this.categorias().some((x) => x.pai_id === c.id);
  }

  protected nomeDe(id: string): string {
    return this.categorias().find((c) => c.id === id)?.nome ?? '';
  }

  /** Categoria com subcategorias abre o nível seguinte; sem subcategorias, já é a escolhida. */
  protected abrirNo(c: CategoriaCatalogo): void {
    this.busca.set('');
    if (this.temFilhas(c)) this.pai.set(c);
    else this.escolher(c);
  }

  protected subir(): void {
    const atual = this.pai();
    this.pai.set(atual?.pai_id ? (this.categorias().find((c) => c.id === atual.pai_id) ?? null) : null);
  }

  protected escolher(c: CategoriaCatalogo): void {
    this.escolhida.set(c);
    // O tipo não é perguntado: vem da categoria (incidente, a menos que ela só aceite requisição)
    this.tipo = c.permite_incidente ? 'incidente' : 'requisicao';
  }

  protected trocar(): void {
    this.escolhida.set(null);
    this.respostas.set({});
  }

  protected responder(campoId: string, valor: string | number | null): void {
    this.respostas.update((r) => ({ ...r, [campoId]: valor == null ? '' : String(valor) }));
  }

  protected escolherArquivos(evento: Event): void {
    const campo = evento.target as HTMLInputElement;
    this.arquivos.update((lista) => [...lista, ...Array.from(campo.files ?? [])].slice(0, 10));
    campo.value = '';
  }

  protected remover(indice: number): void {
    this.arquivos.update((lista) => lista.filter((_, i) => i !== indice));
  }

  /** O editor vazio devolve `<p></p>`: só vale com texto de verdade (ou com uma imagem colada). */
  protected temTexto(): boolean {
    return this.descricao.replace(/<[^>]*>/g, '').trim().length > 0 || /<img\b/i.test(this.descricao);
  }

  protected enviar(): void {
    const categoria = this.escolhida();
    if (!categoria) return;
    this.enviando.set(true);
    const dados = {
      titulo: this.titulo.trim(), descricao: this.descricao, categoria_id: categoria.id, tipo: this.tipo,
      impedindo_trabalho: categoria.perguntar_impedindo ? this.impedindo : null, setor_solicitante_id: this.setorSolicitante,
      relacionado_id: this.relacionadoId, localizacao_id: this.localId || null, rede_porta_id: this.redePorta,
      // Só as respostas dos campos que estão aparecendo
      campos: Object.fromEntries(this.camposVisiveis().map((c) => [c.id, this.respostas()[c.id] ?? '']).filter(([, v]) => v !== '')),
    };
    this.api.abrir(dados, this.arquivos()).subscribe({
      next: (c) => {
        this.enviando.set(false);
        void this.roteador.navigate(['/chamados', c.numero], { queryParams: { aberto: 1 } });
      },
      error: (e) => {
        this.enviando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível abrir o chamado');
      },
    });
  }
}

/** Sem acentos e em minúsculas, para a busca achar "credito" em "Crédito". */
function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}
