import { validarPdf } from '../componentes/envio-pdf/envio-pdf.component';
import {
  formatarCompetencia,
  formatarData,
  formatarMoeda,
  formatarPercentual,
  formatarQuantidade,
  formatarTamanho,
} from './formatadores';

// Intl usa espaço não separável entre "R$" e o número
const semEspacoEspecial = (texto: string) => texto.replace(/ /g, ' ');

describe('formatadores', () => {
  it('formata moeda a partir de texto decimal da API', () => {
    expect(semEspacoEspecial(formatarMoeda('1234.5'))).toBe('R$ 1.234,50');
    expect(formatarMoeda(null)).toBe('R$ -');
  });

  it('formata quantidades com até 4 casas', () => {
    expect(formatarQuantidade('2.5000')).toBe('2,5');
    expect(formatarQuantidade(1.23456)).toBe('1,2346');
  });

  it('formata percentual, data e competência sem depender do fuso', () => {
    expect(formatarPercentual(12.5)).toBe('12,5%');
    expect(formatarData('2026-01-01')).toBe('01/01/2026');
    expect(formatarCompetencia('2026-05-01')).toBe('05/2026');
    expect(formatarCompetencia('2026-05')).toBe('05/2026');
  });

  it('formata tamanho de arquivo', () => {
    expect(formatarTamanho(1258291)).toBe('1,2 MB');
    expect(formatarTamanho(500)).toBe('500 B');
  });
});

describe('validarPdf', () => {
  const arquivo = (nome: string, tamanho: number, tipo = 'application/pdf') =>
    new File([new Uint8Array(tamanho)], nome, { type: tipo });

  it('aceita PDF e recusa outros formatos, vazios e grandes demais', () => {
    expect(validarPdf(arquivo('termo.pdf', 10))).toBeNull();
    expect(validarPdf(arquivo('planilha.xlsx', 10, 'application/vnd.ms-excel'))).toBe('Selecione um arquivo PDF.');
    expect(validarPdf(arquivo('vazio.pdf', 0))).toBe('O arquivo está vazio.');
    expect(validarPdf(arquivo('grande.pdf', 25 * 1024 * 1024 + 1))).toContain('limite de 25 MB');
  });
});
