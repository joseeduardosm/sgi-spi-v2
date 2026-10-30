// Criado por José Eduardo Santana Martins
// Este arquivo serve para quem tem controle total em Contratos ajustar os cortes de alertas, prazos, regras e limites do módulo.

import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { ParametrosContratos, ValoresParametrosContratos } from '../compartilhado/contratos.models';
import { ParametrosContratosService } from '../compartilhado/parametros-contratos.service';

/** Campos de um cartão: rótulo, dica e limites (os mesmos da API; a validação de verdade é a do servidor). */
interface CampoParametro {
  nome: keyof ValoresParametrosContratos;
  rotulo: string;
  ajuda: string;
  tipo?: 'data' | 'decimal' | 'texto';
  min?: number;
  max?: number;
}

interface GrupoParametros {
  id: string;
  titulo: string;
  subtitulo: string;
  campos: CampoParametro[];
}

const GRUPOS: GrupoParametros[] = [
  {
    id: 'alertas',
    titulo: 'Alertas e cortes',
    subtitulo: 'Quando uma competência, um pagamento ou um prazo passa a ser cobrado e com que gravidade aparece nos painéis e no calendário.',
    campos: [
      { nome: 'corte_alertas_a_partir_de', rotulo: 'Corte de pendências e alertas', tipo: 'data', ajuda: 'Competências que terminam antes desta data não geram pendências, alertas, avisos de atraso nem o e-mail de pagamento. Vale o maior entre ela e o "Desconsiderar alertas a partir de" do contrato. Antecipar a data reabre pendências antigas.' },
      { nome: 'corte_marcadores_a_partir_de', rotulo: 'Corte dos marcadores da carteira', tipo: 'data', ajuda: 'Competências que começam antes desta data não aparecem como marcadores na carteira de contratos.' },
      { nome: 'dias_pagamento_vencendo', rotulo: 'Pagamento vencendo (dias)', min: 0, max: 365, ajuda: 'Pagamento que vence em até este número de dias vira risco médio.' },
      { nome: 'dias_atraso', rotulo: 'Medição atrasada (dias)', min: 1, max: 365, ajuda: 'Risco médio depois deste prazo; alto depois do dobro. Também é o prazo do aviso de atraso por e-mail.' },
      { nome: 'dias_vigencia_a_vencer', rotulo: 'Contrato "a vencer" (dias)', min: 1, max: 730, ajuda: 'Fim da vigência em até este número de dias: o contrato fica "a vencer" e a faixa vira alerta.' },
      { nome: 'dias_vigencia_atencao', rotulo: 'Faixa de atenção das vigências (dias)', min: 1, max: 1460, ajuda: 'Usada na linha do tempo de vigências; precisa ser maior que a de "a vencer".' },
      { nome: 'dias_sem_prorrogacao_alto', rotulo: 'A vencer sem prorrogação: risco alto (dias)', min: 1, max: 730, ajuda: 'Com até este número de dias para o fim e sem prorrogação iniciada, o risco é alto (acima, médio).' },
      { nome: 'dias_documento_alto', rotulo: 'Documento a vencer: alto (dias)', min: 0, max: 730, ajuda: 'Validade em até este número de dias: severidade alta no calendário.' },
      { nome: 'dias_documento_medio', rotulo: 'Documento a vencer: médio (dias)', min: 0, max: 730, ajuda: 'Deve ser maior ou igual ao alto. Também marca "vence em breve" nos documentos finais.' },
      { nome: 'dias_fim_vigencia_alto', rotulo: 'Fim da vigência: alto (dias)', min: 0, max: 730, ajuda: 'Fim da vigência no calendário com severidade alta.' },
      { nome: 'dias_fim_vigencia_medio', rotulo: 'Fim da vigência: médio (dias)', min: 0, max: 730, ajuda: 'Deve ser maior ou igual ao alto.' },
    ],
  },
  {
    id: 'regras',
    titulo: 'Regras do contrato',
    subtitulo: 'Limites e prazos que valem na criação do contrato, nos aditamentos e nas medições.',
    campos: [
      { nome: 'vigencia_maxima_padrao_meses', rotulo: 'Vigência máxima padrão (meses)', min: 1, max: 600, ajuda: 'Valor que o formulário de novo contrato já traz preenchido.' },
      { nome: 'maximo_meses_vigencia_retroativa', rotulo: 'Vigência retroativa: máximo (meses)', min: 1, max: 600, ajuda: 'Maior prazo aceito ao cadastrar uma vigência retroativa.' },
      { nome: 'limite_aditamento_sem_autorizacao', rotulo: 'Aditamento sem autorização (%)', tipo: 'decimal', min: 0, max: 1000, ajuda: 'Acréscimo acumulado acima deste percentual exige a autorização do Ordenador de Despesa anexada.' },
      { nome: 'limite_acerto_centavos', rotulo: 'Acerto de centavos por item (R$)', tipo: 'decimal', min: 0, max: 1000, ajuda: 'Maior acerto, para mais ou para menos, permitido em um item medido.' },
      { nome: 'maximo_notas_fiscais', rotulo: 'Notas fiscais por competência', min: 1, max: 200, ajuda: 'Vale também para os documentos de despesa variável.' },
      { nome: 'prazo_pagamento_padrao_dias', rotulo: 'Prazo de pagamento padrão (dias)', min: 0, max: 365, ajuda: 'Sugerido na etapa de nota fiscal e usado nas tarefas enquanto a NF não entrou.' },
      { nome: 'prazo_nota_fiscal_horas', rotulo: 'Prazo da nota fiscal (horas)', min: 1, max: 720, ajuda: 'Depois da medição, nas competências sem prazo de contestação.' },
    ],
  },
  {
    id: 'arquivos',
    titulo: 'Arquivos e limites',
    subtitulo: 'Tamanhos e quantidades aceitos nos envios do módulo. O tamanho de um anexo PDF comum é do servidor e vale para todos os módulos.',
    campos: [
      { nome: 'xml_tamanho_maximo_mb', rotulo: 'XML de nota fiscal (MB)', min: 1, max: 100, ajuda: 'Tamanho máximo do XML lido na etapa de nota fiscal.' },
      { nome: 'planilha_tamanho_maximo_mb', rotulo: 'Planilhas de importação (MB)', min: 1, max: 100, ajuda: 'Cadastro do contrato e modelos por planilha.' },
      { nome: 'maximo_anexos_ocorrencia', rotulo: 'Anexos por ocorrência do diário', min: 1, max: 50, ajuda: 'Quantidade máxima de arquivos em cada ocorrência.' },
      { nome: 'anexos_email_maximo_mb', rotulo: 'Anexos no e-mail do diário (MB)', min: 1, max: 100, ajuda: 'Acima desta soma, os arquivos não vão no e-mail (ficam no sistema e o e-mail avisa).' },
    ],
  },
  {
    id: 'prorrogacao',
    titulo: 'Prorrogação',
    subtitulo: 'Autoridades que assinam os documentos da prorrogação, prazos de publicação e validade do Parecer Referencial da PGE. Entram nas minutas geradas pelo sistema.',
    campos: [
      { nome: 'ssgc_nome', rotulo: 'Subsecretário(a) de Gestão Corporativa (SSGC)', tipo: 'texto', ajuda: 'Assina o termo aditivo e as declarações da prorrogação.' },
      { nome: 'ssgc_cpf', rotulo: 'CPF do(a) SSGC', tipo: 'texto', ajuda: 'Como deve aparecer nos documentos (ex.: 822.684.878-49).' },
      { nome: 'secretario_nome', rotulo: 'Secretário(a)', tipo: 'texto', ajuda: 'Autoridade máxima no Termo de Ciência e Notificação (TCE).' },
      { nome: 'secretario_cpf', rotulo: 'CPF do(a) Secretário(a)', tipo: 'texto', ajuda: 'Como deve aparecer no Termo de Ciência.' },
      { nome: 'autoridade_competente_nome', rotulo: 'Autoridade competente (despacho de autorização)', tipo: 'texto', ajuda: 'Quem assina o despacho que autoriza a prorrogação (Resolução SPI 17/2025).' },
      { nome: 'autoridade_competente_cargo', rotulo: 'Cargo da autoridade competente', tipo: 'texto', ajuda: 'Cargo que aparece abaixo do nome no despacho.' },
      { nome: 'pncp_dias_uteis_licitacao', rotulo: 'Prazo no PNCP: licitação (dias úteis)', min: 1, max: 60, ajuda: 'A partir da assinatura do termo (art. 94 da Lei 14.133). A divulgação é condição de eficácia.' },
      { nome: 'pncp_dias_uteis_direta', rotulo: 'Prazo no PNCP: contratação direta (dias úteis)', min: 1, max: 60, ajuda: 'Dispensa ou inexigibilidade.' },
      { nome: 'aviso_pncp_dias_uteis', rotulo: 'Lembrete do PNCP (dias úteis antes)', min: 0, max: 30, ajuda: 'Quantos dias úteis antes do prazo o sistema avisa a equipe.' },
      { nome: 'parecer_referencial_validade_dias', rotulo: 'Validade do Parecer Referencial (dias)', min: 1, max: 1460, ajuda: 'Contados da emissão (1 ano).' },
      { nome: 'parecer_referencial_vigencia_ate', rotulo: 'Parecer Referencial vale até', tipo: 'data', ajuda: 'Depois desta data o enquadramento avisa que é preciso um parecer novo (NLC nº 1/2026: até 09/02/2027).' },
    ],
  },
];

