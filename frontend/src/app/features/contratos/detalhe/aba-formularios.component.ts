import { DatePipe } from '@angular/common';
import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { DefinicaoFormulario, Formulario, Modelo } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { EditorFormularioComponent, definicaoVazia } from './editor-formulario.component';

/** Aba "Formulários de avaliação": versões do formulário usado na etapa 2 (opcional). */
@Component({
  selector: 'app-aba-formularios',
  imports: [FormsModule, DatePipe, EditorFormularioComponent],
  template: `
    <section class="cartao-dados" aria-labelledby="titulo-formularios">
      <header>
        <div><h2 id="titulo-formularios">Formulários de avaliação</h2><small>Opcional. Sem formulário ativo, a competência vai da medição direto para a nota fiscal.</small></div>
        @if (podeEditar()) { <button type="button" class="acao-primaria" (click)="abrir()"><span>+</span> Gerar formulário</button> }
      </header>
      <div class="corpo">
        @for (f of formularios(); track f.id) {
          <article class="indicador" style="margin-bottom: 12px">
            <div style="display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap">
              <strong style="font-size: 14px">v{{ f.versao }} · {{ f.nome }}</strong>
              <span class="selo-situacao" [class.inativo]="!f.ativo">{{ f.ativo ? 'Ativo' : 'Inativo' }}</span>
            </div>
            <small>{{ f.definicao.escala.length }} notas · {{ f.definicao.grupos.length }} grupos · {{ f.definicao.faixas.length }} faixas ·
              criado por {{ f.criado_por_nome }} em {{ f.criado_em | date: 'dd/MM/yyyy HH:mm' }}</small>
            @if (podeEditar()) {
              <div class="acoes-cartao esquerda">
                @if (!f.ativo) {
                  <button type="button" class="acao-primaria acao-pequena" (click)="ativar(f)">Ativar</button>
                  <button type="button" class="acao-secundaria acao-pequena" (click)="abrir(f)">Editar</button>
                }
                <button type="button" class="acao-secundaria acao-pequena" (click)="duplicar(f)">Duplicar</button>
              </div>
            }
          </article>
        } @empty {
          <p class="estado-vazio">Nenhum formulário cadastrado.</p>
        }
      </div>
    </section>

    @if (aberto()) {
      <app-editor-formulario [titulo]="emEdicao ? 'Editar formulário v' + emEdicao.versao : 'Gerar formulário'" [nomeInicial]="emEdicao?.nome ?? ''"
                             [definicaoInicial]="emEdicao?.definicao ?? definicaoVazia()" [modelos]="modelos()" rotuloSalvar="Salvar versão inativa"
                             (salvar)="salvar($event)" (fechar)="aberto.set(false)" />
    }
  `,
})
export class AbaFormulariosComponent implements OnInit {
  readonly contratoId = input.required<string>();
  readonly podeEditar = input(false);

  private readonly api = inject(ExecucaoApiService);
  private readonly contratos = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly formularios = signal<Formulario[]>([]);
  protected readonly modelos = signal<Modelo[]>([]);
  protected readonly aberto = signal(false);
  protected readonly definicaoVazia = definicaoVazia;
  protected emEdicao: Formulario | null = null;

  ngOnInit(): void {
    this.api.formularios(this.contratoId()).subscribe({ next: (f) => this.formularios.set(f), error: (e) => this.dialogos.mostrarErro(e) });
    this.contratos.modelos('formulario').subscribe({ next: (m) => this.modelos.set(m), error: () => this.modelos.set([]) });
  }

  protected abrir(formulario?: Formulario): void {
    this.emEdicao = formulario ?? null;
    this.aberto.set(true);
  }

  protected salvar(evento: { nome: string; definicao: DefinicaoFormulario }): void {
    this.api.salvarFormulario(this.contratoId(), evento, this.emEdicao?.id).subscribe({
      next: (f) => {
        this.formularios.set(f);
        this.aberto.set(false);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar o formulário'),
    });
  }

  protected async ativar(formulario: Formulario): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Ativar o formulário v${formulario.versao}?`,
      mensagem: 'Ele passa a valer para as competências geradas daqui em diante e para as que ainda estão na medição.',
      rotuloConfirmar: 'Ativar',
      segundos: 3,
    });
    if (ok) this.api.acaoFormulario(this.contratoId(), formulario.id, 'ativar').subscribe({ next: (f) => this.formularios.set(f), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected duplicar(formulario: Formulario): void {
    this.api.acaoFormulario(this.contratoId(), formulario.id, 'duplicar').subscribe({ next: (f) => this.formularios.set(f), error: (e) => this.dialogos.mostrarErro(e) });
  }
}
