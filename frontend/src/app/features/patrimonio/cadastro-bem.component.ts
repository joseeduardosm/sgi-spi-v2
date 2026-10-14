// Criado por José Eduardo Santana Martins
// Este arquivo serve para cadastrar bens (avulso ou em lote), com os campos obrigatórios no topo e o restante em "Mais dados".
import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { catchError, debounceTime, of, Subject, switchMap } from 'rxjs';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { FilaOfflineService } from './fila-offline.service';
import { montarChapa, separarChapa } from './chapa-prefixo';
import { LeitorCodigoComponent } from './leitor-codigo.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { Bem, DadosBem, ROTULOS_CONSERVACAO } from './patrimonio.models';
import { SeletorSalaComponent } from './seletor-sala.component';

/** Modelo do formulário (campos em texto: a conversão acontece ao enviar). */
interface Formulario {
  prefixo: string; chapa: string; descricao: string; localizacao_id: string; conservacao: number; situacao: 'ativo' | 'em_manutencao'; origem: 'proprio' | 'terceiros'; grupo_id: string;
  uge: string; ua: string; divisao: string; valor_aquisicao: string; valor_atual: string; data_aquisicao: string; garantia_meses: string;
  marca: string; modelo: string; numero_serie: string; nota_fiscal: string; fornecedor: string; observacoes: string;
}

const VAZIO: Formulario = {
  prefixo: '', chapa: '', descricao: '', localizacao_id: '', conservacao: 4, situacao: 'ativo', origem: 'proprio', grupo_id: '', uge: '', ua: '', divisao: '', valor_aquisicao: '', valor_atual: '',
  data_aquisicao: '', garantia_meses: '', marca: '', modelo: '', numero_serie: '', nota_fiscal: '', fornecedor: '', observacoes: '',
};

/**
 * `/patrimonio/bens/novo` (avulso: a sala é escolhida no formulário) e `/patrimonio/bens/lote` (a sala é pedida uma vez e tudo o que for cadastrado vai
 * para ela, até trocar de sala ou encerrar o lote; dá para repetir os dados do último bem mudando só a chapa). Sem sinal, o cadastro vai para a fila do aparelho.
 */
