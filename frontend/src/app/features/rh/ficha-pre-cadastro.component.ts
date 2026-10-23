// Criado por José Eduardo Santana Martins
// Este arquivo serve para o formulário da ficha de pré-cadastro do RH: seções de dados pessoais, documentos, contato, endereço, vínculo, formações e experiências.

import { DatePipe } from '@angular/common';
import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged, switchMap } from 'rxjs';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { Cargo } from './rh-cargos.models';
import { RhCargosApiService } from './rh-cargos-api.service';
import { ImportacaoFichasComponent } from './importacao-fichas.component';
import { RhAdmissaoApiService } from './rh-admissao-api.service';
import { RhPreCadastroApiService } from './rh-pre-cadastro-api.service';
import { CamposFicha, fichaVazia, GravacaoFicha, LeituraFicha, LoginDisponivel, ROTULOS_STATUS_FICHA } from './rh-pre-cadastro.models';

/** Um campo do formulário: chave em `CamposFicha`, rótulo e tipo do controle. */
interface CampoForm { chave: keyof CamposFicha; rotulo: string; tipo?: 'text' | 'date' | 'select'; opcoes?: string[]; maximo?: number; ajuda?: string; largo?: boolean }
interface Secao { id: string; titulo: string; campos: CampoForm[] }

const UFS = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'];

/** Largura de cada campo na grade de 12 colunas (o que não está aqui ocupa 4). As linhas fecham em 12 para o formulário ficar alinhado. */
const COLUNAS: Partial<Record<keyof CamposFicha, number>> = {
  nome_completo: 8, nome_social: 4, data_nascimento: 3, sexo: 3, estado_civil: 3, nacionalidade: 3, nome_mae: 6, nome_pai: 6, naturalidade_cidade: 4, naturalidade_uf: 2,
  cpf: 3, rg_numero: 3, rg_orgao: 2, rg_uf: 2, rg_emissao: 2, cin: 4, pis_pasep: 4, cnh: 4, titulo_numero: 6, titulo_zona: 3, titulo_secao: 3, ctps_numero: 6, ctps_serie: 4, ctps_uf: 2,
  email_pessoal: 6, telefone: 3, celular: 3, emergencia_nome: 6, emergencia_parentesco: 3, emergencia_telefone: 3,
  cep: 3, logradouro: 9, numero: 2, complemento: 4, bairro: 6, cidade: 8, uf: 4,
  vinculo_tipo: 4, orgao_origem: 4, cargo_origem: 4, rs_pv: 4, inicio_previsto: 4, observacoes: 12,
};

