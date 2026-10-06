// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o histórico de recusas da nota fiscal (justificativa, PDFs e reenvio do e-mail).

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { DetalheCompetencia } from '../compartilhado/contratos.models';
import { HistoricoRecusasComponent } from './historico-recusas.component';

const arquivo = (nome: string) => ({ anexo_id: nome, nome, tamanho: 10, enviado_em: '2026-10-06T10:00:00Z' });
const detalhe = (extras: Partial<DetalheCompetencia> = {}) => ({
  id: 'c1', contrato_id: 'k1', pode_conferir_retencao: true, pode_recusar: true,
  recusas: [{
    id: 'r1', ordem: 1, justificativa: 'ISS retido incorreto. Veja https://exemplo.com/regra', recusada_por_nome: 'Fin Membro', recusada_em: '2026-10-06T10:00:00Z',
    notas: [{ rotulo: 'NF 123', numero: '123', valor_bruto: '2105.00', chave: null, arquivo: arquivo('nf123.pdf'), xml: null }],
    pdf: arquivo('recusa1.pdf'), email: { enviado_em: '2026-10-06T10:01:00Z', ok: true, destinatarios: ['a@sp.gov.br', 'p@empresa.com'], erro: null },
  }],
  ...extras,
}) as unknown as DetalheCompetencia;

describe('HistoricoRecusasComponent', () => {
  beforeEach(() => TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] }));

  it('lista a recusa com justificativa (link clicável), PDFs e destinatários do e-mail', () => {
    const fixture = TestBed.createComponent(HistoricoRecusasComponent);
    fixture.componentRef.setInput('detalhe', detalhe());
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Recusa nº 1');
    expect(el.textContent).toContain('Baixar PDF da recusa');
    expect(el.textContent).toContain('p@empresa.com');
    expect(el.querySelector('.justificativa-recusa a')?.getAttribute('href')).toBe('https://exemplo.com/regra');
  });

  it('não mostra nada sem recusas e reenvia o e-mail pela API', () => {
    const fixture = TestBed.createComponent(HistoricoRecusasComponent);
    fixture.componentRef.setInput('detalhe', detalhe({ recusas: [] }));
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('.historico-recusas')).toBeNull();
    fixture.componentRef.setInput('detalhe', detalhe());
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    const botao = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find((b) => b.textContent?.includes('Reenviar e-mail'))!;
    botao.click();
    http.expectOne((r) => r.method === 'POST' && r.url.endsWith('/recusas/r1/reenviar-email')).flush({});
  });
});