@Component({
  selector: 'app-cadastro-bem',
  imports: [FormsModule, RouterLink, CabecalhoPatrimonioComponent, SeletorSalaComponent, LeitorCodigoComponent, SeletorUsuariosComponent],
  template: `
    <app-cabecalho-patrimonio [titulo]="lote() ? 'Cadastro em lote' : 'Adicionar bem'" [descricao]="lote() ? 'Escolha a sala uma vez; tudo o que cadastrar vai para ela.' : 'Os campos obrigatórios ficam no topo; o restante em \\'Mais dados\\'.'" />
    <form class="painel-gestao patrimonio pat-formulario pat-compacto" (ngSubmit)="salvar()">
      @if (mensagem()) { <p class="pat-sucesso" role="status">{{ mensagem() }}</p> }
      @if (lote() && cadastrados() > 0) { <p class="pat-resumo-lote">{{ cadastrados() }} bem(ns) cadastrado(s) neste lote na sala {{ rotuloSala() }}.</p> }

      <div class="grade-formulario">
        <div class="ocupa-duas"><label for="cb-sala">Sala *</label>
          <app-seletor-sala idCampo="cb-sala" nome="sala" rotulo="Sala" [leitor]="true" [(valor)]="f.localizacao_id" (valorChange)="aoTrocarSala($event)" /></div>
        @if (precisaDadosSala()) {
          <div class="ocupa-duas pat-painel-sala" role="group" aria-label="Setor e responsável da sala">
            <strong>A sala {{ rotuloSala() }} ainda não tem setor e responsável.</strong>
            <p>Informe-os aqui: valem para todos os bens da sala e são salvos junto com este bem.</p>
            <div class="grade-formulario">
              <div><label for="cb-setor">Setor *</label>
                <select id="cb-setor" name="setor" [(ngModel)]="setorId"><option [ngValue]="null">Escolha o setor</option>
                  @for (s of setores(); track s.id) { <option [ngValue]="s.id">{{ s.nome }}</option> }</select></div>
              <div><label>Responsável *</label>
                <app-seletor-usuarios [fonte]="fonteUsuarios" [multiplo]="false" [(selecionados)]="responsavel" textoAjuda="Pesquisar por nome ou login" idCampo="cb-responsavel" /></div>
            </div>
            @if (!fila.online()) { <p class="pat-aviso">Sem conexão: para cadastrar nesta sala é preciso informar o setor e o responsável, e isso exige internet.</p> }
          </div>
        }


        <fieldset class="ocupa-duas pat-identificacao">
          <legend>Identificação * <small>(chapa <b>ou</b> série)</small></legend>
          <div class="pat-identificacao-campos">
            <div><label for="cb-chapa">Chapa</label>
              <div class="pat-entrada-com-acao">
                @if (estado.prefixos().length) {
                  <select name="prefixo" aria-label="Prefixo da chapa" class="pat-prefixo" [(ngModel)]="f.prefixo" (ngModelChange)="conferirChapa()">
                    @for (p of estado.prefixos(); track p.id) { <option [value]="p.codigo">{{ p.codigo }}</option> }
                  </select>
                }
                <input id="cb-chapa" name="chapa" maxlength="60" autocomplete="off" inputmode="text" placeholder="Número (ex.: 231)" [(ngModel)]="f.chapa" [required]="!f.numero_serie.trim()" (change)="conferirChapa()" />
                <button type="button" class="pat-leitor" aria-label="Ler o código da chapa com a câmera" title="Ler código com a câmera" (click)="lendo.set('chapa')">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10" /></svg></button>
              </div>
              @if (chapaFinal() && chapaFinal() !== f.chapa.trim()) { <small class="dica">A chapa ficará <b>{{ chapaFinal() }}</b>.</small> }</div>
            <div><label for="cb-serie">Número de série</label>
              <div class="pat-entrada-com-acao">
                <input id="cb-serie" name="numero_serie" maxlength="80" autocomplete="off" placeholder="Digite ou leia o código" [(ngModel)]="f.numero_serie" [required]="!f.chapa.trim()" />
                <button type="button" class="pat-leitor" aria-label="Ler o código do número de série com a câmera" title="Ler código com a câmera" (click)="lendo.set('serie')">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10" /></svg></button>
              </div></div>
          </div>
          @if (existente(); as e) { <small class="dica" role="status">{{ e.sala_codigo === 'ATUALIZAR' ? 'Este patrimônio já existe e ainda está sem local: escolha a sala onde ele está e salve.' : 'Este patrimônio já existe no sistema (sala ' + e.sala_rotulo + '): os dados do bem foram carregados.' }}</small> }
        </fieldset>

        <div class="ocupa-duas"><label for="cb-descricao">Descrição do material *</label>
          <div class="pat-seletor-sala">
            <input id="cb-descricao" name="descricao" maxlength="300" autocomplete="off" [ngModel]="f.descricao" (ngModelChange)="digitouDescricao($event)" (blur)="sugestoes.set([])" required />
            @if (sugestoes().length) {
              <ul class="pat-opcoes-sala" role="listbox" aria-label="Descrições já cadastradas">
                @for (s of sugestoes(); track s) { <li role="option" (mousedown)="$event.preventDefault()" (click)="usarSugestao(s)">{{ s }}</li> }
              </ul>
            }
          </div></div>

        <div class="ocupa-duas"><label id="cb-conservacao-rotulo">Estado de conservação *</label>
          <div class="pat-segmentado cinco" role="radiogroup" aria-labelledby="cb-conservacao-rotulo">
            @for (c of conservacoes; track c[0]) {
              <button type="button" role="radio" [class.ativo]="f.conservacao === +c[0]" [attr.aria-checked]="f.conservacao === +c[0]" (click)="f.conservacao = +c[0]"><b>{{ c[0] }}</b><small>{{ c[1] }}</small></button>
            }
          </div></div>
        <div><label id="cb-situacao-rotulo">Situação *</label>
          <div class="pat-segmentado" role="radiogroup" aria-labelledby="cb-situacao-rotulo">
            <button type="button" role="radio" [class.ativo]="f.situacao === 'ativo'" [attr.aria-checked]="f.situacao === 'ativo'" (click)="f.situacao = 'ativo'">Ativo</button>
            <button type="button" role="radio" [class.ativo]="f.situacao === 'em_manutencao'" [attr.aria-checked]="f.situacao === 'em_manutencao'" (click)="f.situacao = 'em_manutencao'">Manutenção</button>
          </div></div>
        <div><label id="cb-origem-rotulo">Origem *</label>
          <div class="pat-segmentado" role="radiogroup" aria-labelledby="cb-origem-rotulo">
            <button type="button" role="radio" [class.ativo]="f.origem === 'proprio'" [attr.aria-checked]="f.origem === 'proprio'" (click)="f.origem = 'proprio'">Próprio</button>
            <button type="button" role="radio" [class.ativo]="f.origem === 'terceiros'" [attr.aria-checked]="f.origem === 'terceiros'" (click)="f.origem = 'terceiros'">Terceiros</button>
          </div></div>
      </div>

      <details class="pat-mais-dados" [open]="maisDados()" (toggle)="maisDados.set($any($event.target).open)">
        <summary>Mais dados (opcionais)</summary>
        <div class="grade-formulario">
          <div><label for="cb-grupo">Grupo de material</label>
            <select id="cb-grupo" name="grupo" [(ngModel)]="f.grupo_id"><option value="">Sem grupo</option>
              @for (g of estado.grupos(); track g.id) { <option [value]="g.id">{{ g.nome }}</option> }</select></div>
          <div><label for="cb-uge">UGE</label><input id="cb-uge" name="uge" maxlength="40" [(ngModel)]="f.uge" /></div>
          <div><label for="cb-ua">UA</label><input id="cb-ua" name="ua" maxlength="40" [(ngModel)]="f.ua" /></div>
          <div><label for="cb-divisao">Divisão</label><input id="cb-divisao" name="divisao" maxlength="80" [(ngModel)]="f.divisao" /></div>
          <div><label for="cb-aquisicao">Valor de aquisição (R$)</label><input id="cb-aquisicao" name="valor_aquisicao" inputmode="decimal" placeholder="0,00" [(ngModel)]="f.valor_aquisicao" /></div>
          <div><label for="cb-atual">Valor atual (R$)</label><input id="cb-atual" name="valor_atual" inputmode="decimal" placeholder="0,00" [(ngModel)]="f.valor_atual" /></div>
          <div><label for="cb-data">Data de aquisição</label><input id="cb-data" name="data_aquisicao" type="date" [(ngModel)]="f.data_aquisicao" /></div>
          <div><label for="cb-garantia">Meses de garantia</label><input id="cb-garantia" name="garantia_meses" type="number" inputmode="numeric" min="0" [(ngModel)]="f.garantia_meses" />
            <small class="dica">{{ fimGarantia() }}</small></div>
          <div><label for="cb-marca">Marca</label><input id="cb-marca" name="marca" maxlength="80" [(ngModel)]="f.marca" /></div>
          <div><label for="cb-modelo">Modelo</label><input id="cb-modelo" name="modelo" maxlength="80" [(ngModel)]="f.modelo" /></div>
          <div><label for="cb-nf">Nota fiscal</label><input id="cb-nf" name="nota_fiscal" maxlength="60" [(ngModel)]="f.nota_fiscal" /></div>
          <div class="ocupa-duas"><label for="cb-fornecedor">Fornecedor</label><input id="cb-fornecedor" name="fornecedor" maxlength="200" [(ngModel)]="f.fornecedor" /></div>
          <div class="ocupa-duas"><label for="cb-obs">Observações</label><textarea id="cb-obs" name="observacoes" rows="3" [(ngModel)]="f.observacoes"></textarea></div>
        </div>
        <small class="dica">As fotos (até três) entram na página do bem, depois do cadastro. O responsável vem da sala.</small>
      </details>

      <div class="pat-barra-inferior">
        @if (lote()) {
          <label class="pat-marca"><input type="checkbox" name="repetir" [(ngModel)]="repetir" /> Repetir os demais dados do último bem (chapa, número de série e descrição sempre voltam em branco)</label>
          <a class="acao-secundaria" routerLink="/patrimonio">Encerrar lote</a>
        } @else { <a class="acao-secundaria" routerLink="/patrimonio">Cancelar</a> }
        <button [class.carregando]="salvando()" type="submit" class="acao-primaria" [disabled]="salvando() || !valido()">{{ salvando() ? 'Salvando…' : lote() ? 'Cadastrar e próximo' : 'Salvar' }}</button>
      </div>
    </form>

    @if (lendo(); as campo) {
      <app-leitor-codigo [mensagem]="campo === 'serie' ? 'Aponte a câmera para o código de barras do número de série' : 'Aponte a câmera para o QR code ou código de barras da chapa'"
                         (lido)="lerCodigo(campo, $event)" (fechar)="lendo.set(null)" />
    }
  `,
})
export class CadastroBemComponent implements OnInit {
  private readonly api = inject(PatrimonioApiService);
  protected readonly fila = inject(FilaOfflineService);
  private readonly roteador = inject(Router);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(PatrimonioEstadoService);

