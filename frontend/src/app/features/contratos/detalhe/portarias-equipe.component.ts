// Criado por José Eduardo Santana Martins
// Este arquivo serve para conduzir a portaria de designação dentro da aba Equipe: nomeações, ciência, autoridade, aceite e histórico.

import { DatePipe } from '@angular/common';
import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { EtapaTrilha, EstadoEtapa, TrilhaEtapasComponent } from '../../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { OpcaoUsuario } from '../../../core/modelos/usuario.model';
import { BotaoCopiarComponent } from '../../../shared/componentes/botao-copiar/botao-copiar.component';
import { SeletorUsuariosComponent } from '../../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { HtmlConfiavelPipe } from '../../contratacoes/html-confiavel.pipe';
import { AutoridadePortaria, GravacaoAutoridade, MembroEquipe, NomeacaoEntrada, NomeacaoPortaria, PainelPortarias, Papel, Portaria, UsuarioAutoridade } from '../compartilhado/contratos.models';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { PortariasApiService } from '../compartilhado/portarias-api.service';
import { PAPEIS } from '../compartilhado/rotulos';

const AUTORIDADE_VAZIA: GravacaoAutoridade = { sigla: '', nome: '', cargo: '', setor: '', usuario_id: null, ativa: true };

/** Portaria de designação na aba Equipe: a equipe só muda por aqui (nomeações → ciência → autoridade → aceite → D.O.E. no Protocolo). */
@Component({
  selector: 'app-portarias-equipe',
  imports: [FormsModule, DatePipe, EnvioPdfComponent, TrilhaEtapasComponent, BotaoCopiarComponent, SeletorUsuariosComponent, HtmlConfiavelPipe, ...PIPES_FORMATACAO],
  template: `
    <section class="cartao-dados" aria-labelledby="titulo-portaria">
      <header>
        <div><h2 id="titulo-portaria">Portarias de designação</h2>
          <small>A equipe só muda por portaria: nomeações, ciência dos nomeados, autoridade e aceite. A nova equipe vale quando o PDF do D.O.E. é anexado (aqui mesmo, depois do aceite, ou pelo Protocolo).</small></div>
        @if (painel()?.pode_criar && !painel()?.em_andamento && !formularioAberto()) {
          <button type="button" class="acao-primaria" (click)="abrirNova()">Nova portaria</button>
        }
      </header>
      @if (formularioAberto()) {
        <form class="bloco-form" (ngSubmit)="salvarNomeacoes()">
          <h3 class="titulo-form">{{ editandoId() ? 'Alterar as nomeações' : 'Nomeações da nova portaria' }}</h3>
          <p class="dica-formulario">A portaria define a equipe inteira: funções sem nomeado deixam de ter responsável quando ela for publicada. Gestor é obrigatório; de 1 a 6 funções.</p>
          <div class="grade-formulario tres-colunas">
            @for (p of papeis; track p.papel) {
              <div>
                <label [for]="'nomeacao-' + p.papel">{{ p.rotulo }}@if (p.papel === 'gestor') { * }</label>
                <app-seletor-usuarios [idCampo]="'nomeacao-' + p.papel" [multiplo]="false" [(selecionados)]="escolhas[p.papel]" [fonte]="contratosApi.opcoesUsuarios" textoAjuda="Pesquisar usuário" />
              </div>
            }
          </div>
          <footer class="acoes-formulario">
            <button type="button" class="acao-secundaria" (click)="fecharFormulario()">Fechar</button>
            <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="salvando()">{{ salvando() ? 'Salvando…' : (editandoId() ? 'Salvar nomeações' : 'Criar portaria') }}</button>
          </footer>
        </form>
      }
      @if (painel(); as p) {
        @if (!p.portarias.length && !formularioAberto()) { <p class="vazio">Nenhuma portaria de designação neste contrato ainda.</p> }
        @for (portaria of p.portarias; track portaria.id) {
          <article class="portaria-cartao">
            <header>
              <div><h3>{{ portaria.titulo }}</h3>
                <small>{{ portaria.status_rotulo }} · criada por {{ portaria.solicitada_por_nome }} em {{ portaria.solicitada_em.slice(0, 10) | dataBr }}@if (portaria.autoridade_nome) { · assina {{ portaria.autoridade_nome }} }</small></div>
            </header>
            @if (portaria.motivo && portaria.status === 'cancelada') { <p><strong>Cancelada:</strong> {{ portaria.motivo }}</p> }
            @if (portaria.motivo && portaria.status === 'aguardando_autoridade') { <p role="alert"><strong>Devolvida pela autoridade:</strong> {{ portaria.motivo }}</p> }
            @if (portaria.status !== 'cancelada') {
              <app-trilha-etapas [etapas]="trilha(portaria)" ariaLabel="Etapas da portaria" [compacta]="portaria.status === 'publicada'" />
            }
            <div class="tabela-gestao-envoltorio">
              <table class="tabela-gestao">
                <thead>
                  <tr>
                    @for (c of colunas; track c.id) {
                      <th [attr.aria-sort]="sentido(c.id)"><button type="button" class="ordenar-coluna" [class.ativa]="ordenarPor() === c.id" (click)="ordenar(c.id)" [title]="'Ordenar por ' + c.rotulo.toLowerCase()">{{ c.rotulo }}<span aria-hidden="true">{{ ordenarPor() === c.id ? (direcao() === 'asc' ? '▲' : '▼') : '↕' }}</span></button></th>
                    }
                  </tr>
                </thead>
                <tbody>
                  @for (n of nomeacoesOrdenadas(portaria); track n.papel) {
                    <tr>
                      <td>{{ n.papel_rotulo }}</td>
                      <td><strong>{{ n.nome }}</strong></td>
                      <td>
                        <div class="situacao-nomeacao">
                          @if (n.dados_pendentes.length) {
                            <span class="selo-situacao alerta" [title]="'O RH precisa atualizar: ' + n.dados_pendentes.join(', ')">Dados pendentes no RH: {{ n.dados_pendentes.join(', ') }}</span>
                          } @else {
                            <span class="selo-situacao">Dados completos</span>
                          }
                          @if (n.ciente_em) {
                            <span class="selo-situacao">Ciência ok · {{ n.ciente_em | date: 'dd/MM/yyyy HH:mm' }}</span>
                          } @else {
                            <span class="selo-situacao alerta">Ciência pendente</span>
                          }
                        </div>
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
            @if (portaria.pode_alterar && (portaria.status === 'nomeacao' || portaria.status === 'aguardando_ciencia')) {
              <p class="dica-formulario">A autoridade só é escolhida quando todas as nomeações estiverem com o cadastro completo e com a ciência de cada nomeado.</p>
            }
            @if (portaria.pendencias.length) { <p role="alert"><strong>Pendências para o aceite:</strong> {{ portaria.pendencias.join('; ') }}.</p> }
            @if (portaria.pode_publicar) {
              <!-- Publicação sem sair do Contratos: anexa o D.O.E. ao número reservado no Protocolo -->
              <section class="cartao-dados" aria-label="Publicar a portaria">
                <header><h3>Publicar a portaria (D.O.E.)</h3></header>
                <div class="corpo">
                  <p class="dica-formulario">Depois de publicada no Diário Oficial, anexe o <strong>PDF do D.O.E.</strong>. Ele fica no número reservado no Protocolo, entra em Documentos Importantes e a nova equipe passa a valer.</p>
                  <div class="acoes-linha">
                    <app-envio-pdf rotulo="Selecionar o PDF do D.O.E." (selecionado)="escolherDoe($event)" />
                    <button type="button" class="acao-primaria" [class.carregando]="salvando()" [disabled]="!doe || salvando()" (click)="publicar(portaria)">Publicar com o PDF do D.O.E.</button>
                  </div>
                </div>
              </section>
            }
            @if (portaria.status === 'aceita' && portaria.tem_evidencia) {
              <p class="aviso-reserva" role="status">Ciências e aceite concluídos: baixe o <strong>PDF de evidência</strong> abaixo e junte-o ao processo no SEI, para seguir com a publicação no D.O.E.</p>
            }
            @if (portaria.aviso_reserva) { <p class="aviso-reserva" role="status">{{ portaria.aviso_reserva }}</p> }
            @if (portaria.status === 'aguardando_autoridade' && portaria.pode_alterar && tudoOk(portaria)) {
              <div class="linha-solicitar">
                <div class="campo-autoridade"><label [for]="'aut-' + portaria.id">Autoridade competente *</label>
                  <select [id]="'aut-' + portaria.id" [name]="'aut-' + portaria.id" [(ngModel)]="autoridadeId">
                    <option value="">Selecione…</option>
                    @for (a of p.autoridades; track a.id) { <option [value]="a.id">{{ a.nome }} — {{ a.cargo }} ({{ a.sigla }})</option> }
                  </select>
                  @if (!p.autoridades.length) { <small class="dica">Nenhuma autoridade cadastrada: peça a quem administra Contratos para cadastrá-la.</small> }
                </div>
                <button type="button" class="acao-primaria" [class.carregando]="salvando()" [disabled]="!autoridadeId || salvando()" (click)="escolherAutoridade(portaria)">Gerar portaria e reservar número</button>
              </div>
            }
            @if (portaria.texto_html) {
              <section class="cartao-dados texto-portaria" aria-label="Texto da portaria">
                <header><h3>Texto da portaria</h3><app-botao-copiar rotulo="Copiar portaria" titulo="Copiar o texto formatado" (acionar)="copiar(portaria)" /></header>
                <div class="corpo"><div class="texto-despacho" [innerHTML]="portaria.texto_html | htmlConfiavel"></div></div>
              </section>
            }
            @if (portaria.aceita_em) { <small>Aceita por {{ portaria.aceita_por_nome }} em {{ portaria.aceita_em | date: 'dd/MM/yyyy HH:mm' }}.</small> }
            @if (portaria.publicada_em) { <small>Publicada em {{ portaria.publicada_em.slice(0, 10) | dataBr }}: PDF do D.O.E. em Documentos Importantes e no Protocolo.</small> }
            @if (portaria.status !== 'cancelada') {
              <div class="acoes-linha">
                @if (portaria.tem_evidencia) { <button type="button" class="acao-secundaria acao-pequena" (click)="baixarEvidencia(portaria)">PDF de evidência (ciências e aceite)</button> }
                @if (portaria.pode_decidir) {
                  <button type="button" class="acao-positiva" (click)="aceitar(portaria)">Aceitar</button>
                  <button type="button" class="acao-recusar" (click)="devolver(portaria)">Devolver</button>
                }
                @if (portaria.pode_alterar && (portaria.status === 'nomeacao' || portaria.status === 'aguardando_ciencia' || portaria.status === 'aguardando_autoridade')) {
                  <button type="button" class="acao-secundaria acao-pequena" (click)="abrirEdicao(portaria)">Alterar nomeações</button>
                }
                @if (portaria.pode_alterar && portaria.status !== 'publicada') { <button type="button" class="acao-perigo acao-pequena" (click)="cancelar(portaria)">Cancelar</button> }
              </div>
            }
          </article>
        }
      }
    </section>

    @if (podeAdministrar()) {
      <section class="cartao-dados" aria-labelledby="titulo-autoridades">
        <header><div><h2 id="titulo-autoridades">Autoridades signatárias</h2>
          <small>A autoridade é um usuário do sistema: ele mesmo dá o aceite. Nome, cargo e setor vêm do cadastro dele (cargo e setor podem ser ajustados).</small></div></header>
        @if (autoridades().length) {
          <div class="tabela-gestao-envoltorio">
            <table class="tabela-gestao">
              <thead><tr><th>Sigla</th><th>Nome</th><th>Cargo</th><th>Setor</th><th>Situação</th><th></th></tr></thead>
              <tbody>
                @for (a of autoridades(); track a.id) {
                  <tr><td>{{ a.sigla }}</td><td>{{ a.nome }}</td><td>{{ a.cargo }}</td><td>{{ a.setor }}</td><td><span class="selo-situacao" [class.inativo]="!a.ativa">{{ a.ativa ? 'Ativa' : 'Desativada' }}</span></td>
                    <td><div class="acoes-linha"><button type="button" (click)="editar(a)">Editar</button><button type="button" (click)="excluir(a)">Excluir</button></div></td></tr>
                }
              </tbody>
            </table>
          </div>
        } @else {
          <p class="vazio">Nenhuma autoridade cadastrada ainda.</p>
        }
        <form class="bloco-form grade-formulario" (ngSubmit)="salvarAutoridade()">
          <h3 class="titulo-form ocupa-duas">{{ editando() ? 'Editar autoridade' : 'Nova autoridade' }}</h3>
          <div><label for="aut-sigla">Sigla *</label><input id="aut-sigla" name="sigla" maxlength="60" placeholder="SPI SSGC" [(ngModel)]="formulario.sigla" required /></div>
          <div><label for="aut-usuario">Autoridade (usuário do sistema) *</label>
            <input id="aut-usuario" name="usuario" list="aut-usuarios" autocomplete="off" placeholder="Digite o nome para buscar…" [(ngModel)]="textoUsuario"
                   (ngModelChange)="aoDigitarUsuario($event)" required />
            <datalist id="aut-usuarios">@for (u of usuarios(); track u.id) { <option [value]="rotuloUsuario(u)"></option> }</datalist></div>
          <div><label for="aut-cargo">Cargo *</label><input id="aut-cargo" name="cargo" maxlength="200" [(ngModel)]="formulario.cargo" required /></div>
          <div><label for="aut-setor">Setor *</label><input id="aut-setor" name="setor" maxlength="200" [(ngModel)]="formulario.setor" required /></div>
          <div class="linha-caixas ocupa-duas"><label><input type="checkbox" name="ativa" [(ngModel)]="formulario.ativa" /> Autoridade ativa (aparece na solicitação de portarias)</label></div>
          <div class="acoes-formulario ocupa-duas">
            @if (editando()) { <button type="button" class="acao-secundaria" (click)="limpar()">Cancelar edição</button> }
            <button type="submit" class="acao-primaria" [disabled]="!formulario.usuario_id || !formulario.sigla.trim()">{{ editando() ? 'Salvar autoridade' : 'Cadastrar autoridade' }}</button>
          </div>
        </form>
      </section>
    }
  `,
  styles: `
    :host { display: grid; gap: 18px; }
    .bloco-form { padding: 18px 20px; }
    .linha-solicitar { display: flex; align-items: flex-end; gap: 16px; border-top: 1px solid var(--cor-e2e5e8); }
    .campo-autoridade { flex: 1; min-width: 0; }
    .campo-autoridade label { display: block; margin-bottom: 7px; font-size: 12px; font-weight: 600; }
    .campo-autoridade select { width: 100%; }
    .dica, .vazio { color: var(--spi-apagado); font-size: 12px; }
    .dica { display: block; margin-top: 6px; }
    .vazio { margin: 0; padding: 16px 20px; }
    .portaria-cartao { display: grid; gap: 10px; margin: 0 20px 18px; padding: 16px 18px; border: 1px solid var(--cor-e2e5e8); border-radius: var(--spi-raio-m); }
    .portaria-cartao h3 { margin: 0 0 2px; font-size: 15px; }
    .portaria-cartao p, .portaria-cartao ul { margin: 0; }
    .aviso-reserva { padding: 10px 12px; border: 1px solid var(--cor-e2e5e8); border-radius: var(--spi-raio-p); background: var(--spi-alerta-suave); }
    .texto-portaria { margin: 0; }
    .situacao-nomeacao { display: flex; flex-wrap: wrap; gap: 6px; }
    .portaria-cartao .acoes-linha { justify-content: flex-start; flex-wrap: wrap; }
    .portaria-cartao .acoes-documento { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
    .titulo-form { margin: 0 0 14px; font-size: 14px; }
    .grade-formulario { border-top: 1px solid var(--cor-e2e5e8); }
    .grade-formulario .acoes-formulario { margin-top: 4px; }
    @media (max-width: 760px) { .linha-solicitar { flex-direction: column; align-items: stretch; } }
  `,
})
export class PortariasEquipeComponent implements OnInit {
  readonly contratoId = input.required<string>();
  /** Equipe vigente (ponto de partida da nova portaria). */
  readonly equipe = input<MembroEquipe[]>([]);
  /** Pode cadastrar as autoridades: SuperRoot, controle total ou gestor/suplente do contrato. */
  readonly podeAdministrar = input(false);

