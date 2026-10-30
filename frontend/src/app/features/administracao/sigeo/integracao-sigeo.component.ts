// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de Administração › Integração SIGEO (credencial, teste e conferência das ordens bancárias).

import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ambiente } from '../../../../environments/ambiente';
import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
import { TrilhaComponent } from '../../../shared/componentes/trilha/trilha.component';
import { erroExibivel } from '../../../shared/utilitarios/erros-api';

/** Resultado de uma conferência (rotina das 08:00, "Executar agora" ou ensaio). */
interface ResultadoConferencia {
  verificadas: number;
  aguardando: number;
  concluidas: { competencia: string; contrato_id: string; ob: string; valor: string }[];
  pendencias: { competencia: string; contrato_id: string; motivo: string }[];
  sugestoes_processo: { contrato_id: string; contrato: string; empresa: string; processos: string[] }[];
  erros: string[];
  empenhos?: ResultadoEmpenhos | null;
}

/** Cadastro de NEs e cancelamentos do SIGEO (rotina diária ou "Cadastrar empenhos agora"). */
interface ResultadoEmpenhos {
  contratos: { contrato_id: string; contrato: string; nes: { numero: string; valor: string; cancelamentos: { numero: string; valor: string }[] }[] }[];
  nes_cadastradas: number;
  cancelamentos: number;
  pendencias: { contrato: string; contrato_id: string; motivo: string }[];
  sem_empenho_no_sigeo: { contrato_id: string; contrato: string; processos: string[] }[];
  erros?: string[];
}

/** Configuração como a API devolve (a senha nunca vem, só se existe). */
interface ConfiguracaoSigeo {
  ativo: boolean;
  url_base: string;
  caminho_analise: string;
  caminho_analise_empenhado: string;
  usuario: string;
  possui_senha: boolean;
  hora_conferencia: number;
  configurada: boolean;
  ultima_execucao_em: string | null;
  ultimo_resultado: ResultadoConferencia | null;
  atualizado_em: string;
  atualizado_por: string;
}

interface ResultadoTeste {
  sucesso: boolean;
  mensagem: string;
  linhas: number | null;
  latencia_ms: number | null;
}