  /** Rota `/bens/lote` liga o modo em lote; `?chapa=` preenche a chapa (vem da leitura de um código que não existe). */
  readonly modo = input<string>('', { alias: 'modo' });
  readonly chapa = input<string>('');
  protected readonly lote = computed(() => this.roteador.url.includes('/bens/lote'));

  protected f: Formulario = { ...VAZIO };
  protected readonly conservacoes = Object.entries(ROTULOS_CONSERVACAO);
  protected readonly salvando = signal(false);
  /** Campo cuja leitura de código (câmera) está aberta: a chapa ou o número de série. */
  protected readonly lendo = signal<'chapa' | 'serie' | null>(null);
  protected readonly maisDados = signal(false);
  protected readonly cadastrados = signal(0);
  protected readonly mensagem = signal('');
  /** Bem que já tem a chapa digitada (os dados dele são carregados no formulário e salvar passa a oferecer a movimentação). */
  protected readonly existente = signal<Bem | null>(null);
  protected repetir = true;
  /** Id da sala escolhida (espelha `f.localizacao_id` para o `computed` enxergar a mudança). */
  protected readonly salaId = signal('');
  /** O servidor recusou por sala sem responsável (os dados do aparelho estavam desatualizados): força o painel. */
  private readonly painelForcado = signal(false);
  /** Painel de setor e responsável: aparece na própria tela assim que a sala escolhida não tem esses dados. */
  protected readonly precisaDadosSala = computed(() => this.painelForcado() || !!this.estado.salas().find((s) => s.id === this.salaId() && s.semResponsavel));
  protected readonly sugestoes = signal<string[]>([]);
  private readonly digitacao$ = new Subject<string>();
  protected readonly setores = signal<{ id: number; nome: string }[]>([]);
  protected setorId: number | null = null;
  protected readonly responsavel = signal<OpcaoUsuario[]>([]);
  protected readonly fonteUsuarios = (busca: string) => this.api.opcoesUsuarios(busca);

