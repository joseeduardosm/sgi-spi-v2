// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de servidores SMTP: cadastro, teste de conexão, envio de teste e exclusão.

import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { SmtpApiService } from './smtp-api.service';
import { GravacaoServidorSmtp, ResultadoSmtp, SegurancaSmtp, ServidorSmtp } from './smtp.models';

/** Porta usual de cada segurança (sugerida ao trocar a segurança no formulário). */
const PORTA_PADRAO: Record<SegurancaSmtp, number> = { starttls: 587, ssl: 465, nenhuma: 25 };

/** Administração de servidores SMTP (restrita ao SuperRoot). */
@Component({
  selector: 'app-servidores-smtp',
  imports: [ReactiveFormsModule, FormsModule, DatePipe],
  templateUrl: './servidores-smtp.component.html',
  host: { '(document:keydown.escape)': 'fecharJanelas()' },
})
export class ServidoresSmtpComponent implements OnInit {
  private readonly api = inject(SmtpApiService);

  protected readonly rotulosSeguranca: Record<SegurancaSmtp, string> = { starttls: 'STARTTLS', ssl: 'SSL', nenhuma: 'Sem cifra' };

  // Lista, carregamento e o servidor com ação em andamento (desabilita os botões daquela linha)
  protected readonly servidores = signal<ServidorSmtp[]>([]);
  protected readonly carregando = signal(true);
  protected readonly idOcupado = signal<string | null>(null);
  protected readonly aviso = signal<{ texto: string; erro: boolean } | null>(null);

  // Janela de cadastro e o resultado do teste feito dentro dela
  protected readonly formularioAberto = signal(false);
  protected readonly emEdicao = signal<ServidorSmtp | null>(null);
  protected readonly salvando = signal(false);
  protected readonly erroFormulario = signal<string | null>(null);
  protected readonly testeFormulario = signal<ResultadoSmtp | null>(null);

  // Janela do e-mail de teste
  protected readonly envioAberto = signal<ServidorSmtp | null>(null);
  protected readonly resultadoEnvio = signal<ResultadoSmtp | null>(null);
  protected destinatario = '';

  protected readonly formulario = inject(NonNullableFormBuilder).group({
    nome: ['', [Validators.required, Validators.maxLength(100)]],
    servidor: ['', [Validators.required, Validators.maxLength(255)]],
    porta: [587, [Validators.required, Validators.min(1), Validators.max(65535)]],
    seguranca: ['starttls' as SegurancaSmtp],
    usuario: ['', [Validators.maxLength(254)]],
    senha: [''],
    remetente_email: ['', [Validators.required, Validators.email, Validators.maxLength(254)]],
    remetente_nome: ['', [Validators.maxLength(150)]],
    responder_para: ['', [Validators.email, Validators.maxLength(254)]],
    tempo_limite_segundos: [20, [Validators.required, Validators.min(3), Validators.max(120)]],
    ativo: [false],
  });

  ngOnInit(): void {
    this.carregar();
  }

  /** Carrega a lista de servidores. */
  protected carregar(): void {
    this.carregando.set(true);
    this.api.listar().subscribe({
      next: (itens) => {
        this.servidores.set(itens);
        this.carregando.set(false);
      },
      error: (erro) => {
        this.carregando.set(false);
        this.mostrarAviso(this.mensagem(erro, 'Não foi possível carregar os servidores.'), true);
      },
    });
  }

  /** Abre o cadastro; o primeiro servidor já vem ativo e com os valores usuais do Microsoft 365. */
  protected abrirFormulario(servidor?: ServidorSmtp): void {
    this.emEdicao.set(servidor ?? null);
    this.erroFormulario.set(null);
    this.testeFormulario.set(null);
    this.formulario.reset({
      nome: servidor?.nome ?? '',
      servidor: servidor?.servidor ?? 'smtp.office365.com',
      porta: servidor?.porta ?? 587,
      seguranca: servidor?.seguranca ?? 'starttls',
      usuario: servidor?.usuario ?? '',
      senha: '',
      remetente_email: servidor?.remetente_email ?? '',
      remetente_nome: servidor?.remetente_nome ?? '',
      responder_para: servidor?.responder_para ?? '',
      tempo_limite_segundos: servidor?.tempo_limite_segundos ?? 20,
      ativo: servidor?.ativo ?? this.servidores().length === 0,
    });
    this.formularioAberto.set(true);
  }