/** Integração com o SIGEO (só SuperRoot): todo dia, na hora configurada, as OBs pagas concluem sozinhas a etapa da ordem bancária das competências. */
@Component({
  selector: 'app-integracao-sigeo',
  imports: [EsqueletoComponent, FormsModule, DatePipe, TrilhaComponent, RouterLink],
  template: `
    <div class="cabecalho-pagina">
      <div>
        <app-trilha [itens]="[{ rotulo: 'Administração' }, { rotulo: 'Integração SIGEO' }]" />
        <h1>Integração SIGEO</h1>
        <small>Todo dia, na hora escolhida abaixo, o SGI lê no SIGEO as ordens bancárias pagas e conclui sozinho a etapa da OB das competências que só esperavam o pagamento.</small>
      </div>
    </div>

    <section class="painel-gestao" aria-labelledby="titulo-sigeo">
      <div class="barra-ferramentas"><div><h2 id="titulo-sigeo">Acesso ao SIGEO</h2>
        <p>A senha fica cifrada no banco e nunca é exibida. Deixe em branco para manter a gravada.</p></div></div>
      @if (aviso(); as a) { <p class="aviso-admin" [class.erro]="a.erro" role="status">{{ a.texto }}</p> }
      @if (config(); as c) {
        <form class="grade-formulario" style="grid-template-columns: 1fr 1fr" (ngSubmit)="salvar()">
          <div class="ocupa-duas"><label for="sigeo-url">Endereço do SIGEO (saw.dll) *</label>
            <input id="sigeo-url" name="url" class="form-control" required maxlength="300" [(ngModel)]="url" /></div>
          <div class="ocupa-duas"><label for="sigeo-analise">Análise consultada *</label>
            <input id="sigeo-analise" name="analise" class="form-control" required maxlength="500" [(ngModel)]="analise" />
            <small class="dica-formulario">Caminho da análise salva no catálogo, com as colunas COD_PROCESSO, COD_DOCUMENTO, DATA_LANCAMENTO, DESCRICAO_DOCUMENTO e VALOR_DOCUMENTO.</small></div>
          <div class="ocupa-duas"><label for="sigeo-empenhado">Análise de empenhos (NEs e cancelamentos)</label>
            <input id="sigeo-empenhado" name="empenhado" class="form-control" maxlength="500" [(ngModel)]="analiseEmpenhado" />
            <small class="dica-formulario">Usada para cadastrar sozinha as NEs dos contratos com Processo Financeiro e sem nenhuma NE. Colunas: COD_PROCESSO, COD_DOCUMENTO, COD_DOCUMENTO_ORIGEM, VALOR_DOCUMENTO (negativo = cancelamento).</small></div>
          <div><label for="sigeo-usuario">Usuário *</label>
            <input id="sigeo-usuario" name="usuario" class="form-control" required autocomplete="off" maxlength="100" [(ngModel)]="usuario" /></div>
          <div><label for="sigeo-senha">Senha {{ c.possui_senha ? '(gravada)' : '*' }}</label>
            <input id="sigeo-senha" name="senha" type="password" class="form-control" autocomplete="new-password" maxlength="200" [(ngModel)]="senha"
                   [placeholder]="c.possui_senha ? 'Em branco mantém a atual' : ''" /></div>
          <div><label for="sigeo-hora">Hora da conferência diária</label>
            <select id="sigeo-hora" name="hora" [(ngModel)]="hora">
              @for (h of horas; track h) { <option [ngValue]="h">{{ h < 10 ? '0' + h : h }}:00</option> }
            </select>
            <small class="dica-formulario">Horário de Brasília. Confere uma vez por dia, a partir desta hora.</small></div>
          <div class="linha-caixas" style="align-self: center"><label><input type="checkbox" name="ativo" [(ngModel)]="ativo" /> Conferência diária ativa</label></div>
          <div class="ocupa-duas acoes-formulario">
            <button type="button" class="acao-secundaria" [class.carregando]="ocupado() === 'testar'" [disabled]="!!ocupado() || !c.configurada" (click)="testar()">Testar acesso</button>
            <button type="submit" class="acao-primaria" [class.carregando]="ocupado() === 'salvar'" [disabled]="!!ocupado() || !url.trim() || !analise.trim() || !usuario.trim()">Salvar</button>
          </div>
        </form>
        @if (teste(); as t) {
          <p class="aviso-bloco" [class.erro]="!t.sucesso" role="status">{{ t.mensagem }}@if (t.latencia_ms !== null) { <span> ({{ t.latencia_ms }} ms)</span> }</p>
        }
        <p class="dica-formulario">Atualizado por {{ c.atualizado_por || '—' }} em {{ c.atualizado_em | date: 'dd/MM/yyyy HH:mm' }}.</p>
      } @else {
        <app-esqueleto tipo="formulario" [linhas]="5" />
      }
    </section>

    @if (config(); as c) {
      <section class="painel-gestao" aria-labelledby="titulo-conferencia">
        <div class="barra-ferramentas">
          <div><h2 id="titulo-conferencia">Conferência das ordens bancárias</h2>
            <p>Conclui a OB quando o processo financeiro do contrato, o mês escrito na OB e o líquido a pagar (notas − retenções) batem. Na dúvida, não conclui e explica o motivo.</p></div>
          <div class="acoes-formulario">
            <button type="button" class="acao-secundaria" [class.carregando]="ocupado() === 'ensaio'" [disabled]="!!ocupado() || !c.configurada" (click)="conferir(true)">Simular</button>
            <button type="button" class="acao-secundaria" [class.carregando]="ocupado() === 'empenhos'" [disabled]="!!ocupado() || !c.configurada" (click)="empenhos(true)">Simular empenhos</button>
            <button type="button" class="acao-secundaria" [class.carregando]="ocupado() === 'cadastrar'" [disabled]="!!ocupado() || !c.configurada" (click)="empenhos(false)">Cadastrar empenhos agora</button>
            <button type="button" class="acao-primaria" [class.carregando]="ocupado() === 'conferir'" [disabled]="!!ocupado() || !c.configurada" (click)="conferir(false)">Conferir agora</button>
          </div>
        </div>
        @if (resultado() ?? c.ultimo_resultado; as r) {
          <p class="dica-formulario">{{ resultado() ? (simulado() ? 'Simulação (nada foi gravado).' : 'Conferência executada agora.') : 'Última conferência em ' + (c.ultima_execucao_em | date: 'dd/MM/yyyy HH:mm') + '.' }}
            {{ r.verificadas }} competência(s) esperando OB · {{ r.concluidas.length }} {{ simulado() && resultado() ? 'seriam concluídas' : 'concluída(s)' }} · {{ r.aguardando }} aguardando pagamento · {{ r.pendencias.length }} com pendência.</p>
          @for (e of r.erros; track $index) { <p class="aviso-bloco erro" role="alert">{{ e }}</p> }
          @if (r.concluidas.length) {
            <div class="tabela-gestao-envoltorio"><table class="tabela-gestao">
              <caption class="somente-leitor">OBs concluídas</caption>
              <thead><tr><th>Competência</th><th>OB</th><th class="num">Valor</th></tr></thead>
              <tbody>@for (x of r.concluidas; track $index) {
                <tr><td><a [routerLink]="['/contratos', x.contrato_id]" [queryParams]="{ aba: 'execucao' }">{{ x.competencia }}</a></td><td class="texto-codigo">{{ x.ob }}</td><td class="num">{{ moeda(x.valor) }}</td></tr>
              }</tbody>
            </table></div>
          }
          @if (r.pendencias.length) {
            <h3 class="titulo-lista-sigeo">Pendências ({{ r.pendencias.length }})</h3>
            <div class="tabela-gestao-envoltorio"><table class="tabela-gestao">
              <thead><tr><th>Competência</th><th>Motivo</th></tr></thead>
              <tbody>@for (x of r.pendencias; track $index) {
                <tr><td><a [routerLink]="['/contratos', x.contrato_id]" [queryParams]="{ aba: 'execucao' }">{{ x.competencia }}</a></td><td>{{ x.motivo }}</td></tr>
              }</tbody>
            </table></div>
          }
          @if (r.empenhos; as e) {
            <h3 class="titulo-lista-sigeo">Empenhos do SIGEO: {{ e.nes_cadastradas }} NE(s) e {{ e.cancelamentos }} cancelamento(s) {{ simulado() && resultado() ? 'seriam cadastrados' : 'cadastrados' }}</h3>
            @if (e.contratos.length) {
              <div class="tabela-gestao-envoltorio"><table class="tabela-gestao">
                <thead><tr><th>Contrato</th><th>NEs (cancelamentos)</th></tr></thead>
                <tbody>@for (x of e.contratos; track x.contrato_id) {
                  <tr><td><a [routerLink]="['/contratos', x.contrato_id]" [queryParams]="{ aba: 'notas' }">{{ x.contrato }}</a></td>
                    <td class="texto-codigo">@for (n of x.nes; track n.numero) { <div>{{ n.numero }} · {{ moeda(n.valor) }}@if (n.cancelamentos.length) { · cancelamento(s): {{ n.cancelamentos.length }} }</div> }</td></tr>
                }</tbody>
              </table></div>
            }
            @for (x of e.pendencias; track $index) { <p class="aviso-bloco" role="status"><strong>{{ x.contrato }}:</strong> {{ x.motivo }}</p> }
            @if (e.sem_empenho_no_sigeo.length) {
              <p class="dica-formulario">Sem empenho na análise do SIGEO (a análise só traz alguns exercícios): {{ nomesSemEmpenho(e) }}.</p>
            }
          }
          @if (r.sugestoes_processo.length) {
            <h3 class="titulo-lista-sigeo">Contratos esperando OB sem processo financeiro ({{ r.sugestoes_processo.length }})</h3>
            <p class="dica-formulario">O SIGEO usa estes processos para o CNPJ da contratada. Preencha o "Processo financeiro" no contrato (Editar › Processos) para a conferência alcançá-lo.</p>
            <div class="tabela-gestao-envoltorio"><table class="tabela-gestao">
              <thead><tr><th>Contrato</th><th>Empresa</th><th>Processo(s) no SIGEO</th></tr></thead>
              <tbody>@for (x of r.sugestoes_processo; track x.contrato_id) {
                <tr><td><a [routerLink]="['/contratos', x.contrato_id, 'editar']">{{ x.contrato }}</a></td><td>{{ x.empresa }}</td><td class="texto-codigo">{{ x.processos.join(' · ') }}</td></tr>
              }</tbody>
            </table></div>
          }
        } @else {
          <p class="estado-vazio">Nenhuma conferência executada ainda.</p>
        }
      </section>
    }
  `,
  // O painel não tem margem interna própria: o conteúdo abaixo do cabeçalho recebe o mesmo recuo (24px) do cabeçalho (padrão da Integração GLPI)
  styles: `
    .painel-gestao > :not(.barra-ferramentas):not(.tabela-gestao-envoltorio) { margin-inline: 24px; }
    .painel-gestao > .barra-ferramentas + :not(.tabela-gestao-envoltorio) { margin-top: 20px; }
    .painel-gestao > :last-child { margin-bottom: 22px; }
    .painel-gestao + .painel-gestao { margin-top: 16px; }
    .grade-formulario .dica-formulario { display: block; margin: 6px 0 14px; }
    .grade-formulario .linha-caixas label { font-size: 13px; font-weight: 600; }
    .titulo-lista-sigeo { margin: 18px 24px 8px; font-size: 0.95rem; font-weight: 700; }
  `,
})
export class IntegracaoSigeoComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/integracao-sigeo`;

  protected readonly config = signal<ConfiguracaoSigeo | null>(null);
  protected readonly aviso = signal<{ texto: string; erro: boolean } | null>(null);
  protected readonly teste = signal<ResultadoTeste | null>(null);
  protected readonly resultado = signal<ResultadoConferencia | null>(null);
  protected readonly simulado = signal(false);
  /** Ação em andamento (trava os botões e mostra o carregando no botão certo). */
  protected readonly ocupado = signal<'' | 'salvar' | 'testar' | 'ensaio' | 'conferir' | 'empenhos' | 'cadastrar'>('');
  protected url = '';
  protected analise = '';
  protected analiseEmpenhado = '';
  protected usuario = '';
  protected senha = '';
  protected ativo = false;
  protected hora = 8;
  protected readonly horas = Array.from({ length: 24 }, (_, i) => i);

  ngOnInit(): void {
    this.http.get<ConfiguracaoSigeo>(this.base).subscribe({ next: (c) => this.preencher(c), error: (e) => this.avisar(erroExibivel(e).mensagem, true) });
  }

  private preencher(c: ConfiguracaoSigeo): void {
    this.config.set(c);
    this.url = c.url_base;
    this.analise = c.caminho_analise;
    this.analiseEmpenhado = c.caminho_analise_empenhado;
    this.usuario = c.usuario;
    this.ativo = c.ativo;
    this.hora = c.hora_conferencia;
    this.senha = '';
  }

  private avisar(texto: string, erro = false): void {
    this.aviso.set({ texto, erro });
  }

  protected nomesSemEmpenho(e: ResultadoEmpenhos): string {
    return e.sem_empenho_no_sigeo.map((x) => `${x.contrato} (${x.processos.join(', ')})`).join('; ');
  }

  protected moeda(valor: string): string {
    return Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }

  protected salvar(): void {
    this.ocupado.set('salvar');
    this.teste.set(null);
    const corpo = { ativo: this.ativo, url_base: this.url.trim(), caminho_analise: this.analise.trim(), caminho_analise_empenhado: this.analiseEmpenhado.trim() || null, usuario: this.usuario.trim(), senha: this.senha || null, hora_conferencia: this.hora };
    this.http.put<ConfiguracaoSigeo>(this.base, corpo).subscribe({
      next: (c) => { this.preencher(c); this.ocupado.set(''); this.avisar('Configuração salva.'); },
      error: (e) => { this.ocupado.set(''); this.avisar(erroExibivel(e).mensagem, true); },
    });
  }

  protected testar(): void {
    this.ocupado.set('testar');
    this.http.post<ResultadoTeste>(`${this.base}/testar`, null).subscribe({
      next: (t) => { this.teste.set(t); this.ocupado.set(''); },
      error: (e) => { this.ocupado.set(''); this.avisar(erroExibivel(e).mensagem, true); },
    });
  }

  /** Cadastra (ou simula) só as NEs e cancelamentos do SIGEO dos contratos com Processo Financeiro e sem NE. */
  protected empenhos(ensaio: boolean): void {
    this.ocupado.set(ensaio ? 'empenhos' : 'cadastrar');
    this.http.post<ResultadoEmpenhos>(`${this.base}/empenhos`, null, { params: { ensaio } }).subscribe({
      next: (e) => {
        const base = this.resultado() ?? { verificadas: 0, aguardando: 0, concluidas: [], pendencias: [], sugestoes_processo: [], erros: [] };
        this.resultado.set({ ...base, empenhos: e, erros: [...(e.erros ?? [])] });
        this.simulado.set(ensaio);
        this.ocupado.set('');
      },
      error: (err) => { this.ocupado.set(''); this.avisar(erroExibivel(err).mensagem, true); },
    });
  }

  /** Simula (nada é gravado) ou confere de verdade, como a rotina das 08:00. */
  protected conferir(ensaio: boolean): void {
    this.ocupado.set(ensaio ? 'ensaio' : 'conferir');
    this.http.post<ResultadoConferencia>(`${this.base}/conferir`, null, { params: { ensaio } }).subscribe({
      next: (r) => {
        this.resultado.set(r);
        this.simulado.set(ensaio);
        this.ocupado.set('');
        if (!ensaio) this.http.get<ConfiguracaoSigeo>(this.base).subscribe((c) => this.config.set(c));
      },
      error: (e) => { this.ocupado.set(''); this.avisar(erroExibivel(e).mensagem, true); },
    });
  }
}
