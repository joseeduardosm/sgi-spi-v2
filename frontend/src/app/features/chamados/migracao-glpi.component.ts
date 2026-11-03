// Criado por José Eduardo Santana Martins
// Este arquivo serve para a aba "Migração do GLPI" dos Parâmetros dos Chamados: conexão só de leitura, teste, os botões "Trazer novidades" e
// "Refazer do zero" e o modal com o andamento (etapas, barra e quantos chamados já foram).

import { DecimalPipe } from '@angular/common';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { EtapaTrilha, TrilhaEtapasComponent } from '../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { ChamadosApiService } from './chamados-api.service';
import { dataHora, LeituraMigracaoGlpi, SetorResumo } from './chamados.models';

/** Etapas na ordem em que o servidor passa (a limpeza só existe no "Refazer do zero"). */
const ETAPAS: { id: string; rotulo: string }[] = [
  { id: 'conexao', rotulo: 'Conexão' }, { id: 'leitura', rotulo: 'Leitura do GLPI' }, { id: 'limpeza', rotulo: 'Limpeza' },
  { id: 'categorias', rotulo: 'Categorias ITIL' }, { id: 'chamados', rotulo: 'Chamados' }, { id: 'detalhes', rotulo: 'Acompanhamentos' },
];

/**
 * Configuração e execução da migração. O GLPI é lido com um usuário só de leitura; a migração roda em segundo plano no servidor e a tela
 * consulta o andamento a cada segundo e meio enquanto ela durar.
 */
