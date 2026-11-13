/**
 * =============================================================================
 * ARQUIVO: detalhe-movimentacao.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Página de uma movimentação de bens do Patrimônio: mostra origem, destino,
 * motivo e andamento, e oferece as ações de autorizar, recusar, cancelar,
 * receber os bens (um a um ou lendo o código) e encerrar o recebimento.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template inline. Recebe o id pela rota
 * (input.required), carrega a movimentação via PatrimonioApiService e guarda
 * em signals. As ações chamam a API e substituem o objeto exibido pela
 * resposta. A leitura de código usa o app-leitor-codigo em modo contínuo.
 *
 * FINALIDADE DE NEGÓCIO:
 * Controla a troca de local dos bens patrimoniais: quem tem controle total
 * autoriza (nunca a própria solicitação), e o recebimento confirma que cada
 * bem chegou ao destino. Bens não recebidos ficam na origem.
 *
 * CONTEXTO NO SISTEMA:
 * Rota filha do módulo Patrimônio (patrimonio.routes.ts). Usa a trilha de
 * etapas (trilhas-patrimonio.ts), o cabeçalho do módulo, o estado de acesso
 * (PatrimonioEstadoService) e os rótulos/cores de status de patrimonio.models.
 *
 * =============================================================================
 */
import { TrilhaEtapasComponent } from '../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { trilhaMovimentacao } from './trilhas-patrimonio';
import { DatePipe } from '@angular/common';
import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { classeMarcador } from '../tarefas/marcadores.paleta';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { LeitorCodigoComponent } from './leitor-codigo.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { COR_STATUS, Movimentacao, ROTULOS_STATUS } from './patrimonio.models';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
@Component({
  selector: 'app-detalhe-movimentacao',
  imports: [TrilhaEtapasComponent, EsqueletoComponent, FormsModule, RouterLink, DatePipe, CabecalhoPatrimonioComponent, LeitorCodigoComponent],
  template: `
    <app-cabecalho-patrimonio titulo="Movimentação" descricao="Origem, destino, motivo e andamento do recebimento." />
    @if (mov(); as m) {
      <section class="painel-gestao patrimonio">
        <app-trilha-etapas [etapas]="trilha(m)" ariaLabel="Etapas da movimentação" />
        <div class="pat-topo-bem">
          <span class="pat-marcadores"><span [class]="marcador(cores[m.status])">{{ rotulos[m.status] }}</span></span>
          <div class="pat-acoes">
            @if (m.status === 'pendente' && souSolicitante(m)) { <button type="button" class="acao-recusar" (click)="acao('cancelar')">Cancelar solicitação</button> }
            @if (m.status === 'pendente' && estado.podeAdministrar() && !souSolicitante(m)) {
              <button type="button" class="acao-recusar" (click)="recusando.set(!recusando())">Recusar</button>
              <button type="button" class="acao-positiva" (click)="acao('autorizar')">Autorizar</button>
            }
            @if (m.status === 'autorizada' && estado.podeAdministrar()) {
              <button type="button" class="acao-positiva" (click)="lendo.set(true)">Receber lendo o código</button>
              <button type="button" class="acao-secundaria" (click)="concluir(m)">Encerrar recebimento</button>
            }
          </div>
        </div>
        @if (m.status === 'pendente' && estado.podeAdministrar() && souSolicitante(m)) { <p class="pat-aviso">Quem solicitou não pode autorizar a própria solicitação: outra pessoa com controle total precisa autorizar.</p> }
        @if (recusando()) {
          <div class="pat-painel-acao"><label for="mv-motivo">Motivo da recusa *</label><textarea id="mv-motivo" name="motivo" rows="3" [(ngModel)]="motivoRecusa"></textarea>
            <button type="button" class="acao-recusar" [disabled]="!motivoRecusa.trim()" (click)="acao('recusar', motivoRecusa)">Confirmar recusa</button></div>
        }
        <dl class="pat-dados">
          <div><dt>Destino</dt><dd>{{ m.destino_rotulo }}</dd></div>
          <div><dt>Motivo</dt><dd>{{ m.motivo }}</dd></div>
          <div><dt>Solicitante</dt><dd>{{ m.solicitante_nome }} · {{ m.solicitada_em | date: 'dd/MM/yyyy HH:mm' }}</dd></div>
          @if (m.decidido_por_nome) { <div><dt>{{ m.status === 'recusada' ? 'Recusada por' : 'Autorizada por' }}</dt><dd>{{ m.decidido_por_nome }} · {{ m.decidido_em | date: 'dd/MM/yyyy HH:mm' }}</dd></div> }
          @if (m.motivo_recusa) { <div><dt>Motivo da recusa</dt><dd>{{ m.motivo_recusa }}</dd></div> }
          @if (m.concluida_em) { <div><dt>Concluída em</dt><dd>{{ m.concluida_em | date: 'dd/MM/yyyy HH:mm' }}</dd></div> }
        </dl>
        <h3 class="pat-subtitulo">Bens ({{ recebidos(m) }}/{{ m.itens.length }} recebidos)</h3>
        <ul class="pat-lista-itens">
          @for (i of m.itens; track i.bem_id) {
            <li><div><strong>{{ i.rotulo }}</strong> <span>{{ i.descricao }}</span><small>De {{ i.origem_rotulo }}</small></div>
              @if (i.recebido_em) { <span [class]="marcador(10)">Recebido {{ i.recebido_em | date: 'HH:mm' }}</span> }
              @else if (m.status === 'autorizada' && estado.podeAdministrar()) { <button type="button" class="acao-positiva acao-pequena" (click)="receber(m, i.bem_id)">Confirmar recebimento</button> }
              @else if (m.status === 'concluida') { <span [class]="marcador(0)">Não chegou</span> }</li>
          }
        </ul>
        <div class="pat-barra-inferior"><a class="acao-secundaria" routerLink="/patrimonio/movimentacoes">Voltar</a></div>
      </section>
      @if (lendo()) { <app-leitor-codigo [continuo]="true" mensagem="Leia o código de cada bem que chegou" (lido)="lerChapa(m, $event)" (fechar)="lendo.set(false)" /> }
    } @else { <app-esqueleto tipo="formulario" [linhas]="5" /> }
  `,
})
/**
 * Página de detalhe de uma movimentação. Os botões aparecem conforme o status
 * (pendente, autorizada, concluída...) e o nível de acesso do usuário.
 */
