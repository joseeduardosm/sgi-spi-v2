/**
 * =============================================================================
 * ARQUIVO: rdm-tarefa.component.spec.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Testar a página da RDM (Requisição de Mudança) de uma tarefa: formulário
 * editável, linhas repetíveis, modo só leitura e a decisão da liderança.
 *
 * RESUMO TÉCNICO:
 * Usa o TestBed do Angular com HttpTestingController para simular a resposta
 * de GET /tarefas/7/rdm. As funções formulario() e leitura() montam dados
 * falsos; montar() cria o componente, responde a chamada e devolve um atalho
 * para achar botões pelo texto. Cada caso confere seções, botões e atributos.
 *
 * FINALIDADE DE NEGÓCIO:
 * Protege o fluxo de aprovação de mudanças: quem pode editar vê "Salvar
 * rascunho" e "Enviar"; a liderança vê a RDM travada e só pode aprovar ou
 * reprovar (reprovar exige motivo); a RDM reprovada mostra o motivo e permite
 * reenviar.
 *
 * CONTEXTO NO SISTEMA:
 * Testa rdm-tarefa.component.ts (Módulo Tarefas) com os tipos de rdm.models.ts.
 * Roda com o Vitest via "npx ng test".
 *
 * =============================================================================
 */

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';

import { FormularioRdm, RdmLeitura } from './rdm.models';
import { RdmTarefaComponent } from './rdm-tarefa.component';

/**
 * Monta um formulário de RDM vazio, no mesmo formato que a API devolve.
 * O cronograma já vem com as três etapas fixas e a gestão do conhecimento com
 * uma linha (INVENTÁRIO), como no modelo da Prodesp.
 */
function formulario(): FormularioRdm {
  return {
    titulo: 'Trocar placa', identificacao: { data_solicitacao: '2026-11-06', solicitante: 'Ana', area: 'CAS1', tipo: '' }, objetivo: '', justificativa: '',
    categorizacao: { acao: '', finalidade: '', prioridade: '', risco: '', impacto: '' },
    abrangencia: { departamentos: '', usuarios_internos: '', usuarios_externos: '', ics: '', indisponibilidade: '', tempo_indisponibilidade: '' },
    cronograma: ['HOMOLOGAÇÃO', 'EXECUÇÃO', 'VALIDAÇÃO'].map((etapa) => ({ etapa, inicio: '', duracao: '', termino: '' })),
    janela: { inicio_data: null, inicio_hora: '', fim_data: null, fim_hora: '', tempo: '' }, plano_execucao: [], comunicacao: [], rollback: [],
    rollback_justificativa: '', conhecimento: [{ tipo_documento: 'INVENTÁRIO', acao: '', responsavel: '' }], conhecimento_observacoes: '',
    complementares: { categoria: '', descricao_tecnica: '', responsavel_execucao: '', equipes_envolvidas: '', impacto_previsto: '', riscos: '', medidas_preventivas: '',
      procedimentos_validacao: '', criterios_sucesso: '', pre_requisitos: [], responsavel_analise_tecnica: '', observacoes_adicionais: '' },
  };
}

/**
 * Monta a resposta de leitura da RDM da tarefa #7. Por padrão é um rascunho
 * editável; `extras` sobrescreve só os campos que o teste quer mudar
 * (situação, permissões, motivo etc.).
 */
function leitura(extras: Partial<RdmLeitura>): RdmLeitura {
  return { tarefa_numero: 7, tarefa_titulo: 'Trocar placa', existe: false, numero: '', rotulo: 'RDM SGI (sem número) - Trocar placa', situacao: 'rascunho',
    formulario: formulario(), enviada_em: null, enviada_por_nome: '', decidida_em: null, decidida_por_nome: '', motivo_reprovacao: '', tem_pdf: false,
    pode_editar: true, pode_decidir: false, ...extras };
}

/**
 * Cria o componente, responde a chamada GET da RDM com `dados` (o
 * HttpTestingController intercepta a requisição em vez de ir à rede) e
 * devolve o elemento raiz e um atalho `botao(texto)` que acha o botão cujo
 * texto começa com o valor informado.
 */
function montar(dados: RdmLeitura) {
  const fixture = TestBed.createComponent(RdmTarefaComponent);
  fixture.detectChanges();
  TestBed.inject(HttpTestingController).expectOne((r) => r.url.endsWith('/tarefas/7/rdm')).flush(dados);
  fixture.detectChanges();
  const raiz = fixture.nativeElement as HTMLElement;
  const botao = (texto: string) => Array.from(raiz.querySelectorAll('button')).find((b) => b.textContent?.trim().startsWith(texto)) as HTMLButtonElement | undefined;
  return { fixture, raiz, botao };
}

describe('RdmTarefaComponent', () => {
  // Antes de cada caso: HTTP de teste, roteador vazio e uma rota falsa com o
  // parâmetro "numero" = 7 (o componente lê o número da tarefa da URL).
  beforeEach(() => TestBed.configureTestingModule({
    providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([]), { provide: ActivatedRoute, useValue: { snapshot: { paramMap: new Map([['numero', '7']]) } } }],
  }));

  it('editável: as seções da matriz, adicionar atividade e os botões de salvar e enviar', () => {
    const { fixture, raiz, botao } = montar(leitura({}));
    expect(raiz.textContent).toContain('Plano de remediação (rollback)');
    expect(raiz.textContent).toContain('Informações complementares');
    expect(raiz.querySelectorAll('.linha-rdm').length).toBe(0);
    botao('Adicionar atividade')!.click();
    fixture.detectChanges();
    expect(raiz.querySelectorAll('.linha-rdm').length).toBe(1);
    expect(botao('Salvar rascunho')).toBeTruthy();
    expect(botao('Enviar para aprovação')).toBeTruthy();
    expect(raiz.querySelector('fieldset')?.hasAttribute('disabled')).toBe(false);
  });

  // Liderança com RDM pendente: o fieldset fica desabilitado e só aparecem os
  // botões de decisão; sem motivo digitado, "Reprovar" fica desabilitado.
  it('pendente para a liderança: só leitura, com aprovar e reprovar (reprovar exige motivo)', () => {
    const { raiz, botao } = montar(leitura({ existe: true, numero: '00001/2026', rotulo: 'RDM SGI 00001/2026 - Trocar placa', situacao: 'pendente', pode_editar: false, pode_decidir: true }));
    expect(raiz.querySelector('fieldset')?.hasAttribute('disabled')).toBe(true);
    expect(botao('Salvar rascunho')).toBeUndefined();
    expect(botao('Aprovar RDM')?.className).toContain('acao-positiva');
    expect(botao('Reprovar RDM')?.disabled).toBe(true);
    expect(raiz.querySelector('.selo-status')?.getAttribute('data-chamado')).toBe('alerta');
  });

  it('reprovada: mostra o motivo e oferece o reenvio', () => {
    const { raiz, botao } = montar(leitura({ existe: true, numero: '00001/2026', situacao: 'reprovada', motivo_reprovacao: 'Falta o rollback.' }));
    expect(raiz.querySelector('.aviso-bloco.erro')?.textContent).toContain('Falta o rollback.');
    expect(botao('Reenviar para aprovação')).toBeTruthy();
  });
});
