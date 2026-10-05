// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela da CGP validar ou recusar as alterações de cadastro e preencher os dados funcionais.

import { DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DadosFuncionaisComponent } from './dados-funcionais.component';
import { ImportacaoFuncionaisComponent } from './importacao-funcionais.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { UsuariosApiService } from '../usuarios/usuarios-api.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { RhApiService } from './rh-api.service';
import { AlteracaoCadastral, CadastroRh, UsuarioPendente } from './rh.models';
import { LinkificarPipe } from '../../shared/utilitarios/linkificar.pipe';

/**
 * Validações de cadastro (só CGP): usuários com alterações pendentes; para cada um, atual × proposto com
 * Validar e Recusar (justificativa + correção), os dados funcionais e o histórico completo.
 */
@Component({
  selector: 'app-validacoes',
  imports: [LinkificarPipe, FormsModule, DatePipe, CabecalhoRhComponent, SeletorUsuariosComponent, DadosFuncionaisComponent, ImportacaoFuncionaisComponent],
  templateUrl: './validacoes.component.html',
})
export class ValidacoesComponent implements OnInit {
  private readonly api = inject(RhApiService);
  protected readonly usuariosApi = inject(UsuariosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);

  protected readonly pendencias = signal<UsuarioPendente[] | null>(null);
  // Validação em lote: filtro por campo e usuários marcados na lista
  protected readonly filtroCampo = signal('');
  protected readonly marcados = signal<number[]>([]);
  /** Campos com alteração pendente (para o filtro), com a quantidade. */
  protected readonly campos = computed(() => {
    const contagem = new Map<string, { rotulo: string; total: number }>();
    for (const p of this.pendencias() ?? []) {
      for (const a of p.alteracoes) contagem.set(a.campo, { rotulo: a.rotulo, total: (contagem.get(a.campo)?.total ?? 0) + 1 });
    }
    return [...contagem.entries()].map(([campo, v]) => ({ campo, ...v })).sort((x, y) => x.rotulo.localeCompare(y.rotulo));
  });
  /** Usuários com alguma alteração no campo escolhido (ou todos). */
  protected readonly pendenciasFiltradas = computed(() => {
    const campo = this.filtroCampo();
    return (this.pendencias() ?? []).filter((p) => !campo || p.alteracoes.some((a) => a.campo === campo));
  });
  /** Alterações que "Validar selecionadas" vai validar: as dos usuários marcados, só do campo filtrado (se houver). */
  protected readonly idsSelecionados = computed(() => {
    const campo = this.filtroCampo();
    const marcados = new Set(this.marcados());
    return this.pendenciasFiltradas()
      .filter((p) => marcados.has(p.usuario_id))
      .flatMap((p) => p.alteracoes.filter((a) => !campo || a.campo === campo).map((a) => a.id));
  });
  protected readonly cadastro = signal<CadastroRh | null>(null);
  protected readonly semPermissao = signal(false);
  protected readonly importando = signal(false);
  // Recusa em andamento
  protected readonly recusando = signal<AlteracaoCadastral | null>(null);
  protected justificativa = '';
  protected correcao = '';
  // Busca de um usuário qualquer (para ajustar dados funcionais sem pendências)
  protected buscaUsuario: OpcaoUsuario[] = [];

  ngOnInit(): void {
    this.carregarPendencias();
    const id = Number(this.rota.snapshot.queryParamMap.get('usuario'));
    if (id) this.abrir(id);
  }

  protected carregarPendencias(): void {
    this.api.pendencias().subscribe({
      next: (p) => this.pendencias.set(p),
      error: (e) => {
        if (e?.status === 403) this.semPermissao.set(true);
        else this.dialogos.mostrarErro(e, 'Não foi possível carregar as pendências');
      },
    });
  }

  protected abrir(usuarioId: number): void {
    this.api.cadastro(usuarioId).subscribe({
      next: (c) => this.aplicar(c),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível abrir o cadastro'),
    });
  }

  protected abrirBusca(): void {
    const u = this.buscaUsuario[0];
    if (u) this.abrir(u.id);
  }

  private aplicar(c: CadastroRh): void {
    this.cadastro.set(c);
  }

  protected validar(a: AlteracaoCadastral): void {
    this.dialogos.executar(this.api.validar(a.id), 'Validando…').subscribe({
      next: (c) => {
        this.aplicar(c);
        this.carregarPendencias();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível validar'),
    });
  }

  protected marcar(usuarioId: number, marcado: boolean): void {
    this.marcados.update((ids) => (marcado ? [...ids, usuarioId] : ids.filter((x) => x !== usuarioId)));
  }

  protected marcarTodos(marcado: boolean): void {
    this.marcados.set(marcado ? this.pendenciasFiltradas().map((p) => p.usuario_id) : []);
  }

  protected async validarSelecionadas(): Promise<void> {
    const ids = this.idsSelecionados();
    if (!ids.length) return;
    const campo = this.campos().find((c) => c.campo === this.filtroCampo())?.rotulo;
    const ok = await this.dialogos.confirmar({
      titulo: 'Validar em lote?',
      mensagem: `${ids.length} alteração(ões) de ${this.marcados().filter((id) => this.pendenciasFiltradas().some((p) => p.usuario_id === id)).length} usuário(s)` +
        (campo ? `, só do campo "${campo}"` : '') + ' passam a valer.',
      rotuloConfirmar: 'Validar',
    });
    if (ok) this.executarLote(ids);
  }

  /** "Validar todas deste usuário": todas as pendências do cadastro aberto. */
  protected validarTodasDoUsuario(c: CadastroRh): void {
    this.executarLote(c.pendentes.map((a) => a.id), c.usuario_id);
  }

  private executarLote(ids: string[], reabrir?: number): void {
    this.dialogos.executar(this.api.validarLote(ids), 'Validando…').subscribe({
      next: (r) => {
        this.marcados.set([]);
        this.carregarPendencias();
        const aberto = reabrir ?? this.cadastro()?.usuario_id;
        if (aberto) this.abrir(aberto);
        if (r.erros.length) {
          this.dialogos.avisar(`${r.validadas} validada(s), ${r.erros.length} não validada(s)`, r.erros.map((e) => e.detalhe).join('\n'));
        }
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível validar'),
    });
  }

  protected iniciarRecusa(a: AlteracaoCadastral): void {
    this.recusando.set(a);
    this.justificativa = '';
    this.correcao = a.valor_anterior ?? '';
  }

  protected recusar(): void {
    const a = this.recusando();
    if (!a || !this.justificativa.trim()) return;
    this.dialogos.executar(this.api.recusar(a.id, this.justificativa.trim(), this.correcao.trim() || null), 'Registrando a correção…').subscribe({
      next: (c) => {
        this.recusando.set(null);
        this.aplicar(c);
        this.carregarPendencias();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível recusar'),
    });
  }

  protected rotulosStatus: Record<string, string> = { pendente: 'Pendente', validada: 'Validada', recusada: 'Corrigida', substituida: 'Substituída' };
}