export class DetalheMovimentacaoComponent implements OnInit {
  /** Função que monta as etapas da trilha a partir da movimentação. */
  protected readonly trilha = trilhaMovimentacao;
  // inject() pede ao Angular a instância de um serviço sem precisar de construtor.
  private readonly api = inject(PatrimonioApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(PatrimonioEstadoService);
  /** Id da movimentação, vindo do parâmetro da rota (input() recebe valor de fora do componente). */
  readonly movimentacaoId = input.required<string>();
  /** Movimentação exibida; null enquanto carrega (signal é um valor reativo que atualiza a tela ao mudar). */
  protected readonly mov = signal<Movimentacao | null>(null);
  /** Leitor de código aberto (recebimento pela câmera). */
  protected readonly lendo = signal(false);
  /** Painel de motivo da recusa aberto. */
  protected readonly recusando = signal(false);
  /** Texto do motivo da recusa, ligado ao textarea por ngModel. */
  protected motivoRecusa = '';
  protected readonly marcador = classeMarcador;
  protected readonly cores = COR_STATUS;
  protected readonly rotulos = ROTULOS_STATUS;

  /**
   * Carrega o nível de acesso do usuário e a movimentação. O subscribe
   * "assina" o Observable do HttpClient: a requisição só sai quando alguém assina.
   */
  ngOnInit(): void {
    void this.estado.carregar();
    this.api.movimentacao(this.movimentacaoId()).subscribe({ next: (m) => this.mov.set(m), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a movimentação') });
  }

  /** Diz se o usuário logado é quem pediu a movimentação (ele não pode autorizar a própria, só cancelar). */
  protected souSolicitante(m: Movimentacao): boolean {
    return m.solicitante_id === this.estado.acesso()?.usuario_id;
  }

  /** Quantos bens da movimentação já tiveram o recebimento confirmado. */
  protected recebidos(m: Movimentacao): number {
    return m.itens.filter((i) => i.recebido_em).length;
  }

  /**
   * Executa autorizar, recusar ou cancelar no servidor e troca a movimentação
   * exibida pela resposta (com o novo status). Na recusa, o motivo é obrigatório.
   */
  protected acao(acao: 'autorizar' | 'recusar' | 'cancelar', motivo?: string): void {
    this.api.acaoMovimentacao(this.movimentacaoId(), acao, motivo).subscribe({
      next: (m) => { this.mov.set(m); this.recusando.set(false); }, error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível concluir a ação'),
    });
  }

  /** Confirma no servidor que um bem chegou ao destino e atualiza a lista. */
  protected receber(m: Movimentacao, bemId: string): void {
    this.api.receber(m.id, bemId).subscribe({ next: (x) => this.mov.set(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível confirmar o recebimento') });
  }

  /** Cada código lido (chapa ou número de série) confirma o recebimento do bem correspondente (códigos fora da movimentação são avisadas e ignoradas). */
  protected lerChapa(m: Movimentacao, chapa: string): void {
    const codigo = chapa.trim().toLowerCase();
    const item = (this.mov() ?? m).itens.find((i) => [i.chapa, i.numero_serie, i.rotulo].some((v) => (v ?? '').toLowerCase() === codigo));
    if (!item) { this.dialogos.avisar('Fora da movimentação', `O bem ${chapa} (chapa ou número de série) não faz parte desta movimentação.`); return; }
    if (item.recebido_em) return;
    this.receber(m, item.bem_id);
  }

  /**
   * Encerra o recebimento. Se ainda faltam bens, pede confirmação antes,
   * avisando que os não recebidos ficam na origem.
   */
  protected async concluir(m: Movimentacao): Promise<void> {
    const faltam = m.itens.length - this.recebidos(m);
    const ok = !faltam || await this.dialogos.confirmar({ titulo: 'Encerrar o recebimento?', mensagem: `${faltam} bem(ns) não foram recebidos e ficam na origem, livres para outra movimentação.`, rotuloConfirmar: 'Encerrar', segundos: 2 });
    if (ok) this.api.acaoMovimentacao(m.id, 'concluir').subscribe({ next: (x) => this.mov.set(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível encerrar') });
  }
}
