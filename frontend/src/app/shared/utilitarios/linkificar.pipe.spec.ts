// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a transformação de endereços em links clicáveis.

import { linkificarTexto } from './linkificar.pipe';

describe('linkificarTexto', () => {
  it('transforma http e https em links que abrem em outra aba', () => {
    const html = linkificarTexto('Veja https://sei.sp.gov.br/doc?id=1 e http://exemplo.com/a');
    expect(html).toContain('<a class="link-texto" href="https://sei.sp.gov.br/doc?id=1" target="_blank" rel="noopener noreferrer">https://sei.sp.gov.br/doc?id=1</a>');
    expect(html).toContain('href="http://exemplo.com/a"');
  });

  it('não leva a pontuação do fim da frase para dentro do link', () => {
    expect(linkificarTexto('Acesse https://exemplo.com/x.')).toMatch(/href="https:\/\/exemplo\.com\/x" [^>]*>https:\/\/exemplo\.com\/x<\/a>\.$/);
    expect(linkificarTexto('(https://exemplo.com/x)')).toBe('(<a class="link-texto" href="https://exemplo.com/x" target="_blank" rel="noopener noreferrer">https://exemplo.com/x</a>)');
  });

  it('escapa qualquer marcação digitada (sem script nem atributo solto)', () => {
    const html = linkificarTexto('<img src=x onerror=alert(1)> https://a.com/"onmouseover="x');
    expect(html).not.toContain('<img');
    expect(html).toContain('&lt;img');
    expect(html).not.toMatch(/href="[^"]*"[^>]*onmouseover/);
  });

  it('mantém texto sem endereço e trata vazio; "http://" solto não vira link', () => {
    expect(linkificarTexto('só texto & mais')).toBe('só texto &amp; mais');
    expect(linkificarTexto(null)).toBe('');
    expect(linkificarTexto('http:// nada')).not.toContain('<a');
  });
});