  protected readonly rotuloSala = () => this.estado.rotuloDaSala(this.f.localizacao_id);
  protected readonly valido = () => !!((this.f.chapa.trim() || this.f.numero_serie.trim()) && this.f.descricao.trim() && this.f.localizacao_id
    && (!this.precisaDadosSala() || (!!this.setorId && this.responsavel().length > 0 && this.fila.online())));

  constructor() {
    this.digitacao$.pipe(
      debounceTime(250),
      switchMap((texto) => (texto.trim().length < 2 ? of([]) : this.api.sugestoesDescricao(texto).pipe(catchError(() => of([]))))),
      takeUntilDestroyed(),
    ).subscribe((lista) => this.sugestoes.set(lista.filter((s) => s.trim().toLowerCase() !== this.f.descricao.trim().toLowerCase())));
  }

  ngOnInit(): void {
    void this.estado.carregar().then(() => this.definirPrefixoPadrao());
    if (this.chapa()) this.aplicarCodigo(this.chapa());
  }

  /** O prefixo padrão (SPI) vem selecionado; no lote ele só é posto uma vez, e o que a pessoa escolher depois permanece. */
  private definirPrefixoPadrao(): void {
    if (!this.f.prefixo) this.f.prefixo = this.estado.prefixoPadrao();
  }

