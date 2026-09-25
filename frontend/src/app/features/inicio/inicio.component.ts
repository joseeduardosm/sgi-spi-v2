import { Component, inject, input } from '@angular/core';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';

/** Página inicial autenticada. Ponto de entrada para os futuros módulos. */
@Component({
  selector: 'app-inicio',
  template: `
    <div class="cabecalho-pagina">
      <div>
        <p>Início</p>
        <h1>Olá, {{ autenticacao.usuario()?.nome_completo }}</h1>
        <small>Os módulos do Contratos SPI aparecerão na barra lateral, em "Módulos", à medida que forem disponibilizados.</small>
      </div>
    </div>
    @if (acesso() === 'negado') {
      <div class="alert alert-warning" role="status">
        Você não possui acesso ao módulo solicitado. Solicite a revisão da ACL a um administrador do sistema.
      </div>
    }
  `,
})
export class InicioComponent {
  protected readonly autenticacao = inject(AutenticacaoService);
  /** Parâmetro de consulta preenchido pelo guardaAcl ao negar acesso. */
  readonly acesso = input<string>();
}
