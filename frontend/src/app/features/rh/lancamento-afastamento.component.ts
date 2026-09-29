// Criado por José Eduardo Santana Martins
// Este arquivo serve para a CGP lançar férias ou licença-prêmio em nome do servidor (já aprovada ou gozada).

import { Component, inject, model, output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { UsuariosApiService } from '../usuarios/usuarios-api.service';
import { RhApiService } from './rh-api.service';
import { TipoAfastamento } from './rh.models';

/**
 * Lançamento pela CGP: férias ou licença-prêmio já combinadas ou gozadas fora do sistema, inclusive retroativas.
 * Sem antecedência, dia vedado ou mínimo de dias; o saldo pode ser ignorado (ex.: períodos anteriores ao sistema).
 */
@Component({
  selector: 'app-lancamento-afastamento',
  imports: [FormsModule, SeletorUsuariosComponent],
  host: { '(document:keydown.escape)': 'aberta.set(false)' },
  template: `
    @if (aberta()) {
      <div class="fundo-modal" role="presentation" (click)="aberta.set(false)"></div>
      <section class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-lancamento">
        <header>
          <div><span class="modal-sobretitulo">CGP</span><h2 id="titulo-lancamento">Lançar afastamento</h2></div>
          <button type="button" aria-label="Fechar" (click)="aberta.set(false)">×</button>
        </header>
        <form (ngSubmit)="lancar()">
          <p class="dica-formulario" style="margin-top: 0">Para férias ou licença-prêmio já combinadas ou gozadas fora do sistema. O lançamento
            já nasce aprovado (ou gozado), entra no saldo e na folha de ponto, e o servidor recebe e-mail.</p>
          <div class="grade-formulario">
            <div class="ocupa-duas"><label for="lanc-pessoa">Servidor *</label>
              <app-seletor-usuarios idCampo="lanc-pessoa" [multiplo]="false" [(selecionados)]="pessoa" [fonte]="usuariosApi.opcoesGestor"
                                    textoAjuda="Pesquisar servidor" /></div>
            <div><label for="lanc-tipo">Tipo</label>
              <select id="lanc-tipo" name="tipo" [(ngModel)]="tipo">
                <option value="ferias">Férias</option><option value="licenca_premio">Licença-prêmio</option>
              </select></div>
            <div><label for="lanc-situacao">Situação</label>
              <select id="lanc-situacao" name="situacao" [(ngModel)]="situacao">
                <option value="aprovado">Aprovado (a gozar ou em curso)</option><option value="gozado">Gozado (já terminou)</option>
              </select></div>
            <div><label for="lanc-inicio">Início *</label><input id="lanc-inicio" name="inicio" type="date" required [(ngModel)]="inicio" /></div>
            <div><label for="lanc-fim">Fim *</label><input id="lanc-fim" name="fim" type="date" required [(ngModel)]="fim" /></div>
            <div class="ocupa-duas"><label for="lanc-justificativa">Motivo *</label>
              <input id="lanc-justificativa" name="justificativa" maxlength="2000" required placeholder="Ex.: férias registradas na planilha da CGP"
                     [(ngModel)]="justificativa" /></div>
          </div>
          <div class="linha-caixas" style="margin-top: 0">
            <label><input type="checkbox" name="ignorar" [(ngModel)]="ignorarSaldo" /> Ignorar saldo (ex.: período anterior ao sistema)</label>
          </div>
          <footer>
            <button type="button" class="acao-secundaria" (click)="aberta.set(false)">Cancelar</button>
            <button type="submit" class="acao-primaria" [disabled]="!pessoa.length || !inicio || !fim || justificativa.trim().length < 3">Lançar</button>
          </footer>
        </form>
      </section>
    }
  `,
})
export class LancamentoAfastamentoComponent {
  readonly aberta = model(false);
  readonly lancado = output<void>();
  private readonly api = inject(RhApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly usuariosApi = inject(UsuariosApiService);
  protected pessoa: OpcaoUsuario[] = [];
  protected tipo: TipoAfastamento = 'ferias';
  protected situacao: 'aprovado' | 'gozado' = 'aprovado';
  protected inicio = '';
  protected fim = '';
  protected justificativa = '';
  protected ignorarSaldo = false;

  protected lancar(): void {
    const pessoa = this.pessoa[0];
    if (!pessoa) return;
    const dados = {
      usuario_id: pessoa.id, tipo: this.tipo, inicio: this.inicio, fim: this.fim, situacao: this.situacao,
      justificativa: this.justificativa.trim(), ignorar_saldo: this.ignorarSaldo,
    };
    this.dialogos.executar(this.api.lancar(dados), 'Lançando…').subscribe({
      next: () => {
        this.aberta.set(false);
        this.lancado.emit();
        this.dialogos.avisar('Afastamento lançado', `${pessoa.nome_completo}: lançamento registrado e e-mail enviado ao servidor.`);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível lançar'),
    });
  }
}
