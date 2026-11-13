/**
 * =============================================================================
 * ARQUIVO: modelo-prorrogacao.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Página de detalhe de uma máscara da prorrogação (Contratos > Modelos):
 * escolhe qual documento do processo ela escreve, guarda o texto-base e mostra
 * os placeholders (#nome) que podem ser usados nesse texto.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template e estilos embutidos. Lê o id da URL
 * (input), carrega a lista de placeholders da prorrogação e, quando não é
 * "novo", procura a máscara na lista de modelos do tipo prorrogacao. O editor
 * rico (carregado com @defer) recebe os placeholders clicados no cursor. Ao
 * salvar, envia nome, ativo, variante e html para ContratosApiService.
 *
 * FINALIDADE DE NEGÓCIO:
 * Padroniza os sete documentos que o SGI gera no processo de prorrogação
 * (despachos, declarações, minuta do aditivo e termos do TCE-SP), evitando que
 * cada gestor redija do zero e garantindo que só dados conhecidos do contrato
 * sejam preenchidos automaticamente.
 *
 * CONTEXTO NO SISTEMA:
 * Rota filha de /contratos/modelos (ver modelos.component.ts). Usa
 * ContratosApiService (modelos, placeholdersProrrogacao, salvarModelo),
 * EditorRicoComponent do módulo Contratações e semAcento das Tarefas. O texto
 * salvo é usado pelo backend ao gerar os documentos da prorrogação.
 *
 * =============================================================================
 */