@Component({
  selector: 'app-migracao-glpi',
  imports: [FormsModule, DecimalPipe, EsqueletoComponent, TrilhaEtapasComponent],
  template: `
    @if (estado(); as e) {
      <p class="dica-formulario">Traz os chamados do GLPI para cá, quando você quiser. O GLPI é lido com um usuário <strong>só de leitura</strong>
        (nada é gravado lá). As categorias do GLPI viram <strong>categorias ITIL</strong>; pessoas e grupos casam sozinhos pelo login, e-mail e nome.
        O chamado <strong>ainda aberto</strong> no GLPI vira chamado normal aqui (painel e fila). Por padrão vêm só os não solucionados; desmarcando a
        opção abaixo, vem também o histórico de resolvidos (somente leitura). Os anexos ficam no GLPI.</p>

      <form class="grade-formulario" (ngSubmit)="salvar()" #fm="ngForm">
        <div><label for="mg-host">Servidor do banco do GLPI</label>
          <input id="mg-host" name="host" class="texto-codigo" placeholder="Ex.: 10.23.1.242" [(ngModel)]="cfg.host" /></div>
        <div><label for="mg-porta">Porta</label><input id="mg-porta" name="porta" type="number" min="1" max="65535" [(ngModel)]="cfg.porta" /></div>
        <div><label for="mg-banco">Banco</label><input id="mg-banco" name="banco" class="texto-codigo" [(ngModel)]="cfg.banco" /></div>
        <div><label for="mg-usuario">Usuário (só leitura)</label><input id="mg-usuario" name="usuario" class="texto-codigo" autocomplete="off" [(ngModel)]="cfg.usuario" /></div>
        <div><label for="mg-senha">Senha</label>
          <input id="mg-senha" name="senha" type="password" autocomplete="new-password" [placeholder]="e.senha_cadastrada ? 'Cadastrada: deixe vazio para manter' : 'Senha do usuário'"
            [(ngModel)]="senha" /></div>
        <div><label for="mg-setor">Setor padrão</label>
          <select id="mg-setor" name="setor" [(ngModel)]="cfg.setor_padrao_id">
            <option [ngValue]="null">Escolha</option>
            @for (s of setores(); track s.id) { <option [ngValue]="s.id">{{ s.caminho || s.nome }}</option> }
          </select>
          <small class="dica-formulario">Fica com os chamados que não têm grupo responsável no GLPI.</small></div>
        <div class="ocupa-duas"><label class="linha-caixa"><input type="checkbox" name="abertos" [(ngModel)]="cfg.so_abertos" />
          Trazer só os chamados não solucionados (o histórico de resolvidos fica no GLPI)</label></div>
        <div class="ocupa-duas"><label class="linha-caixa"><input type="checkbox" name="ativa" [(ngModel)]="cfg.ativa" />
          Migração ativa (desmarque depois da virada: os botões somem e as rotas recusam)</label></div>
        <div class="ocupa-duas acoes-formulario">
          <button type="button" class="acao-secundaria" [class.carregando]="testando()" [disabled]="testando() || !e.ativa" (click)="testar()">Testar conexão</button>
          <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando()">Salvar conexão</button>
        </div>
      </form>

      @if (e.ativa) {
        <section class="mg-acoes" aria-labelledby="mg-titulo">
          <header>
            <h3 id="mg-titulo">Migrar agora</h3>
            <small>{{ e.ultima_sincronizacao ? 'Última migração: ' + data(e.ultima_sincronizacao) : 'Ainda não houve migração.' }}</small>
          </header>
          <div class="mg-opcoes">
            <div>
              <strong>Trazer novidades</strong>
              <p>Traz os chamados novos e regrava os que mudaram no GLPI desde a última vez (na primeira, traz tudo). Pode rodar quantas vezes quiser.</p>
              <button type="button" class="acao-primaria" [disabled]="emAndamento()" (click)="executar('novidades')">Trazer novidades</button>
            </div>
            <div>
              <strong>Refazer do zero</strong>
              <p>Apaga <strong>todos</strong> os chamados, inclusive os abertos aqui no SGI, e traz tudo do GLPI de novo. Use para demonstração e treinamento.</p>
              <button type="button" class="acao-perigo" [disabled]="emAndamento()" (click)="executar('refazer')">Refazer do zero</button>
            </div>
          </div>
          @if (e.andamento.situacao) {
            <p class="mg-ultima" [class.erro]="e.andamento.situacao === 'erro'">{{ e.andamento.mensagem }}
              <button type="button" class="acao-secundaria acao-pequena" (click)="modalAberto.set(true)">Ver andamento</button></p>
          }
        </section>
      } @else {
        <p class="aviso-formulario">A migração está desativada. Marque "Migração ativa" e salve para voltar a usar.</p>
      }
    } @else {
      <app-esqueleto tipo="formulario" [linhas]="4" />
    }

    @if (modalAberto() && estado(); as e) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="titulo-andamento-glpi">
        <header>
          <div><span class="modal-sobretitulo">Migração do GLPI · {{ e.andamento.modo === 'refazer' ? 'Refazer do zero' : 'Trazer novidades' }}</span>
            <h2 id="titulo-andamento-glpi">{{ tituloModal() }}</h2></div>
          <button type="button" aria-label="Fechar" (click)="modalAberto.set(false)">×</button>
        </header>
        <div class="corpo-andamento">
          <app-trilha-etapas [etapas]="etapas()" [mostrarProgresso]="false" ariaLabel="Etapas da migração" />
          <div class="cabeca-andamento">
            <span>{{ e.andamento.mensagem }}</span>
            <b>{{ (e.andamento.percentual ?? 0) | number: '1.0-0' }}%</b>
          </div>
          <div class="trilho-andamento" [class.erro]="e.andamento.situacao === 'erro'" [class.concluido]="e.andamento.situacao === 'concluido'"
               role="progressbar" aria-label="Andamento da migração" aria-valuemin="0" aria-valuemax="100" [attr.aria-valuenow]="e.andamento.percentual ?? 0" aria-live="polite">
            <i [style.width.%]="e.andamento.percentual ?? 0"></i>
          </div>
          @if (e.andamento.chamados_total) {
            <p class="contador-andamento"><b>{{ e.andamento.chamados_migrados ?? 0 }}</b> de {{ e.andamento.chamados_total }} chamados do GLPI conferidos</p>
          }
          @if (e.andamento.situacao === 'concluido' && e.andamento.resumo; as r) {
            <ul class="resumo-andamento">
              <li><b>{{ r.novos }}</b> chamado(s) novo(s)</li><li><b>{{ r.atualizados }}</b> atualizado(s)</li><li><b>{{ r.sem_mudanca }}</b> sem mudança</li>
              @if (r.resolvidos_nao_migrados) { <li><b>{{ r.resolvidos_nao_migrados }}</b> resolvido(s) no GLPI (não migrados)</li> }
              @if (r.trabalhados_sgi) { <li><b>{{ r.trabalhados_sgi }}</b> já trabalhado(s) no SGI (não sobrescritos)</li> }
              <li><b>{{ r.categorias_itil }}</b> categoria(s) ITIL nova(s)</li><li><b>{{ r.acompanhamentos }}</b> acompanhamento(s)</li><li><b>{{ r.solucoes }}</b> solução(ões)</li>
            </ul>
            @if (r.total_avisos) {
              <details class="avisos-andamento"><summary>{{ r.total_avisos }} aviso(s) para conferir (pessoas sem par, categorias repetidas…)</summary>
                <ul>@for (a of r.avisos; track $index) { <li>{{ a }}</li> }</ul>
                @if (r.total_avisos > r.avisos.length) { <small>Mostrando os {{ r.avisos.length }} primeiros.</small> }
              </details>
            }
          } @else if (e.andamento.situacao === 'erro') {
            <p class="aviso-bloco erro">A migração parou e nada foi gravado (tudo roda numa transação só). Confira a mensagem acima e tente de novo.</p>
          } @else {
            <p class="dica-andamento">Pode fechar esta janela: o servidor continua e o andamento aparece de novo ao voltar a esta aba.</p>
          }
          <footer>
            <button type="button" class="acao-secundaria" (click)="modalAberto.set(false)">{{ emAndamento() ? 'Continuar em segundo plano' : 'Fechar' }}</button>
          </footer>
        </div>
      </section>
    }
  `,
  styles: `
    .mg-acoes { margin-top: 20px; padding: 16px 20px; border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-g); background: var(--spi-superficie);
      header { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 12px;
        h3 { margin: 0; font-size: 16px; font-weight: 700; } small { color: var(--spi-apagado); } } }
    .mg-opcoes { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px;
      > div { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; padding: 14px 16px; border-radius: var(--spi-raio-m); background: var(--spi-superficie-alt); }
      p { margin: 0; color: var(--spi-apagado); font-size: 13px; } }
    .mg-ultima { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 14px 0 0; font-size: 13px; color: var(--spi-texto);
      &.erro { color: var(--spi-perigo); } }
    // Modal de andamento: o mesmo desenho do Backup geral
    .corpo-andamento { padding: 22px 25px; display: flex; flex-direction: column; gap: 14px; }
    .cabeca-andamento { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; color: var(--spi-texto); font-size: var(--spi-texto-compacto);
      b { font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; } }
    .trilho-andamento { height: 10px; overflow: hidden; border-radius: var(--spi-raio-pilula); background: var(--spi-borda);
      i { display: block; height: 100%; border-radius: var(--spi-raio-pilula); background: var(--spi-vermelho); transition: width 300ms ease-out; }
      &.concluido i { background: var(--spi-sucesso); }
      &.erro i { background: var(--spi-perigo); } }
    .contador-andamento { margin: 0; font-size: 14px; color: var(--spi-texto); b { font-size: 20px; font-variant-numeric: tabular-nums; } }
    .resumo-andamento { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin: 0; padding: 0; list-style: none;
      li { padding: 10px 12px; border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-m); font-size: 13px; color: var(--spi-apagado); }
      b { display: block; font-size: 20px; color: var(--spi-titulo); } }
    .avisos-andamento { font-size: 13px; ul { max-height: 200px; overflow-y: auto; margin: 8px 0; padding-left: 18px; } }
    .dica-andamento { margin: 0; color: var(--spi-apagado); font-size: var(--spi-texto-compacto); }
    .aviso-bloco { margin: 0; }
    footer { margin-top: 4px; }
    @media (prefers-reduced-motion: reduce) { .trilho-andamento i { transition: none; } }
  `,
})
export class MigracaoGlpiComponent implements OnInit {
  private readonly api = inject(ChamadosApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly estado = signal<LeituraMigracaoGlpi | null>(null);
  protected readonly setores = signal<SetorResumo[]>([]);
  protected readonly salvando = signal(false);
  protected readonly testando = signal(false);
  protected readonly modalAberto = signal(false);
  protected cfg = { ativa: true, host: '', porta: 3306, banco: 'helpdesk', usuario: '', setor_padrao_id: null as number | null, so_abertos: true };
  protected senha = '';
  protected data = dataHora;
  private consulta?: ReturnType<typeof setTimeout>;

  protected readonly emAndamento = computed(() => this.estado()?.andamento.situacao === 'em_andamento');
  protected readonly tituloModal = computed(() => ({ concluido: 'Migração concluída', erro: 'A migração não terminou' } as Record<string, string>)[
    this.estado()?.andamento.situacao ?? ''] ?? 'Migrando do GLPI');
  protected readonly etapas = computed<EtapaTrilha[]>(() => {
    const a = this.estado()?.andamento;
    if (!a) return [];
    const lista = ETAPAS.filter((e) => e.id !== 'limpeza' || a.modo === 'refazer');
    const indice = Math.max(0, lista.findIndex((e) => e.id === a.etapa));
    return lista.map((e, i) => {
      if (a.situacao === 'concluido') return { ...e, estado: 'concluida' };
      if (i < indice) return { ...e, estado: 'concluida' };
      if (i === indice) return { ...e, estado: a.situacao === 'erro' ? 'recusada' : 'atual', subtitulo: a.situacao === 'erro' ? 'falhou' : undefined };
      return { ...e, estado: 'aguardando' };
    });
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.consulta));
  }

