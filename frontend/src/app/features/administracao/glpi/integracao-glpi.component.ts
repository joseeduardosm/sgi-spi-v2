// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de Administração › Integração GLPI (endereço, tokens, liga/desliga e teste).

import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ambiente } from '../../../../environments/ambiente';
import { TrilhaComponent } from '../../../shared/componentes/trilha/trilha.component';
import { erroExibivel } from '../../../shared/utilitarios/erros-api';

/** Configuração da integração, como a API devolve (os tokens nunca vêm, só se existem). */
interface ConfiguracaoGlpi {
  ativo: boolean;
  url_base: string;
  possui_app_token: boolean;
  possui_user_token: boolean;
  configurada: boolean;
  prefixo_titulo: string;
  grupo_atribuido_id: number | null;
  sla_atendimento_id: number | null;
  sla_solucao_id: number | null;
  template_id: number | null;
  atualizado_em: string;
  atualizado_por: string;
}

interface ResultadoTeste {
  sucesso: boolean;
  mensagem: string;
  latencia_ms: number | null;
}

/** Integração com o GLPI (restrita ao SuperRoot): é por ela que o item "Abrir Chamado" cria o chamado no helpdesk. */
@Component({
  selector: 'app-integracao-glpi',
  imports: [FormsModule, DatePipe, TrilhaComponent],
  template: `
    <div class="cabecalho-pagina">
      <div>
        <app-trilha [itens]="[{ rotulo: 'Administração' }, { rotulo: 'Integração GLPI' }]" />
        <h1>Integração GLPI</h1>
        <small>Abertura de chamados pelo SGI: o chamado é criado no GLPI, em nome do usuário, pela API REST.</small>
      </div>
    </div>

    <section class="painel-gestao" aria-labelledby="titulo-glpi">
      <div class="barra-ferramentas"><div><h2 id="titulo-glpi">Conexão</h2>
        <p>Os tokens ficam cifrados no banco e nunca são exibidos. Deixe em branco para manter o que já está gravado.</p></div></div>

      @if (aviso(); as a) { <p class="aviso-admin" [class.erro]="a.erro" role="status">{{ a.texto }}</p> }

      @if (config(); as c) {
        <form class="grade-formulario" style="grid-template-columns: 1fr 1fr" (ngSubmit)="salvar()">
          <div class="ocupa-duas">
            <label for="glpi-url">Endereço do GLPI *</label>
            <input id="glpi-url" name="url" class="form-control" required maxlength="300" placeholder="https://chamados.spi.sp.gov.br" [(ngModel)]="url" />
            <small class="dica-formulario">Sem <code>/apirest.php</code>. O servidor do SGI precisa estar liberado no cliente de API do GLPI.</small>
          </div>
          <div>
            <label for="glpi-app">App-Token {{ c.possui_app_token ? '(gravado)' : '(opcional)' }}</label>
            <input id="glpi-app" name="app" type="password" class="form-control" autocomplete="new-password" maxlength="200" [(ngModel)]="appToken"
                   [placeholder]="c.possui_app_token ? 'Em branco mantém o atual' : ''" />
          </div>
          <div>
            <label for="glpi-user">user_token da conta de serviço {{ c.possui_user_token ? '(gravado)' : '*' }}</label>
            <input id="glpi-user" name="user" type="password" class="form-control" autocomplete="new-password" maxlength="200" [(ngModel)]="userToken"
                   [placeholder]="c.possui_user_token ? 'Em branco mantém o atual' : ''" />
          </div>
          <p class="secao-formulario ocupa-duas">Como o chamado é montado (formulário "Informática" do GLPI)</p>
          <div><label for="glpi-prefixo">Prefixo do título</label>
            <input id="glpi-prefixo" name="prefixo" class="form-control" maxlength="80" [(ngModel)]="prefixo" /><small class="dica-formulario">Título: <code>{{ prefixo || '…' }} | assunto</code></small></div>
          <div><label for="glpi-grupo">Grupo atribuído (id no GLPI)</label>
            <input id="glpi-grupo" name="grupo" type="number" min="0" class="form-control" [(ngModel)]="grupo" /><small class="dica-formulario">0 = nenhum. SUPORTE = 4.</small></div>
          <div><label for="glpi-sla-at">SLA de atendimento (id)</label>
            <input id="glpi-sla-at" name="slaat" type="number" min="0" class="form-control" [(ngModel)]="slaAtendimento" /><small class="dica-formulario">0 = nenhum. TECNOLOGIA - ATENDIMENTO = 2.</small></div>
          <div><label for="glpi-sla-so">SLA de solução (id)</label>
            <input id="glpi-sla-so" name="slaso" type="number" min="0" class="form-control" [(ngModel)]="slaSolucao" /><small class="dica-formulario">0 = nenhum. TECNOLOGIA - SOLUÇÃO = 1.</small></div>
          <div><label for="glpi-modelo">Modelo de chamado (id)</label>
            <input id="glpi-modelo" name="modelo" type="number" min="0" class="form-control" [(ngModel)]="modelo" /><small class="dica-formulario">0 = nenhum. Padrão do GLPI = 1.</small></div>
          <div class="ocupa-duas">
            <label class="opcao-meus"><input type="checkbox" name="ativo" [(ngModel)]="ativo" /> Integração ativa (o item "Abrir Chamado" cria o chamado no GLPI)</label>
          </div>
          <div class="ocupa-duas acoes-formulario">
            <button type="button" class="acao-secundaria" [disabled]="ocupado() || !c.configurada" (click)="testar()">Testar conexão</button>
            <button type="submit" class="acao-primaria" [disabled]="ocupado() || !url.trim()">Salvar</button>
          </div>
        </form>
        @if (teste(); as t) {
          <p class="aviso-bloco" [class.erro]="!t.sucesso" role="status">
            {{ t.mensagem }}@if (t.latencia_ms !== null) { <span> ({{ t.latencia_ms }} ms)</span> }
          </p>
        }
        <p class="dica-formulario">Atualizado por {{ c.atualizado_por || '—' }} em {{ c.atualizado_em | date: 'dd/MM/yyyy HH:mm' }}.</p>
      } @else {
        <p class="estado-vazio">Carregando…</p>
      }
    </section>
  `,
  // O painel não tem margem interna própria: o conteúdo abaixo do cabeçalho recebe o mesmo recuo (24px) do cabeçalho
  styles: `
    .painel-gestao > :not(.barra-ferramentas) { margin-inline: 24px; }
    .painel-gestao > .barra-ferramentas + * { margin-top: 20px; }
    .painel-gestao > :last-child { margin-bottom: 22px; }
  `,
})
export class IntegracaoGlpiComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/integracao-glpi`;

  protected readonly config = signal<ConfiguracaoGlpi | null>(null);
  protected readonly aviso = signal<{ texto: string; erro: boolean } | null>(null);
  protected readonly teste = signal<ResultadoTeste | null>(null);
  protected readonly ocupado = signal(false);
  protected url = '';
  protected appToken = '';
  protected userToken = '';
  protected ativo = false;
  protected prefixo = '';
  protected grupo = 0;
  protected slaAtendimento = 0;
  protected slaSolucao = 0;
  protected modelo = 0;

  ngOnInit(): void {
    this.http.get<ConfiguracaoGlpi>(this.base).subscribe({ next: (c) => this.preencher(c), error: (e) => this.avisar(erroExibivel(e).mensagem, true) });
  }

  private preencher(c: ConfiguracaoGlpi): void {
    this.config.set(c);
    this.url = c.url_base;
    this.ativo = c.ativo;
    this.prefixo = c.prefixo_titulo;
    this.grupo = c.grupo_atribuido_id ?? 0;
    this.slaAtendimento = c.sla_atendimento_id ?? 0;
    this.slaSolucao = c.sla_solucao_id ?? 0;
    this.modelo = c.template_id ?? 0;
    this.appToken = this.userToken = '';
  }

  private avisar(texto: string, erro = false): void {
    this.aviso.set({ texto, erro });
  }

  /** Salva (token em branco mantém o gravado). */
  protected salvar(): void {
    this.ocupado.set(true);
    this.teste.set(null);
    const corpo = { ativo: this.ativo, url_base: this.url.trim(), app_token: this.appToken || null, user_token: this.userToken || null,
      prefixo_titulo: this.prefixo.trim() || null, grupo_atribuido_id: this.grupo ?? 0, sla_atendimento_id: this.slaAtendimento ?? 0, sla_solucao_id: this.slaSolucao ?? 0, template_id: this.modelo ?? 0 };
    this.http.put<ConfiguracaoGlpi>(this.base, corpo).subscribe({
      next: (c) => {
        this.ocupado.set(false);
        this.preencher(c);
        this.avisar('Configuração salva.');
      },
      error: (e) => {
        this.ocupado.set(false);
        this.avisar(erroExibivel(e).mensagem, true);
      },
    });
  }

  /** Abre e encerra uma sessão no GLPI com o que está gravado. */
  protected testar(): void {
    this.ocupado.set(true);
    this.http.post<ResultadoTeste>(`${this.base}/testar`, {}).subscribe({
      next: (r) => {
        this.ocupado.set(false);
        this.teste.set(r);
      },
      error: (e) => {
        this.ocupado.set(false);
        this.avisar(erroExibivel(e).mensagem, true);
      },
    });
  }
}