  private readonly api = inject(PortariasApiService);
  protected readonly contratosApi = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly papeis = PAPEIS;
  protected readonly painel = signal<PainelPortarias | null>(null);
  protected readonly autoridades = signal<AutoridadePortaria[]>([]);
  protected readonly usuarios = signal<UsuarioAutoridade[]>([]);
  protected readonly editando = signal<string | null>(null);
  protected readonly formularioAberto = signal(false);
  protected readonly editandoId = signal<string | null>(null);
  protected readonly salvando = signal(false);
  // PDF do D.O.E. escolhido para publicar a portaria
  protected doe: File | null = null;
  /** Usuário escolhido em cada função do formulário de nomeações. */
  protected escolhas: Record<Papel, OpcaoUsuario[]> = this.escolhasVazias();
  protected autoridadeId = '';

  // Tabela de nomeações: colunas ordenáveis (Função | Nome | Situação)
  protected readonly colunas: { id: 'funcao' | 'nome' | 'situacao'; rotulo: string }[] = [
    { id: 'funcao', rotulo: 'Função' }, { id: 'nome', rotulo: 'Nome' }, { id: 'situacao', rotulo: 'Situação' },
  ];
  protected readonly ordenarPor = signal<'funcao' | 'nome' | 'situacao'>('funcao');
  protected readonly direcao = signal<'asc' | 'desc'>('asc');

