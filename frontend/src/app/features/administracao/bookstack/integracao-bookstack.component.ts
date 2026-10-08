// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de Administração › Integração BookStack (endereço, token, liga/desliga e teste).

import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ambiente } from '../../../../environments/ambiente';
import { TrilhaComponent } from '../../../shared/componentes/trilha/trilha.component';
import { erroExibivel } from '../../../shared/utilitarios/erros-api';

/** Configuração como a API devolve (o token nunca vem, só se existe). */
interface ConfiguracaoBookstack {
  ativo: boolean;
  url_base: string;
  possui_token: boolean;
  livros_permitidos: string;
  configurada: boolean;
  atualizado_em: string;
  atualizado_por: string;
}

interface ResultadoTeste {
  sucesso: boolean;
  mensagem: string;
  latencia_ms: number | null;
  livros_visiveis: number | null;
}

/** Integração com o BookStack (restrita ao SuperRoot): é por ela que o módulo Manuais lê as instruções. */
@Component({
  selector: 'app-integracao-bookstack',
  imports: [FormsModule, DatePipe, TrilhaComponent],
  template: `
    <div class="cabecalho-pagina">
      <div>
        <app-trilha [itens]="[{ rotulo: 'Administração' }, { rotulo: 'Integração BookStack' }]" />
        <h1>Integração BookStack</h1>
        <small>Os manuais são escritos no BookStack e lidos pelo portal (módulo Manuais) com uma conta de serviço somente leitura.</small>
      </div>
    </div>

    <section class="painel-gestao" aria-labelledby="titulo-bookstack">
      <div class="barra-ferramentas"><div><h2 id="titulo-bookstack">Conexão</h2>
        <p>No BookStack, crie um usuário só de leitura, dê a ele o direito "Acessar a API do sistema" e gere um token (ID e segredo). O token fica cifrado no banco e nunca é exibido; deixe em branco para manter o gravado.</p></div></div>

      @if (aviso(); as a) { <p class="aviso-admin" [class.erro]="a.erro" role="status">{{ a.texto }}</p> }

      @if (config(); as c) {
        <form class="grade-formulario" style="grid-template-columns: 1fr 1fr" (ngSubmit)="salvar()">
          <div class="ocupa-duas">
            <label for="bs-url">Endereço do BookStack *</label>
            <input id="bs-url" name="url" class="form-control" required maxlength="300" placeholder="https://instrucoes.spi.sp.gov.br" [(ngModel)]="url" />
          </div>
          <div>
            <label for="bs-id">ID do token {{ c.possui_token ? '(gravado)' : '*' }}</label>
            <input id="bs-id" name="id" type="password" class="form-control" autocomplete="new-password" maxlength="200" [(ngModel)]="tokenId"
                   [placeholder]="c.possui_token ? 'Em branco mantém o atual' : ''" />
          </div>
          <div>
            <label for="bs-segredo">Segredo do token {{ c.possui_token ? '(gravado)' : '*' }}</label>
            <input id="bs-segredo" name="segredo" type="password" class="form-control" autocomplete="new-password" maxlength="200" [(ngModel)]="tokenSegredo"
                   [placeholder]="c.possui_token ? 'Em branco mantém o atual' : ''" />
          </div>
          <div class="ocupa-duas">
            <label for="bs-livros">Livros exibidos (ids)</label>
            <input id="bs-livros" name="livros" class="form-control" maxlength="200" placeholder="147" pattern="\s*(\d+\s*(,\s*\d+\s*)*)?" [(ngModel)]="livros" />
            <small class="dica-formulario">Ids dos livros do BookStack que o portal mostra, separados por vírgula (o id está no endereço, em <code>/manuais/livros/147</code>). Vazio = nenhum livro é exibido. Com um só livro, o item Manuais abre direto nele.</small>
          </div>
          <div class="ocupa-duas">
            <label class="opcao-meus"><input type="checkbox" name="ativo" [(ngModel)]="ativo" /> Integração ativa (o módulo Manuais lê o BookStack)</label>
          </div>
          <div class="ocupa-duas acoes-formulario">
            <button type="button" class="acao-secundaria" [disabled]="ocupado() || !c.configurada" (click)="testar()">Testar conexão</button>
            <button type="submit" class="acao-primaria" [disabled]="ocupado() || !url.trim()">Salvar</button>
          </div>
        </form>
        @if (teste(); as t) {
          <p class="aviso-bloco" [class.erro]="!t.sucesso" role="status">
            {{ t.mensagem }}@if (t.latencia_ms !== null) { <span> ({{ t.latencia_ms }} ms)</span> }@if (t.livros_visiveis !== null) { <span> · a conta enxerga {{ t.livros_visiveis }} livro(s)</span> }
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
export class IntegracaoBookstackComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/integracao-bookstack`;

  protected readonly config = signal<ConfiguracaoBookstack | null>(null);
  protected readonly aviso = signal<{ texto: string; erro: boolean } | null>(null);
  protected readonly teste = signal<ResultadoTeste | null>(null);
  protected readonly ocupado = signal(false);
  protected url = '';
  protected tokenId = '';
  protected tokenSegredo = '';
  protected ativo = false;
  protected livros = '';

  ngOnInit(): void {
    this.http.get<ConfiguracaoBookstack>(this.base).subscribe({ next: (c) => this.preencher(c), error: (e) => this.avisar(erroExibivel(e).mensagem, true) });
  }

  private preencher(c: ConfiguracaoBookstack): void {
    this.config.set(c);
    this.url = c.url_base;
    this.ativo = c.ativo;
    this.livros = c.livros_permitidos;
    this.tokenId = this.tokenSegredo = '';
  }

  private avisar(texto: string, erro = false): void {
    this.aviso.set({ texto, erro });
  }

  /** Salva (token em branco mantém o gravado). */
  protected salvar(): void {
    this.ocupado.set(true);
    this.teste.set(null);
    const corpo = { ativo: this.ativo, url_base: this.url.trim(), token_id: this.tokenId.trim() || null, token_segredo: this.tokenSegredo.trim() || null, livros_permitidos: this.livros.trim() };
    this.http.put<ConfiguracaoBookstack>(this.base, corpo).subscribe({
      next: (c) => { this.preencher(c); this.avisar('Configuração salva.'); this.ocupado.set(false); },
      error: (e) => { this.avisar(erroExibivel(e).mensagem, true); this.ocupado.set(false); },
    });
  }

  protected testar(): void {
    this.ocupado.set(true);
    this.http.post<ResultadoTeste>(`${this.base}/testar`, {}).subscribe({
      next: (r) => { this.teste.set(r); this.ocupado.set(false); },
      error: (e) => { this.avisar(erroExibivel(e).mensagem, true); this.ocupado.set(false); },
    });
  }
}