import { Component, inject, input, OnInit, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { EditorRicoComponent } from '../../contratacoes/editor-rico.component';
import { semAcento } from '../../tarefas/marcadores.paleta';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { Modelo, PlaceholderPortaria, VarianteProrrogacao } from '../compartilhado/contratos.models';

import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
/**
 * Página da máscara da prorrogação (`/contratos/modelos/prorrogacao/novo` ou `.../prorrogacao/:id`): minutas, declarações e despachos do processo. O editor ocupa a largura toda e a lista de
 * placeholders fica ao lado, sempre visível; a barra de ações fica fixa no pé da página. A API só aceita os placeholders da lista.
 */
@Component({
  selector: 'app-modelo-prorrogacao',
  imports: [EsqueletoComponent, FormsModule, RouterLink, CabecalhoModuloComponent, EditorRicoComponent],
  template: `
    <app-cabecalho-modulo [titulo]="id() === 'novo' ? 'Nova máscara da prorrogação' : 'Máscara da prorrogação'" [trilha]="['Modelos', 'Prorrogação']"
      descricao="Texto-base de um documento do processo de prorrogação. Os placeholders (#nome) são trocados pelos dados do contrato e da prorrogação; o que faltar aparece entre colchetes." />

    @if (carregando()) {
      <app-esqueleto tipo="formulario" [linhas]="5" />
    } @else {
      <form class="pagina-mascara" (ngSubmit)="salvar()">
        <section class="cartao-dados dados-mascara">
          <div class="grade-formulario">
            <div><label for="mascara-nome">Nome *</label><input id="mascara-nome" name="nome" required maxlength="300" [(ngModel)]="nome" /></div>
            <div><label for="mascara-variante">Documento *</label>
              <select id="mascara-variante" name="variante" [(ngModel)]="variante">
                @for (v of variantes; track v.id) { <option [value]="v.id">{{ v.rotulo }}</option> }
              </select></div>
            <div class="linha-caixas ocupa-duas"><label><input type="checkbox" name="ativo" [(ngModel)]="ativo" /> Ativa (só uma máscara ativa por documento)</label></div>
          </div>
        </section>

        <div class="corpo-mascara">
          <section class="cartao-dados editor-mascara" aria-labelledby="titulo-texto-mascara">
            <header><h2 id="titulo-texto-mascara">Texto do documento</h2></header>
            @defer (on idle) { <app-editor-rico [(html)]="html" rotulo="Texto da máscara da prorrogação" /> } @placeholder { <app-esqueleto tipo="formulario" [linhas]="3" /> }
          </section>
          <aside class="cartao-dados placeholders-mascara" aria-labelledby="titulo-placeholders">
            <header><div><h2 id="titulo-placeholders">Placeholders permitidos</h2>
              <small>Clique para inserir no cursor. Qualquer outro <code>#</code> impede salvar.</small></div></header>
            <div class="busca-placeholders"><input type="search" name="busca-placeholder" autocomplete="off" placeholder="Pesquisar placeholder…" aria-label="Pesquisar placeholder" [ngModel]="busca()" (ngModelChange)="busca.set($event)" /></div>
            <ul>
              @for (p of placeholdersFiltrados(); track p.nome) {
                <li><button type="button" class="acao-secundaria acao-pequena texto-codigo" (click)="inserir(p)">#{{ p.nome }}</button><small>{{ p.descricao }}</small></li>
              } @empty { <li><small>Nenhum placeholder encontrado.</small></li> }
            </ul>
          </aside>
        </div>

        <footer class="acoes-mascara">
          <a class="acao-secundaria" routerLink="/contratos/modelos">Voltar aos modelos</a>
          <button [class.carregando]="salvando()" type="submit" class="acao-primaria" [disabled]="salvando() || !nome.trim() || !html.trim()">Salvar máscara</button>
        </footer>
      </form>
    }
  `,
  styles: `
    .pagina-mascara { display: grid; gap: 16px; }
    .dados-mascara { padding: 16px 20px 0; }
    .corpo-mascara { display: grid; grid-template-columns: minmax(0, 1fr) 270px; gap: 16px; align-items: start; }
    .editor-mascara { padding-bottom: 16px; }
    .editor-mascara > header, .placeholders-mascara > header { padding: 14px 20px 8px; }
    .editor-mascara app-editor-rico { display: block; margin: 0 20px; }
    :host ::ng-deep .editor-mascara .editor-rico .superficie-editor { min-height: max(420px, calc(100vh - 430px)); font-size: 14px; line-height: 1.6; }
    .placeholders-mascara { position: sticky; top: 12px; max-height: min(520px, calc(100vh - 100px)); overflow: auto; padding-bottom: 12px; }
    .busca-placeholders { padding: 0 20px 10px; }
    .placeholders-mascara ul { display: grid; gap: 10px; margin: 0; padding: 0 20px; list-style: none; }
    .placeholders-mascara li { display: grid; gap: 4px; }
    .placeholders-mascara li button { justify-self: start; }
    .placeholders-mascara li small { color: var(--spi-apagado); }
    .acoes-mascara { position: sticky; bottom: 0; z-index: 20; display: flex; justify-content: flex-end; gap: 10px; padding: 12px 20px;
      border-top: 1px solid var(--cor-e2e5e8); background: var(--cor-ffffff); }
    @media (max-width: 1000px) { .corpo-mascara { grid-template-columns: 1fr; } .placeholders-mascara { position: static; max-height: none; } }
  `,
})
export class ModeloProrrogacaoComponent implements OnInit {
  /** `novo` ou o id da máscara (vem da URL). `input` declara uma entrada do componente; com o roteador configurado, o parâmetro da rota chega aqui. */
  readonly id = input.required<string>();

  // `inject` pega do Angular as instâncias dos serviços (injeção de dependência),
  // sem precisar declará-las no construtor.
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  private readonly editor = viewChild(EditorRicoComponent);

  // `signal` guarda um valor reativo: quando muda com `.set`, o template que o lê
  // é redesenhado. Os campos simples (nome, ativo, variante, html) usam ngModel.
  protected readonly carregando = signal(true);
  protected readonly salvando = signal(false);
  protected readonly placeholders = signal<PlaceholderPortaria[]>([]);
  protected readonly busca = signal('');
  protected nome = '';
  protected ativo = true;
  protected variante: VarianteProrrogacao = 'minuta_aditivo';
  /** Os sete documentos que o SGI escreve para o processo da prorrogação. */
  protected readonly variantes: { id: VarianteProrrogacao; rotulo: string }[] = [
    { id: 'despacho_instrucao', rotulo: 'Despacho de instrução (CCC/DGA → SSGC)' },
    { id: 'declaracao_atendimento_licitacao', rotulo: 'Declaração de Atendimento — contrato de licitação (Anexo II)' },
    { id: 'declaracao_atendimento_direta', rotulo: 'Declaração de Atendimento — dispensa ou inexigibilidade (Anexo III)' },
    { id: 'minuta_aditivo', rotulo: 'Minuta do Termo de Aditamento (Anexo I)' },
    { id: 'termo_ciencia', rotulo: 'Termo de Ciência e de Notificação (TCE-SP)' },
    { id: 'declaracao_tce', rotulo: 'Declaração de documentos à disposição do TCE-SP' },
    { id: 'despacho_autorizacao', rotulo: 'Despacho de autorização da prorrogação' },
  ];
  protected html = '';

  /**
   * Carrega os dados da tela ao abrir.
   * - Sempre busca a lista de placeholders permitidos (a API recusa outros).
   * - Para "novo", não há o que carregar: só libera o formulário.
   * - Para um id, procura a máscara na lista de modelos da prorrogação; se não
   *   existir (id inválido ou apagado), volta para a lista de modelos.
   * `subscribe` é como se "assina" um Observable do HttpClient: a requisição só
   * sai quando alguém assina, e `next`/`error` recebem a resposta ou a falha.
   */
  ngOnInit(): void {
    this.api.placeholdersProrrogacao().subscribe({ next: (p) => this.placeholders.set(p), error: (e) => this.dialogos.mostrarErro(e) });
    if (this.id() === 'novo') {
      this.carregando.set(false);
      return;
    }
    this.api.modelos('prorrogacao', false).subscribe({
      next: (lista) => {
        const modelo = lista.find((m) => m.id === this.id());
        if (modelo) this.aplicar(modelo);
        else void this.roteador.navigate(['/contratos/modelos']);
        this.carregando.set(false);
      },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar a máscara'); },
    });
  }

  /** Copia os dados da máscara carregada para os campos do formulário (variante padrão: minuta do aditivo). */
  private aplicar(modelo: Modelo): void {
    this.nome = modelo.nome;
    this.ativo = modelo.ativo;
    this.variante = (modelo.conteudo.variante as VarianteProrrogacao) ?? 'minuta_aditivo';
    this.html = modelo.conteudo.html ?? '';
  }

  /** A pesquisa casa o nome ou a descrição (sem acento). */
  protected placeholdersFiltrados(): PlaceholderPortaria[] {
    const termo = semAcento(this.busca().trim().replace(/^#/, ''));
    return this.placeholders().filter((p) => !termo || semAcento(`${p.nome} ${p.descricao}`).includes(termo));
  }

  /** Insere `#nome` do placeholder clicado na posição do cursor do editor rico (se o editor já tiver sido carregado). */
  protected inserir(placeholder: PlaceholderPortaria): void {
    this.editor()?.inserir(`#${placeholder.nome}`);
  }

  /**
   * Grava a máscara: cria uma nova (id "novo") ou atualiza a existente.
   * Em caso de sucesso volta para a lista de modelos; em erro, mostra a mensagem
   * da API (por exemplo, placeholder não permitido) e libera o botão.
   */
  protected salvar(): void {
    this.salvando.set(true);
    const dados = { tipo: 'prorrogacao', nome: this.nome.trim(), ativo: this.ativo, variante: this.variante, html: this.html };
    this.api.salvarModelo(dados, this.id() === 'novo' ? undefined : this.id()).subscribe({
      next: () => void this.roteador.navigate(['/contratos/modelos']),
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível salvar a máscara'); },
    });
  }
}
