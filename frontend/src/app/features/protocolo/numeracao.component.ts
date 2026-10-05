// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela principal do Protocolo: grade de números, reserva do próximo, detalhe com linha do tempo e ações.

import { DatePipe } from '@angular/common';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { debounceTime, Subject } from 'rxjs';

import { AcessoService } from '../../core/acesso/acesso.service';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { ContratosApiService } from '../contratos/compartilhado/contratos-api.service';
import { ResumoContrato } from '../contratos/compartilhado/contratos.models';
import { LinkificarPipe } from '../../shared/utilitarios/linkificar.pipe';
import { CabecalhoProtocoloComponent } from './cabecalho-protocolo.component';
import { ProtocoloApiService } from './protocolo-api.service';
import { ListaNumeros, NumeroProtocolo, ROTULOS_ESTADO, ROTULOS_EVENTO, SequenciaProtocolo, TipoProtocolo } from './protocolo.models';

type Janela = null | 'reservar' | 'detalhe';
type AcaoMotivo = 'liberar' | 'anular';

/**
 * Numeração do Protocolo. Quem tem acesso reserva o **próximo número** da sequência; só CONTROLE_TOTAL clica num número livre para
 * lançá-lo. Cada número tem linha do tempo (visível mesmo se o documento for sigiloso), anexo, sigilo, vínculo com contrato,
 * liberação e anulação.
 */
