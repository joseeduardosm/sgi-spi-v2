import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { UsuariosApiService } from '../usuarios/usuarios-api.service';
import { Setor, SetoresApiService } from './setores-api.service';

/** Setores institucionais e grupos sistêmicos, usados como grupos de acesso na ACL. */
@Component({
  selector: 'app-setores',
  imports: [FormsModule, ReactiveFormsModule, SeletorUsuariosComponent],
  templateUrl: './setores.component.html',
  host: { '(document:keydown.escape)': 'fecharFormulario()' },
})
export class SetoresComponent implements OnInit {
  protected readonly autenticacao = inject(AutenticacaoService);
  private readonly api = inject(SetoresApiService);
  protected readonly usuarios = inject(UsuariosApiService);

  protected readonly ehAdministrador = computed(() => this.autenticacao.possuiPapel('SuperRoot'));
  protected busca = '';
  private readonly termo = signal('');
  protected readonly setores = signal<Setor[]>([]);
  protected readonly filtrados = computed(() => {
    const termo = this.termo().toLowerCase();
    return termo
      ? this.setores().filter((s) => `${s.nome} ${s.setor_pai_nome ?? ''} ${s.lider_nome ?? ''}`.toLowerCase().includes(termo))
      : this.setores();
  });
  protected readonly carregando = signal(true);
  protected readonly aviso = signal<{ texto: string; erro: boolean } | null>(null);

  protected readonly formularioAberto = signal(false);
  protected readonly emEdicao = signal<Setor | null>(null);
  protected readonly salvando = signal(false);
  protected readonly erroFormulario = signal<string | null>(null);
  protected readonly lider = signal<OpcaoUsuario[]>([]);
  protected readonly membros = signal<OpcaoUsuario[]>([]);
  protected readonly formulario = inject(NonNullableFormBuilder).group({
    nome: ['', [Validators.required, Validators.maxLength(150)]],
    setor_pai_id: [0],
    sistemico: [false],
    ativo: [true],
  });

  /** Setores que podem ser pai do setor em edição (exclui ele mesmo). */
  protected readonly opcoesPai = computed(() => this.setores().filter((s) => s.id !== this.emEdicao()?.id));

  ngOnInit(): void {
    this.carregar();
  }

  protected aoPesquisar(valor: string): void {
    this.termo.set(valor.trim());
  }

  protected carregar(): void {
    this.carregando.set(true);
    this.api.listar().subscribe({
      next: (itens) => {
        this.setores.set(itens);
        this.carregando.set(false);
      },
      error: (erro) => {
        this.carregando.set(false);
        this.aviso.set({ texto: this.mensagem(erro, 'Não foi possível carregar os setores.'), erro: true });
      },
    });
  }

  protected abrirFormulario(setor?: Setor): void {
    this.emEdicao.set(setor ?? null);
    this.erroFormulario.set(null);
    this.formulario.reset({ nome: setor?.nome ?? '', setor_pai_id: setor?.setor_pai_id ?? 0, sistemico: setor?.sistemico ?? false, ativo: setor?.ativo ?? true });
    this.lider.set(setor?.lider_id ? [{ id: setor.lider_id, nome_completo: setor.lider_nome ?? '', login: '', cargo: '', ativo: true }] : []);
    this.membros.set([]);
    this.formularioAberto.set(true);
    if (setor) this.api.consultar(setor.id).subscribe((detalhe) => this.membros.set(detalhe.membros));
  }

  protected fecharFormulario(): void {
    if (!this.salvando()) this.formularioAberto.set(false);
  }

  protected salvar(): void {
    if (this.formulario.invalid) {
      this.formulario.markAllAsTouched();
      this.erroFormulario.set('Informe o nome do setor.');
      return;
    }
    const valores = this.formulario.getRawValue();
    const dados = {
      nome: valores.nome.trim(),
      setor_pai_id: Number(valores.setor_pai_id) || null,
      lider_id: this.lider()[0]?.id ?? null,
      sistemico: valores.sistemico,
      ativo: valores.ativo,
      membros_ids: this.membros().map((m) => m.id),
    };
    const atual = this.emEdicao();
    this.salvando.set(true);
    this.erroFormulario.set(null);
    (atual ? this.api.alterar(atual.id, dados) : this.api.criar(dados)).subscribe({
      next: (setor) => {
        this.salvando.set(false);
        this.formularioAberto.set(false);
        this.aviso.set({ texto: `Setor "${setor.nome}" salvo com ${setor.total_membros} membro(s).`, erro: false });
        this.carregar();
      },
      error: (erro) => {
        this.salvando.set(false);
        this.erroFormulario.set(this.mensagem(erro, 'Não foi possível salvar o setor.'));
      },
    });
  }

  protected excluir(setor: Setor): void {
    if (!confirm(`Excluir o setor "${setor.nome}"?`)) return;
    this.api.excluir(setor.id).subscribe({
      next: () => {
        this.aviso.set({ texto: `Setor "${setor.nome}" excluído.`, erro: false });
        this.carregar();
      },
      error: (erro) => this.aviso.set({ texto: this.mensagem(erro, 'Não foi possível excluir o setor.'), erro: true }),
    });
  }

  private mensagem(erro: unknown, padrao: string): string {
    if (erro instanceof HttpErrorResponse && typeof erro.error?.detalhe === 'string') return erro.error.detalhe;
    return padrao;
  }
}
