// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir os campos do perfil institucional, reaproveitados em "Meu perfil" e no cadastro de usuários.

import { Component, computed, DestroyRef, inject, input, model, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ReactiveFormsModule } from '@angular/forms';
import { Observable, startWith } from 'rxjs';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { FormularioPerfil } from './formulario-perfil';
import { UsuariosApiService } from './usuarios-api.service';
import { OpcaoDepartamento } from './usuarios.models';

/** Campos do perfil institucional (grade de 2 colunas), usados em "Meu perfil" e no cadastro de usuários. */
@Component({
  selector: 'app-campos-perfil',
  imports: [ReactiveFormsModule, SeletorUsuariosComponent],
  template: `
    <div class="grade-formulario" [formGroup]="formulario()">
      <div class="ocupa-duas">
        <label for="perfil-nome_completo">Nome completo {{ marca }}</label>
        <input id="perfil-nome_completo" formControlName="nome_completo" autocomplete="name" />
      </div>
      <div>
        <label for="perfil-email">E-mail {{ marca }}</label>
        <input id="perfil-email" type="email" formControlName="email" autocomplete="email" />
      </div>
      <div>
        <label for="perfil-cargo">Cargo {{ marca }}</label>
        <input id="perfil-cargo" formControlName="cargo" />
      </div>
      <div>
        <label for="perfil-ramal">Ramal {{ marca }}</label>
        <input id="perfil-ramal" formControlName="ramal" inputmode="numeric" />
      </div>
      <div>
        <label for="perfil-celular">Celular</label>
        <input id="perfil-celular" formControlName="celular" inputmode="tel" autocomplete="tel" />
      </div>
      <div class="ocupa-duas">
        <label for="perfil-departamento">Departamento {{ marca }}</label>
        <select id="perfil-departamento" formControlName="departamento">
          <option value="">Selecione o departamento</option>
          @if (valorForaDaLista(); as atual) { <option [value]="atual">{{ atual }} (não cadastrado em Setores)</option> }
          @for (d of departamentos(); track d.id) {
            <option [value]="d.nome">{{ recuo(d.nivel) }}{{ d.nome }}</option>
          }
        </select>
        @if (carregouDepartamentos() && !departamentos().length) {
          <small class="dica-formulario">Nenhum setor cadastrado ainda. Cadastre os departamentos em Setores.</small>
        }
      </div>
      <div>
        <label for="perfil-andar">Andar {{ marca }}</label>
        <input id="perfil-andar" formControlName="andar" />
      </div>
      <div>
        <label for="perfil-predio">Prédio {{ marca }}</label>
        <input id="perfil-predio" formControlName="predio" />
      </div>
      <div>
        <label for="perfil-data_nascimento">Data de nascimento</label>
        <input id="perfil-data_nascimento" type="date" formControlName="data_nascimento" />
      </div>
      <div>
        <label for="perfil-gestor">Gestor imediato</label>
        <app-seletor-usuarios idCampo="perfil-gestor" [multiplo]="false" [(selecionados)]="gestor" [fonte]="fonteGestor()"
                              textoAjuda="Pesquisar gestor" />
      </div>
    </div>
  `,
})
export class CamposPerfilComponent implements OnInit {
  // O formulário vem de fora (a tela dona dele decide validações e envio); o gestor é de mão dupla
  readonly formulario = input.required<FormularioPerfil>();
  readonly gestor = model<OpcaoUsuario[]>([]);
  // Função de busca de usuários para o seletor de gestor
  readonly fonteGestor = input.required<(busca: string) => Observable<OpcaoUsuario[]>>();
  /** Exibe a marca "*" nos campos obrigatórios. */
  readonly marcarObrigatorios = input(true);

  private readonly api = inject(UsuariosApiService);
  private readonly destruir = inject(DestroyRef);
  // Departamentos = setores ativos e institucionais cadastrados em "Setores"
  protected readonly departamentos = signal<OpcaoDepartamento[]>([]);
  protected readonly carregouDepartamentos = signal(false);
  private readonly valorDepartamento = signal('');

  /** Valor atual que não está em Setores (ex.: vindo do AD): continua visível e selecionado. */
  protected readonly valorForaDaLista = computed(() => {
    const atual = this.valorDepartamento();
    return atual && this.carregouDepartamentos() && !this.departamentos().some((d) => d.nome === atual) ? atual : null;
  });

  ngOnInit(): void {
    const controle = this.formulario().controls.departamento;
    controle.valueChanges.pipe(startWith(controle.value), takeUntilDestroyed(this.destruir)).subscribe((valor) => this.valorDepartamento.set(valor ?? ''));
    this.api.opcoesDepartamento().subscribe({
      next: (opcoes) => {
        this.departamentos.set(opcoes);
        this.carregouDepartamentos.set(true);
      },
      error: () => this.carregouDepartamentos.set(true),
    });
  }

  /** Recuo visual da hierarquia no combobox (espaços não separáveis). */
  protected recuo(nivel: number): string {
    return '\u00A0\u00A0\u00A0'.repeat(nivel);
  }

  /** Asterisco exibido ao lado dos rótulos obrigatórios. */
  get marca(): string {
    return this.marcarObrigatorios() ? '*' : '';
  }
}
