// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a página "Meu perfil", onde o usuário atualiza e revalida o próprio cadastro.

import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { FotoPerfilComponent } from '../diretorio/foto-perfil.component';
import { CamposPerfilComponent } from '../usuarios/campos-perfil.component';
import { criarFormularioPerfil, dadosDoFormularioPerfil, gestorComoOpcao, preencherFormularioPerfil } from '../usuarios/formulario-perfil';
import { UsuariosApiService } from '../usuarios/usuarios-api.service';
import { PerfilLeitura, ROTULOS_PERFIL } from '../usuarios/usuarios.models';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';

/** Atualização e revalidação do próprio perfil institucional. */
@Component({
  selector: 'app-perfil',
  imports: [ReactiveFormsModule, CamposPerfilComponent, FotoPerfilComponent, DatePipe, TrilhaComponent],
  templateUrl: './perfil.component.html',
})
export class PerfilComponent implements OnInit {
  protected readonly autenticacao = inject(AutenticacaoService);
  protected readonly api = inject(UsuariosApiService);
  private readonly roteador = inject(Router);

  // Formulário do perfil (com os campos obrigatórios exigidos) e estado da tela
  protected readonly formulario = criarFormularioPerfil(inject(NonNullableFormBuilder), true);
  protected readonly gestor = signal<OpcaoUsuario[]>([]);
  protected readonly perfil = signal<PerfilLeitura | null>(null);
  protected readonly carregando = signal(true);
  protected readonly salvando = signal(false);
  protected readonly aviso = signal<{ texto: string; erro: boolean } | null>(null);
  // Modal da confirmação mensal: aparece quando a revisão do mês ainda não foi feita
  protected readonly modalMensal = signal(!!inject(AutenticacaoService).usuario()?.revisao_obrigatoria);
  protected readonly mesAtual = new Date().toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' });
  protected readonly haPendencias = computed(() => Object.values(this.perfil()?.situacao_campos ?? {}).some((s) => s.pendente));

  /** Nomes legíveis dos campos que ainda faltam preencher (vindos da sessão). */
  protected rotulosPendentes(): string {
    return (this.autenticacao.usuario()?.campos_pendentes ?? []).map((c) => ROTULOS_PERFIL[c] ?? c).join(', ');
  }

  /** Ao abrir a tela, carrega o perfil atual e preenche o formulário. */
  ngOnInit(): void {
    this.api.meuPerfil().subscribe({
      next: (perfil) => {
        this.perfil.set(perfil);
        // Campos com alteração pendente mostram o valor proposto: confirmar de novo mantém a proposta
        const propostos: Record<string, string> = {};
        for (const [campo, situacao] of Object.entries(perfil.situacao_campos ?? {})) {
          if (situacao.pendente && campo !== 'gestor_id') propostos[campo] = situacao.valor_proposto ?? '';
        }
        preencherFormularioPerfil(this.formulario, { ...perfil, ...propostos });
        const gestorPendente = perfil.situacao_campos?.['gestor_id'];
        this.gestor.set(gestorPendente?.pendente && gestorPendente.valor_proposto
          ? [{ id: Number(gestorPendente.valor_proposto), nome_completo: gestorPendente.valor_proposto_rotulo ?? '', login: '', cargo: '', ativo: true }]
          : gestorComoOpcao(perfil));
        this.carregando.set(false);
      },
      error: () => {
        this.carregando.set(false);
        this.aviso.set({ texto: 'Não foi possível carregar seu cadastro.', erro: true });
      },
    });
  }

  /** Grava e revalida o perfil; se era isso que restringia o acesso, libera o portal e volta ao início. */
  protected salvar(): void {
    if (this.formulario.invalid) {
      this.formulario.markAllAsTouched();
      this.modalMensal.set(false);
      this.aviso.set({ texto: 'Preencha todos os campos obrigatórios (*) com valores válidos.', erro: true });
      return;
    }
    if ((this.perfil()?.superior_obrigatorio ?? true) && !this.gestor().length) {
      this.modalMensal.set(false);
      this.aviso.set({ texto: 'Informe o seu superior imediato.', erro: true });
      return;
    }
    const estavaRestrito = !!this.autenticacao.usuario()?.perfil_restrito;
    this.salvando.set(true);
    this.aviso.set(null);
    // O gestor vem do seletor de usuários (no máximo um)
    this.api.revisarMeuPerfil(dadosDoFormularioPerfil(this.formulario, this.gestor()[0]?.id ?? null)).subscribe({
      next: (usuario) => {
        this.salvando.set(false);
        // Atualiza a sessão com o novo usuário (perfil_restrito recalculado pela API)
        this.autenticacao.definirUsuario(usuario);
        this.modalMensal.set(false);
        this.aviso.set({ texto: 'Cadastro confirmado neste mês. Alterações seguem para validação da CGP.', erro: false });
        this.api.meuPerfil().subscribe((p) => this.perfil.set(p));
        if (estavaRestrito && !usuario.perfil_restrito) void this.roteador.navigateByUrl('/');
      },
      error: (erro: unknown) => {
        this.salvando.set(false);
        const detalhe = erro instanceof HttpErrorResponse ? erro.error?.detalhe : null;
        this.modalMensal.set(false);
        this.aviso.set({ texto: typeof detalhe === 'string' ? detalhe : 'Não foi possível salvar.', erro: true });
      },
    });
  }
}
