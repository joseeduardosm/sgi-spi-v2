// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir os campos do perfil institucional, reaproveitados em "Meu perfil" e no cadastro de usuários.

import { Component, input, model } from '@angular/core';
import { ReactiveFormsModule } from '@angular/forms';
import { Observable } from 'rxjs';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { FormularioPerfil } from './formulario-perfil';

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
        <input id="perfil-departamento" formControlName="departamento" />
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
export class CamposPerfilComponent {
  // O formulário vem de fora (a tela dona dele decide validações e envio); o gestor é de mão dupla
  readonly formulario = input.required<FormularioPerfil>();
  readonly gestor = model<OpcaoUsuario[]>([]);
  // Função de busca de usuários para o seletor de gestor
  readonly fonteGestor = input.required<(busca: string) => Observable<OpcaoUsuario[]>>();
  /** Exibe a marca "*" nos campos obrigatórios. */
  readonly marcarObrigatorios = input(true);

  /** Asterisco exibido ao lado dos rótulos obrigatórios. */
  get marca(): string {
    return this.marcarObrigatorios() ? '*' : '';
  }
}
