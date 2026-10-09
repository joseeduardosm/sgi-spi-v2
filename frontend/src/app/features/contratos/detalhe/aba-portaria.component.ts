// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir a aba "Portaria" do contrato: solicitação, aceite da autoridade, minuta e PDF publicado.

import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { OpcaoUsuario } from '../../../core/modelos/usuario.model';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { AutoridadePortaria, GravacaoAutoridade, PainelPortarias, Portaria } from '../compartilhado/contratos.models';
import { PortariasApiService } from '../compartilhado/portarias-api.service';

const AUTORIDADE_VAZIA: GravacaoAutoridade = { sigla: '', nome: '', cargo: '', setor: '', usuario_id: null, ativa: true };

/** Aba "Portaria": designa gestor e fiscais, com o número reservado no Protocolo e aceite da autoridade. */
@Component({
  selector: 'app-aba-portaria',
  imports: [FormsModule, EnvioPdfComponent, ...PIPES_FORMATACAO],
  template: `
    <section class="cartao-dados" aria-labelledby="titulo-portaria">
      <header>
        <div><h2 id="titulo-portaria">Portaria de designação</h2>
          <small>Gestor e fiscais do contrato. O número é reservado no Protocolo ao solicitar; a autoridade escolhida dá o aceite aqui mesmo.</small></div>
      </header>
      @if (painel(); as p) {
        @if (podeEditar() && !p.em_andamento) {
          <form class="bloco-form linha-solicitar" (ngSubmit)="solicitar()">
            <div class="campo-autoridade"><label for="portaria-autoridade">Autoridade signatária *</label>
              <select id="portaria-autoridade" name="autoridade" [(ngModel)]="autoridadeId" required>
                <option value="">Selecione…</option>
                @for (a of p.autoridades; track a.id) { <option [value]="a.id">{{ a.nome }} — {{ a.cargo }} ({{ a.sigla }})</option> }
              </select>
              @if (!p.autoridades.length) { <small class="dica">Nenhuma autoridade cadastrada: peça a quem administra Contratos para cadastrá-la.</small> }
            </div>
            <button type="submit" class="acao-primaria" [disabled]="!autoridadeId">Solicitar portaria</button>
          </form>
        } @else if (!p.portarias.length) {
          <p class="vazio">Nenhuma portaria solicitada para este contrato.</p>
        }
        @for (portaria of p.portarias; track portaria.id) {
          <article class="portaria-cartao">
            <header>
              <div><h3>{{ portaria.titulo }}</h3>
                <small>{{ portaria.status_rotulo }} · solicitada por {{ portaria.solicitada_por_nome }} em {{ portaria.solicitada_em.slice(0, 10) | dataBr }} · assina {{ portaria.autoridade_nome }}</small></div>
            </header>
            @if (portaria.status === 'devolvida' && portaria.motivo) { <p role="alert"><strong>Devolvida:</strong> {{ portaria.motivo }}</p> }
            @if (portaria.status === 'cancelada' && portaria.motivo) { <p><strong>Cancelada:</strong> {{ portaria.motivo }}</p> }
            @if (portaria.pendencias.length) {
              <p role="alert"><strong>Pendências para o aceite:</strong> {{ portaria.pendencias.join('; ') }}.</p>
            }
            <ul>
              @for (pessoa of portaria.equipe; track pessoa.papel) {
                <li>{{ pessoa.papel_rotulo }}: {{ pessoa.nome }} @if (!pessoa.rs_informado) { <small>(RS não cadastrado)</small> }</li>
              }
            </ul>
            <p><strong>Revogação:</strong> {{ portaria.anterior ? 'cita a ' + portaria.anterior : 'sem portaria anterior (máscara sem revogação)' }}</p>
            @if (portaria.aceita_em) { <small>Aceita por {{ portaria.aceita_por_nome }} em {{ portaria.aceita_em.slice(0, 10) | dataBr }}.</small> }
            @if (portaria.publicada_em) { <small>Publicada em {{ portaria.publicada_em.slice(0, 10) | dataBr }}: PDF em Documentos Importantes e no Protocolo.</small> }

            @if (portaria.status !== 'cancelada') {
              <div class="acoes-linha">
                <button type="button" class="acao-secundaria acao-pequena" (click)="baixar(portaria, 'docx')">Minuta Word</button>
                <button type="button" class="acao-secundaria acao-pequena" (click)="baixar(portaria, 'pdf')">Minuta PDF</button>
                @if (portaria.pode_decidir) {
                  <button type="button" class="acao-aprovar" (click)="aceitar(portaria)">Aceitar</button>
                  <button type="button" (click)="devolver(portaria)">Devolver</button>
                }
                @if (portaria.pode_alterar) {
                  @if (portaria.status === 'devolvida' || portaria.status === 'aguardando_aceite') {
                    <button type="button" class="acao-secundaria acao-pequena" (click)="reenviar(portaria)">{{ portaria.status === 'devolvida' ? 'Reenviar para aceite' : 'Atualizar texto' }}</button>
                  }
                  @if (portaria.status !== 'publicada') { <button type="button" class="acao-perigo acao-pequena" (click)="cancelar(portaria)">Cancelar</button> }
                }
              </div>
              @if (portaria.pode_alterar && portaria.status === 'aceita') {
                <div class="acoes-documento">
                  <small>Depois de publicar no SEI e no DOE, anexe o PDF publicado:</small>
                  <app-envio-pdf rotulo="Anexar PDF publicado" (selecionado)="publicar(portaria, $event)" />
                </div>
              }
            }
          </article>
        }
      }
    </section>

    @if (podeAdministrar()) {
      <section class="cartao-dados" aria-labelledby="titulo-autoridades">
        <header><div><h2 id="titulo-autoridades">Autoridades signatárias</h2>
          <small>Cargo, setor e nome vêm daqui. O usuário vinculado é quem dá o aceite pela autoridade.</small></div></header>
        @if (autoridades().length) {
          <div class="tabela-gestao-envoltorio">
            <table class="tabela-gestao">
              <thead><tr><th>Sigla</th><th>Nome</th><th>Cargo</th><th>Setor</th><th>Aceite por</th><th>Situação</th><th></th></tr></thead>
              <tbody>
                @for (a of autoridades(); track a.id) {
                  <tr><td>{{ a.sigla }}</td><td>{{ a.nome }}</td><td>{{ a.cargo }}</td><td>{{ a.setor }}</td><td>{{ a.usuario_nome || '—' }}</td><td>{{ a.ativa ? 'Ativa' : 'Desativada' }}</td>
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
          <div><label for="aut-nome">Nome *</label><input id="aut-nome" name="nome" maxlength="200" [(ngModel)]="formulario.nome" required /></div>
          <div><label for="aut-cargo">Cargo *</label><input id="aut-cargo" name="cargo" maxlength="200" [(ngModel)]="formulario.cargo" required /></div>
          <div><label for="aut-setor">Setor *</label><input id="aut-setor" name="setor" maxlength="200" [(ngModel)]="formulario.setor" required /></div>
          <div><label for="aut-busca">Buscar usuário que dá o aceite</label>
            <input id="aut-busca" name="busca" placeholder="Digite ao menos 2 letras do nome" [(ngModel)]="busca" (ngModelChange)="buscarUsuarios()" /></div>
          <div><label for="aut-usuario">Usuário que dá o aceite</label>
            <select id="aut-usuario" name="usuario" [(ngModel)]="formulario.usuario_id">
              <option [ngValue]="null">Nenhum</option>
              @for (u of usuarios(); track u.id) { <option [ngValue]="u.id">{{ u.nome_completo }}</option> }
            </select></div>
          <div class="linha-caixas ocupa-duas"><label><input type="checkbox" name="ativa" [(ngModel)]="formulario.ativa" /> Autoridade ativa (aparece na solicitação de portarias)</label></div>
          <div class="acoes-formulario ocupa-duas">
            @if (editando()) { <button type="button" class="acao-secundaria" (click)="limpar()">Cancelar edição</button> }
            <button type="submit" class="acao-primaria">{{ editando() ? 'Salvar autoridade' : 'Cadastrar autoridade' }}</button>
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
    .campo-autoridade label { display: block; margin-bottom: 7px; font-size: 12px; font-weight: 700; }
    .campo-autoridade select { width: 100%; }
    .dica, .vazio { color: var(--spi-apagado); font-size: 12px; }
    .dica { display: block; margin-top: 6px; }
    .vazio { margin: 0; padding: 16px 20px; }
    .portaria-cartao { display: grid; gap: 10px; margin: 0 20px 18px; padding: 16px 18px; border: 1px solid var(--cor-e2e5e8); border-radius: 8px; }
    .portaria-cartao h3 { margin: 0 0 2px; font-size: 15px; }
    .portaria-cartao p, .portaria-cartao ul { margin: 0; }
    .portaria-cartao ul { padding-left: 20px; line-height: 1.7; }
    .portaria-cartao .acoes-linha { justify-content: flex-start; flex-wrap: wrap; }
    .portaria-cartao .acoes-documento { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
    .titulo-form { margin: 0 0 14px; font-size: 14px; }
    .grade-formulario { border-top: 1px solid var(--cor-e2e5e8); }
    .grade-formulario .acoes-formulario { margin-top: 4px; }
    @media (max-width: 760px) { .linha-solicitar { flex-direction: column; align-items: stretch; } }
  `,
})
export class AbaPortariaComponent implements OnInit {
  readonly contratoId = input.required<string>();
  readonly podeEditar = input(false);
  /** Controle total em Contratos: cadastra as autoridades. */
  readonly podeAdministrar = input(false);

