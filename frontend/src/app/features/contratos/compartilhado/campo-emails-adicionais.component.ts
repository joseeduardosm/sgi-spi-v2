/**
 * =============================================================================
 * ARQUIVO: campo-emails-adicionais.component.ts
 *
 * FINALIDADE:
 * Campo "Outros e-mails desta ocorrência" do diário de bordo. Serve para digitar
 * endereços de e-mail além da equipe e dos prepostos e para reaproveitar os já
 * usados antes no mesmo contrato.
 *
 * RESUMO TÉCNICO:
 * - `escolhidos` (model, mão dupla): lista dos e-mails que vão receber. O pai
 *   (aba Diário) lê esta lista e a envia à API em `emails_adicionais`.
 * - `salvos` (input): e-mails guardados no contrato (`DiarioContrato.emails_salvos`).
 *   Os que ainda não foram escolhidos aparecem como pílulas "+ e-mail".
 * - `removerSalvo` (output): avisa o pai que a pessoa quer tirar um e-mail da
 *   lista do contrato. Quem chama a API e confirma é o pai.
 * - O texto digitado vira ficha ao apertar Enter, vírgula ou "Adicionar". A
 *   validação usa o mesmo formato da API (`algo@dominio.ext`).
 *
 * FINALIDADE DE NEGÓCIO:
 * Algumas ocorrências precisam chegar a pessoas que não são prepostos (outro
 * fiscal, um responsável da obra, outro órgão). O usuário digita o e-mail uma
 * vez e, nas próximas ocorrências do mesmo contrato, só clica para incluir.
 *
 * CONTEXTO NO SISTEMA:
 * Usado em `detalhe/aba-diario.component.ts`, logo abaixo da caixa "Enviar por
 * e-mail" (`opcao-email.component.ts`). O backend guarda os e-mails em
 * `contratos_diario_emails_salvos` (ver `docs/endpoints/contratos-diario.md`).
 *
 * =============================================================================
 */

import { ChangeDetectionStrategy, Component, computed, input, model, output, signal } from '@angular/core';

import { EmailSalvoDiario } from './contratos.models';

/**
 * Formato aceito: "algo@dominio.ext", sem espaços. É a MESMA regra do backend
 * (`EMAIL_VALIDO` em `backend/app/schemas/contratos/diario.py`). Se mudar uma, mude a outra,
 * senão a tela aceita um e-mail que a API recusa (ou o contrário).
 */
export const EMAIL_VALIDO = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** Limite de e-mails adicionais por ocorrência (o mesmo `max_length` da API). */
export const MAXIMO_EMAILS_ADICIONAIS = 20;