const SECOES: Secao[] = [
  { id: 'identificacao', titulo: 'Identificação', campos: [
    { chave: 'nome_completo', rotulo: 'Nome completo *', largo: true, maximo: 200 },
    { chave: 'nome_social', rotulo: 'Nome social', maximo: 200 },
    { chave: 'data_nascimento', rotulo: 'Data de nascimento', tipo: 'date' },
    { chave: 'sexo', rotulo: 'Sexo', tipo: 'select', opcoes: ['Feminino', 'Masculino', 'Outro', 'Prefere não informar'] },
    { chave: 'estado_civil', rotulo: 'Estado civil', tipo: 'select', opcoes: ['Solteiro(a)', 'Casado(a)', 'União estável', 'Separado(a)', 'Divorciado(a)', 'Viúvo(a)'] },
    { chave: 'nacionalidade', rotulo: 'Nacionalidade', maximo: 60 },
    { chave: 'naturalidade_cidade', rotulo: 'Naturalidade (cidade)', maximo: 100 },
    { chave: 'naturalidade_uf', rotulo: 'Naturalidade (UF)', tipo: 'select', opcoes: UFS },
    { chave: 'nome_mae', rotulo: 'Nome da mãe', maximo: 200 },
    { chave: 'nome_pai', rotulo: 'Nome do pai', maximo: 200 },
  ] },
  { id: 'documentos', titulo: 'Documentos', campos: [
    { chave: 'cpf', rotulo: 'CPF', maximo: 14, ajuda: 'Os dígitos verificadores são conferidos.' },
    { chave: 'rg_numero', rotulo: 'RG (número)', maximo: 30 },
    { chave: 'rg_orgao', rotulo: 'RG (órgão emissor)', maximo: 30 },
    { chave: 'rg_uf', rotulo: 'RG (UF)', tipo: 'select', opcoes: UFS },
    { chave: 'rg_emissao', rotulo: 'RG (emissão)', tipo: 'date' },
    { chave: 'cin', rotulo: 'CIN (Carteira de Identidade Nacional)', maximo: 30 },
    { chave: 'pis_pasep', rotulo: 'PIS/PASEP', maximo: 14 },
    { chave: 'titulo_numero', rotulo: 'Título de eleitor', maximo: 20 },
    { chave: 'titulo_zona', rotulo: 'Zona', maximo: 5 },
    { chave: 'titulo_secao', rotulo: 'Seção', maximo: 5 },
    { chave: 'ctps_numero', rotulo: 'CTPS (número)', maximo: 20 },
    { chave: 'ctps_serie', rotulo: 'CTPS (série)', maximo: 10 },
    { chave: 'ctps_uf', rotulo: 'CTPS (UF)', tipo: 'select', opcoes: UFS },
    { chave: 'cnh', rotulo: 'CNH', maximo: 20 },
  ] },
  { id: 'contato', titulo: 'Contato', campos: [
    { chave: 'email_pessoal', rotulo: 'E-mail pessoal', maximo: 200 },
    { chave: 'telefone', rotulo: 'Telefone', maximo: 30 },
    { chave: 'celular', rotulo: 'Celular', maximo: 30 },
    { chave: 'emergencia_nome', rotulo: 'Contato de emergência (nome)', maximo: 200 },
    { chave: 'emergencia_parentesco', rotulo: 'Parentesco', maximo: 60 },
    { chave: 'emergencia_telefone', rotulo: 'Telefone de emergência', maximo: 30 },
  ] },
  { id: 'endereco', titulo: 'Endereço', campos: [
    { chave: 'cep', rotulo: 'CEP', maximo: 9 },
    { chave: 'logradouro', rotulo: 'Logradouro', largo: true, maximo: 200 },
    { chave: 'numero', rotulo: 'Número', maximo: 20 },
    { chave: 'complemento', rotulo: 'Complemento', maximo: 100 },
    { chave: 'bairro', rotulo: 'Bairro', maximo: 100 },
    { chave: 'cidade', rotulo: 'Cidade', maximo: 100 },
    { chave: 'uf', rotulo: 'UF', tipo: 'select', opcoes: UFS },
  ] },
  { id: 'vinculo', titulo: 'Vínculo com o serviço público', campos: [
    { chave: 'vinculo_tipo', rotulo: 'Tipo de vínculo', tipo: 'select', opcoes: ['Servidor efetivo cedido', 'Comissionado sem vínculo', 'Empregado público', 'Outro'] },
    { chave: 'orgao_origem', rotulo: 'Órgão de origem', maximo: 200 },
    { chave: 'cargo_origem', rotulo: 'Cargo de origem', maximo: 200 },
    { chave: 'rs_pv', rotulo: 'RS/PV (matrícula)', maximo: 30 },
    { chave: 'inicio_previsto', rotulo: 'Início previsto', tipo: 'date' },
  ] },
];

