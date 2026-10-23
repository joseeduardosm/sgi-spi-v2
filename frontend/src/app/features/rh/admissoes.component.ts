// Criado por José Eduardo Santana Martins
// Este arquivo serve para a lista de admissões do RH (a trilha de quem está entrando na SPI), com busca, filtro por situação e início de nova admissão a partir de uma ficha.

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { RhAdmissaoApiService } from './rh-admissao-api.service';
import { ResumoAdmissao } from './rh-admissao.models';
import { RhPreCadastroApiService } from './rh-pre-cadastro-api.service';
import { ResumoFicha } from './rh-pre-cadastro.models';

const SITUACOES: [string, string][] = [['andamento', 'Em andamento'], ['concluida', 'Concluídas'], ['cancelada', 'Canceladas']];

/** Admissões: cada linha é a trilha de uma pessoa (chamado, documentos, resolução, Protocolo, publicação, e-mail, posse, entrada no SGI). */
@Component({
  selector: 'app-admissoes',
  imports: [FormsModule, RouterLink, CabecalhoRhComponent, EsqueletoComponent],
  host: { '(document:keydown.escape)': 'novaAberta.set(false)' },
  template: `
    <app-cabecalho-rh titulo="Admissões" [trilha]="['Admissões']" descricao="Da ficha à posse: chamado no GLPI, documentos, resolução, número no Protocolo, publicação, e-mail e entrada no SGI." />

    <section class="painel-gestao" aria-labelledby="titulo-admissoes">
      <div class="barra-ferramentas">
        <div><h2 id="titulo-admissoes">Admissões</h2><p>{{ itens().length }} admissão(ões) encontrada(s).</p></div>
        <div class="acoes-formulario"><button type="button" class="acao-primaria" (click)="abrirNova()"><span>+</span> Nova admissão</button></div>
      </div>
      <div class="filtros-gestao">
        <input type="search" aria-label="Buscar" placeholder="Buscar por nome, login, cargo ou unidade" [(ngModel)]="busca" (ngModelChange)="carregar()" />
      </div>
      <div class="chips-filtro" role="group" aria-label="Situação">
        <button type="button" [class.ativo]="status === ''" (click)="filtrar('')">Todas</button>
        @for (s of situacoes; track s[0]) { <button type="button" [class.ativo]="status === s[0]" (click)="filtrar(s[0])">{{ s[1] }}</button> }
      </div>
      <div class="tabela-gestao-envoltorio">
        <table class="tabela-gestao">
          <thead><tr><th>Pessoa</th><th>Cargo</th><th>Etapa</th><th>Situação</th><th class="coluna-acoes">Ações</th></tr></thead>
          <tbody>
            @if (carregando()) { <tr><td colspan="5"><app-esqueleto tipo="tabela" [colunas]="4" [linhas]="5" /></td></tr> }
            @for (a of itens(); track a.id) {
              <tr>
                <td><strong>{{ a.nome }}</strong>@if (a.login_proposto) { <small class="texto-codigo">{{ a.login_proposto }}</small> }</td>
                <td>{{ a.cargo_rotulo }}<small>{{ a.setor_nome }}</small></td>
                <td>{{ a.status === 'andamento' ? a.etapa_rotulo : '—' }}</td>
                <td><span [class]="a.status === 'andamento' ? 'selo-situacao alerta' : a.status === 'concluida' ? 'selo-situacao' : 'selo-origem'">{{ rotulo(a.status) }}</span></td>
                <td class="coluna-acoes"><div class="acoes-linha"><a class="acao-secundaria acao-pequena" [routerLink]="['/rh/admissoes', a.id]">Abrir</a></div></td>
              </tr>
            } @empty {
              @if (!carregando()) { <tr><td class="estado-vazio" colspan="5">Nenhuma admissão encontrada.</td></tr> }
            }
          </tbody>
        </table>
      </div>
    </section>

    @if (novaAberta()) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="novaAberta.set(false)"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-nova-admissao">
        <header>
          <div><span class="modal-sobretitulo">Admissões</span><h2 id="titulo-nova-admissao">Nova admissão</h2></div>
          <button type="button" aria-label="Fechar" (click)="novaAberta.set(false)">×</button>
        </header>
        <form (ngSubmit)="iniciar()">
          <div class="grade-formulario">
            <div class="ocupa-duas"><label for="adm-ficha">Ficha de pré-cadastro *</label>
              <select id="adm-ficha" name="ficha" [(ngModel)]="fichaEscolhida">
                <option [ngValue]="0">Escolher…</option>
                @for (f of fichas(); track f.id) { <option [ngValue]="f.id">{{ f.nome_completo }} · {{ f.cargo_rotulo }} · {{ f.login_proposto }}</option> }
              </select></div>
          </div>
          <p class="dica-formulario">Só aparecem fichas com login proposto e cargo pretendido (uma vaga de RH &gt; Cargos) e sem admissão iniciada.</p>
          <footer>
            <button type="button" class="acao-secundaria" (click)="novaAberta.set(false)">Cancelar</button>
            <button type="submit" class="acao-primaria" [disabled]="!fichaEscolhida">Iniciar admissão</button>
          </footer>
        </form>
      </section>
    }
  `,
})
export class AdmissoesComponent implements OnInit {
  private readonly api = inject(RhAdmissaoApiService);
  private readonly fichasApi = inject(RhPreCadastroApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);

  protected readonly situacoes = SITUACOES;
  protected readonly itens = signal<ResumoAdmissao[]>([]);
  protected readonly fichas = signal<ResumoFicha[]>([]);
  protected readonly carregando = signal(true);
  protected readonly novaAberta = signal(false);
  protected busca = '';
  protected status = 'andamento';
  protected fichaEscolhida = 0;

  ngOnInit(): void {
    this.carregar();
  }

  protected carregar(): void {
    this.carregando.set(true);
    this.api.listar(this.status, this.busca.trim()).subscribe({
      next: (l) => { this.itens.set(l); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar as admissões'); },
    });
  }

  protected filtrar(status: string): void {
    this.status = status;
    this.carregar();
  }

  protected rotulo(s: string): string {
    return SITUACOES.find((x) => x[0] === s)?.[1] ?? s;
  }

  protected abrirNova(): void {
    this.fichaEscolhida = 0;
    // Fichas ainda sem admissão: em rascunho ou aguardando a conta, com login e cargo
    this.fichasApi.listar().subscribe((l) => this.fichas.set(l.filter((f) => ['rascunho', 'aguardando_conta'].includes(f.status) && f.login_proposto && f.cargo_rotulo)));
    this.novaAberta.set(true);
  }

  protected iniciar(): void {
    this.dialogos.executar(this.api.iniciar(this.fichaEscolhida), 'Iniciando…').subscribe({
      next: (a) => { this.novaAberta.set(false); void this.roteador.navigate(['/rh/admissoes', a.id]); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível iniciar a admissão'),
    });
  }
}
