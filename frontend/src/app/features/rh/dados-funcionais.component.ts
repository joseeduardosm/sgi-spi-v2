// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir e gravar os dados funcionais do RH (autorizador, período aquisitivo, LP, jornada e documentos), exclusivos da CGP.

import { DatePipe } from '@angular/common';
import { Component, computed, effect, inject, input, output, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Observable, of, switchMap, tap } from 'rxjs';
import { RouterLink } from '@angular/router';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { UsuariosApiService } from '../usuarios/usuarios-api.service';
import { RhApiService } from './rh-api.service';
import { CadastroRh } from './rh.models';

/** "15/03" válido (29/02 aceito)? Vazio também é válido (não informado). */
export function inicioAquisitivoValido(texto: string): boolean {
  if (!texto.trim()) return true;
  const m = /^(\d{2})\/(\d{2})$/.exec(texto.trim());
  if (!m) return false;
  const dia = Number(m[1]);
  const mes = Number(m[2]);
  const ultimo = new Date(Date.UTC(2024, mes, 0)).getUTCDate(); // 2024 é bissexto
  return mes >= 1 && mes <= 12 && dia >= 1 && dia <= ultimo;
}

/** Dados funcionais editáveis no formulário (valores iniciais: nada informado). */
function vazio() {
  return {
    sem_superior: false, exercicio: new Date().getFullYear() as number | null, saldo_lp_dias: 0,
    jornada_semanal_horas: null as number | null, regime_plantao: false, horario_estudante: false,
    horario_trabalho_inicio: null as string | null, horario_trabalho_fim: null as string | null,
    intervalo_inicio: null as string | null, intervalo_fim: null as string | null, rg_cin: null as string | null, rs_pv: null as string | null,
  };
}

function dataBr(texto: string): string {
  return texto.split('-').reverse().join('/');
}

/**
 * Bloco "Dados funcionais do RH": autorizador (sugestão: o superior imediato), substituto, topo da hierarquia,
 * início do período aquisitivo (dd/mm) com o período vigente e o histórico, o saldo de licença-prêmio, a jornada, os horários
 * e os documentos (RG/CIN, RS/PV).
 * Só aparece para a CGP e o SuperRoot (a API responde 403 aos demais). Usado em Validações e em Usuários.
 */