/** Formulário da ficha (nova ou existente): dados em seções, login proposto com checagem no SGI e no AD, formações e experiências. */
@Component({
  selector: 'app-ficha-pre-cadastro',
  imports: [FormsModule, DatePipe, CabecalhoRhComponent, EsqueletoComponent, ImportacaoFichasComponent],
  template: `
    @if (!minha()) { <app-cabecalho-rh [titulo]="titulo()" [trilha]="['Pré-cadastro', titulo()]" descricao="Os dados pessoais são sensíveis: só o RH vê esta ficha." /> }

    @if (ficha(); as f) {
      @if (!minha() && !lida()) {
        <div class="acoes-formulario" style="margin-bottom: 16px">
          <button type="button" class="acao-secundaria" (click)="importacaoAberta.set(true)">Preencher por planilha (formulário XLSX)</button>
        </div>
        <app-importacao-fichas [aberta]="importacaoAberta()" (abertaChange)="fecharImportacao($event)" (importado)="importou = true" />
      }
      @if (minha()) {
        <p class="aviso-bloco">@if (somenteLeitura()) { Estes dados foram cadastrados pelo RH na sua admissão. Para corrigir algo, fale com o RH. }
          @else if (lida()?.validado_em) { Ficha validada pelo RH em {{ lida()?.validado_em | date: 'dd/MM/yyyy HH:mm' }}. Se você alterar, o RH valida de novo. }
          @else if (lida()?.enviada_em) { Ficha enviada em {{ lida()?.enviada_em | date: 'dd/MM/yyyy HH:mm' }}, aguardando a validação do RH. }
          @else { Preencha seus dados cadastrais. Depois de enviar, o RH confere e valida. Só você e o RH veem estes dados. }</p>
      } @else if (lida()?.enviada_em && !lida()?.validado_em && lida()?.status === 'vinculado') {
        <p class="aviso-bloco">A própria pessoa enviou esta ficha em {{ lida()?.enviada_em | date: 'dd/MM/yyyy HH:mm' }}. Confira os dados e valide.</p>
      }
      @if (somenteLeitura() && !minha()) {
        <p class="aviso-bloco">Esta ficha está {{ rotuloStatus() }}@if (lida()?.usuario_nome) { (conta de <b>{{ lida()?.usuario_nome }}</b>) } e não pode mais ser alterada aqui.</p>
      }
      <form class="parametros-rh" (ngSubmit)="salvar(f)">
        <fieldset [disabled]="somenteLeitura()" class="sem-borda">
          @for (s of secoes; track s.id) {
            <section class="cartao-dados" [attr.aria-labelledby]="'sec-' + s.id">
              <header><div><h2 [id]="'sec-' + s.id">{{ s.titulo }}</h2></div></header>
              <div class="corpo">
                <div class="grade-ficha">
                  @for (c of s.campos; track c.chave) {
                    @if (!(minha() && c.chave === 'rs_pv')) {
                    <div class="campo" [style.--col]="colunas(c.chave)">
                      <label [for]="'f-' + c.chave">{{ c.rotulo }}</label>
                      @if (c.tipo === 'select') {
                        <select [id]="'f-' + c.chave" [name]="c.chave" [ngModel]="valor(f, c.chave)" (ngModelChange)="definir(f, c.chave, $event)">
                          <option value="">—</option>
                          @for (o of c.opcoes; track o) { <option [value]="o">{{ o }}</option> }
                        </select>
                      } @else if (c.tipo === 'date') {
                        <input [id]="'f-' + c.chave" [name]="c.chave" type="date" [ngModel]="valor(f, c.chave)" (ngModelChange)="definir(f, c.chave, $event || null)" />
                      } @else {
                        <input [id]="'f-' + c.chave" [name]="c.chave" type="text" [attr.maxlength]="c.maximo" [ngModel]="valor(f, c.chave)" (ngModelChange)="definir(f, c.chave, $event)" />
                      }
                      @if (c.ajuda) { <small class="ajuda">{{ c.ajuda }}</small> }
                    </div>
                    }
                  }
                </div>
                @if (s.id === 'vinculo' && !minha()) {
                  <div class="grade-ficha" style="margin-top: 18px">
                    <div class="campo" style="--col: 6">
                      <label for="f-setor">Setor pretendido</label>
                      <select id="f-setor" name="setor_pretendido" [ngModel]="setorPretendido()" (ngModelChange)="escolherSetor(f, $event)">
                        <option [ngValue]="null">—</option>
                        @for (st of setoresComVagas(); track st.id) { <option [ngValue]="st.id">{{ st.nome }}</option> }
                      </select>
                      <small class="ajuda">Só aparecem setores com vaga em RH &gt; Cargos.</small>
                    </div>
                    <div class="campo" style="--col: 6">
                      <label for="f-cargo">Cargo pretendido (vaga)</label>
                      <select id="f-cargo" name="cargo_id" [(ngModel)]="f.cargo_id" [disabled]="!setorPretendido()">
                        <option [ngValue]="null">{{ setorPretendido() ? '—' : 'Escolha o setor primeiro' }}</option>
                        @for (c of vagasDoSetor(); track c.id) { <option [ngValue]="c.id">{{ c.rotulo }}</option> }
                      </select>
                    </div>
                    <div class="campo" style="--col: 12"><label for="f-obs">Observações</label><textarea id="f-obs" name="observacoes" rows="3" maxlength="4000" [(ngModel)]="f.observacoes"></textarea></div>
                  </div>
                }
              </div>
            </section>
          }

          <section class="cartao-dados" aria-labelledby="sec-formacoes">
            <header><div><h2 id="sec-formacoes">Formação</h2><small>Inclua quantas formações forem necessárias.</small></div></header>
            <div class="corpo">
              @for (x of f.formacoes; track $index; let i = $index) {
                <div class="item-repetido">
                  <div class="grade-parametros duas">
                    <div class="campo"><label [for]="'fo-nivel-' + i">Nível</label>
                      <select [id]="'fo-nivel-' + i" [name]="'fo-nivel-' + i" [(ngModel)]="x.nivel"><option value="">—</option>@for (n of niveis; track n) { <option [value]="n">{{ n }}</option> }</select></div>
                    <div class="campo"><label [for]="'fo-curso-' + i">Curso</label><input [id]="'fo-curso-' + i" [name]="'fo-curso-' + i" maxlength="200" [(ngModel)]="x.curso" /></div>
                    <div class="campo"><label [for]="'fo-inst-' + i">Instituição</label><input [id]="'fo-inst-' + i" [name]="'fo-inst-' + i" maxlength="200" [(ngModel)]="x.instituicao" /></div>
                    <div class="campo"><label [for]="'fo-ano-' + i">Ano de conclusão</label><input [id]="'fo-ano-' + i" [name]="'fo-ano-' + i" type="number" min="1950" max="2100" [(ngModel)]="x.ano_conclusao" /></div>
                  </div>
                  <div class="rodape-item">
                    <div class="opcoes-parametros"><label class="opcao"><input type="checkbox" [name]="'fo-and-' + i" [(ngModel)]="x.em_andamento" /><span><strong>Em andamento</strong></span></label></div>
                    @if (!somenteLeitura()) { <button type="button" class="acao-secundaria acao-pequena" (click)="f.formacoes.splice(i, 1)">Remover formação</button> }
                  </div>
                </div>
              } @empty { <p class="dica-formulario">Nenhuma formação informada.</p> }
              @if (!somenteLeitura()) { <button type="button" class="acao-secundaria" (click)="f.formacoes.push(novaFormacao())">+ Formação</button> }
            </div>
          </section>

          <section class="cartao-dados" aria-labelledby="sec-experiencias">
            <header><div><h2 id="sec-experiencias">Experiências anteriores</h2><small>Órgãos e empresas por onde a pessoa passou.</small></div></header>
            <div class="corpo">
              @for (x of f.experiencias; track $index; let i = $index) {
                <div class="item-repetido">
                  <div class="grade-parametros duas">
                    <div class="campo"><label [for]="'ex-emp-' + i">Órgão ou empresa</label><input [id]="'ex-emp-' + i" [name]="'ex-emp-' + i" maxlength="200" [(ngModel)]="x.empresa" /></div>
                    <div class="campo"><label [for]="'ex-cargo-' + i">Cargo</label><input [id]="'ex-cargo-' + i" [name]="'ex-cargo-' + i" maxlength="200" [(ngModel)]="x.cargo" /></div>
                    <div class="campo"><label [for]="'ex-ini-' + i">Início</label><input [id]="'ex-ini-' + i" [name]="'ex-ini-' + i" type="date" [(ngModel)]="x.inicio" /></div>
                    <div class="campo"><label [for]="'ex-fim-' + i">Fim</label><input [id]="'ex-fim-' + i" [name]="'ex-fim-' + i" type="date" [(ngModel)]="x.fim" /></div>
                    <div class="campo campo-largo"><label [for]="'ex-desc-' + i">Descrição das atividades</label><textarea [id]="'ex-desc-' + i" [name]="'ex-desc-' + i" rows="3" maxlength="4000" [(ngModel)]="x.descricao"></textarea></div>
                  </div>
                  @if (!somenteLeitura()) { <div class="rodape-item"><button type="button" class="acao-secundaria acao-pequena" (click)="f.experiencias.splice(i, 1)">Remover experiência</button></div> }
                </div>
              } @empty { <p class="dica-formulario">Nenhuma experiência informada.</p> }
              @if (!somenteLeitura()) { <button type="button" class="acao-secundaria" (click)="f.experiencias.push(novaExperiencia())">+ Experiência</button> }
            </div>
          </section>

          @if (!minha()) {
          <section class="cartao-dados" aria-labelledby="sec-login">
            <header><div><h2 id="sec-login">Login e conta</h2><small>O login proposto segue para a TI no chamado de criação da conta.</small></div></header>
            <div class="corpo">
              <div class="grade-parametros">
                <div class="campo">
                  <label for="f-login">Login proposto</label>
                  <input id="f-login" name="login_proposto" maxlength="60" autocomplete="off" placeholder="ex.: maria.souza" [ngModel]="f.login_proposto ?? ''" (ngModelChange)="mudarLogin(f, $event)" />
                  @if (checando()) { <small class="ajuda">Conferindo no SGI e no AD…</small> }
                  @else if (situacaoLogin(); as s) {
                    <small class="ajuda" [class.texto-erro]="!s.disponivel">{{ s.disponivel ? '✓' : '✗' }} {{ s.detalhe }}@if (s.disponivel && !s.verificado_no_ad) { (o AD não foi conferido) }</small>
                  }
                </div>
              </div>
              <div class="opcoes-parametros" style="margin-top: 18px">
                <label class="opcao"><input type="checkbox" name="pronta" [checked]="f.status === 'aguardando_conta'" (change)="f.status = $any($event.target).checked ? 'aguardando_conta' : 'rascunho'" />
                  <span><strong>Ficha pronta: aguardando a criação da conta</strong>
                    <small>Exige o login proposto. Quando a conta aparecer no AD, a ficha se liga a ela. Desmarcada, a ficha fica como rascunho.</small></span></label>
              </div>
            </div>
          </section>
          }
        </fieldset>

        <footer class="rodape-parametros">
          <span class="atualizacao">@if (lida(); as l) { Situação: <b>{{ rotuloStatus() }}</b> }</span>
          @if (lida() && !somenteLeitura() && !minha()) { <button type="button" class="acao-recusar" (click)="cancelar()">Cancelar ficha</button> }
          @if (lida() && !minha() && !lida()?.login_proposto && lida()?.enviada_em && !lida()?.validado_em) { <button type="button" class="acao-positiva" (click)="validar()">Validar ficha</button> }
          @if (lida() && !minha() && !somenteLeitura() && lida()?.login_proposto && lida()?.cargo_rotulo) { <button type="button" class="acao-secundaria" (click)="iniciarAdmissao()">Iniciar admissão</button> }
          @if (!minha()) { <button type="button" class="acao-secundaria" (click)="voltar()">Voltar</button> }
          @if (!somenteLeitura() || ehLegadoEditavel()) { <button type="submit" class="acao-primaria" [class.carregando]="salvando()" [disabled]="!f.nome_completo.trim()">{{ minha() ? 'Enviar para validação' : 'Salvar ficha' }}</button> }
        </footer>
      </form>
    } @else { <app-esqueleto tipo="formulario" [linhas]="6" /> }
  `,
})
export class FichaPreCadastroComponent implements OnInit {
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  private readonly api = inject(RhPreCadastroApiService);
  private readonly cargosApi = inject(RhCargosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly admissoes = inject(RhAdmissaoApiService);
  private readonly autenticacao = inject(AutenticacaoService);

  /** Modo "minha ficha": a própria pessoa (legados) preenche e o RH valida; sem login proposto, cargo pretendido nem RS/PV. */
  readonly minha = input(false);

  protected readonly secoes = SECOES;
  protected readonly niveis = ['Ensino médio', 'Técnico', 'Graduação', 'Pós-graduação', 'Mestrado', 'Doutorado'];
  protected readonly ficha = signal<GravacaoFicha | null>(null);
  protected readonly lida = signal<LeituraFicha | null>(null);
  protected readonly vagas = signal<Cargo[]>([]);
  /** Setor escolhido antes do cargo: filtra as vagas do combo seguinte. */
  protected readonly setorPretendido = signal<number | null>(null);
  protected readonly setoresComVagas = computed(() => {
    const unicos = new Map<number, string>();
    for (const v of this.vagas()) unicos.set(v.setor_id, v.setor_nome);
    return [...unicos].map(([id, nome]) => ({ id, nome })).sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
  });
  protected readonly vagasDoSetor = computed(() => this.vagas().filter((v) => v.setor_id === this.setorPretendido()));
  protected readonly salvando = signal(false);
  protected readonly importacaoAberta = signal(false);
  protected readonly checando = signal(false);
  protected readonly situacaoLogin = signal<LoginDisponivel | null>(null);
  private readonly digitado = new Subject<string>();

  protected titulo = () => (this.lida() ? this.lida()!.nome_completo : 'Nova ficha');
  /** Ficha de quem já tinha conta (sem login proposto) continua editável: a pessoa e o RH podem corrigir antes de validar. */
  protected ehLegadoEditavel = () => this.lida()?.status === 'vinculado' && !this.lida()?.login_proposto;
  protected somenteLeitura = () => ['vinculado', 'cancelado'].includes(this.lida()?.status ?? '') && !this.ehLegadoEditavel();
  protected rotuloStatus = () => (this.lida() ? ROTULOS_STATUS_FICHA[this.lida()!.status].toLowerCase() : '');

  ngOnInit(): void {
    this.cargosApi.cargos({ situacao: 'vago' }).subscribe({ next: (v) => { this.vagas.set(v); this.deduzirSetor(); }, error: () => undefined });
    // Confere o login depois de uma pausa na digitação, para não consultar o AD a cada tecla
    this.digitado.pipe(
      debounceTime(500), distinctUntilChanged(),
      switchMap((login) => { this.checando.set(true); return this.api.loginDisponivel(login, this.lida()?.id ?? null); }),
    ).subscribe({ next: (r) => { this.situacaoLogin.set(r); this.checando.set(false); }, error: () => this.checando.set(false) });

    const id = this.rota.snapshot.paramMap.get('id');
    if (this.minha()) {
      this.admissoes.minhaFicha().subscribe({ next: (l) => (l ? this.carregarLida(l) : this.ficha.set({ ...fichaVazia(), nome_completo: this.autenticacao.usuario()?.nome_completo ?? '' })), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível abrir a sua ficha') });
      return;
    }
    if (!id) { this.ficha.set(fichaVazia()); return; }
    this.api.obter(Number(id)).subscribe({ next: (l) => this.carregarLida(l), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível abrir a ficha') });
  }

  private carregarLida(l: LeituraFicha): void {
    this.lida.set(l);
    const { id: _i, usuario_id: _u, usuario_nome: _n, vinculado_em: _v, enviada_em: _e, validado_em: _va, cargo_rotulo: _c, criado_em: _ce, atualizado_em: _a, ...dados } = l;
    this.ficha.set({ ...dados, status: l.status === 'aguardando_conta' ? 'aguardando_conta' : 'rascunho' } as GravacaoFicha);
    this.deduzirSetor();
  }

  /** Numa ficha já salva, o setor pretendido é o do cargo escolhido (as vagas e a ficha chegam em chamadas separadas). */
  private deduzirSetor(): void {
    const cargoId = this.ficha()?.cargo_id;
    const vaga = cargoId ? this.vagas().find((v) => v.id === cargoId) : undefined;
    if (vaga) this.setorPretendido.set(vaga.setor_id);
  }

  protected escolherSetor(f: GravacaoFicha, setorId: number | null): void {
    this.setorPretendido.set(setorId);
    f.cargo_id = null;
  }

  protected colunas(chave: keyof CamposFicha): number {
    return COLUNAS[chave] ?? 4;
  }

  /** Depois de importar, ao fechar a janela a pessoa vai para a lista de fichas (a ficha em branco não faz mais sentido). */
  protected importou = false;

  protected fecharImportacao(aberta: boolean): void {
    this.importacaoAberta.set(aberta);
    if (!aberta && this.importou) this.voltar();
  }

  protected valor(f: GravacaoFicha, chave: keyof CamposFicha): string {
    return (f[chave] as string | null) ?? '';
  }

  protected definir(f: GravacaoFicha, chave: keyof CamposFicha, valor: string | null): void {
    (f as unknown as Record<string, unknown>)[chave] = valor;
  }

  protected mudarLogin(f: GravacaoFicha, valor: string): void {
    f.login_proposto = valor.trim() ? valor.trim().toLowerCase() : null;
    this.situacaoLogin.set(null);
    if (f.login_proposto) this.digitado.next(f.login_proposto);
  }

  protected novaFormacao() { return { nivel: '', curso: '', instituicao: '', ano_conclusao: null, em_andamento: false }; }
  protected novaExperiencia() { return { empresa: '', cargo: '', inicio: null, fim: null, descricao: '' }; }

  protected salvar(f: GravacaoFicha): void {
    this.salvando.set(true);
    const id = this.lida()?.id;
    const dados: GravacaoFicha = { ...f, nome_completo: f.nome_completo.trim() };
    const chamada = this.minha() ? this.admissoes.enviarMinhaFicha(dados) : id ? this.api.alterar(id, dados) : this.api.criar(dados);
    chamada.subscribe({
      next: (l) => {
        this.salvando.set(false);
        this.dialogos.avisar(this.minha() ? 'Ficha enviada' : 'Ficha salva', this.minha() ? 'O RH vai conferir e validar os seus dados.' : 'Os dados da ficha foram gravados.');
        if (this.minha()) { this.lida.set(l); return; }
        if (!id) void this.roteador.navigate(['/rh/pre-cadastros', l.id], { replaceUrl: true });
        else this.lida.set(l);
      },
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível salvar a ficha'); },
    });
  }

  protected async cancelar(): Promise<void> {
    const l = this.lida();
    if (!l || !(await this.dialogos.confirmar({ titulo: 'Cancelar esta ficha?', mensagem: 'O login proposto fica livre para outra ficha. A ficha continua na lista como cancelada.', rotuloConfirmar: 'Cancelar ficha', perigo: true }))) return;
    this.api.cancelar(l.id).subscribe({ next: () => this.voltar(), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível cancelar a ficha') });
  }

  protected validar(): void {
    const l = this.lida();
    if (!l) return;
    this.dialogos.executar(this.admissoes.validarFicha(l.id), 'Validando…').subscribe({
      next: (n) => { this.lida.set(n); this.dialogos.avisar('Ficha validada', 'A validação entrou no histórico funcional da pessoa.'); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível validar a ficha'),
    });
  }

  protected iniciarAdmissao(): void {
    const l = this.lida();
    if (!l) return;
    this.dialogos.executar(this.admissoes.iniciar(l.id), 'Iniciando…').subscribe({
      next: (a) => void this.roteador.navigate(['/rh/admissoes', a.id]),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível iniciar a admissão'),
    });
  }

  protected voltar(): void {
    void this.roteador.navigate(['/rh/pre-cadastros']);
  }
}
