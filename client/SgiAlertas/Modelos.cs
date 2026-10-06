// Criado por José Eduardo Santana Martins
// Este arquivo serve para descrever os dados que a API do SGI devolve (login e mensageria).

using System.Text.Json.Serialization;

namespace SgiSpi.Alertas;

/// <summary>Mensagem da caixa de entrada (<c>GET /api/mensagens</c>).</summary>
internal sealed record MensagemResumo(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("assunto")] string Assunto,
    [property: JsonPropertyName("prioridade")] string Prioridade,
    [property: JsonPropertyName("categoria")] string Categoria,
    [property: JsonPropertyName("autor_nome")] string AutorNome,
    [property: JsonPropertyName("link")] string? Link);

internal sealed record PaginaMensagens(
    [property: JsonPropertyName("itens")] List<MensagemResumo> Itens,
    [property: JsonPropertyName("total")] int Total);

/// <summary>Aviso que o sistema manda abrir em janela (<c>janela</c> do resumo da caixa).</summary>
internal sealed record JanelaAviso(
    [property: JsonPropertyName("id")] string Id);

internal sealed record ResumoCaixa(
    [property: JsonPropertyName("pendentes")] int Pendentes,
    [property: JsonPropertyName("nao_lidas")] int NaoLidas,
    [property: JsonPropertyName("janela")] JanelaAviso? Janela);

internal sealed record UsuarioLogado(string Login, string Nome);