  /** Ao trocar a segurança, sugere a porta usual dela. */
  protected aoTrocarSeguranca(): void {
    this.formulario.controls.porta.setValue(PORTA_PADRAO[this.formulario.controls.seguranca.value]);
  }

  /** Com usuário e remetente vazios, o remetente segue o usuário (caso comum do Microsoft 365). */
  protected aoSairDoUsuario(): void {
    const { usuario, remetente_email } = this.formulario.getRawValue();
    if (usuario.includes('@') && !remetente_email) this.formulario.controls.remetente_email.setValue(usuario);
  }

  /** Fecha as janelas, a menos que haja operação em andamento. */
  protected fecharJanelas(): void {
    if (this.salvando()) return;
    this.formularioAberto.set(false);
    this.envioAberto.set(null);
  }

  /** Valida e grava o servidor. */
  protected salvar(): void {
    const erro = this.validar();
    if (erro) {
      this.erroFormulario.set(erro);
      return;
    }
    const dados = this.dadosDoFormulario();
    const atual = this.emEdicao();
    this.salvando.set(true);
    this.erroFormulario.set(null);
    (atual ? this.api.alterar(atual.id, dados) : this.api.criar(dados)).subscribe({
      next: (salvo) => {
        this.salvando.set(false);
        this.formularioAberto.set(false);
        this.mostrarAviso(`Servidor "${salvo.nome}" salvo${salvo.ativo ? ' e ativado' : ''}.`, false);
        this.carregar();
      },
      error: (e) => {
        this.salvando.set(false);
        this.erroFormulario.set(this.mensagem(e, 'Não foi possível salvar o servidor.'));
      },
    });
  }

  /** Testa os dados do formulário. Na edição sem senha nova, testa o servidor salvo (senha gravada). */
  protected testarFormulario(): void {
    const erro = this.validar();
    if (erro) {
      this.erroFormulario.set(erro);
      return;
    }
    const atual = this.emEdicao();
    const dados = this.dadosDoFormulario();
    this.salvando.set(true);
    this.erroFormulario.set(null);
    this.testeFormulario.set(null);
    const usarSalvo = atual && dados.usuario && !dados.senha && atual.possui_senha;
    (usarSalvo ? this.api.testar(atual.id) : this.api.testarSemSalvar(dados)).subscribe({
      next: (resultado) => {
        this.salvando.set(false);
        this.testeFormulario.set(resultado);
      },
      error: (e) => {
        this.salvando.set(false);
        this.erroFormulario.set(this.mensagem(e, 'Não foi possível testar a conexão.'));
      },
    });
  }

  /** Testa a conexão de um servidor salvo, a partir da lista. */
  protected testar(servidor: ServidorSmtp): void {
    this.idOcupado.set(servidor.id);
    this.api.testar(servidor.id).subscribe({
      next: (r) => {
        this.idOcupado.set(null);
        this.mostrarAviso(r.sucesso ? `${servidor.nome}: ${r.mensagem} (${r.latencia_ms} ms)` : `${servidor.nome}: ${r.mensagem}`, !r.sucesso);
        this.carregar();
      },
      error: (e) => {
        this.idOcupado.set(null);
        this.mostrarAviso(this.mensagem(e, 'Não foi possível testar a conexão.'), true);
      },
    });
  }

  /** Abre a janela do e-mail de teste. */
  protected abrirEnvio(servidor: ServidorSmtp): void {
    this.resultadoEnvio.set(null);
    this.destinatario = servidor.ultimo_envio_para ?? '';
    this.envioAberto.set(servidor);
  }