  private aplicarCodigo(codigo: string): void {
    const partes = separarChapa(codigo, this.estado.prefixos());
    if (partes) { this.f.prefixo = partes.prefixo; this.f.chapa = partes.numero; } else this.f.chapa = codigo.trim();
  }

  /** A chapa como o servidor vai gravar (prefixo + número com 6 dígitos). */
  protected chapaFinal(): string {
    return montarChapa(this.f.prefixo, this.f.chapa);
  }

  protected aoTrocarSala(id: string): void {
    this.salaId.set(id);
    this.painelForcado.set(false);
    this.setorId = null;
    this.responsavel.set([]);
    if (this.precisaDadosSala() && !this.setores().length) this.api.opcoesSetores().subscribe((s) => this.setores.set(s));
  }

  /** Mostra o fim da garantia (aquisição + meses) enquanto a pessoa digita; sem a data de aquisição, "indefinida". */
  protected fimGarantia(): string {
    if (!this.f.data_aquisicao || this.f.garantia_meses === '') return 'Garantia indefinida (falta a data de aquisição ou os meses).';
    const [a, m, d] = this.f.data_aquisicao.split('-').map(Number);
    const fim = new Date(a, m - 1 + Number(this.f.garantia_meses), d);
    return `Fim da garantia: ${fim.toLocaleDateString('pt-BR')}`;
  }

  private corpo(): DadosBem {
    const f = this.f;
    const texto = (v: string) => v.trim() || null;
    const numero = (v: string) => (v.trim() ? v.trim().replace(',', '.') : null);
    return {
      id_cliente: crypto.randomUUID(), prefixo: f.prefixo || null, chapa: f.chapa.trim(), descricao: f.descricao.trim(), localizacao_id: f.localizacao_id, conservacao: f.conservacao, situacao: f.situacao, origem: f.origem,
      grupo_id: f.grupo_id || null, uge: texto(f.uge), ua: texto(f.ua), divisao: texto(f.divisao), valor_aquisicao: numero(f.valor_aquisicao), valor_atual: numero(f.valor_atual),
      data_aquisicao: f.data_aquisicao || null, garantia_meses: f.garantia_meses === '' ? null : Number(f.garantia_meses), marca: texto(f.marca), modelo: texto(f.modelo),
      numero_serie: texto(f.numero_serie), nota_fiscal: texto(f.nota_fiscal), fornecedor: texto(f.fornecedor), observacoes: texto(f.observacoes),
    };
  }

  /** Código lido pela câmera: vai para a chapa (e confere se o bem já existe) ou para o número de série. */
  protected lerCodigo(campo: 'chapa' | 'serie', codigo: string): void {
    const valor = codigo.trim();
    if (campo === 'serie') {
      this.f.numero_serie = valor;
      return;
    }
    this.aplicarCodigo(valor);
    this.conferirChapa();
  }

