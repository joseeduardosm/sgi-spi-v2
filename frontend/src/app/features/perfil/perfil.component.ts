import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { CamposPerfilComponent } from '../usuarios/campos-perfil.component';
import { criarFormularioPerfil, dadosDoFormularioPerfil, gestorComoOpcao, preencherFormularioPerfil } from '../usuarios/formulario-perfil';
import { UsuariosApiService } from '../usuarios/usuarios-api.service';
import { PerfilLeitura, ROTULOS_PERFIL } from '../usuarios/usuarios.models';

/** Atualização e revalidação do próprio perfil institucional. */
@Component({
  selector: 'app-perfil',
  imports: [ReactiveFormsModule, CamposPerfilComponent, DatePipe],
  templateUrl: './perfil.component.html',
})
export class PerfilComponent implements OnInit {
  protected readonly autenticacao = inject(AutenticacaoService);
  protected readonly api = inject(UsuariosApiService);
  private readonly roteador = inject(Router);

  protected readonly formulario = criarFormularioPerfil(inject(NonNullableFormBuilder), true);
  protected readonly gestor = signal<OpcaoUsuario[]>([]);
  protected readonly perfil = signal<PerfilLeitura | null>(null);
  protected readonly carregando = signal(true);
  protected readonly salvando = signal(false);
  protected readonly aviso = signal<{ texto: string; erro: boolean } | null>(null);

  protected rotulosPendentes(): string {
    return (this.autenticacao.usuario()?.campos_pendentes ?? []).map((c) => ROTULOS_PERFIL[c] ?? c).join(', ');
  }

  ngOnInit(): void {
    this.api.meuPerfil().subscribe({
      next: (perfil) => {
        this.perfil.set(perfil);
        preencherFormularioPerfil(this.formulario, perfil);
        this.gestor.set(gestorComoOpcao(perfil));
        this.carregando.set(false);
      },
      error: () => {
        this.carregando.set(false);
        this.aviso.set({ texto: 'Não foi possível carregar seu cadastro.', erro: true });
      },
    });
  }

  protected salvar(): void {
    if (this.formulario.invalid) {
      this.formulario.markAllAsTouched();
      this.aviso.set({ texto: 'Preencha todos os campos obrigatórios (*) com valores válidos.', erro: true });
      return;
    }
    const estavaRestrito = !!this.autenticacao.usuario()?.perfil_restrito;
    this.salvando.set(true);
    this.aviso.set(null);
    this.api.revisarMeuPerfil(dadosDoFormularioPerfil(this.formulario, this.gestor()[0]?.id ?? null)).subscribe({
      next: (usuario) => {
        this.salvando.set(false);
        this.autenticacao.definirUsuario(usuario);
        this.aviso.set({ texto: 'Cadastro confirmado. A próxima revalidação será em 30 dias.', erro: false });
        this.api.meuPerfil().subscribe((p) => this.perfil.set(p));
        if (estavaRestrito && !usuario.perfil_restrito) void this.roteador.navigateByUrl('/');
      },
      error: (erro: unknown) => {
        this.salvando.set(false);
        const detalhe = erro instanceof HttpErrorResponse ? erro.error?.detalhe : null;
        this.aviso.set({ texto: typeof detalhe === 'string' ? detalhe : 'Não foi possível salvar.', erro: true });
      },
    });
  }
}