  ngOnInit(): void {
    this.api.setoresAtivos().subscribe({ next: (s) => this.setores.set(s), error: () => undefined });
    this.carregar(true);
  }

  /** Lê configuração e andamento; enquanto houver migração rodando, consulta de novo em instantes. */
  private carregar(preencher = false): void {
    this.api.migracaoGlpi().subscribe({
      next: (e) => {
        this.estado.set(e);
        if (preencher) {
          this.cfg = { ativa: e.ativa, host: e.host, porta: e.porta, banco: e.banco, usuario: e.usuario, setor_padrao_id: e.setor_padrao_id, so_abertos: e.so_abertos };
          if (e.andamento.situacao === 'em_andamento') this.modalAberto.set(true);
        }
        clearTimeout(this.consulta);
        if (e.andamento.situacao === 'em_andamento') this.consulta = setTimeout(() => this.carregar(), 1500);
      },
      error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível ler a migração do GLPI'),
    });
  }

  protected salvar(): void {
    this.salvando.set(true);
    this.api.gravarMigracaoGlpi({ ...this.cfg, senha: this.senha || null }).subscribe({
      next: (e) => { this.salvando.set(false); this.senha = ''; this.estado.set(e); },
      error: (erro) => { this.salvando.set(false); this.dialogos.mostrarErro(erro, 'Não foi possível salvar a conexão'); },
    });
  }

  protected testar(): void {
    this.testando.set(true);
    this.api.testarMigracaoGlpi().subscribe({
      next: (r) => {
        this.testando.set(false);
        this.dialogos.avisar('Conexão funcionando', `GLPI ${r.versao || '(versão não informada)'}: ${r.chamados} chamado(s) lá.`);
      },
      error: (erro) => { this.testando.set(false); this.dialogos.mostrarErro(erro, 'A conexão com o GLPI falhou'); },
    });
  }

  protected async executar(modo: 'novidades' | 'refazer'): Promise<void> {
    if (modo === 'refazer') {
      const ok = await this.dialogos.confirmar({
        titulo: 'Refazer a migração do zero?', perigo: true, segundos: 5, rotuloConfirmar: 'Apagar e trazer de novo',
        mensagem: 'TODOS os chamados serão apagados, inclusive os abertos aqui no SGI (com acompanhamentos, soluções e anexos), e o GLPI é trazido de novo. Não há como desfazer.',
      });
      if (!ok) return;
    }
    this.api.executarMigracaoGlpi(modo).subscribe({
      next: (e) => { this.estado.set(e); this.modalAberto.set(true); this.carregar(); },
      error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível começar a migração'),
    });
  }
}
