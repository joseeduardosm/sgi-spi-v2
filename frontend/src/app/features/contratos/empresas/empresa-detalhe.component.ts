// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar o cadastro e o detalhe de uma empresa contratada e de seus prepostos.

import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { AcessoService } from '../../../core/acesso/acesso.service';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { DetalheEmpresa, GravacaoEmpresa, GravacaoPreposto, Preposto } from '../compartilhado/contratos.models';
import { formatarCnpj, formatarCpf } from '../compartilhado/rotulos';

// Preposto em branco, usado para limpar o formulário
const PREPOSTO_VAZIO: GravacaoPreposto = { cpf: '', nome: '', telefone: '', email: '', cargo: '', ativo: true };

/** Tela 9: cadastro/detalhe da empresa e seus prepostos. */
@Component({
  selector: 'app-empresa-detalhe',
  imports: [FormsModule, RouterLink, CabecalhoModuloComponent],
  // Qualquer clique fora fecha o menu de ações aberto
  host: { '(document:click)': 'menuAberto.set(null)' },
  templateUrl: './empresa-detalhe.component.html',
})
export class EmpresaDetalheComponent implements OnInit {
  /** Parâmetro de rota (ausente em /empresas/nova). */
  readonly empresaId = input<string>();

  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  protected readonly acesso = inject(AcessoService);

  // Estado: empresa carregada, campos da empresa e do preposto em edição
  protected readonly empresa = signal<DetalheEmpresa | null>(null);
  protected readonly carregando = signal(false);
  protected readonly menuAberto = signal<string | null>(null);
  protected dados: GravacaoEmpresa = { cnpj: '', razao_social: '', nome_fantasia: '', endereco: '', ativa: true };
  protected preposto: GravacaoPreposto = { ...PREPOSTO_VAZIO };
  protected prepostoEmEdicao: string | null = null;
  protected readonly cpf = formatarCpf;

  /** Com id na rota, carrega a empresa; sem id, a tela abre vazia para cadastro. */
  ngOnInit(): void {
    const id = this.empresaId();
    if (id) {
      this.carregando.set(true);
      this.api.empresa(id).subscribe({
        next: (e) => this.aplicar(e),
        error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível carregar a empresa'),
      });
    }
  }

  /** Guarda a empresa e preenche o formulário (CNPJ com máscara). */
  private aplicar(empresa: DetalheEmpresa): void {
    this.empresa.set(empresa);
    this.dados = { cnpj: formatarCnpj(empresa.cnpj), razao_social: empresa.razao_social, nome_fantasia: empresa.nome_fantasia, endereco: empresa.endereco, ativa: empresa.ativa };
    this.carregando.set(false);
  }

  /** Cadastra ou altera a empresa; no cadastro, troca a URL para a da empresa criada. */
  protected salvar(): void {
    const id = this.empresa()?.id;
    this.api.salvarEmpresa({ ...this.dados }, id).subscribe({
      next: (e) => {
        this.aplicar(e);
        if (!id) void this.roteador.navigate(['/contratos/empresas', e.id], { replaceUrl: true });
      },
      error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível salvar a empresa'),
    });
  }

  /** Pede confirmação e exclui a empresa. */
  protected async excluir(): Promise<void> {
    const e = this.empresa();
    if (!e) return;
    const ok = await this.dialogos.confirmar({ titulo: `Excluir ${e.razao_social}?`, mensagem: 'A empresa e seus prepostos serão removidos.', rotuloConfirmar: 'Excluir empresa', segundos: 3 });
    if (ok) this.api.excluirEmpresa(e.id).subscribe({ next: () => void this.roteador.navigate(['/contratos/empresas']), error: (erro) => this.dialogos.mostrarErro(erro) });
  }

  /** Carrega um preposto no formulário para edição. */
  protected editarPreposto(evento: Event, p: Preposto): void {
    evento.stopPropagation();
    this.menuAberto.set(null);
    this.prepostoEmEdicao = p.id;
    this.preposto = { cpf: formatarCpf(p.cpf), nome: p.nome, telefone: p.telefone, email: p.email, cargo: p.cargo, ativo: p.ativo };
  }

  /** Limpa o formulário do preposto (volta ao modo "novo"). */
  protected limparPreposto(): void {
    this.prepostoEmEdicao = null;
    this.preposto = { ...PREPOSTO_VAZIO };
  }

  /** Cadastra ou altera o preposto; a API devolve a empresa atualizada. */
  protected salvarPreposto(): void {
    const e = this.empresa();
    if (!e) return;
    this.api.salvarPreposto(e.id, { ...this.preposto }, this.prepostoEmEdicao ?? undefined).subscribe({
      next: (novo) => {
        this.aplicar(novo);
        this.limparPreposto();
      },
      error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível salvar o preposto'),
    });
  }

  /** Pede confirmação e exclui o preposto, recarregando a empresa. */
  protected async excluirPreposto(evento: Event, p: Preposto): Promise<void> {
    evento.stopPropagation();
    this.menuAberto.set(null);
    const e = this.empresa();
    if (!e) return;
    const ok = await this.dialogos.confirmar({ titulo: `Excluir o preposto ${p.nome}?`, mensagem: 'O contato será removido da empresa.', rotuloConfirmar: 'Excluir' });
    if (ok) this.api.excluirPreposto(e.id, p.id).subscribe({ next: () => this.api.empresa(e.id).subscribe((x) => this.aplicar(x)), error: (erro) => this.dialogos.mostrarErro(erro) });
  }

  /** Abre ou fecha o menu de ações de um preposto. */
  protected alternarMenu(evento: Event, id: string): void {
    evento.stopPropagation();
    this.menuAberto.set(this.menuAberto() === id ? null : id);
  }
}