@Component({
  selector: 'app-numeracao',
  imports: [LinkificarPipe, FormsModule, DatePipe, CabecalhoProtocoloComponent],
  template: `
    <app-cabecalho-protocolo titulo="Protocolo" descricao="Reserve o próximo número de ofícios, portarias e resoluções e anexe o documento." />
    <section class="painel-gestao protocolo">
      @if (!carregado()) {
        <p class="estado-vazio">Carregando…</p>
      } @else if (!tipos().length) {
        <p class="estado-vazio">Nenhum tipo de documento cadastrado. @if (administra()) { Cadastre em <b>Administração</b>. }</p>
      } @else {
        <div class="barra-protocolo">
          <div class="campo"><label for="pt-tipo">Tipo de documento</label>
            <select id="pt-tipo" [ngModel]="tipoId()" (ngModelChange)="escolherTipo($event)">
              @for (t of tipos(); track t.id) { <option [value]="t.id">{{ t.nome }}</option> }
            </select></div>
          <div class="campo curto"><label for="pt-ano">Exercício</label>
            <select id="pt-ano" [ngModel]="sequenciaId()" (ngModelChange)="escolherSequencia($event)">
              @for (s of sequenciasDoTipo(); track s.id) { <option [value]="s.id">{{ s.exercicio }}</option> }
              @empty { <option value="">sem sequência</option> }
            </select></div>
          @if (lista(); as l) {
            <div class="resumo-protocolo"><strong>{{ l.livres }}</strong> livre(s) · faixa {{ l.sequencia.inicio }} a {{ l.sequencia.fim }}</div>
            <button type="button" class="acao-primaria" [disabled]="l.livres === 0" (click)="abrirReserva(null)">Reservar próximo número</button>
          }
        </div>

        @if (lista(); as l) {
          <div class="legenda-protocolo" aria-label="Legenda">
            <span class="livre">Livre</span><span class="reservado">Reservado, sem documento</span><span class="utilizado">Utilizado, com documento</span><span class="anulado">Anulado</span>
          </div>
          <div class="grade-numeros">
            @for (n of l.itens; track n.id) {
              <button type="button" [class]="'numero ' + n.estado" [title]="n.estado === 'livre' ? 'Número livre' : n.finalidade" (click)="clicarNumero(n)">
                <strong>{{ n.numero }}</strong>
                <small>{{ rotulos[n.estado] }}@if (n.sigiloso) { <span aria-label="Documento sigiloso" title="Documento sigiloso"> 🔒</span> }</small>
              </button>
            }
          </div>
        } @else {
          <p class="estado-vazio">{{ sequenciaId() ? 'Carregando os números…' : 'Este tipo ainda não tem sequência. Peça à administração para criar a do exercício.' }}</p>
        }
      }
    </section>

    @if (janela() === 'reservar') {
      <div class="fundo-modal" role="presentation" (click)="fechar()"></div>
      <section class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-reserva">
        <header>
          <div><span class="modal-sobretitulo">Reserva</span>
            <h2 id="titulo-reserva">@if (alvo()) { Lançar o número {{ alvo()!.numero_formatado }} } @else { Reservar o próximo número }</h2></div>
          <button type="button" aria-label="Fechar" (click)="fechar()">×</button>
        </header>
        <form (ngSubmit)="reservar()" class="form-protocolo">
          <div class="grade-formulario uma-coluna">
            <div><label for="pr-finalidade">Finalidade *</label>
              <textarea id="pr-finalidade" name="finalidade" rows="4" maxlength="1000" [(ngModel)]="finalidade"></textarea></div>
            <div><label for="pr-busca">Contrato (opcional)</label>
              <input id="pr-busca" name="busca" placeholder="Buscar por número ou apelido" [ngModel]="buscaContrato()" (ngModelChange)="buscarContratos($event)" /></div>
            @if (contratos().length) {
              <div><label for="pr-contrato">Contrato encontrado</label>
                <select id="pr-contrato" name="contrato" [(ngModel)]="contratoId">
                  <option [ngValue]="null">Sem vínculo</option>
                  @for (c of contratos(); track c.id) { <option [ngValue]="c.id">{{ c.numero }}{{ c.apelido ? ' · ' + c.apelido : '' }}</option> }
                </select></div>
            }
          </div>
          <footer>
            <button type="button" class="acao-secundaria" (click)="fechar()">Cancelar</button>
            <button type="submit" class="acao-positiva" [disabled]="!finalidade.trim() || ocupado()">Reservar</button>
          </footer>
        </form>
      </section>
    }

    @if (janela() === 'detalhe' && detalhe(); as n) {
      <div class="fundo-modal" role="presentation" (click)="fechar()"></div>
      <section class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="titulo-numero">
        <header>
          <div><span class="modal-sobretitulo">{{ n.tipo_nome }} · {{ rotulos[n.estado] }}</span><h2 id="titulo-numero">Nº {{ n.numero_formatado }}</h2></div>
          <button type="button" aria-label="Fechar" (click)="fechar()">×</button>
        </header>
        <div class="corpo-numero">
          <dl class="dados-numero">
            <div><dt>Finalidade</dt><dd>{{ n.finalidade || '—' }}</dd></div>
            <div><dt>Reservado por</dt><dd>{{ n.reservado_por_nome || '—' }}</dd></div>
            <div><dt>Reservado em</dt><dd>{{ n.reservado_em ? (n.reservado_em | date: 'dd/MM/yyyy HH:mm') : '—' }}</dd></div>
            @if (n.contrato_numero) { <div><dt>Contrato</dt><dd>{{ n.contrato_numero }}</dd></div> }
            @if (n.estado === 'anulado') { <div class="inteira"><dt>Anulado</dt><dd>{{ n.anulado_em | date: 'dd/MM/yyyy HH:mm' }} · {{ n.motivo_anulacao }}</dd></div> }
          </dl>

          @if (n.arquivo; as a) {
            <div class="documento-numero">
              <span>📄 {{ a.nome }}</span>
              @if (a.pode_baixar) { <button type="button" class="acao-secundaria acao-pequena" (click)="baixar(n)">Baixar</button> }
              @else { <small class="dica-formulario">🔒 Documento sigiloso: só quem reservou o número e o SuperRoot abrem o arquivo.</small> }
            </div>
          }

          <div class="acoes-numero">
            @if (n.pode_anexar) {
              <label class="acao-secundaria seletor-arquivo">Anexar documento<input type="file" (change)="anexar(n, $event)" /></label>
            }
            @if (n.pode_alterar_sigilo) {
              <label class="opcao-sigilo"><input type="checkbox" [checked]="n.sigiloso" (change)="alternarSigilo(n)" /> Documento sigiloso (só eu e o SuperRoot abrimos o arquivo)</label>
            }
            @if (n.pode_liberar) { <button type="button" class="acao-secundaria" (click)="abrirMotivo('liberar')">Liberar reserva</button> }
            @if (administra() && n.estado !== 'anulado') { <button type="button" class="acao-recusar" (click)="abrirMotivo('anular')">Anular número</button> }
          </div>

          @if (motivoAcao(); as acao) {
            <form class="form-motivo" (ngSubmit)="confirmarMotivo(n)">
              <div class="grade-formulario uma-coluna">
                <div><label for="pm-motivo">{{ acao === 'liberar' ? 'Motivo da liberação *' : 'Motivo da anulação *' }}</label>
                  <input id="pm-motivo" name="motivo" maxlength="2000" [(ngModel)]="motivo" /></div>
              </div>
              <button type="submit" [class]="acao === 'anular' ? 'acao-recusar' : 'acao-primaria'" [disabled]="!motivo.trim() || ocupado()">{{ acao === 'liberar' ? 'Liberar' : 'Anular' }}</button>
              <button type="button" class="acao-secundaria" (click)="motivoAcao.set(null)">Cancelar</button>
            </form>
          }

          <h3 class="subtitulo-numero">Linha do tempo</h3>
          <ol class="linha-do-tempo-protocolo">
            @for (e of n.eventos; track $index) {
              <li><b>{{ eventos[e.tipo] }}</b>@if (e.texto) { <span> · <span [innerHTML]="e.texto | linkificar"></span></span> }
                <small>{{ e.autor_nome }} · {{ e.ocorrido_em | date: 'dd/MM/yyyy HH:mm' }}</small></li>
            } @empty { <li>Sem movimentação.</li> }
          </ol>
        </div>
      </section>
    }
  `,
})
export class NumeracaoComponent implements OnInit {
  private readonly api = inject(ProtocoloApiService);
  private readonly contratosApi = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly acesso = inject(AcessoService);
  private readonly destruir = inject(DestroyRef);