  private readonly api = inject(PortariasApiService);
  private readonly contratos = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly painel = signal<PainelPortarias | null>(null);
  protected readonly autoridades = signal<AutoridadePortaria[]>([]);
  protected readonly usuarios = signal<OpcaoUsuario[]>([]);
  protected readonly editando = signal<string | null>(null);
  protected autoridadeId = '';
  protected busca = '';
  protected formulario: GravacaoAutoridade = { ...AUTORIDADE_VAZIA };

  ngOnInit(): void {
    this.carregar();
    if (this.podeAdministrar()) this.api.autoridades().subscribe({ next: (a) => this.autoridades.set(a), error: (e) => this.dialogos.mostrarErro(e) });
  }

  private carregar(): void {
    this.api.painel(this.contratoId()).subscribe({ next: (p) => this.painel.set(p), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Aplica a resposta de uma ação (o painel atualizado) ou mostra o erro. */
  private tratar(operacao: ReturnType<PortariasApiService['painel']>, titulo: string, mensagem = 'Executando a solicitação…'): void {
    this.dialogos.executar(operacao, mensagem).subscribe({
      next: (p) => { this.painel.set(p); this.autoridadeId = ''; },
      error: (e) => this.dialogos.mostrarErro(e, titulo),
    });
  }

  protected solicitar(): void {
    this.tratar(this.api.solicitar(this.contratoId(), this.autoridadeId), 'Não foi possível solicitar a portaria', 'Reservando o número no Protocolo…');
  }

  protected reenviar(p: Portaria): void {
    this.tratar(this.api.reenviar(this.contratoId(), p.id), 'Não foi possível reenviar a portaria');
  }

  protected async aceitar(p: Portaria): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Aceitar a ${p.titulo}?`, mensagem: 'O texto é atualizado com a equipe e o RS atuais. Depois do aceite, exporte a minuta e publique no SEI e no DOE.', rotuloConfirmar: 'Aceitar' });
    if (ok) this.tratar(this.api.aceitar(this.contratoId(), p.id), 'Não foi possível aceitar a portaria');
  }

  protected devolver(p: Portaria): void {
    const motivo = window.prompt('Motivo da devolução:');
    if (motivo?.trim()) this.tratar(this.api.devolver(this.contratoId(), p.id, motivo.trim()), 'Não foi possível devolver a portaria');
  }

  protected cancelar(p: Portaria): void {
    const motivo = window.prompt(`Motivo do cancelamento da ${p.titulo} (o número volta a ficar livre no Protocolo):`);
    if (motivo?.trim()) this.tratar(this.api.cancelar(this.contratoId(), p.id, motivo.trim()), 'Não foi possível cancelar a portaria');
  }

  protected publicar(p: Portaria, arquivo: File | null): void {
    if (arquivo) this.tratar(this.api.publicar(this.contratoId(), p.id, arquivo), 'Não foi possível anexar o PDF publicado', 'Enviando o PDF publicado…');
  }

  protected baixar(p: Portaria, formato: 'docx' | 'pdf'): void {
    this.api.baixarMinuta(this.contratoId(), p.id, formato).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  // --- Autoridades ---

  protected buscarUsuarios(): void {
    if (this.busca.trim().length < 2) return;
    this.contratos.opcoesUsuarios(this.busca.trim()).subscribe({ next: (u) => this.usuarios.set(u), error: () => this.usuarios.set([]) });
  }

  protected editar(a: AutoridadePortaria): void {
    this.editando.set(a.id);
    this.formulario = { sigla: a.sigla, nome: a.nome, cargo: a.cargo, setor: a.setor, usuario_id: a.usuario_id, ativa: a.ativa };
    this.usuarios.set(a.usuario_id ? [{ id: a.usuario_id, login: '', nome_completo: a.usuario_nome ?? '', cargo: '', ativo: true }] : []);
  }

  protected limpar(): void {
    this.editando.set(null);
    this.formulario = { ...AUTORIDADE_VAZIA };
    this.busca = '';
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