/** Parâmetros de Contratos (só controle total ou SuperRoot grava): nenhum prazo, corte ou limite fica fixo no código. */
@Component({
  selector: 'app-parametros-contratos',
  imports: [EsqueletoComponent, FormsModule, DatePipe, CabecalhoModuloComponent],
  template: `
    <app-cabecalho-modulo titulo="Parâmetros de Contratos" [trilha]="['Parâmetros']" descricao="Cortes de alertas, prazos, regras e limites do módulo. Valem para todos os contratos e já refletem nas telas, nos painéis e nos e-mails." />
    @if (p(); as x) {
      <form class="parametros-rh" (ngSubmit)="salvar(x)">
        @for (g of grupos; track g.id) {
          <section class="cartao-dados" [attr.aria-labelledby]="'titulo-' + g.id">
            <header>
              <div><h2 [id]="'titulo-' + g.id">{{ g.titulo }}</h2><small>{{ g.subtitulo }}</small></div>
              <button type="button" class="acao-secundaria acao-pequena" (click)="restaurar(x, g)">Restaurar padrão</button>
            </header>
            <div class="corpo">
              <div class="grade-parametros">
                @for (c of g.campos; track c.nome) {
                  <div class="campo">
                    <label [for]="'p-' + c.nome">{{ c.rotulo }}</label>
                    @if (c.tipo === 'data') {
                      <input [id]="'p-' + c.nome" [name]="c.nome" type="date" required [(ngModel)]="valores[c.nome]" />
                    } @else if (c.tipo === 'texto') {
                      <input [id]="'p-' + c.nome" [name]="c.nome" type="text" required maxlength="200" [(ngModel)]="valores[c.nome]" />
                    } @else {
                      <input [id]="'p-' + c.nome" [name]="c.nome" type="number" required [attr.min]="c.min" [attr.max]="c.max" [attr.step]="c.tipo === 'decimal' ? '0.01' : '1'" [(ngModel)]="valores[c.nome]" />
                    }
                    <small class="ajuda">{{ c.ajuda }}</small>
                    @if (alterado(x, c.nome)) { <small class="ajuda">Valor de fábrica: {{ x.padroes[c.nome] }}</small> }
                  </div>
                }
              </div>
            </div>
          </section>
        }
        <footer class="rodape-parametros">
          <span class="atualizacao">@if (x.atualizado_por_nome) { Atualizado por <b>{{ x.atualizado_por_nome }}</b> em {{ x.atualizado_em | date: 'dd/MM/yyyy HH:mm' }} } @else { Parâmetros ainda não alterados }</span>
          <button type="submit" class="acao-primaria">Salvar parâmetros</button>
        </footer>
      </form>
    } @else { <app-esqueleto tipo="formulario" [linhas]="6" /> }
  `,
})
export class ParametrosContratosComponent implements OnInit {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly compartilhado = inject(ParametrosContratosService);
  protected readonly grupos = GRUPOS;
  protected readonly p = signal<ParametrosContratos | null>(null);
  /** Cópia editável dos valores (o que a pessoa digita só vale depois de salvar). */
  protected valores = {} as Record<keyof ValoresParametrosContratos, string | number>;