  protected readonly rotulos = ROTULOS_ESTADO;
  protected readonly eventos = ROTULOS_EVENTO;
  protected readonly carregado = signal(false);
  protected readonly tipos = signal<TipoProtocolo[]>([]);
  protected readonly tipoId = signal('');
  protected readonly sequenciaId = signal('');
  protected readonly lista = signal<ListaNumeros | null>(null);
  protected readonly janela = signal<Janela>(null);
  protected readonly detalhe = signal<NumeroProtocolo | null>(null);
  protected readonly alvo = signal<NumeroProtocolo | null>(null);
  protected readonly ocupado = signal(false);
  protected readonly motivoAcao = signal<AcaoMotivo | null>(null);
  protected readonly contratos = signal<ResumoContrato[]>([]);
  protected readonly buscaContrato = signal('');
  protected finalidade = '';
  protected contratoId: string | null = null;
  protected motivo = '';
  private readonly digitacao = new Subject<string>();

  protected readonly administra = () => this.acesso.pode('protocolo', 'CONTROLE_TOTAL');
  protected readonly sequenciasDoTipo = computed<SequenciaProtocolo[]>(() => this.tipos().find((t) => t.id === this.tipoId())?.sequencias ?? []);

  ngOnInit(): void {
    this.digitacao.pipe(debounceTime(300), takeUntilDestroyed(this.destruir)).subscribe((termo) => {
      if (termo.trim().length < 2) { this.contratos.set([]); return; }
      this.contratosApi.listar(termo.trim(), 1, 10).subscribe({ next: (p) => this.contratos.set(p.itens), error: () => this.contratos.set([]) });
    });
    this.recarregarTipos();
  }

  private recarregarTipos(manter?: { tipo: string; sequencia: string }): void {
    this.api.tipos().subscribe({
      next: (r) => {
        this.tipos.set(r.itens);
        this.carregado.set(true);
        const tipo = r.itens.find((t) => t.id === (manter?.tipo ?? this.tipoId())) ?? r.itens[0];
        if (!tipo) return;
        this.tipoId.set(tipo.id);
        const sequencia = tipo.sequencias.find((s) => s.id === (manter?.sequencia ?? this.sequenciaId())) ?? tipo.sequencias[0];
        this.sequenciaId.set(sequencia?.id ?? '');
        this.carregarNumeros();
      },
      error: (e) => { this.carregado.set(true); this.dialogos.mostrarErro(e, 'Não foi possível carregar o Protocolo'); },
    });
  }

  protected escolherTipo(id: string): void {
    this.tipoId.set(id);
    // O exercício mais recente do tipo (ou o do ano corrente, se existir)
    const sequencias = this.tipos().find((t) => t.id === id)?.sequencias ?? [];
    this.sequenciaId.set((sequencias.find((s) => s.exercicio === new Date().getFullYear()) ?? sequencias[0])?.id ?? '');
    this.carregarNumeros();
  }

