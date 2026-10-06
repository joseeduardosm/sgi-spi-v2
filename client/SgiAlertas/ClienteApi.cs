// Criado por José Eduardo Santana Martins
// Este arquivo serve para falar com a API do SGI: DNS do portal e, se ele falhar, o IP alternativo (mesmo certificado).

using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Net.Sockets;
using System.Text.Json;

namespace SgiSpi.Alertas;

/// <summary>Não foi possível chegar ao servidor (rede, DNS e IP alternativo falharam).</summary>
internal sealed class SemConexaoException(string mensagem, Exception? interna = null) : Exception(mensagem, interna);

/// <summary>Login recusado ou erro do servidor.</summary>
internal sealed class LoginRecusadoException(string mensagem) : Exception(mensagem);

internal sealed class ClienteApi : IDisposable
{
    private static readonly JsonSerializerOptions OpcoesJson = new() { PropertyNameCaseInsensitive = true };

    private readonly Configuracao _configuracao;
    private readonly HttpClient _http;
    private string? _token;

    /// <summary>O servidor recusou o token (expirou ou foi invalidado): é preciso entrar de novo.</summary>
    public event Action? SessaoExpirada;

    public UsuarioLogado? Usuario { get; private set; }
    public bool Autenticado => _token is not null;

    public ClienteApi(Configuracao configuracao)
    {
        _configuracao = configuracao;
        var manipulador = new SocketsHttpHandler
        {
            ConnectTimeout = TimeSpan.FromSeconds(20),
            PooledConnectionLifetime = TimeSpan.FromMinutes(5),
            // A conexão TCP tenta o DNS e, só se falhar, o IP alternativo. O HTTPS é negociado depois, sempre com o nome do
            // portal (SNI e certificado), então o IP alternativo não enfraquece a verificação do certificado.
            ConnectCallback = ConectarAsync,
        };
        _http = new HttpClient(manipulador) { BaseAddress = new Uri(configuracao.UrlBase), Timeout = TimeSpan.FromSeconds(25) };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("SgiSpiAlertas/1.0");
    }

    private async ValueTask<Stream> ConectarAsync(SocketsHttpConnectionContext contexto, CancellationToken cancelamento)
    {
        var destino = contexto.DnsEndPoint;
        try
        {
            using var limite = CancellationTokenSource.CreateLinkedTokenSource(cancelamento);
            limite.CancelAfter(TimeSpan.FromSeconds(6));
            return await AbrirAsync(destino.Host, destino.Port, limite.Token);
        }
        catch (Exception) when (!cancelamento.IsCancellationRequested
                                && !string.IsNullOrWhiteSpace(_configuracao.IpAlternativo)
                                && destino.Host.Equals(_configuracao.Servidor, StringComparison.OrdinalIgnoreCase))
        {
            return await AbrirAsync(_configuracao.IpAlternativo!, destino.Port, cancelamento);
        }
    }

    private static async Task<Stream> AbrirAsync(string host, int porta, CancellationToken cancelamento)
    {
        var soquete = new Socket(SocketType.Stream, ProtocolType.Tcp) { NoDelay = true };
        try
        {
            await soquete.ConnectAsync(host, porta, cancelamento);
            return new NetworkStream(soquete, ownsSocket: true);
        }
        catch
        {
            soquete.Dispose();
            throw;
        }
    }

    /// <summary>Entra com login e senha (a senha não é guardada; só o token fica em memória).</summary>
    public async Task EntrarAsync(string login, string senha, CancellationToken cancelamento = default)
    {
        HttpResponseMessage resposta;
        try
        {
            resposta = await _http.PostAsJsonAsync("/api/autenticacao/login", new { login, senha }, cancelamento);
        }
        catch (Exception erro) when (erro is HttpRequestException or TaskCanceledException or IOException)
        {
            throw new SemConexaoException("Não foi possível conectar ao SGI. Verifique a rede e tente de novo.", erro);
        }

        using (resposta)
        {
            if (resposta.StatusCode == HttpStatusCode.Unauthorized)
                throw new LoginRecusadoException("Usuário ou senha inválidos.");
            if (resposta.StatusCode == HttpStatusCode.TooManyRequests)
                throw new LoginRecusadoException("Muitas tentativas. Aguarde um pouco e tente de novo.");
            if (!resposta.IsSuccessStatusCode)
                throw new LoginRecusadoException($"O SGI recusou o login (código {(int)resposta.StatusCode}).");

            using var documento = JsonDocument.Parse(await resposta.Content.ReadAsStringAsync(cancelamento));
            var raiz = documento.RootElement;
            _token = raiz.GetProperty("token_acesso").GetString();
            var usuario = raiz.GetProperty("usuario");
            var loginSessao = usuario.TryGetProperty("login", out var l) ? l.GetString() ?? login : login;
            var nome = usuario.TryGetProperty("nome_completo", out var n) && n.ValueKind == JsonValueKind.String ? n.GetString() ?? loginSessao : loginSessao;
            Usuario = new UsuarioLogado(loginSessao, nome);
        }
    }

    public void Sair()
    {
        _token = null;
        Usuario = null;
    }

    public Task<ResumoCaixa?> ResumoAsync(CancellationToken cancelamento = default) =>
        ObterAsync<ResumoCaixa>("/api/mensagens/resumo", cancelamento);

    public Task<PaginaMensagens?> PendentesAsync(CancellationToken cancelamento = default) =>
        ObterAsync<PaginaMensagens>("/api/mensagens?estado=pendentes&pagina=1&tamanho_pagina=30", cancelamento);

    private async Task<T?> ObterAsync<T>(string caminho, CancellationToken cancelamento)
    {
        if (_token is null) throw new InvalidOperationException("Não autenticado.");
        using var pedido = new HttpRequestMessage(HttpMethod.Get, caminho);
        pedido.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _token);
        HttpResponseMessage resposta;
        try
        {
            resposta = await _http.SendAsync(pedido, cancelamento);
        }
        catch (Exception erro) when (erro is HttpRequestException or TaskCanceledException or IOException)
        {
            throw new SemConexaoException("Sem conexão com o SGI.", erro);
        }

        using (resposta)
        {
            if (resposta.StatusCode == HttpStatusCode.Unauthorized)
            {
                Sair();
                SessaoExpirada?.Invoke();
                return default;
            }
            if (!resposta.IsSuccessStatusCode)
                throw new SemConexaoException($"O SGI respondeu com erro {(int)resposta.StatusCode}.");

            // Renovação deslizante: o servidor manda um token novo quando o atual está perto de vencer
            if (resposta.Headers.TryGetValues("X-Token-Renovado", out var renovado) && renovado.FirstOrDefault() is { Length: > 0 } novo)
                _token = novo;
            return await resposta.Content.ReadFromJsonAsync<T>(OpcoesJson, cancelamento);
        }
    }

    public void Dispose() => _http.Dispose();
}
