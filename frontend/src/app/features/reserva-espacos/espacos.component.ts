// Criado por José Eduardo Santana Martins
// Este arquivo serve para o fiscal cadastrar, alterar, inativar e excluir os espaços reserváveis.

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoReservasComponent } from './cabecalho-reservas.component';
import { EstadoReservasService } from './estado-reservas.service';
import { ReservasApiService } from './reservas-api.service';
import { Espaco } from './reservas.models';

const VAZIO: Omit<Espaco, 'id'> = { nome: '', localizacao: '', cor: '#0b5cad', capacidade: null, equipamentos: '', descricao: '', ativo: true };

@Component({
  selector: 'app-espacos-reservas',
  imports: [FormsModule, CabecalhoReservasComponent],
  template: `
    <app-cabecalho-reservas titulo="Espaços" descricao="Salas, anfiteatro e outros espaços que podem ser reservados." />
    <section class="painel-gestao protocolo reservas">
      <div class="barra-protocolo"><span class="espacador"></span><button type="button" class="acao-primaria" (click)="novo()">Novo espaço</button></div>
      @if (form(); as f) {
        <form class="grade-formulario cartao-dados form-espaco" (ngSubmit)="salvar()">
          <div><label for="es-nome">Nome</label><input id="es-nome" name="nome" required maxlength="120" [(ngModel)]="f.nome" /></div>
          <div><label for="es-loc">Localização</label><input id="es-loc" name="loc" maxlength="200" [(ngModel)]="f.localizacao" /></div>
          <div><label for="es-cor">Cor na agenda</label><input id="es-cor" name="cor" type="color" [(ngModel)]="f.cor" /></div>
          <div><label for="es-cap">Capacidade (lugares)</label><input id="es-cap" name="cap" type="number" min="1" [(ngModel)]="f.capacidade" /></div>
          <div class="ocupa-duas"><label for="es-eq">Equipamentos</label><input id="es-eq" name="eq" maxlength="2000" placeholder="Projetor, TV, videoconferência…" [(ngModel)]="f.equipamentos" /></div>
          <div class="ocupa-duas"><label class="linha-caixa"><input type="checkbox" name="ativo" [(ngModel)]="f.ativo" /> Ativo (aceita reservas)</label></div>
          <div class="ocupa-duas acoes-formulario">
            <button type="submit" class="acao-primaria" [disabled]="!f.nome.trim()">Salvar</button>
            <button type="button" class="acao-secundaria" (click)="form.set(null)">Cancelar</button>
          </div>
        </form>
      }
      <div class="tabela-gestao-envoltorio">
        <table class="tabela-gestao">
          <thead><tr><th>Espaço</th><th>Localização</th><th>Capacidade</th><th>Situação</th><th></th></tr></thead>
          <tbody>
            @for (e of estado.espacos(); track e.id) {
              <tr>
                <td><i class="ponto-cor" [style.background]="e.cor"></i><strong>{{ e.nome }}</strong>@if (e.equipamentos) { <small> · {{ e.equipamentos }}</small> }</td>
                <td>{{ e.localizacao || '—' }}</td><td>{{ e.capacidade ?? '—' }}</td>
                <td><span [class]="'selo-reserva ' + (e.ativo ? 'DEFERIDA' : 'CANCELADA')">{{ e.ativo ? 'Ativo' : 'Inativo' }}</span></td>
                <td class="acoes-linha">
                  <button type="button" class="acao-secundaria acao-pequena" (click)="editar(e)">Editar</button>
                  <button type="button" class="acao-recusar acao-pequena" (click)="excluir(e)">Excluir</button>
                </td>
              </tr>
            } @empty { <tr><td colspan="5" class="estado-vazio">Nenhum espaço cadastrado.</td></tr> }
          </tbody>
        </table>
      </div>
    </section>
  `,
})
export class EspacosReservasComponent implements OnInit {
  private readonly api = inject(ReservasApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(EstadoReservasService);

  protected readonly form = signal<(Omit<Espaco, 'id'> & { id?: number }) | null>(null);

  ngOnInit(): void {
    this.estado.carregar().subscribe();
  }

  protected novo(): void {
    this.form.set({ ...VAZIO });
  }

  protected editar(e: Espaco): void {
    this.form.set({ ...e });
  }

  protected salvar(): void {
    const { id, ...dados } = this.form()!;
    this.api.salvarEspaco(dados, id).subscribe({
      next: () => { this.form.set(null); this.estado.carregar().subscribe(); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar o espaço'),
    });
  }

  protected async excluir(e: Espaco): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Excluir este espaço?', mensagem: `"${e.nome}" será excluído. Se já teve reservas, ele apenas será inativado e o histórico é preservado.`, rotuloConfirmar: 'Excluir', segundos: 3, perigo: true,
    });
    if (!ok) return;
    this.api.excluirEspaco(e.id).subscribe({
      next: (r) => { if (r.resultado === 'inativado') this.dialogos.avisar('Espaço inativado', 'O espaço tem reservas e foi apenas inativado.'); this.estado.carregar().subscribe(); },
      error: (er) => this.dialogos.mostrarErro(er, 'Não foi possível excluir o espaço'),
    });
  }
}