  protected escolherSequencia(id: string): void {
    this.sequenciaId.set(id);
    this.carregarNumeros();
  }

  private carregarNumeros(): void {
    this.lista.set(null);
    if (!this.sequenciaId()) return;
    this.api.numeros(this.sequenciaId()).subscribe({ next: (l) => this.lista.set(l), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected clicarNumero(n: NumeroProtocolo): void {
    // Livre: só a administração escolhe o número (os demais usam "Reservar próximo número")
    if (n.estado === 'livre') {
      if (this.administra()) this.abrirReserva(n);
      else this.dialogos.avisar('Reserva sequencial', 'Para manter a sequência, use "Reservar próximo número": o sistema entrega o menor número livre.');
      return;
    }
    this.api.detalhe(n.id).subscribe({ next: (d) => this.abrirDetalhe(d), error: (e) => this.dialogos.mostrarErro(e) });
  }

  private abrirDetalhe(d: NumeroProtocolo): void {
    this.detalhe.set(d);
    this.motivoAcao.set(null);
    this.motivo = '';
    this.janela.set('detalhe');
  }

  protected abrirReserva(n: NumeroProtocolo | null): void {
    this.alvo.set(n);
    this.finalidade = '';
    this.contratoId = null;
    this.buscaContrato.set('');
    this.contratos.set([]);
    this.janela.set('reservar');
  }

  protected buscarContratos(termo: string): void {
    this.buscaContrato.set(termo);
    this.digitacao.next(termo);
  }

  protected fechar(): void {
    this.janela.set(null);
    this.detalhe.set(null);
    this.alvo.set(null);
    this.motivoAcao.set(null);
  }

  protected reservar(): void {
    if (!this.finalidade.trim()) return;
    const dados = { finalidade: this.finalidade.trim(), contrato_id: this.contratoId };
    const alvo = this.alvo();
    this.ocupado.set(true);
    const chamada = alvo ? this.api.lancar(alvo.id, dados) : this.api.proximo(this.sequenciaId(), dados);
    chamada.subscribe({
      next: (n) => {
        this.ocupado.set(false);
        this.carregarNumeros();
        // O número reservado abre na hora, para anexar o documento ou marcar o sigilo
        this.abrirDetalhe(n);
      },
      error: (e) => {
        this.ocupado.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível reservar o número');
        this.carregarNumeros();
      },
    });
  }

  /** Aplica o resultado de uma ação ao detalhe aberto e à grade. */
  private atualizado(n: NumeroProtocolo): void {
    this.ocupado.set(false);
    this.detalhe.set(n);
    this.motivoAcao.set(null);
    this.motivo = '';
    this.carregarNumeros();
  }

  private falha(e: unknown, titulo: string): void {
    this.ocupado.set(false);
    this.dialogos.mostrarErro(e, titulo);
  }

  protected abrirMotivo(acao: AcaoMotivo): void {
    this.motivo = '';
    this.motivoAcao.set(acao);
  }

  protected confirmarMotivo(n: NumeroProtocolo): void {
    const acao = this.motivoAcao();
    if (!acao || !this.motivo.trim()) return;
    this.ocupado.set(true);
    const chamada = acao === 'liberar' ? this.api.liberar(n.id, this.motivo.trim()) : this.api.anular(n.id, this.motivo.trim());
    chamada.subscribe({ next: (r) => this.atualizado(r), error: (e) => this.falha(e, acao === 'liberar' ? 'Não foi possível liberar' : 'Não foi possível anular') });
  }

  protected anexar(n: NumeroProtocolo, evento: Event): void {
    const entrada = evento.target as HTMLInputElement;
    const arquivo = entrada.files?.[0];
    if (!arquivo) return;
    this.ocupado.set(true);
    this.api.anexar(n.id, arquivo).subscribe({ next: (r) => this.atualizado(r), error: (e) => this.falha(e, 'Não foi possível anexar o documento') });
    entrada.value = '';
  }

  protected alternarSigilo(n: NumeroProtocolo): void {
    this.api.sigilo(n.id, !n.sigiloso).subscribe({ next: (r) => this.atualizado(r), error: (e) => this.falha(e, 'Não foi possível alterar o sigilo') });
  }

  protected baixar(n: NumeroProtocolo): void {
    this.api.baixar(n.id, n.arquivo?.nome ?? 'documento').subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar o documento') });
  }
}
