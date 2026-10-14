// Criado por José Eduardo Santana Martins
// Este arquivo serve para a administração das notificações: eventos obrigatórios por setor ou usuário e o painel de entregas (e-mail e navegador).

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { NotificacoesApiService } from '../../../core/notificacoes/notificacoes-api.service';
import {
  CANAIS_NOTIFICACAO, CanalNotificacao, Destinatarios, EventoPreferencia, Obrigatoria, PainelEntregas, ROTULOS_CANAL,
} from '../../../core/notificacoes/notificacoes.models';
import { DialogosService } from '../../../shared/servicos/dialogos.service';

/**
 * Parte da tela "Notificações do sistema":
 * - **Obrigatórias:** a administração escolhe evento + canal para um setor ou usuário (ex.: "Conferir retenção" sempre por e-mail para o Financeiro).
 *   Quem recebe vê a caixa marcada e travada ("definida pela administração"). A lista começa vazia.
 * - **Painel de entregas:** quantas notificações saíram por e-mail e navegador, as falhas recentes e as inscrições do navegador com problema.
 */
@Component({
  selector: 'app-administracao-notificacoes',
  imports: [FormsModule],
  template: `
    <section class="painel-gestao" aria-labelledby="titulo-obrigatorias">
      <div class="barra-ferramentas">
        <div>
          <h2 id="titulo-obrigatorias">Notificações obrigatórias</h2>
          <p>Eventos que chegam por um canal para um setor ou usuário, sem que a pessoa possa desligar. Nada vem obrigatório de fábrica.</p>
        </div>
      </div>
      <form class="adm-form" (ngSubmit)="criar()">
        <div class="campo"><label for="obr-evento">Evento</label>
          <select id="obr-evento" name="evento" [(ngModel)]="evento" (ngModelChange)="canal = ''">
            <option value="">Escolha o evento</option>
            @for (e of eventos(); track e.chave) { <option [value]="e.chave">{{ e.rotulo }}</option> }
          </select></div>
        <div class="campo"><label for="obr-canal">Canal</label>
          <select id="obr-canal" name="canal" [(ngModel)]="canal">
            <option value="">Escolha o canal</option>
            @for (c of canaisDoEvento(); track c) { <option [value]="c">{{ rotulos[c] }}</option> }
          </select></div>
        <div class="campo"><label for="obr-tipo">Vale para</label>
          <select id="obr-tipo" name="tipo" [(ngModel)]="tipoAlvo" (ngModelChange)="alvo = null">
            <option value="setor">Um setor</option>
            <option value="usuario">Um usuário</option>
          </select></div>
        <div class="campo"><label for="obr-alvo">{{ tipoAlvo === 'setor' ? 'Setor' : 'Usuário' }}</label>
          <select id="obr-alvo" name="alvo" [(ngModel)]="alvo">
            <option [ngValue]="null">Escolha</option>
            @if (tipoAlvo === 'setor') { @for (s of destinatarios()?.setores ?? []; track s.id) { <option [ngValue]="s.id">{{ s.nome }}</option> } }
            @else { @for (u of destinatarios()?.usuarios ?? []; track u.id) { <option [ngValue]="u.id">{{ u.nome }}</option> } }
          </select></div>
        <div class="adm-botao"><button type="submit" class="acao-primaria" [disabled]="!evento || !canal || alvo === null">Tornar obrigatório</button></div>
      </form>
      <div class="tabela-gestao-envoltorio">
        <table class="tabela-gestao">
          <thead><tr><th>Evento</th><th>Canal</th><th>Vale para</th><th class="coluna-acoes">Ações</th></tr></thead>
          <tbody>
            @for (o of obrigatorias(); track o.id) {
              <tr>
                <td><strong>{{ o.evento_rotulo }}</strong></td>
                <td>{{ rotulos[o.canal] }}</td>
                <td>{{ o.setor_nome ? 'Setor: ' + o.setor_nome : 'Usuário: ' + o.usuario_nome }}</td>
                <td class="coluna-acoes"><button type="button" class="acao-recusar acao-pequena" (click)="remover(o)">Remover</button></td>
              </tr>
            } @empty { <tr><td class="estado-vazio" colspan="4">Nenhuma notificação obrigatória.</td></tr> }
          </tbody>
        </table>
      </div>
    </section>

    <section class="painel-gestao" aria-labelledby="titulo-painel-entregas">
      <div class="barra-ferramentas">
        <div>
          <h2 id="titulo-painel-entregas">Painel de entregas</h2>
          <p>O que saiu por e-mail e pelo navegador. As inscrições do navegador com 404/410, 10 falhas seguidas ou 90 dias sem uso são apagadas todo dia.</p>
        </div>
        <div class="campo adm-periodo"><label for="pe-dias">Período</label>
          <select id="pe-dias" name="dias" [(ngModel)]="dias" (ngModelChange)="carregarPainel()">
            <option [ngValue]="1">Último dia</option><option [ngValue]="7">Últimos 7 dias</option><option [ngValue]="30">Últimos 30 dias</option>
          </select></div>
      </div>
      @if (painel(); as p) {
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <thead><tr><th>Canal</th><th class="num">Enviadas</th><th class="num">Falhas</th></tr></thead>
            <tbody>@for (l of p.por_canal; track l.canal) { <tr><td>{{ rotulos[l.canal] }}</td><td class="num">{{ l.enviadas }}</td><td class="num">{{ l.falhas }}</td></tr> }</tbody>
          </table>
        </div>
        <p class="dica-formulario adm-nota">Navegadores inscritos: {{ p.inscricoes_total }}, dos quais {{ p.inscricoes_com_falhas }} com 3 ou mais falhas seguidas.</p>
        @if (p.ultimas_falhas.length) {
          <ul class="adm-erros">@for (f of p.ultimas_falhas; track $index) { <li>{{ f }}</li> }</ul>
        } @else { <p class="dica-formulario adm-nota">Nenhuma falha no período.</p> }
      }
    </section>
  `,
  styles: `
    :host { display: block; }
    section.painel-gestao { margin-top: 24px; }
    .adm-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px 16px; align-items: end; padding: 0 24px 16px; }
    .adm-botao { padding-bottom: 14px; }
    .adm-periodo { min-width: 190px; }
    .adm-nota { margin: 12px 24px 16px; }
    .adm-erros { margin: 0 24px 20px; padding-left: 18px; color: var(--cor-464f5a); font-size: 13px; display: grid; gap: 6px; }
  `,
})
export class AdministracaoNotificacoesComponent implements OnInit {
  private readonly api = inject(NotificacoesApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly rotulos = ROTULOS_CANAL;
  protected readonly obrigatorias = signal<Obrigatoria[]>([]);
  protected readonly eventos = signal<EventoPreferencia[]>([]);
  protected readonly destinatarios = signal<Destinatarios | null>(null);
  protected readonly painel = signal<PainelEntregas | null>(null);
  protected evento = '';
  protected canal: CanalNotificacao | '' = '';
  protected tipoAlvo: 'setor' | 'usuario' = 'setor';
  protected alvo: number | null = null;
  protected dias = 7;

  ngOnInit(): void {
    this.api.obrigatorias().subscribe({ next: (l) => this.obrigatorias.set(l), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar as obrigatórias') });
    this.api.preferencias().subscribe((p) => this.eventos.set(p.modulos.flatMap((m) => m.eventos)));
    this.api.destinatarios().subscribe((d) => this.destinatarios.set(d));
    this.carregarPainel();
  }

  /** Canais que o evento escolhido aceita (novidades do sistema só saem por e-mail). */
  protected canaisDoEvento(): CanalNotificacao[] {
    const e = this.eventos().find((x) => x.chave === this.evento);
    return e ? CANAIS_NOTIFICACAO.filter((c) => e.canais[c].disponivel) : [];
  }

  protected carregarPainel(): void {
    this.api.painelEntregas(this.dias).subscribe({ next: (p) => this.painel.set(p), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o painel') });
  }

  protected criar(): void {
    if (!this.evento || !this.canal || this.alvo === null) return;
    const dados = { evento: this.evento, canal: this.canal, setor_id: this.tipoAlvo === 'setor' ? this.alvo : null, usuario_id: this.tipoAlvo === 'usuario' ? this.alvo : null };
    this.api.criarObrigatoria(dados).subscribe({
      next: () => { this.evento = ''; this.canal = ''; this.alvo = null; this.api.obrigatorias().subscribe((l) => this.obrigatorias.set(l)); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar'),
    });
  }

  protected async remover(o: Obrigatoria): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Remover a obrigatoriedade?', mensagem: `"${o.evento_rotulo}" por ${ROTULOS_CANAL[o.canal].toLowerCase()} deixa de ser obrigatório para ${o.setor_nome ?? o.usuario_nome}. Cada pessoa passa a decidir por si.`,
      rotuloConfirmar: 'Remover', perigo: true,
    });
    if (!ok) return;
    this.api.removerObrigatoria(o.id).subscribe({
      next: () => this.api.obrigatorias().subscribe((l) => this.obrigatorias.set(l)),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível remover'),
    });
  }
}