@Component({
  selector: 'app-dados-funcionais',
  imports: [FormsModule, DatePipe, RouterLink, SeletorUsuariosComponent],
  template: `
    @if (cadastro(); as c) {
      <div class="bloco-dados-funcionais">
        <p class="secao-formulario" style="margin-top: 0">Dados funcionais do RH <small>(exclusivos da CGP; o usuário não vê)</small></p>
        @if (c.pendentes.length && mostrarLinkValidacoes()) {
          <p class="aviso-bloco informativo">{{ c.pendentes.length }} alteração(ões) de cadastro aguardando validação.
            <a class="link-arquivo" [routerLink]="['/rh/validacoes']" [queryParams]="{ usuario: c.usuario_id }">Analisar</a></p>
        }
        <div class="grade-formulario">
          <div><label [for]="id('autorizador')">Autorizador de férias e LP</label>
            <app-seletor-usuarios [idCampo]="id('autorizador')" [multiplo]="false" [(selecionados)]="autorizador" [fonte]="usuariosApi.opcoesGestor"
                                  textoAjuda="Pesquisar autorizador" />
            @if (!c.funcionais.autorizador_id && c.funcionais.autorizador_sugerido_id) { <small class="dica-formulario">Sugestão: o superior imediato.</small> }</div>
          <div><label [for]="id('substituto')">Substituto do autorizador</label>
            <app-seletor-usuarios [idCampo]="id('substituto')" [multiplo]="false" [(selecionados)]="substituto" [fonte]="usuariosApi.opcoesGestor"
                                  textoAjuda="Pesquisar substituto" />
            <small class="dica-formulario">Aprova quando este usuário, como autorizador, estiver afastado.</small></div>
          <div><label [for]="id('inicio')">Início do período aquisitivo (dd/mm)</label>
            <input [id]="id('inicio')" inputmode="numeric" maxlength="5" placeholder="dd/mm" [class.invalido]="!inicioValido()"
                   [ngModel]="inicio()" (ngModelChange)="digitarInicio($event)" [ngModelOptions]="{ standalone: true }" />
            <small class="dica-formulario" [class.texto-erro]="!inicioValido()">{{ inicioValido()
              ? 'Todo ano, nesta data, começa um novo exercício: entram os dias de férias dele e o saldo não usado do anterior expira.'
              : 'Use dd/mm com uma data válida (ex.: 15/03).' }}</small></div>
          <div class="linha-caixas" style="align-self: center"><label><input type="checkbox" [(ngModel)]="funcionais.sem_superior" [ngModelOptions]="{ standalone: true }" />
            Topo da hierarquia (sem superior imediato)</label></div>
          <div><label [for]="id('exercicio')">Exercício da licença-prêmio</label>
            <input [id]="id('exercicio')" type="number" min="2000" max="2100" [(ngModel)]="funcionais.exercicio" [ngModelOptions]="{ standalone: true }" /></div>
          <div><label [for]="id('lp')">Dias de licença-prêmio</label>
            <input [id]="id('lp')" type="number" min="0" max="365" [(ngModel)]="funcionais.saldo_lp_dias" [ngModelOptions]="{ standalone: true }" /></div>
        </div>

        <p class="secao-formulario">Jornada e documentos</p>
        <div class="grade-formulario">
          <div><label [for]="id('jornada')">Jornada de trabalho (horas semanais)</label>
            <input [id]="id('jornada')" type="number" min="1" max="80" placeholder="Ex.: 40" [(ngModel)]="funcionais.jornada_semanal_horas" [ngModelOptions]="{ standalone: true }" /></div>
          <div class="linha-caixas" style="align-self: center">
            <label><input type="checkbox" [(ngModel)]="funcionais.regime_plantao" [ngModelOptions]="{ standalone: true }" /> Regime de plantão</label>
            <label><input type="checkbox" [(ngModel)]="funcionais.horario_estudante" [ngModelOptions]="{ standalone: true }" /> Horário de estudante</label></div>
          <div><label [for]="id('trabalho-inicio')">Horário de trabalho</label>
            <div class="par-horarios">
              <input [id]="id('trabalho-inicio')" type="time" aria-label="Início do horário de trabalho" [(ngModel)]="funcionais.horario_trabalho_inicio" [ngModelOptions]="{ standalone: true }" />
              <span>às</span>
              <input type="time" aria-label="Fim do horário de trabalho" [(ngModel)]="funcionais.horario_trabalho_fim" [ngModelOptions]="{ standalone: true }" /></div></div>
          <div><label [for]="id('intervalo-inicio')">Intervalo de almoço e descanso</label>
            <div class="par-horarios">
              <input [id]="id('intervalo-inicio')" type="time" aria-label="Início do intervalo" [(ngModel)]="funcionais.intervalo_inicio" [ngModelOptions]="{ standalone: true }" />
              <span>às</span>
              <input type="time" aria-label="Fim do intervalo" [(ngModel)]="funcionais.intervalo_fim" [ngModelOptions]="{ standalone: true }" /></div></div>
          <div><label [for]="id('rg')">RG/CIN nº</label>
            <input [id]="id('rg')" maxlength="30" placeholder="Ex.: 12.345.678-9" [(ngModel)]="funcionais.rg_cin" [ngModelOptions]="{ standalone: true }" /></div>
          <div><label [for]="id('rspv')">RS/PV nº</label>
            <input [id]="id('rspv')" maxlength="30" placeholder="Ex.: 1.234.567/8" [(ngModel)]="funcionais.rs_pv" [ngModelOptions]="{ standalone: true }" /></div>
        </div>
        @if (erroHorarios(); as erro) { <p class="texto-erro dica-formulario">{{ erro }}</p> }
        @if (botaoProprio()) {
          <div class="acoes-cartao">
          @if (c.funcionais.atualizado_por_nome) { <small class="dica-formulario">Atualizado por {{ c.funcionais.atualizado_por_nome }} em {{ c.funcionais.atualizado_em | date: 'dd/MM/yyyy HH:mm' }}</small> }
          <button type="button" class="acao-secundaria acao-pequena" [disabled]="!inicioValido() || !!erroHorarios()" (click)="salvar()">Salvar dados funcionais</button>
        </div>
        }

        @if (vigente(); as v) {
          <div class="cartao-periodo">
            <div><small>Exercício vigente ({{ v.exercicio }})</small><strong>{{ data(v.inicio) }} a {{ data(v.fim) }}</strong></div>
            <div><small>Creditados</small><strong>{{ v.dias_creditados }}</strong>@if (v.origem === 'ajuste_cgp') { <em>ajustado</em> }</div>
            <div><small>Agendados</small><strong>{{ v.usado }}</strong></div>
            <div class="destaque"><small>Disponíveis</small><strong>{{ v.disponivel }}</strong></div>
          </div>
          <div class="ajuste-periodo">
            <label [for]="id('ajuste')">Ajustar dias creditados do período vigente</label>
            <input [id]="id('ajuste')" type="number" min="0" max="365" [(ngModel)]="ajuste" [ngModelOptions]="{ standalone: true }" />
            @if (botaoProprio()) {
              <button type="button" class="acao-secundaria acao-pequena" [disabled]="ajuste === null || ajuste === v.dias_creditados" (click)="ajustar()">Ajustar</button>
            }
            <small class="dica-formulario">Ex.: férias já gozadas antes do sistema.</small>
          </div>
        }
        @if (c.funcionais.periodos.length > 1) {
          <details class="historico-periodos">
            <summary>Períodos anteriores</summary>
            <table class="tabela-gestao">
              <thead><tr><th>Exercício</th><th class="num">Creditados</th><th class="num">Usados</th><th class="num">Expirados</th></tr></thead>
              <tbody>
                @for (per of c.funcionais.periodos; track per.inicio) {
                  @if (!per.vigente) {
                    <tr><td>{{ per.exercicio }} · {{ data(per.inicio) }} a {{ data(per.fim) }}</td><td class="num">{{ per.dias_creditados }}</td><td class="num">{{ per.usado }}</td>
                      <td class="num">{{ per.dias_expirados ?? '—' }}</td></tr>
                  }
                }
              </tbody>
            </table>
          </details>
        }
      </div>
    }
  `,
})
export class DadosFuncionaisComponent {
  /** Usuário cujos dados funcionais são exibidos. */
  readonly usuarioId = input.required<number>();
  /** Cadastro já carregado por quem usa o componente (evita uma segunda consulta). */
  readonly cadastroInicial = input<CadastroRh | null>(null);
  readonly mostrarLinkValidacoes = input(true);
  /**
   * Botões próprios ("Salvar dados funcionais" e "Ajustar"). Na página do usuário ficam ocultos: o "Salvar usuário"
   * grava tudo junto, chamando `gravacao()`. Na tela Validações, onde não há outro botão, ficam visíveis.
   */
  readonly botaoProprio = input(true);
  readonly salvo = output<CadastroRh>();