  ngOnInit(): void {
    this.api.parametros().subscribe({ next: (x) => this.receber(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar os parâmetros') });
  }

  private receber(x: ParametrosContratos): void {
    this.valores = { ...x } as unknown as Record<keyof ValoresParametrosContratos, string | number>;
    this.p.set(x);
    this.compartilhado.atualizar(x);
  }

  /** O valor digitado difere do de fábrica? (mostra o padrão ao lado para a pessoa saber voltar) */
  protected alterado(x: ParametrosContratos, nome: keyof ValoresParametrosContratos): boolean {
    return String(this.valores[nome]) !== String(x.padroes[nome]) && Number(this.valores[nome]) !== Number(x.padroes[nome]);
  }

  /** Volta os campos do cartão aos valores de fábrica (só no formulário: continua preciso salvar). */
  protected restaurar(x: ParametrosContratos, g: GrupoParametros): void {
    for (const c of g.campos) this.valores[c.nome] = x.padroes[c.nome];
  }

  protected salvar(x: ParametrosContratos): void {
    // A data de corte antecipada reabre pendências antigas: pede confirmação antes de gravar
    const antecipou = String(this.valores.corte_alertas_a_partir_de) < x.corte_alertas_a_partir_de;
    const gravar = () =>
      this.dialogos.executar(this.api.salvarParametros(this.valores as unknown as ValoresParametrosContratos), 'Salvando…').subscribe({
        next: (novo) => {
          this.receber(novo);
          this.dialogos.avisar('Parâmetros salvos', 'Os valores já valem para todos os contratos.');
        },
        error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar (só quem tem controle total em Contratos altera os parâmetros)'),
      });
    if (!antecipou) return void gravar();
    void this.dialogos
      .confirmar({
        titulo: 'Antecipar o corte de alertas?',
        mensagem: 'Competências anteriores ao corte atual voltam a gerar pendências, alertas, avisos de atraso e e-mails de pagamento. Confirme só se é isso que você quer.',
        rotuloConfirmar: 'Sim, antecipar o corte',
        perigo: true,
        segundos: 3,
      })
      .then((ok) => ok && gravar());
  }
}
