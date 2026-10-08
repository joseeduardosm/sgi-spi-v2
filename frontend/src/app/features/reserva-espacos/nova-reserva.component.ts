// Criado por José Eduardo Santana Martins
// Este arquivo serve para solicitar (ou, para o fiscal, registrar já deferida) uma reserva e para alterar uma reserva aguardando aprovação.

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoReservasComponent } from './cabecalho-reservas.component';
import { EstadoReservasService } from './estado-reservas.service';
import { ReservasApiService } from './reservas-api.service';
import { GravacaoReserva, isoLocal, Recorrencia, UsuarioBusca } from './reservas.models';

@Component({
  selector: 'app-nova-reserva',
  imports: [FormsModule, RouterLink, CabecalhoReservasComponent],
  template: `
    <app-cabecalho-reservas [titulo]="editando() ? 'Alterar reserva' : 'Nova reserva'"
      [descricao]="editando() ? 'Só é possível alterar enquanto a reserva aguarda aprovação.' : 'Informe quando precisa do espaço; os fiscais analisam a solicitação.'" />
    <section class="painel-gestao protocolo reservas">
      <form class="grade-formulario" (ngSubmit)="salvar()" #f="ngForm">
        <div class="ocupa-duas"><label for="nr-titulo">Título da reunião ou evento</label>
          <input id="nr-titulo" name="titulo" maxlength="200" required [(ngModel)]="dados.titulo" /></div>
        <div><label for="nr-data">Data</label><input id="nr-data" name="data" type="date" required [(ngModel)]="dados.data" (ngModelChange)="atualizarEspacos()" /></div>
        <div class="par-horas">
          <div><label for="nr-ini">Início</label><input id="nr-ini" name="ini" type="time" required [(ngModel)]="dados.hora_inicio" (ngModelChange)="atualizarEspacos()" /></div>
          <div><label for="nr-fim">Término</label><input id="nr-fim" name="fim" type="time" required [(ngModel)]="dados.hora_fim" (ngModelChange)="atualizarEspacos()" /></div>
        </div>
        <div><label for="nr-espaco">Espaço</label>
          <select id="nr-espaco" name="espaco" required [(ngModel)]="dados.espaco_id">
            <option [ngValue]="0" disabled>Escolha o espaço</option>
            @for (e of opcoesEspaco(); track e.id) { <option [ngValue]="e.id">{{ e.nome }}{{ e.capacidade ? ' (' + e.capacidade + ' lugares)' : '' }}</option> }
          </select>
          @if (!editando() && livres() !== null) { <small class="dica">{{ livres()!.length }} espaço(s) livre(s) neste horário.</small> }</div>
        <div><label for="nr-part">Participantes (opcional)</label><input id="nr-part" name="part" type="number" min="1" [(ngModel)]="dados.participantes" /></div>
        @if (!editando()) {
          <div><label for="nr-rec">Repetir</label>
            <select id="nr-rec" name="rec" [(ngModel)]="dados.recorrencia">
              <option value="nenhuma">Não repete</option><option value="diaria">Todos os dias</option><option value="semanal">Toda semana</option>
              <option value="quinzenal">A cada 15 dias</option><option value="mensal">Todo mês</option>
            </select></div>
          @if (dados.recorrencia !== 'nenhuma') {
            <div><label for="nr-ate">Repetir até</label><input id="nr-ate" name="ate" type="date" required [min]="dados.data" [(ngModel)]="dados.recorrencia_ate" /></div>
          }
        }
        @if (estado.ehFiscal() && !editando()) {
          <div class="ocupa-duas caixa-predefinida">
            <label class="linha-caixa"><input type="checkbox" name="pre" [(ngModel)]="predefinida" /> Reserva predefinida (já registrada como deferida, em nome de outra pessoa)</label>
          </div>
          @if (predefinida) {
            <div><label for="nr-resp">Responsável (usuário do SGI)</label>
              <input id="nr-resp" name="resp" placeholder="Digite para buscar" [ngModel]="busca" (ngModelChange)="buscar($event)" autocomplete="off" />
              @if (encontrados().length) {
                <ul class="lista-busca">@for (u of encontrados(); track u.id) { <li><button type="button" (click)="escolher(u)">{{ u.nome }} <small>{{ u.login }}</small></button></li> }</ul>
              }
              @if (dados.responsavel_id) { <small class="dica">Escolhido: {{ busca }}</small> }</div>
            <div><label for="nr-resp-nome">ou nome digitado</label><input id="nr-resp-nome" name="respnome" maxlength="200" [(ngModel)]="dados.responsavel_nome" [disabled]="!!dados.responsavel_id" /></div>
          }
        }
        <div class="ocupa-duas"><label for="nr-obs">Observações (opcional)</label>
          <textarea id="nr-obs" name="obs" rows="3" maxlength="4000" [(ngModel)]="dados.observacoes"></textarea></div>
        <div class="ocupa-duas acoes-formulario">
          <button type="submit" class="acao-primaria" [disabled]="f.invalid || enviando() || !dados.espaco_id">{{ editando() ? 'Salvar alterações' : predefinida ? 'Registrar reserva' : 'Enviar solicitação' }}</button>
          <a class="acao-secundaria" routerLink="/reserva-espacos">Cancelar</a>
        </div>
      </form>
    </section>
  `,
})
export class NovaReservaComponent implements OnInit {
  private readonly api = inject(ReservasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  protected readonly estado = inject(EstadoReservasService);

  protected readonly editando = signal<number | null>(null);
  protected readonly enviando = signal(false);
  protected readonly livres = signal<{ id: number }[] | null>(null);
  protected readonly encontrados = signal<UsuarioBusca[]>([]);
  protected predefinida = false;
  protected busca = '';
  protected dados: GravacaoReserva = {
    espaco_id: 0, data: isoLocal(new Date()), hora_inicio: '09:00', hora_fim: '10:00', titulo: '', observacoes: '', participantes: null,
    recorrencia: 'nenhuma' as Recorrencia, recorrencia_ate: null, responsavel_id: null, responsavel_nome: '',
  };

  protected opcoesEspaco = () => this.estado.espacos().filter((e) => e.ativo);

  ngOnInit(): void {
    this.estado.carregar().subscribe();
    const id = Number(this.rota.snapshot.paramMap.get('id'));
    const data = this.rota.snapshot.queryParamMap.get('data');
    if (data) this.dados.data = data;
    if (id) {
      this.editando.set(id);
      this.api.detalhe(id).subscribe({
        next: (r) => {
          this.dados = { ...this.dados, espaco_id: r.espaco_id, data: r.data, hora_inicio: r.hora_inicio.slice(0, 5), hora_fim: r.hora_fim.slice(0, 5), titulo: r.titulo, observacoes: r.observacoes, participantes: r.participantes };
        },
        error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a reserva'),
      });
    } else this.atualizarEspacos();
  }

  protected atualizarEspacos(): void {
    const { data, hora_inicio: ini, hora_fim: fim } = this.dados;
    if (this.editando() || !data || !ini || !fim || fim <= ini) return this.livres.set(null);
    this.api.disponibilidade(data, ini, fim).subscribe({ next: (l) => this.livres.set(l), error: () => this.livres.set(null) });
  }

  protected buscar(texto: string): void {
    this.busca = texto;
    this.dados.responsavel_id = null;
    if (texto.trim().length < 2) return this.encontrados.set([]);
    this.api.usuarios(texto.trim()).subscribe((u) => this.encontrados.set(u));
  }

  protected escolher(u: UsuarioBusca): void {
    this.dados.responsavel_id = u.id;
    this.busca = u.nome;
    this.dados.responsavel_nome = '';
    this.encontrados.set([]);
  }

  protected salvar(): void {
    this.enviando.set(true);
    const falha = (e: unknown) => { this.enviando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível salvar a reserva'); };
    const id = this.editando();
    if (id) {
      this.api.editar(id, this.dados).subscribe({ next: () => this.roteador.navigate(['/reserva-espacos/reservas', id]), error: falha });
      return;
    }
    const dados = { ...this.dados, recorrencia_ate: this.dados.recorrencia === 'nenhuma' ? null : this.dados.recorrencia_ate };
    this.api.solicitar(dados, this.predefinida).subscribe({
      next: (r) => {
        this.enviando.set(false);
        const resumo = r.reservas.length > 1 ? `${r.reservas.length} reservas foram criadas.` : 'A solicitação foi enviada.';
        if (r.avisos.length) this.dialogos.avisar('Reserva registrada', `${resumo}\n\nAtenção:\n${r.avisos.join('\n')}`);
        this.roteador.navigate(['/reserva-espacos/reservas', r.reservas[0].id]);
      },
      error: falha,
    });
  }
}
