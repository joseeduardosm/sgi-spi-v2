// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela Administração › Versões: na homologação, atualizar pelo ramo do GitHub e aprovar a versão; na produção,
// instalar uma versão aprovada. A atualização roda no servidor (backup, código, dependências, migrações, build, reinício) e volta sozinha se falhar.

import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ambiente } from '../../../../environments/ambiente';
import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
import { TrilhaComponent } from '../../../shared/componentes/trilha/trilha.component';
import { EtapaTrilha, TrilhaEtapasComponent } from '../../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';

interface Commit { commit: string; titulo: string; autor: string; data: string }
interface VersaoAprovada { alvo: string; aprovada_por: string | null; aprovada_em: string | null; mensagem: string; novidades: string; commits: Commit[] }
interface Andamento {
  operacao: 'atualizar' | null;
  situacao: 'em_andamento' | 'concluido' | 'erro' | 'reiniciando' | null;
  mensagem: string;
  etapa: string | null;
  percentual: number | null;
  de: string | null;
  para: string | null;
  voltou: boolean | null;
  atualizado_em: string | null;
}
interface PainelVersoes {
  homologacao: boolean; versao: string; versao_no_disco: string; commit: string; arvore_limpa: boolean; ramo: string; aprovada: string | null;
  commits_novos: Commit[]; versoes: VersaoAprovada[]; andamento: Andamento; log: string;
}

/** Etapas da atualização, na ordem em que o servidor passa por elas (as mesmas do scripts/atualizar-versao.py). */
const ETAPAS: { id: string; rotulo: string }[] = [
  { id: 'conferir', rotulo: 'Conferir' },
  { id: 'backup', rotulo: 'Backup geral' },
  { id: 'codigo', rotulo: 'Trocar o código' },
  { id: 'dependencias', rotulo: 'Dependências' },
  { id: 'migracoes', rotulo: 'Atualizar o banco' },
  { id: 'build', rotulo: 'Compilar as telas' },
  { id: 'reiniciar', rotulo: 'Reiniciar' },
];