@Component({
  selector: 'app-campo-emails-adicionais',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="campo-emails-adicionais">
      <label class="rotulo" [for]="idCampo">Outros e-mails desta ocorrência <small>(opcional, além da equipe e dos prepostos)</small></label>

      <!-- Fichas dos e-mails já escolhidos: o "×" tira o e-mail SÓ desta ocorrência -->
      @if (escolhidos().length) {
        <ul class="fichas-emails-adicionais" aria-label="E-mails escolhidos para esta ocorrência">
          @for (e of escolhidos(); track e) {
            <li><span class="texto-email">{{ e }}</span>
              <button type="button" class="botao-icone" [attr.aria-label]="'Tirar ' + e + ' desta ocorrência'" (click)="tirar(e)">×</button></li>
          }
        </ul>
      }

      <!-- Digitação: Enter, vírgula ou o botão transformam o texto em ficha -->
      <div class="linha-digitacao">
        <input [id]="idCampo" type="email" autocomplete="email" placeholder="nome@empresa.com.br"
               [value]="texto()" (input)="aoDigitar($any($event.target).value)" (keydown)="aoTeclar($event)"
               [attr.aria-invalid]="!!erro()" [attr.aria-describedby]="erro() ? idCampo + '-erro' : null" />
        <button type="button" class="acao-secundaria acao-pequena" (click)="adicionar()">Adicionar</button>
      </div>
      @if (erro()) { <small class="erro-campo" [id]="idCampo + '-erro'" role="alert">{{ erro() }}</small> }

      <!-- E-mails usados antes neste contrato: vêm DESMARCADOS; clicar inclui nesta ocorrência -->
      @if (disponiveis().length) {
        <p class="titulo-salvos">Usados antes neste contrato</p>
        <ul class="chips-filtro salvos" aria-label="E-mails usados antes neste contrato">
          @for (s of disponiveis(); track s.id) {
            <li>
              <button type="button" [attr.aria-label]="'Incluir ' + s.email + ' nesta ocorrência'" (click)="incluir(s.email)">+ {{ s.email }}</button>
              @if (podeRemover()) {
                <span class="botao-remover-salvo"><button type="button" class="botao-icone" [attr.aria-label]="'Remover ' + s.email + ' da lista do contrato'"
                  title="Remover da lista do contrato" (click)="removerSalvo.emit(s)">×</button></span>
              }
            </li>
          }
        </ul>
      }
    </div>
  `,
  styles: `
    :host { display: block; margin: 4px 0 12px; }
    .campo-emails-adicionais { max-width: 640px; }
    .rotulo { display: block; margin-bottom: 6px; color: var(--spi-rotulo); font-size: 13px; font-weight: 600; }
    .rotulo small { color: var(--spi-apagado); font-weight: 400; }
    /* Fichas com "×": mesmo visual de "Quem pode escolher este assunto" (Parâmetros dos Chamados) */
    .fichas-emails-adicionais { display: flex; flex-wrap: wrap; gap: var(--spi-espaco-8); margin: 0 0 var(--spi-espaco-8); padding: 0; list-style: none; }
    .fichas-emails-adicionais li { display: inline-flex; align-items: center; gap: 6px; padding: 4px 6px 4px 12px; border: 1px solid var(--spi-borda);
      border-radius: var(--spi-raio-pilula); background: var(--spi-superficie-alt); color: var(--spi-texto); font-size: 13px; }
    .texto-email { word-break: break-all; }
    /* Botão só com o "×": discreto, redondo, com anel de foco do sistema */
    .botao-icone { width: 24px; height: 24px; padding: 0; border: 0; border-radius: var(--spi-raio-pilula); background: transparent;
      color: var(--spi-apagado); font-size: 16px; line-height: 1; cursor: pointer; }
    .botao-icone:hover { background: var(--spi-superficie); color: var(--spi-perigo); }
    .botao-icone:focus-visible { outline: none; box-shadow: var(--spi-anel-foco); }
    .linha-digitacao { display: flex; align-items: center; gap: var(--spi-espaco-8); }
    .linha-digitacao input { flex: 1; min-width: 0; }
    .erro-campo { display: block; margin-top: 4px; color: var(--spi-perigo); font-size: 12px; }
    .titulo-salvos { margin: var(--spi-espaco-12) 0 6px; color: var(--spi-apagado); font-size: 12px; font-weight: 600; }
    /* O ".chips-filtro" global (Tarefas) põe padding e borda inferior de barra de filtros: aqui é uma lista dentro do formulário, então zera */
    .salvos { display: flex; flex-wrap: wrap; gap: var(--spi-espaco-8); margin: 0; padding: 0; border: 0; list-style: none; }
    .salvos li { display: inline-flex; align-items: center; gap: 2px; }
    .salvos li > button { word-break: break-all; }
    @media (max-width: 600px) { .linha-digitacao { flex-wrap: wrap; } .linha-digitacao input { flex-basis: 100%; } }
  `,
})
export class CampoEmailsAdicionaisComponent {
  /** E-mails escolhidos para esta ocorrência (mão dupla com o pai via `[(escolhidos)]`). */
  readonly escolhidos = model<string[]>([]);
  /** E-mails salvos no contrato (vêm da API em `DiarioContrato.emails_salvos`). */
  readonly salvos = input<EmailSalvoDiario[]>([]);
  /** Mostra o "×" que tira o e-mail da lista do contrato (só para quem pode editar o contrato). */
  readonly podeRemover = input(true);
  /** Pedido para tirar um e-mail da lista do contrato. O pai confirma e chama a API. */
  readonly removerSalvo = output<EmailSalvoDiario>();

  /** Texto que está sendo digitado (ainda não virou ficha). */
  protected readonly texto = signal('');
  /** Mensagem de erro do campo (e-mail inválido, limite atingido); `null` quando está tudo certo. */
  protected readonly erro = signal<string | null>(null);
  /** Id único do `<input>`, para o `<label for>` e o `aria-describedby` funcionarem mesmo com dois campos na tela. */
  protected readonly idCampo = `emails-adicionais-${Math.random().toString(36).slice(2, 8)}`;

  /** Salvos que ainda NÃO foram escolhidos: são os oferecidos como "+ e-mail". */
  protected readonly disponiveis = computed(() => {
    const ja = new Set(this.escolhidos());
    return this.salvos().filter((s) => !ja.has(s.email));
  });

  /** Guarda o que foi digitado. Se a pessoa colar "a@x.com, b@y.com", cada parte antes da vírgula vira ficha. */
  protected aoDigitar(valor: string): void {
    this.erro.set(null);
    if (valor.includes(',') || valor.includes(';')) {
      const partes = valor.split(/[,;]/);
      // A última parte pode estar incompleta (a pessoa ainda está digitando): fica no campo
      const resto = partes.pop() ?? '';
      for (const parte of partes) this.incluir(parte);
      this.texto.set(resto);
      return;
    }
    this.texto.set(valor);
  }

  /** Enter adiciona sem enviar o formulário inteiro; Backspace no campo vazio tira a última ficha (atalho comum em campos de pílulas). */
  protected aoTeclar(evento: KeyboardEvent): void {
    if (evento.key === 'Enter') {
      evento.preventDefault();
      this.adicionar();
    } else if (evento.key === 'Backspace' && !this.texto() && this.escolhidos().length) {
      this.tirar(this.escolhidos()[this.escolhidos().length - 1]);
    }
  }

  /** Botão "Adicionar" (ou Enter): transforma o texto do campo em ficha. */
  protected adicionar(): void {
    if (this.incluir(this.texto())) this.texto.set('');
  }

  /**
   * Inclui um e-mail na ocorrência. Devolve `true` se deu certo (ou se já estava incluído).
   * Regras: tira espaços, passa para minúsculas (a API guarda assim), valida o formato,
   * não repete e respeita o limite de 20.
   */
  incluir(bruto: string): boolean {
    const email = bruto.trim().toLowerCase();
    if (!email) return false;
    if (!EMAIL_VALIDO.test(email)) {
      this.erro.set(`E-mail inválido: ${email}`);
      return false;
    }
    if (this.escolhidos().includes(email)) return true;
    if (this.escolhidos().length >= MAXIMO_EMAILS_ADICIONAIS) {
      this.erro.set(`No máximo ${MAXIMO_EMAILS_ADICIONAIS} e-mails adicionais por ocorrência.`);
      return false;
    }
    this.erro.set(null);
    this.escolhidos.set([...this.escolhidos(), email]);
    return true;
  }

  /** Tira o e-mail só desta ocorrência (se estiver salvo no contrato, ele volta para "Usados antes"). */
  protected tirar(email: string): void {
    this.escolhidos.set(this.escolhidos().filter((e) => e !== email));
  }
}
