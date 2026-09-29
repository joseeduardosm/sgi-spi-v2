// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela da CGP validar ou recusar as alterações de cadastro e preencher os dados funcionais.

import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DadosFuncionaisComponent } from './dados-funcionais.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { UsuariosApiService } from '../usuarios/usuarios-api.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { RhApiService } from './rh-api.service';
import { AlteracaoCadastral, CadastroRh, UsuarioPendente } from './rh.models';

/**
 * Validações de cadastro (só CGP): usuários com alterações pendentes; para cada um, atual × proposto com
 * Validar e Recusar (justificativa + correção), os dados funcionais e o histórico completo.
 */
@Component({
  selector: 'app-validacoes',
  imports: [FormsModule, DatePipe, CabecalhoRhComponent, SeletorUsuariosComponent, DadosFuncionaisComponent],
  templateUrl: './validacoes.component.html',
})
export class ValidacoesComponent implements OnInit {
  private readonly api = inject(RhApiService);
  protected readonly usuariosApi = inject(UsuariosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);

  protected readonly pendencias = signal<UsuarioPendente[] | null>(null);
  protected readonly cadastro = signal<CadastroRh | null>(null);
  protected readonly semPermissao = signal(false);
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