  /** Ao terminar de digitar (ou ler) a chapa: se o bem já existe, carrega os dados dele; a sala escolhida (destino) é mantida. */
  protected conferirChapa(): void {
    const chapa = this.chapaFinal();
    this.existente.set(null);
    if (!chapa || !this.fila.online()) return;
    this.api.bemPorChapa(chapa).subscribe({ next: (bem) => this.carregarExistente(bem), error: () => undefined });
  }

  private carregarExistente(bem: Bem): void {
    const texto = (v: string | number | null) => (v === null || v === undefined ? '' : String(v));
    const sala = this.f.localizacao_id || bem.localizacao_id;
    this.f = {
      prefixo: this.f.prefixo, chapa: bem.chapa ?? this.f.chapa, descricao: bem.descricao, localizacao_id: sala, conservacao: bem.conservacao,
      situacao: bem.situacao === 'em_manutencao' ? 'em_manutencao' : 'ativo', origem: bem.origem, grupo_id: texto(bem.grupo_id), uge: texto(bem.uge), ua: texto(bem.ua),
      divisao: texto(bem.divisao), valor_aquisicao: texto(bem.valor_aquisicao), valor_atual: texto(bem.valor_atual), data_aquisicao: texto(bem.data_aquisicao),
      garantia_meses: texto(bem.garantia_meses), marca: texto(bem.marca), modelo: texto(bem.modelo), numero_serie: texto(bem.numero_serie),
      nota_fiscal: texto(bem.nota_fiscal), fornecedor: texto(bem.fornecedor), observacoes: texto(bem.observacoes),
    };
    if (bem.chapa) this.aplicarCodigo(bem.chapa);
    this.salaId.set(sala);
    this.existente.set(bem);
  }