  private readonly api = inject(RhApiService);
  protected readonly usuariosApi = inject(UsuariosApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly cadastro = signal<CadastroRh | null>(null);
  protected readonly inicio = signal('');
  protected readonly inicioValido = computed(() => inicioAquisitivoValido(this.inicio()));
  protected readonly vigente = computed(() => this.cadastro()?.funcionais.periodos.find((p) => p.vigente) ?? null);
  protected autorizador: OpcaoUsuario[] = [];
  protected substituto: OpcaoUsuario[] = [];
  protected ajuste: number | null = null;
  protected funcionais = vazio();

  /** Mesmas regras da API: horário e intervalo com início e fim; o intervalo termina depois de começar. */
  protected erroHorarios(): string | null {
    const f = this.funcionais;
    if (!f.horario_trabalho_inicio !== !f.horario_trabalho_fim) return 'Informe o início e o fim do horário de trabalho (ou nenhum dos dois).';
    if (f.horario_trabalho_inicio && f.horario_trabalho_inicio === f.horario_trabalho_fim) return 'O horário de trabalho precisa terminar em hora diferente do início.';
    if (!f.intervalo_inicio !== !f.intervalo_fim) return 'Informe o início e o fim do intervalo (ou nenhum dos dois).';
    if (f.intervalo_inicio && f.intervalo_fim && f.intervalo_fim <= f.intervalo_inicio) return 'O intervalo precisa terminar depois de começar.';
    if (f.jornada_semanal_horas !== null && (f.jornada_semanal_horas < 1 || f.jornada_semanal_horas > 80)) return 'A jornada vai de 1 a 80 horas semanais.';
    return null;
  }

  constructor() {
    // Recarrega quando muda o usuário (ou chega o cadastro já carregado); sem permissão (403), o bloco não aparece
    effect(() => {
      const id = this.usuarioId();
      const inicial = this.cadastroInicial();
      untracked(() => {
        if (inicial && inicial.usuario_id === id) {
          this.aplicar(inicial);
          return;
        }
        this.cadastro.set(null);
        this.api.cadastro(id).subscribe({ next: (c) => this.aplicar(c), error: () => this.cadastro.set(null) });
      });
    });
  }

  protected id(campo: string): string {
    return `rh-${campo}-${this.usuarioId()}`;
  }

  protected data(texto: string): string {
    return dataBr(texto);
  }

  /** Máscara dd/mm: só dígitos, com a barra depois do dia. */
  protected digitarInicio(valor: string): void {
    const digitos = (valor ?? '').replace(/\D/g, '').slice(0, 4);
    this.inicio.set(digitos.length > 2 ? `${digitos.slice(0, 2)}/${digitos.slice(2)}` : digitos);
  }

  private aplicar(c: CadastroRh): void {
    this.cadastro.set(c);
    const f = c.funcionais;
    const opcao = (id: number | null, nome: string | null): OpcaoUsuario[] => (id ? [{ id, nome_completo: nome ?? '', login: '', cargo: '', ativo: true }] : []);
    // Autorizador: o definido ou, na falta, a sugestão (o superior imediato em vigor)
    this.autorizador = f.autorizador_id ? opcao(f.autorizador_id, f.autorizador_nome) : opcao(f.autorizador_sugerido_id, c.perfil['gestor_id']);
    this.substituto = opcao(f.substituto_id, f.substituto_nome);
    this.inicio.set(f.inicio_periodo_aquisitivo ?? '');
    this.funcionais = {
      sem_superior: f.sem_superior, exercicio: f.exercicio ?? new Date().getFullYear(), saldo_lp_dias: f.saldo_lp_dias,
      jornada_semanal_horas: f.jornada_semanal_horas, regime_plantao: f.regime_plantao, horario_estudante: f.horario_estudante,
      horario_trabalho_inicio: f.horario_trabalho_inicio, horario_trabalho_fim: f.horario_trabalho_fim,
      intervalo_inicio: f.intervalo_inicio, intervalo_fim: f.intervalo_fim, rg_cin: f.rg_cin, rs_pv: f.rs_pv,
    };
    this.ajuste = f.periodos.find((p) => p.vigente)?.dias_creditados ?? null;
  }

  /** Há bloco carregado (o usuário é CGP ou SuperRoot)? Sem ele, não há o que gravar. */
  carregado(): boolean {
    return !!this.cadastro();
  }

  /** Motivo que impede gravar (para a página mostrar antes de salvar), ou null. */
  erroValidacao(): string | null {
    if (!this.cadastro()) return null;
    if (!this.inicioValido()) return 'Início do período aquisitivo: use dd/mm com uma data válida (ex.: 15/03).';
    return this.erroHorarios();
  }

  /**
   * Gravação para quem usa o bloco sem os botões próprios: dados funcionais e, se o campo foi alterado, o ajuste
   * dos dias do período vigente. Null quando não há o que gravar (bloco não carregado).
   */
  gravacao(): Observable<CadastroRh> | null {
    const c = this.cadastro();
    if (!c) return null;
    const ajuste = this.ajuste;
    const ajustar = ajuste !== null && ajuste !== (this.vigente()?.dias_creditados ?? null);
    return this.api.salvarFuncionais(c.usuario_id, this.dadosParaGravar()).pipe(
      switchMap((novo) => (ajustar ? this.api.ajustarPeriodo(c.usuario_id, ajuste) : of(novo))),
      tap((novo) => {
        this.aplicar(novo);
        this.salvo.emit(novo);
      }),
    );
  }

  private dadosParaGravar() {
    return {
      ...this.funcionais, inicio_periodo_aquisitivo: this.inicio().trim() || null,
      // Campo vazio (number/time) chega como null ou '': a API recebe null
      jornada_semanal_horas: this.funcionais.jornada_semanal_horas || null,
      horario_trabalho_inicio: this.funcionais.horario_trabalho_inicio || null, horario_trabalho_fim: this.funcionais.horario_trabalho_fim || null,
      intervalo_inicio: this.funcionais.intervalo_inicio || null, intervalo_fim: this.funcionais.intervalo_fim || null,
      rg_cin: this.funcionais.rg_cin?.trim() || null, rs_pv: this.funcionais.rs_pv?.trim() || null,
      autorizador_id: this.autorizador[0]?.id ?? null, substituto_id: this.substituto[0]?.id ?? null,
    };
  }

  protected salvar(): void {
    const c = this.cadastro();
    if (!c || !this.inicioValido()) return;
    this.dialogos.executar(this.api.salvarFuncionais(c.usuario_id, this.dadosParaGravar()), 'Salvando os dados funcionais…').subscribe({
      next: (novo) => {
        this.aplicar(novo);
        this.salvo.emit(novo);
        this.dialogos.avisar('Dados funcionais salvos', `Dados funcionais de ${novo.nome} atualizados.`);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar os dados funcionais'),
    });
  }

  protected ajustar(): void {
    const c = this.cadastro();
    if (!c || this.ajuste === null) return;
    this.dialogos.executar(this.api.ajustarPeriodo(c.usuario_id, this.ajuste), 'Ajustando o período…').subscribe({
      next: (novo) => {
        this.aplicar(novo);
        this.salvo.emit(novo);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível ajustar o período'),
    });
  }
}
