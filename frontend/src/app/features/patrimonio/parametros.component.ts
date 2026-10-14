// Criado por José Eduardo Santana Martins
// Este arquivo serve para os parâmetros do Patrimônio: grupos de material (vida útil e residual da depreciação) e o valor da UFESP.
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { Grupo, PrefixoChapa } from './patrimonio.models';

@Component({
  selector: 'app-parametros-patrimonio',
  imports: [FormsModule, CabecalhoPatrimonioComponent],
  template: `
    <app-cabecalho-patrimonio titulo="Parâmetros" descricao="Grupos de material, vida útil e residual da depreciação, o valor da UFESP e os prefixos das chapas." />
    <section class="painel-gestao patrimonio">
      <h3 class="pat-subtitulo">UFESP</h3>
      <div class="pat-linha-campo">
        <input name="ufesp" inputmode="decimal" aria-label="Valor da UFESP em reais" [(ngModel)]="ufesp" />
        <button type="button" class="acao-primaria" (click)="salvarUfesp()">Salvar</button>
      </div>
      <small class="dica">Um bem de valor abaixo de 45 UFESP e vida útil menor que dois anos não é patrimoniável (aviso no cadastro).</small>

      <h3 class="pat-subtitulo">Prefixos das chapas</h3>
      <p class="pat-dica">O prefixo vem antes do número da chapa (ex.: SPI000231). O padrão já vem selecionado no cadastro; no cadastro em lote, o que a pessoa escolher permanece até ela trocar. Números com menos de 6 dígitos são completados com zeros.</p>
      <ul class="pat-prefixos">
        @for (p of prefixos(); track p.id) {
          <li [class.inativo]="!p.ativo">
            <strong>{{ p.codigo }}</strong>
            @if (p.padrao) { <span class="pat-selo-prefixo">padrão</span> }
            @if (!p.ativo) { <span class="pat-selo-prefixo inativo">inativo</span> }
            <span class="pat-acoes-prefixo">
              @if (!p.padrao && p.ativo) { <button type="button" class="acao-secundaria acao-pequena" (click)="tornarPadrao(p)">Tornar padrão</button> }
              @if (!p.padrao) { <button type="button" class="acao-secundaria acao-pequena" (click)="alternarAtivo(p)">{{ p.ativo ? 'Inativar' : 'Ativar' }}</button> }
              @if (!p.padrao) { <button type="button" class="acao-recusar acao-pequena" (click)="excluirPrefixo(p)">Excluir</button> }
            </span>
          </li>
        } @empty { <li class="estado-vazio">Nenhum prefixo cadastrado.</li> }
      </ul>
      <div class="pat-linha-campo">
        <input name="novo-prefixo" maxlength="20" aria-label="Novo prefixo" placeholder="Novo prefixo (ex.: DERSA)" [(ngModel)]="novoPrefixo" (keydown.enter)="criarPrefixo()" />
        <button type="button" class="acao-primaria" [disabled]="!novoPrefixo.trim()" (click)="criarPrefixo()">Adicionar prefixo</button>
      </div>

      <h3 class="pat-subtitulo">Grupos de material</h3>
      <p class="pat-dica">A tabela oficial de vida útil por grupo ainda será obtida: até lá, ela é editável aqui. Bens de terceiros e culturais não depreciam.</p>
      <ul class="pat-lista-itens">
        @for (g of grupos(); track g.id) {
          <li class="pat-grupo">
            <div><strong>{{ g.codigo }}</strong> <span>{{ g.nome }}</span></div>
            <div class="pat-linha-campo">
              <label>Vida útil (meses)<input type="number" min="1" [name]="'v' + g.id" [(ngModel)]="g.vida_util_meses" /></label>
              <label>Residual (%)<input inputmode="decimal" [name]="'r' + g.id" [(ngModel)]="g.residual_percentual" /></label>
              <label class="pat-marca"><input type="checkbox" [name]="'d' + g.id" [(ngModel)]="g.deprecia" /> Deprecia</label>
              <button type="button" class="acao-secundaria acao-pequena" (click)="salvar(g)">Salvar</button>
              <button type="button" class="acao-recusar acao-pequena" (click)="excluir(g)">Excluir</button>
            </div>
          </li>
        } @empty { <li class="estado-vazio">Nenhum grupo cadastrado.</li> }
      </ul>

      <h3 class="pat-subtitulo">Novo grupo</h3>
      <div class="grade-formulario">
        <div><label for="g-codigo">Código</label><input id="g-codigo" name="codigo" maxlength="40" [(ngModel)]="novo.codigo" /></div>
        <div><label for="g-nome">Nome</label><input id="g-nome" name="nome" maxlength="200" [(ngModel)]="novo.nome" /></div>
        <div><label for="g-vida">Vida útil (meses)</label><input id="g-vida" name="vida" type="number" min="1" [(ngModel)]="novo.vida" /></div>
        <div><label for="g-residual">Residual (%)</label><input id="g-residual" name="residual" inputmode="decimal" [(ngModel)]="novo.residual" /></div>
      </div>
      <div class="pat-barra-inferior"><button type="button" class="acao-primaria" [disabled]="!novo.codigo.trim() || !novo.nome.trim()" (click)="criar()">Criar grupo</button></div>
    </section>
  `,
})
export class ParametrosPatrimonioComponent implements OnInit {
  private readonly api = inject(PatrimonioApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly estado = inject(PatrimonioEstadoService);
  protected readonly grupos = signal<Grupo[]>([]);
  protected readonly prefixos = signal<PrefixoChapa[]>([]);
  protected novoPrefixo = '';
  protected ufesp = '';
  protected novo = { codigo: '', nome: '', vida: null as number | null, residual: '10' };

  ngOnInit(): void {
    this.api.parametros().subscribe((p) => (this.ufesp = p.ufesp));
    this.carregar();
  }

  private carregar(): void {
    this.api.grupos(true).subscribe((g) => { this.grupos.set(g); void this.estado.carregar(true); });
    this.api.prefixos(true).subscribe((p) => this.prefixos.set(p));
  }

  protected salvarUfesp(): void {
    this.api.salvarParametros(this.ufesp.trim().replace(',', '.')).subscribe({ next: (p) => (this.ufesp = p.ufesp), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar a UFESP') });
  }

  protected salvar(g: Grupo): void {
    this.api.atualizarGrupo(g.id, { vida_util_meses: g.vida_util_meses, residual_percentual: String(g.residual_percentual).replace(',', '.'), deprecia: g.deprecia }).subscribe({
      next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar o grupo'),
    });
  }

  protected criar(): void {
    this.api.criarGrupo({ codigo: this.novo.codigo.trim(), nome: this.novo.nome.trim(), vida_util_meses: this.novo.vida, residual_percentual: this.novo.residual.replace(',', '.') }).subscribe({
      next: () => { this.novo = { codigo: '', nome: '', vida: null, residual: '10' }; this.carregar(); }, error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar o grupo'),
    });
  }

  protected async excluir(g: Grupo): Promise<void> {
    if (await this.dialogos.confirmar({ titulo: `Excluir o grupo ${g.codigo}?`, mensagem: 'Grupo com bens só pode ser inativado.', rotuloConfirmar: 'Excluir', segundos: 2 })) {
      this.api.excluirGrupo(g.id).subscribe({ next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir') });
    }
  }

  protected criarPrefixo(): void {
    if (!this.novoPrefixo.trim()) return;
    this.api.criarPrefixo(this.novoPrefixo.trim()).subscribe({
      next: () => { this.novoPrefixo = ''; this.carregar(); }, error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar o prefixo'),
    });
  }

  protected tornarPadrao(p: PrefixoChapa): void {
    this.api.atualizarPrefixo(p.id, { padrao: true }).subscribe({ next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível trocar o padrão') });
  }

  protected alternarAtivo(p: PrefixoChapa): void {
    this.api.atualizarPrefixo(p.id, { ativo: !p.ativo }).subscribe({ next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível alterar o prefixo') });
  }

  protected async excluirPrefixo(p: PrefixoChapa): Promise<void> {
    if (await this.dialogos.confirmar({ titulo: `Excluir o prefixo ${p.codigo}?`, mensagem: 'Prefixo com bens só pode ser inativado.', rotuloConfirmar: 'Excluir', segundos: 2 })) {
      this.api.excluirPrefixo(p.id).subscribe({ next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir') });
    }
  }
}