  /** Bem que já existe: em vez de cadastrar de novo, pergunta se é para registrar a movimentação (a sala escolhida vira o destino). */
  private async perguntarMovimentacao(bem: Bem): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Bem já cadastrado', mensagem: 'Esse bem já existe no sistema. Registrar movimentação?', rotuloConfirmar: 'Sim, registrar movimentação',
    });
    if (!ok) return;
    const destino = this.f.localizacao_id && this.f.localizacao_id !== bem.localizacao_id ? { destino: this.f.localizacao_id } : {};
    void this.roteador.navigate(['/patrimonio/movimentacoes/nova'], { queryParams: { bem: bem.id, ...destino } });
  }

  /** Bem que já existe e ainda está sem local (levantamento inicial): confirma a sala escolhida e grava na hora, sem movimentação. */
  private async perguntarLocalizacao(bem: Bem): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Bem já cadastrado', mensagem: `Esse bem já está no sistema. Confirmar que ele está na sala ${this.rotuloSala()}?`, rotuloConfirmar: 'Sim, está nesta sala',
    });
    if (!ok) return;
    this.salvando.set(true);
    this.api.localizarBem(bem.id, this.f.localizacao_id).subscribe({
      next: () => {
        this.salvando.set(false);
        this.existente.set(null);
        if (!this.lote()) { void this.roteador.navigate(['/patrimonio/bens', bem.id]); return; }
        // No lote segue para o próximo bem, na mesma sala
        this.cadastrados.update((n) => n + 1);
        this.mensagem.set(`Bem ${bem.rotulo} localizado na sala ${this.rotuloSala()}. Pronto para o próximo.`);
        this.f = { ...VAZIO, localizacao_id: this.f.localizacao_id };
      },
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível localizar o bem'); },
    });
  }

  /** O que fazer com um bem que já existe: sem local, confirma a sala; em outra sala, oferece a movimentação; na mesma sala, só avisa. */
  private tratarExistente(bem: Bem): void {
    if (bem.sala_codigo === 'ATUALIZAR') void this.perguntarLocalizacao(bem);
    else if (this.f.localizacao_id === bem.localizacao_id) this.dialogos.avisar('Mesma sala', 'Esse bem já está registrado nesta sala.');
    else void this.perguntarMovimentacao(bem);
  }

  protected salvar(): void {
    if (!this.valido() || this.salvando()) return;
    const existente = this.existente();
    const seguir = () => (existente ? this.tratarExistente(existente) : this.enviarBem());
    // Sala sem setor e responsável: salva esses dados primeiro (também para localizar um bem sem local) e, em seguida, segue
    const precisaSala = this.precisaDadosSala() && (!existente || existente.sala_codigo === 'ATUALIZAR');
    if (precisaSala) {
      this.salvando.set(true);
      this.api.dadosSala(this.f.localizacao_id, this.setorId!, this.responsavel()[0].id).subscribe({
        next: () => { this.painelForcado.set(false); void this.estado.carregar(true).then(() => { this.salvando.set(false); seguir(); }); },
        error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível salvar os dados da sala'); },
      });
      return;
    }
    seguir();
  }

  private enviarBem(): void {
    const corpo = this.corpo();
    // Sem sinal: guarda no aparelho (o `id_cliente` evita duplicar no reenvio) e segue para o próximo
    if (!this.fila.online()) {
      void this.fila.enfileirar({ tipo: 'cadastro_bem', corpo }, `Cadastro do bem ${corpo.chapa || corpo.numero_serie}`).then(() => this.depoisDeSalvar(true));
      return;
    }
    this.salvando.set(true);
    this.api.cadastrarBem(corpo).subscribe({
      next: (bem) => this.depoisDeSalvar(false, bem.id),
      error: (e) => {
        this.salvando.set(false);
        if (e?.status === 0) { void this.fila.enfileirar({ tipo: 'cadastro_bem', corpo }, `Cadastro do bem ${corpo.chapa || corpo.numero_serie}`).then(() => this.depoisDeSalvar(true)); return; }
        // A sala ainda não tem setor e responsável: o sistema pede antes de salvar
        if (e?.error?.codigo === 'sala_sem_responsavel') { this.pedirDadosSala(); return; }
        if (e?.error?.codigo === 'conflito' && corpo.chapa) {
          this.api.bemPorChapa(corpo.chapa).subscribe({ next: (bem) => { this.carregarExistente(bem); this.tratarExistente(bem); }, error: () => this.dialogos.mostrarErro(e, 'Não foi possível cadastrar o bem') });
          return;
        }
        this.dialogos.mostrarErro(e, 'Não foi possível cadastrar o bem');
      },
    });
  }

  private pedirDadosSala(): void {
    this.painelForcado.set(true);
    this.api.opcoesSetores().subscribe((s) => this.setores.set(s));
  }

  /** Ao digitar a descrição, busca (depois de uma pausa) o que já foi cadastrado para sugerir e padronizar. */
  protected digitouDescricao(texto: string): void {
    this.f.descricao = texto;
    this.digitacao$.next(texto);
  }

  protected usarSugestao(descricao: string): void {
    this.f.descricao = descricao;
    this.sugestoes.set([]);
  }

  private depoisDeSalvar(naFila: boolean, bemId?: string): void {
    this.salvando.set(false);
    if (this.lote()) {
      this.cadastrados.update((n) => n + 1);
      // Mantém a sala; a chapa, o número de série e a descrição são sempre limpos; os demais dados se repetem ou também são limpos, conforme a opção
      this.existente.set(null);
      // O prefixo escolhido permanece de um bem para o outro (a pessoa pode trocá-lo no meio do lote)
      this.f = this.repetir ? { ...this.f, chapa: '', numero_serie: '', descricao: '' } : { ...VAZIO, localizacao_id: this.f.localizacao_id, prefixo: this.f.prefixo };
      this.sugestoes.set([]);
      this.mensagem.set(naFila ? 'Guardado no aparelho: será enviado quando o sinal voltar.' : 'Bem cadastrado. Pronto para o próximo.');
      return;
    }
    if (naFila) { this.dialogos.avisar('Guardado no aparelho', 'Sem conexão: o cadastro será enviado quando o sinal voltar.'); void this.roteador.navigate(['/patrimonio']); return; }
    void this.roteador.navigate(['/patrimonio/bens', bemId]);
  }
}