  protected ordenar(coluna: 'funcao' | 'nome' | 'situacao'): void {
    if (this.ordenarPor() === coluna) this.direcao.update((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { this.ordenarPor.set(coluna); this.direcao.set('asc'); }
  }

  protected sentido(coluna: string): 'ascending' | 'descending' | 'none' {
    return this.ordenarPor() !== coluna ? 'none' : this.direcao() === 'asc' ? 'ascending' : 'descending';
  }

  /** Passos da portaria na trilha comum: do status atual para trás tudo está concluído; devolvida volta ao passo 3 (o motivo aparece como aviso). */
  protected trilha(p: Portaria): EtapaTrilha[] {
    const ordem: Record<string, number> = { nomeacao: 0, aguardando_ciencia: 1, aguardando_autoridade: 2, aguardando_aceite: 3, aceita: 5, publicada: 6 };
    const posicao = ordem[p.status] ?? 0;
    const cientes = p.nomeacoes.filter((n) => !!n.ciente_em).length;
    const passos: { id: string; rotulo: string; subtitulo?: (e: EstadoEtapa) => string | undefined }[] = [
      { id: 'nomeacoes', rotulo: 'Nomeações', subtitulo: (e) => (e === 'atual' ? 'dados do RH pendentes' : undefined) },
      { id: 'ciencia', rotulo: 'Ciência dos nomeados', subtitulo: (e) => (e === 'atual' ? `${cientes} de ${p.nomeacoes.length} cientes` : undefined) },
      { id: 'autoridade', rotulo: 'Autoridade e texto', subtitulo: (e) => (e === 'atual' ? 'escolher a autoridade' : undefined) },
      { id: 'aceite', rotulo: 'Aceite da autoridade', subtitulo: (e) => (e === 'atual' ? 'aguardando o aceite' : undefined) },
      { id: 'evidencia', rotulo: 'PDF de evidência', subtitulo: (e) => (e === 'concluida' ? 'gerado no aceite' : undefined) },
      { id: 'doe', rotulo: 'Publicação (D.O.E.)', subtitulo: (e) => (e === 'atual' ? 'anexar o D.O.E.' : undefined) },
    ];
    return passos.map((passo, i) => {
      const estado: EstadoEtapa = i < posicao ? 'concluida' : i === posicao && p.status !== 'publicada' ? 'atual' : p.status === 'publicada' ? 'concluida' : 'bloqueada';
      return { id: passo.id, rotulo: passo.rotulo, estado, subtitulo: passo.subtitulo?.(estado) };
    });
  }

  /** Todas as nomeações com cadastro completo e ciência dada: só então a autoridade pode ser escolhida. */
  protected tudoOk(p: Portaria): boolean {
    return p.nomeacoes.length > 0 && p.nomeacoes.every((n) => !n.dados_pendentes.length && !!n.ciente_em);
  }

  /** Texto da situação de uma nomeação (também é a chave da ordenação por situação). */
  private situacao(_p: Portaria, n: NomeacaoPortaria): string {
    // Pior situação primeiro: dados pendentes, depois ciência pendente, depois tudo certo
    if (n.dados_pendentes.length) return '1 Dados pendentes no RH';
    return n.ciente_em ? `3 Ciência ok ${n.ciente_em}` : '2 Ciência pendente';
  }

  /** Nomeações na ordem escolhida (função segue a ordem dos papéis da equipe, não a alfabética). */
  protected nomeacoesOrdenadas(p: Portaria): NomeacaoPortaria[] {
    const ordemPapel = (n: NomeacaoPortaria) => PAPEIS.findIndex((x) => x.papel === n.papel);
    const chave = (n: NomeacaoPortaria): string | number =>
      this.ordenarPor() === 'funcao' ? ordemPapel(n) : this.ordenarPor() === 'nome' ? n.nome.toLowerCase() : this.situacao(p, n);
    const sinal = this.direcao() === 'asc' ? 1 : -1;
    return [...p.nomeacoes].sort((a, b) => {
      const x = chave(a), y = chave(b);
      return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), 'pt-BR')) * sinal;
    });
  }
  protected textoUsuario = '';
  protected formulario: GravacaoAutoridade = { ...AUTORIDADE_VAZIA };

  ngOnInit(): void {
    this.carregar();
    if (this.podeAdministrar()) this.api.autoridades().subscribe({ next: (a) => this.autoridades.set(a), error: (e) => this.dialogos.mostrarErro(e) });
  }

  private carregar(): void {
    this.api.painel(this.contratoId()).subscribe({ next: (p) => this.painel.set(p), error: (e) => this.dialogos.mostrarErro(e) });
  }

  private escolhasVazias(): Record<Papel, OpcaoUsuario[]> {
    return Object.fromEntries(PAPEIS.map((p) => [p.papel, [] as OpcaoUsuario[]])) as unknown as Record<Papel, OpcaoUsuario[]>;
  }

  private opcao(id: number, nome: string, login = ''): OpcaoUsuario {
    return { id, login, nome_completo: nome, cargo: '', ativo: true };
  }

  /** Aplica a resposta de uma ação (o painel atualizado) ou mostra o erro. */
  private tratar(operacao: ReturnType<PortariasApiService['painel']>, titulo: string, mensagem = 'Executando a solicitação…'): void {
    this.dialogos.executar(operacao, mensagem).subscribe({
      next: (p) => { this.painel.set(p); this.autoridadeId = ''; this.fecharFormulario(); },
      error: (e) => this.dialogos.mostrarErro(e, titulo),
    });
  }

  // --- Nomeações ---

  /** Nova portaria: o formulário nasce com a equipe vigente (a portaria define a equipe inteira). */
  protected abrirNova(): void {
    this.escolhas = this.escolhasVazias();
    for (const m of this.equipe()) this.escolhas[m.papel] = [this.opcao(m.usuario_id, m.nome, m.login)];
    this.editandoId.set(null);
    this.formularioAberto.set(true);
  }

  protected abrirEdicao(p: Portaria): void {
    this.escolhas = this.escolhasVazias();
    for (const n of p.nomeacoes) if (n.usuario_id !== null) this.escolhas[n.papel as Papel] = [this.opcao(n.usuario_id, n.nome)];
    this.editandoId.set(p.id);
    this.formularioAberto.set(true);
  }

  protected fecharFormulario(): void {
    this.formularioAberto.set(false);
    this.editandoId.set(null);
  }

  protected salvarNomeacoes(): void {
    const nomeacoes: NomeacaoEntrada[] = PAPEIS.filter((p) => this.escolhas[p.papel][0]).map((p) => ({ papel: p.papel, usuario_id: this.escolhas[p.papel][0].id }));
    if (!nomeacoes.some((n) => n.papel === 'gestor')) {
      this.dialogos.avisar('Faltam nomeações', 'Indique o gestor: ele é obrigatório na portaria.');
      return;
    }
    const id = this.editandoId();
    this.salvando.set(true);
    const operacao = id ? this.api.alterarNomeacoes(this.contratoId(), id, nomeacoes) : this.api.criar(this.contratoId(), nomeacoes);
    operacao.subscribe({
      next: (p) => { this.salvando.set(false); this.painel.set(p); this.fecharFormulario(); },
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível salvar as nomeações'); },
    });
  }

  protected escolherAutoridade(p: Portaria): void {
    this.salvando.set(true);
    this.dialogos.executar(this.api.escolherAutoridade(this.contratoId(), p.id, this.autoridadeId), 'Gerando a portaria e reservando o número no Protocolo…').subscribe({
      next: (painel) => { this.salvando.set(false); this.painel.set(painel); this.autoridadeId = ''; },
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível gerar a portaria'); },
    });
  }

  protected async aceitar(p: Portaria): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Aceitar a ${p.titulo}?`, mensagem: 'O texto é atualizado com os dados atuais e o PDF de evidência (ciências e aceite) é gerado para juntar ao SEI.', rotuloConfirmar: 'Aceitar' });
    if (ok) this.tratar(this.api.aceitar(this.contratoId(), p.id), 'Não foi possível aceitar a portaria');
  }

  protected devolver(p: Portaria): void {
    const motivo = window.prompt('Motivo da devolução (o número volta a ficar livre no Protocolo):');
    if (motivo?.trim()) this.tratar(this.api.devolver(this.contratoId(), p.id, motivo.trim()), 'Não foi possível devolver a portaria');
  }

  protected cancelar(p: Portaria): void {
    const motivo = window.prompt(`Motivo do cancelamento da ${p.titulo} (o número, se reservado, volta a ficar livre no Protocolo):`);
    if (motivo?.trim()) this.tratar(this.api.cancelar(this.contratoId(), p.id, motivo.trim()), 'Não foi possível cancelar a portaria');
  }

  protected escolherDoe(arquivo: File | null): void {
    this.doe = arquivo;
  }

  /** Anexa o PDF do D.O.E. ao número reservado e publica a portaria (a nova equipe passa a valer). */
  protected async publicar(p: Portaria): Promise<void> {
    if (!this.doe) return;
    const ok = await this.dialogos.confirmar({
      titulo: `Publicar a ${p.titulo}?`,
      mensagem: 'O PDF do D.O.E. é anexado ao número reservado, a portaria vira publicada e a nova equipe passa a valer no contrato (as funções que ela não cita ficam sem responsável).',
      rotuloConfirmar: 'Publicar',
    });
    if (!ok) return;
    this.salvando.set(true);
    this.dialogos.executar(this.api.publicar(this.contratoId(), p.id, this.doe), 'Publicando a portaria e aplicando a nova equipe…').subscribe({
      next: (painel) => { this.salvando.set(false); this.painel.set(painel); this.doe = null; },
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível publicar a portaria'); },
    });
  }

  protected baixarEvidencia(p: Portaria): void {
    this.api.baixarEvidencia(this.contratoId(), p.id).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Copia o texto da portaria com a formatação (HTML) e, por garantia, em texto puro: no SEI ou no Word, o negrito e o centralizado vêm junto. */
  protected copiar(p: Portaria): void {
    const html = p.texto_html;
    if (!html) return;
    const caixa = document.createElement('div');
    caixa.innerHTML = html;
    document.body.appendChild(caixa);
    const texto = caixa.innerText;
    caixa.remove();
    const item = typeof ClipboardItem !== 'undefined'
      ? new ClipboardItem({ 'text/html': new Blob([html], { type: 'text/html' }), 'text/plain': new Blob([texto], { type: 'text/plain' }) })
      : null;
    const gravar = item ? navigator.clipboard.write([item]) : navigator.clipboard.writeText(texto);
    void gravar.catch(() => navigator.clipboard?.writeText(texto).catch(() => undefined));
  }

  // --- Autoridades ---

  protected rotuloUsuario(u: UsuarioAutoridade): string {
    return `${u.nome_completo} (${u.login})`;
  }

  /** Busca usuários enquanto digita; ao escolher uma opção da lista, preenche nome, cargo e setor com o cadastro dele. */
  protected aoDigitarUsuario(texto: string): void {
    const escolhido = this.usuarios().find((u) => this.rotuloUsuario(u) === texto);
    if (escolhido) {
      this.formulario.usuario_id = escolhido.id;
      this.formulario.nome = escolhido.nome_completo;
      this.formulario.cargo = escolhido.cargo;
      this.formulario.setor = escolhido.departamento;
      return;
    }
    this.formulario.usuario_id = null;
    if (texto.trim().length >= 2) this.api.usuariosParaAutoridade(texto.trim()).subscribe({ next: (u) => this.usuarios.set(u), error: () => this.usuarios.set([]) });
  }

  protected editar(a: AutoridadePortaria): void {
    this.editando.set(a.id);
    this.formulario = { sigla: a.sigla, nome: a.nome, cargo: a.cargo, setor: a.setor, usuario_id: a.usuario_id, ativa: a.ativa };
    this.textoUsuario = a.usuario_nome ? `${a.usuario_nome}` : a.nome;
    this.usuarios.set([]);
  }

  protected limpar(): void {
    this.editando.set(null);
    this.formulario = { ...AUTORIDADE_VAZIA };
    this.textoUsuario = '';
    this.usuarios.set([]);
  }

  protected salvarAutoridade(): void {
    const id = this.editando();
    const operacao = id ? this.api.alterarAutoridade(id, this.formulario) : this.api.criarAutoridade(this.formulario);
    operacao.subscribe({
      next: (a) => { this.autoridades.set(a); this.limpar(); this.carregar(); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar a autoridade'),
    });
  }

  protected async excluir(a: AutoridadePortaria): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir ${a.nome}?`, mensagem: 'Autoridades que já assinaram portarias não podem ser excluídas: desative-as.', rotuloConfirmar: 'Excluir', perigo: true });
    if (!ok) return;
    this.api.excluirAutoridade(a.id).subscribe({ next: (l) => { this.autoridades.set(l); this.carregar(); }, error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir') });
  }
}