  /** Envia o e-mail de teste e mostra o resultado na própria janela. */
  protected enviarTeste(): void {
    const servidor = this.envioAberto();
    if (!servidor || !this.destinatario.trim()) return;
    this.salvando.set(true);
    this.resultadoEnvio.set(null);
    this.api.enviarTeste(servidor.id, this.destinatario.trim()).subscribe({
      next: (r) => {
        this.salvando.set(false);
        this.resultadoEnvio.set(r);
        this.carregar();
      },
      error: (e) => {
        this.salvando.set(false);
        this.resultadoEnvio.set({ sucesso: false, latencia_ms: 0, mensagem: this.mensagem(e, 'Não foi possível enviar.'), id_mensagem: null });
      },
    });
  }

  /** Pede confirmação e exclui o servidor. */
  protected excluir(servidor: ServidorSmtp): void {
    if (!confirm(`Excluir o servidor "${servidor.nome}"?${servidor.ativo ? ' Ele está ativo: o sistema deixará de enviar e-mails.' : ''}`)) return;
    this.idOcupado.set(servidor.id);
    this.api.excluir(servidor.id).subscribe({
      next: () => {
        this.idOcupado.set(null);
        this.mostrarAviso(`Servidor "${servidor.nome}" excluído.`, false);
        this.carregar();
      },
      error: (e) => {
        this.idOcupado.set(null);
        this.mostrarAviso(this.mensagem(e, 'Não foi possível excluir o servidor.'), true);
      },
    });
  }

  /** Mesmas regras da API, para avisar antes de enviar. */
  private validar(): string | null {
    if (this.formulario.invalid) {
      this.formulario.markAllAsTouched();
      return 'Confira os campos: nome, servidor, porta, remetente (e-mail válido) e tempo limite (3 a 120 s).';
    }
    const v = this.formulario.getRawValue();
    if (/:\/\/|:|\s/.test(v.servidor.trim())) return 'Informe só o nome ou IP do servidor; a porta vai no campo próprio.';
    if (v.seguranca === 'ssl' && Number(v.porta) === 587) return 'A porta 587 usa STARTTLS; para SSL direto use a porta 465.';
    if (v.seguranca === 'starttls' && Number(v.porta) === 465) return 'A porta 465 usa SSL direto; para STARTTLS use a porta 587.';
    // Com usuário, precisa de senha: digitada agora ou (na edição) já gravada
    const atual = this.emEdicao();
    if (v.usuario.trim() && !v.senha && !atual?.possui_senha) return 'Informe a senha da conta de autenticação.';
    return null;
  }

  /** Lê o formulário no formato da API: porta e tempo como número, senha vazia como null. */
  private dadosDoFormulario(): GravacaoServidorSmtp {
    const v = this.formulario.getRawValue();
    return {
      ...v,
      nome: v.nome.trim(),
      servidor: v.servidor.trim(),
      usuario: v.usuario.trim(),
      remetente_email: v.remetente_email.trim(),
      responder_para: v.responder_para.trim(),
      porta: Number(v.porta),
      tempo_limite_segundos: Number(v.tempo_limite_segundos),
      senha: v.senha || null,
    };
  }

  /** Mostra uma mensagem de sucesso ou de erro no topo da tela. */
  private mostrarAviso(texto: string, erro: boolean): void {
    this.aviso.set({ texto, erro });
  }

  /** Mensagem da API, se houver, ou a padrão da operação. */
  private mensagem(erro: unknown, padrao: string): string {
    if (erro instanceof HttpErrorResponse) {
      if (typeof erro.error?.detalhe === 'string') return erro.error.detalhe;
      if (Array.isArray(erro.error?.erros) && erro.error.erros.length) {
        return erro.error.erros.map((e: { mensagem?: string }) => e.mensagem).filter(Boolean).join(' ');
      }
      if (erro.status === 0 || erro.status >= 502) return 'Serviço indisponível. Tente novamente em instantes.';
    }
    return padrao;
  }
}