@Component({
  selector: 'app-versoes-sistema',
  imports: [EsqueletoComponent, FormsModule, DatePipe, DecimalPipe, TrilhaComponent, TrilhaEtapasComponent],
  template: `
    <div class="cabecalho-pagina">
      <div>
        <app-trilha [itens]="[{ rotulo: 'Administração' }, { rotulo: 'Versões' }]" />
        <h1>Versões do sistema</h1>
        <small>A homologação acompanha o GitHub e aprova versões; a produção instala só versões aprovadas. Antes de atualizar, o sistema gera o backup geral e, se algo falhar, volta sozinho.</small>
      </div>
    </div>

    @if (painel(); as p) {
      <p class="dica-formulario" style="margin: 0 0 14px">
        <span class="selo-status" [attr.data-chamado]="p.homologacao ? 'alerta' : 'info'">{{ p.homologacao ? 'Homologação' : 'Produção' }}</span>
        Versão em execução: <span class="texto-codigo">{{ p.versao }}</span>
        @if (p.versao_no_disco !== p.versao) { · no disco: <span class="texto-codigo">{{ p.versao_no_disco }}</span> (reinicie a API) }
        · commit <span class="texto-codigo">{{ p.commit }}</span>
      </p>
      @if (!p.arvore_limpa) {
        <p class="aviso-bloco erro" style="margin-bottom: 14px">Há alterações locais não commitadas neste servidor: atualizar e aprovar ficam bloqueados até o commit (ou o descarte) delas.</p>
      }
      @if (p.andamento.situacao === 'erro') {
        <p class="aviso-bloco erro" style="margin-bottom: 14px" role="status">{{ p.andamento.mensagem }}</p>
      }

      @if (p.homologacao) {
        <!-- Homologação: o ramo do GitHub e a aprovação da versão em execução -->
        <section class="painel-gestao" aria-labelledby="titulo-ramo">
          <div class="barra-ferramentas"><div><h2 id="titulo-ramo">Atualizar a homologação</h2>
            <p>Leva este servidor ao último commit do ramo <span class="texto-codigo">{{ p.ramo }}</span> no GitHub.</p></div>
            <button type="button" class="acao-secundaria" [class.carregando]="buscando()" [disabled]="buscando()" (click)="buscar()">Buscar no GitHub</button></div>
          <div class="corpo" style="padding: 0 24px 20px">
            @if (p.commits_novos.length) {
              <ul class="lista-commits">
                @for (c of p.commits_novos; track c.commit) { <li><span class="texto-codigo">{{ c.commit }}</span> {{ c.titulo }} <small>{{ c.autor }} · {{ c.data | date: 'dd/MM/yyyy HH:mm' }}</small></li> }
              </ul>
              <div class="grade-formulario">
                <div><label for="ver-confirmacao-h">Digite ATUALIZAR para confirmar *</label><input id="ver-confirmacao-h" autocomplete="off" [(ngModel)]="confirmacao" /></div>
              </div>
              <div class="acoes-formulario">
                <button type="button" class="acao-primaria" [disabled]="confirmacao !== 'ATUALIZAR' || ocupado() || !p.arvore_limpa" (click)="atualizar(p.ramo)">Atualizar para o último commit</button>
              </div>
            } @else { <p class="estado-vazio">A homologação já está no último commit do ramo (clique em "Buscar no GitHub" para conferir).</p> }
          </div>
        </section>

        <section class="painel-gestao" aria-labelledby="titulo-aprovar" style="margin-top: 18px">
          <div class="barra-ferramentas"><div><h2 id="titulo-aprovar">Aprovar para a produção</h2>
            <p>Testou a versão em execução? Aprovar cria a tag dela no GitHub, e a produção passa a enxergá-la.</p></div></div>
          <div class="corpo" style="padding: 0 24px 20px">
            @if (p.aprovada) {
              <p><span class="selo-status" data-chamado="sucesso">Aprovada</span> Esta versão já foi aprovada como <span class="texto-codigo">{{ p.aprovada }}</span>.</p>
            } @else {
              <div class="acoes-formulario">
                <button type="button" class="acao-positiva" [class.carregando]="aprovando()" [disabled]="aprovando() || ocupado() || !p.arvore_limpa" (click)="aprovar()">Aprovar esta versão para produção</button>
              </div>
            }
          </div>
        </section>
      } @else {
        <!-- Produção: as versões aprovadas mais novas que a em execução -->
        <section class="painel-gestao" aria-labelledby="titulo-versoes">
          <div class="barra-ferramentas"><div><h2 id="titulo-versoes">Versões aprovadas</h2>
            <p>Versões aprovadas na homologação, mais novas que a em execução.</p></div>
            <button type="button" class="acao-secundaria" [class.carregando]="buscando()" [disabled]="buscando()" (click)="buscar()">Buscar no GitHub</button></div>
          <div class="corpo" style="padding: 0 24px 20px">
            @for (v of p.versoes; track v.alvo; let primeira = $first) {
              <article class="cartao-versao">
                <header><h3 class="texto-codigo">{{ v.alvo }}</h3>
                  @if (primeira) { <span class="selo-status" data-chamado="sucesso">Mais recente</span> }
                  <small>Aprovada por {{ v.aprovada_por || '—' }}@if (v.aprovada_em) { em {{ v.aprovada_em | date: 'dd/MM/yyyy HH:mm' }} }</small></header>
                @if (v.novidades) { <pre class="novidades-versao">{{ v.novidades }}</pre> }
                @else { <p class="dica-formulario">{{ v.commits.length }} commit(s), sem novidades no CHANGELOG.</p> }
                <div class="acoes-formulario">
                  <button type="button" class="acao-primaria" [disabled]="ocupado() || !p.arvore_limpa" (click)="escolher(v.alvo)">Atualizar para {{ v.alvo }}</button>
                </div>
              </article>
            } @empty { <p class="estado-vazio">Nenhuma versão aprovada mais nova que a em execução (clique em "Buscar no GitHub" para conferir).</p> }
            @if (escolhida(); as alvo) {
              <div class="grade-formulario" style="margin-top: 14px">
                <div><label for="ver-confirmacao-p">Digite ATUALIZAR para instalar {{ alvo }} *</label><input id="ver-confirmacao-p" autocomplete="off" [(ngModel)]="confirmacao" /></div>
              </div>
              <div class="acoes-formulario">
                <button type="button" class="acao-secundaria" (click)="escolhida.set(null)">Cancelar</button>
                <button type="button" class="acao-primaria" [disabled]="confirmacao !== 'ATUALIZAR' || ocupado()" (click)="atualizar(alvo)">Instalar {{ alvo }}</button>
              </div>
            }
          </div>
        </section>
      }
    } @else {
      <app-esqueleto tipo="formulario" [linhas]="4" />
    }

    <!-- Modal de andamento da atualização (mesmo desenho do Backup geral) -->
    @if (modalAberto() && painel()?.andamento; as a) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="titulo-andamento-versao">
        <header>
          <div>
            <span class="modal-sobretitulo">Atualização do sistema</span>
            <h2 id="titulo-andamento-versao">{{ tituloModal() }}</h2>
          </div>
          <button type="button" aria-label="Fechar" (click)="modalAberto.set(false)">×</button>
        </header>
        <div class="corpo-andamento">
          @if (a.de || a.para) { <p class="dica-andamento"><span class="texto-codigo">{{ a.de }}</span> → <span class="texto-codigo">{{ a.para }}</span></p> }
          <app-trilha-etapas [etapas]="etapasModal()" [mostrarProgresso]="false" ariaLabel="Etapas da atualização" />
          <div class="cabeca-andamento"><span>{{ a.mensagem }}</span><b>{{ a.percentual ?? 0 | number: '1.0-0' }}%</b></div>
          <div class="trilho-andamento" [class.erro]="a.situacao === 'erro'" [class.concluido]="a.situacao === 'concluido'"
               role="progressbar" aria-label="Andamento da atualização" aria-valuemin="0" aria-valuemax="100" [attr.aria-valuenow]="a.percentual ?? 0" aria-live="polite">
            <i [style.width.%]="a.percentual ?? 0"></i>
          </div>
          @if (a.situacao === 'erro') {
            <p class="aviso-bloco erro">{{ a.voltou === false ? 'A volta automática também falhou: restaure pelo backup indicado em Backup geral.' : 'O sistema voltou para a versão anterior.' }}</p>
            @if (painel()?.log) { <details><summary>Log da atualização</summary><pre class="log-atualizacao">{{ painel()?.log }}</pre></details> }
          } @else if (a.situacao === 'reiniciando') {
            <p class="aviso-bloco informativo">A API está reiniciando com a versão nova. Esta página recarrega sozinha quando ela voltar.</p>
          } @else if (a.situacao === 'concluido') {
            <p class="aviso-bloco informativo">Atualização concluída. Recarregue a página para usar a versão nova.</p>
          } @else {
            <p class="dica-andamento">Pode fechar esta janela: o servidor continua, e o andamento aparece de novo ao voltar a esta tela.</p>
          }
          <footer>
            @if (a.situacao === 'concluido') { <button type="button" class="acao-primaria" (click)="recarregar()">Recarregar a página</button> }
            @else { <button type="button" class="acao-secundaria" (click)="modalAberto.set(false)">{{ ocupado() ? 'Continuar em segundo plano' : 'Fechar' }}</button> }
          </footer>
        </div>
      </section>
    }
  `,
  styles: `
    .lista-commits { margin: 0 0 14px; padding-left: 18px; display: grid; gap: 4px; font-size: var(--spi-texto-compacto); small { color: var(--spi-apagado); } }
    .cartao-versao { padding: 14px 16px; margin-bottom: 12px; border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-m);
      header { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; h3 { margin: 0; font-size: var(--spi-texto-destaque); font-weight: 700; } small { color: var(--spi-apagado); } } }
    .novidades-versao, .log-atualizacao { margin: 10px 0; padding: 10px 12px; max-height: 260px; overflow: auto; white-space: pre-wrap; font-family: var(--spi-fonte-mono);
      font-size: 12px; background: var(--spi-superficie-alt); border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-p); }
    .corpo-andamento { padding: 22px 25px; display: flex; flex-direction: column; gap: 14px; }
    .cabeca-andamento { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; color: var(--spi-texto); font-size: var(--spi-texto-compacto);
      b { font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; } }
    .trilho-andamento { height: 10px; overflow: hidden; border-radius: var(--spi-raio-pilula); background: var(--spi-borda);
      i { display: block; height: 100%; border-radius: var(--spi-raio-pilula); background: var(--spi-vermelho); transition: width 300ms ease-out; }
      &.concluido i { background: var(--spi-sucesso); }
      &.erro i { background: var(--spi-perigo); } }
    .dica-andamento { margin: 0; color: var(--spi-apagado); font-size: var(--spi-texto-compacto); }
    .aviso-bloco { margin: 0; }
    footer { margin-top: 4px; }
    @media (prefers-reduced-motion: reduce) { .trilho-andamento i { transition: none; } }
  `,
})
export class VersoesSistemaComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly dialogos = inject(DialogosService);
  private readonly base = `${ambiente.urlApi}/admin/versoes`;

  protected readonly painel = signal<PainelVersoes | null>(null);
  protected readonly buscando = signal(false);
  protected readonly aprovando = signal(false);
  protected readonly modalAberto = signal(false);
  /** Produção: a versão escolhida, aguardando a confirmação digitada. */
  protected readonly escolhida = signal<string | null>(null);
  protected confirmacao = '';
  private consulta: ReturnType<typeof setTimeout> | undefined;

  protected readonly ocupado = computed(() => ['em_andamento', 'reiniciando'].includes(this.painel()?.andamento.situacao ?? ''));

  protected readonly tituloModal = computed(() => {
    const a = this.painel()?.andamento;
    if (a?.situacao === 'erro') return 'A atualização não terminou';
    if (a?.situacao === 'concluido') return `Atualizado para ${a.para ?? ''}`;
    if (a?.situacao === 'reiniciando') return 'Reiniciando o sistema';
    return `Atualizando para ${a?.para ?? ''}`;
  });

  /** Etapas do modal com a situação de cada uma, a partir da etapa informada pelo servidor (mesma lógica do Backup geral). */
  protected readonly etapasModal = computed<EtapaTrilha[]>(() => {
    const a = this.painel()?.andamento;
    const indice = Math.max(0, ETAPAS.findIndex((e) => e.id === a?.etapa));
    return ETAPAS.map((e, i) => {
      if (a?.situacao === 'concluido') return { ...e, estado: 'concluida' };
      if (i < indice) return { ...e, estado: 'concluida' };
      if (i === indice) return { ...e, estado: a?.situacao === 'erro' ? 'recusada' : 'atual', subtitulo: a?.situacao === 'erro' ? 'falhou' : undefined };
      return { ...e, estado: 'aguardando' };
    });
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.consulta));
  }

  ngOnInit(): void {
    this.carregar(true);
  }

  /** Carrega o painel; enquanto a atualização roda, consulta a cada 3 s (e, reiniciando, espera a API voltar). */
  private carregar(abrindoTela = false): void {
    this.http.get<PainelVersoes>(this.base).subscribe({
      next: (p) => {
        if (abrindoTela && ['em_andamento', 'reiniciando'].includes(p.andamento.situacao ?? '')) this.modalAberto.set(true);
        this.aplicar(p);
      },
      // Durante o reinício a API some por alguns segundos: tenta de novo em vez de mostrar erro
      error: (e) => (this.ocupado() ? this.agendar(4000) : this.dialogos.mostrarErro(e, 'Não foi possível carregar as versões')),
    });
  }

  private aplicar(p: PainelVersoes): void {
    this.painel.set(p);
    clearTimeout(this.consulta);
    if (['em_andamento', 'reiniciando'].includes(p.andamento.situacao ?? '')) this.agendar(3000);
  }

  private agendar(ms: number): void {
    clearTimeout(this.consulta);
    this.consulta = setTimeout(() => this.carregar(), ms);
  }

  protected buscar(): void {
    this.buscando.set(true);
    this.http.post<PainelVersoes>(`${this.base}/buscar`, {}).subscribe({
      next: (p) => { this.buscando.set(false); this.aplicar(p); },
      error: (e) => { this.buscando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível buscar no GitHub'); },
    });
  }

  protected escolher(alvo: string): void {
    this.confirmacao = '';
    this.escolhida.set(alvo);
  }

  protected async atualizar(alvo: string): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Atualizar o sistema para ${alvo}?`,
      mensagem: 'O servidor gera o backup geral, troca o código, atualiza o banco, compila as telas e reinicia (alguns minutos). Se algo falhar, volta sozinho para a versão atual.',
      rotuloConfirmar: 'Atualizar agora',
      segundos: 3,
    });
    if (!ok) return;
    this.modalAberto.set(true);
    this.http.post<PainelVersoes>(`${this.base}/atualizar`, { alvo, confirmacao: this.confirmacao }).subscribe({
      next: (p) => { this.confirmacao = ''; this.escolhida.set(null); this.aplicar(p); },
      error: (e) => { this.modalAberto.set(false); this.dialogos.mostrarErro(e, 'Não foi possível iniciar a atualização'); },
    });
  }

  protected async aprovar(): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Aprovar esta versão para a produção?',
      mensagem: `A versão em execução (${this.painel()?.versao ?? ''}) ganha uma tag no GitHub e passa a aparecer na produção para instalar.`,
      rotuloConfirmar: 'Aprovar',
    });
    if (!ok) return;
    this.aprovando.set(true);
    this.http.post<{ tag: string }>(`${this.base}/aprovar`, {}).subscribe({
      next: ({ tag }) => { this.aprovando.set(false); this.dialogos.avisar('Versão aprovada', `A versão foi aprovada como ${tag} e já aparece na produção.`); this.carregar(); },
      error: (e) => { this.aprovando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível aprovar a versão'); },
    });
  }

  protected recarregar(): void {
    window.location.reload();
  }
}
