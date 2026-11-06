// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a tela Administração › Versões: o que aparece na produção, na homologação e no modal de erro.

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';

import { VersoesSistemaComponent } from './versoes-sistema.component';

const ANDAMENTO_VAZIO = { operacao: null, situacao: null, mensagem: '', etapa: null, percentual: null, de: null, para: null, voltou: null, atualizado_em: null };

function painel(extras: Record<string, unknown>) {
  return { homologacao: false, versao: 'v2026.11.01', versao_no_disco: 'v2026.11.01', commit: 'abc1234', arvore_limpa: true, ramo: 'estado-atual-servidor',
    aprovada: null, commits_novos: [], versoes: [], andamento: ANDAMENTO_VAZIO, log: '', ...extras };
}

/** Monta a tela respondendo o GET inicial com o painel dado. */
function montar(dados: Record<string, unknown>): HTMLElement {
  const fixture = TestBed.createComponent(VersoesSistemaComponent);
  fixture.detectChanges();
  TestBed.inject(HttpTestingController).expectOne((r) => r.url.endsWith('/admin/versoes')).flush(painel(dados));
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('VersoesSistemaComponent', () => {
  beforeEach(() => TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])] }));

  it('na produção lista as versões aprovadas com as novidades e o botão de atualizar', () => {
    const raiz = montar({ versoes: [{ alvo: 'v2026.11.06', aprovada_por: 'Fulano', aprovada_em: '2026-11-06T10:00:00-03:00', mensagem: '', novidades: '- Cores nas VLANs', commits: [] }] });
    expect(raiz.textContent).toContain('Produção');
    expect(raiz.querySelector('.cartao-versao h3')?.textContent).toContain('v2026.11.06');
    expect(raiz.querySelector('.novidades-versao')?.textContent).toContain('Cores nas VLANs');
    expect(Array.from(raiz.querySelectorAll('button')).some((b) => b.textContent?.includes('Atualizar para v2026.11.06'))).toBe(true);
  });

  it('na homologação mostra os commits novos do ramo e o botão de aprovar', () => {
    const raiz = montar({ homologacao: true, commits_novos: [{ commit: 'def5678', titulo: 'Nova tela', autor: 'Dev', data: '2026-11-06T09:00:00-03:00' }] });
    expect(raiz.textContent).toContain('Homologação');
    expect(raiz.querySelector('.lista-commits')?.textContent).toContain('Nova tela');
    expect(Array.from(raiz.querySelectorAll('button')).some((b) => b.textContent?.includes('Aprovar esta versão'))).toBe(true);
  });

  it('com alteração local avisa e bloqueia', () => {
    const raiz = montar({ arvore_limpa: false });
    expect(raiz.querySelector('.aviso-bloco.erro')?.textContent).toContain('não commitadas');
  });

  it('entrando com a atualização em andamento, abre o modal com a etapa atual', () => {
    const raiz = montar({ andamento: { ...ANDAMENTO_VAZIO, operacao: 'atualizar', situacao: 'em_andamento', etapa: 'build', percentual: 80, mensagem: 'Compilando…', de: 'v1', para: 'v2' } });
    expect(raiz.querySelector('[role="dialog"]')?.textContent).toContain('Atualizando para v2');
    expect(raiz.querySelector('[role="progressbar"]')?.getAttribute('aria-valuenow')).toBe('80');
  });
});
