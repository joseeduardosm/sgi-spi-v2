// Criado por José Eduardo Santana Martins
// Este arquivo serve para solicitar a movimentação de bens: escolhe os bens (leitura de código, chapa ou número de série digitados), o destino e o motivo.
import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { FilaOfflineService } from './fila-offline.service';
import { LeitorCodigoComponent } from './leitor-codigo.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { BuscaBemComponent } from './busca-bem.component';
import { Bem } from './patrimonio.models';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { SeletorSalaComponent } from './seletor-sala.component';

/** Bem escolhido na solicitação; sem sinal, só a chapa é conhecida (`verificado` falso). */
interface Escolhido { chapa: string; id?: string; descricao: string; sala: string; verificado: boolean }

/** `/patrimonio/movimentacoes/nova` (`?bem=<id>` já escolhe um bem). Sem sinal, o pedido vai para a fila do aparelho com as chapas lidas. */
@Component({
  selector: 'app-nova-movimentacao',
  imports: [FormsModule, RouterLink, CabecalhoPatrimonioComponent, SeletorSalaComponent, LeitorCodigoComponent, BuscaBemComponent],
  template: `
    <app-cabecalho-patrimonio titulo="Solicitar movimentação" descricao="Escolha os bens (de salas diferentes, se for o caso), o destino e o motivo." />
    <form class="painel-gestao patrimonio pat-formulario" (ngSubmit)="enviar()">
      <h3 class="pat-subtitulo">1. Bens</h3>
      <div class="pat-linha-campo">
        <app-busca-bem [(texto)]="chapa" nome="chapa" placeholder="Digite parte da chapa ou do nº de série" (escolhido)="aceitar($event)" (enviar)="adicionar($event)" />
        <button type="button" class="acao-secundaria" (click)="adicionar(chapa)">Adicionar</button>
        <button type="button" class="acao-secundaria" (click)="lendo.set(true)">Ler código</button>
      </div>
      <ul class="pat-lista-itens">
        @for (b of escolhidos(); track b.chapa) {
          <li><div><strong>{{ b.chapa }}</strong> <span>{{ b.descricao || 'Bem ainda não verificado (sem conexão)' }}</span><small>{{ b.sala }}</small></div>
            <button type="button" class="acao-recusar acao-pequena" (click)="tirar(b.chapa)">Tirar</button></li>
        } @empty { <li class="estado-vazio">Nenhum bem escolhido.</li> }
      </ul>

      <h3 class="pat-subtitulo">2. Destino</h3>
      <app-seletor-sala nome="destino" rotulo="Sala de destino" [leitor]="true" placeholder="Escolha a sala de destino" [(valor)]="destino" />
      <h3 class="pat-subtitulo">3. Motivo</h3>
      <textarea name="motivo" rows="3" placeholder="Por que os bens vão mudar de sala?" [(ngModel)]="motivo"></textarea>

      <div class="pat-barra-inferior">
        <a class="acao-secundaria" routerLink="/patrimonio/movimentacoes">Cancelar</a>
        <button type="submit" class="acao-primaria" [disabled]="enviando() || !escolhidos().length || !destino || !motivo.trim()">{{ enviando() ? 'Enviando…' : 'Solicitar movimentação' }}</button>
      </div>
    </form>
    @if (lendo()) { <app-leitor-codigo [continuo]="true" (lido)="adicionar($event)" (fechar)="lendo.set(false)" /> }
  `,
})
export class NovaMovimentacaoComponent implements OnInit {
  private readonly api = inject(PatrimonioApiService);
  private readonly fila = inject(FilaOfflineService);
  private readonly roteador = inject(Router);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(PatrimonioEstadoService);

  readonly bem = input<string>('');
  /** `?destino=<sala>` já escolhe a sala de destino (vem do cadastro de um bem que já existe). */
  readonly destinoInicial = input<string>('', { alias: 'destino' });
  protected readonly escolhidos = signal<Escolhido[]>([]);
  protected readonly lendo = signal(false);
  protected readonly enviando = signal(false);
  protected chapa = '';
  protected destino = '';
  protected motivo = '';

  ngOnInit(): void {
    void this.estado.carregar();
    if (this.destinoInicial()) this.destino = this.destinoInicial();
    if (this.bem()) this.api.bem(this.bem()).subscribe((b) => this.incluir(this.deBem(b)));
  }

  /** Bem sem chapa (só número de série) entra pelo id: o rótulo "S/N ..." serve de chave na lista. */
  private deBem(b: Bem): Escolhido {
    return { chapa: b.chapa ?? b.rotulo, id: b.chapa ? undefined : b.id, descricao: b.descricao, sala: b.sala_rotulo, verificado: true };
  }

  private incluir(b: Escolhido): void {
    if (!this.escolhidos().some((x) => x.chapa.toLowerCase() === b.chapa.toLowerCase())) this.escolhidos.update((l) => [...l, b]);
  }

  /** Bem escolhido na lista de sugestões ou achado pela chapa/série: avisa se não pode ser movimentado agora; senão entra na solicitação. */
  protected aceitar(b: Bem): void {
    if (['baixado', 'extraviado'].includes(b.situacao) || b.classificacao_pendente || b.em_movimentacao) { this.dialogos.avisar('Bem indisponível', `O bem ${b.rotulo} não pode ser movimentado agora (${b.baixado_em ? 'baixado' : b.situacao === 'extraviado' ? 'extraviado' : b.classificacao_pendente ? 'classificação pendente' : 'já está em outra movimentação'}).`); return; }
    this.incluir(this.deBem(b));
  }

  /** Confere o bem no servidor (mostra a descrição e já avisa se ele não pode ser movimentado); sem sinal, guarda só a chapa. */
  protected adicionar(chapa: string): void {
    const c = chapa.trim();
    this.chapa = '';
    if (!c) return;
    if (!this.fila.online()) { this.incluir({ chapa: c, descricao: '', sala: '', verificado: false }); return; }
    this.api.bemPorChapa(c).subscribe({
      next: (b) => this.aceitar(b),
      error: (e) => (e?.status === 0 ? this.incluir({ chapa: c, descricao: '', sala: '', verificado: false }) : this.dialogos.avisar('Bem não encontrado', `Não há bem com a chapa ou o número de série ${c}.`)),
    });
  }

  protected tirar(chapa: string): void {
    this.escolhidos.update((l) => l.filter((b) => b.chapa !== chapa));
  }

  protected enviar(): void {
    const corpo = { id_cliente: crypto.randomUUID(), chapas: this.escolhidos().filter((b) => !b.id).map((b) => b.chapa), bens_ids: this.escolhidos().filter((b) => b.id).map((b) => b.id!), destino_id: this.destino, motivo: this.motivo.trim() };
    const guardar = () => this.fila.enfileirar({ tipo: 'solicitar_movimentacao', corpo }, `Movimentação de ${this.escolhidos().length} bem(ns)`).then(() => {
      this.dialogos.avisar('Guardado no aparelho', 'Sem conexão: a solicitação será enviada quando o sinal voltar.');
      void this.roteador.navigate(['/patrimonio/movimentacoes']);
    });
    if (!this.fila.online()) { void guardar(); return; }
    this.enviando.set(true);
    this.api.solicitarMovimentacao(corpo).subscribe({
      next: (m) => void this.roteador.navigate(['/patrimonio/movimentacoes', m.id]),
      error: (e) => { this.enviando.set(false); if (e?.status === 0) void guardar(); else this.dialogos.mostrarErro(e, 'Não foi possível solicitar a movimentação'); },
    });
  }
}
