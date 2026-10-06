// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar o ícone da bandeja, o login e a consulta periódica das mensagens do SGI.

using System.Diagnostics;
using System.Drawing;

namespace SgiSpi.Alertas;

internal sealed class AplicativoBandeja : ApplicationContext
{
    private readonly Configuracao _configuracao = Configuracao.Carregar();
    private readonly ClienteApi _api;
    private readonly GerenciadorAlertas _alertas = new();
    private readonly NotifyIcon _icone = new() { Visible = true };
    private readonly ToolStripMenuItem _situacao = new() { Enabled = false };
    private readonly ToolStripMenuItem _pendentes = new() { Enabled = false, Text = "Mensagens pendentes: —" };
    private readonly ToolStripMenuItem _entrar = new() { Text = "Entrar…" };
    private readonly System.Windows.Forms.Timer _consulta = new();
    private readonly System.Windows.Forms.Timer _inicio = new() { Interval = 400 };

    private Vistos? _vistos;
    private bool _consultando;
    private bool _loginAberto;

    public AplicativoBandeja()
    {
        _api = new ClienteApi(_configuracao);
        _api.SessaoExpirada += () => _icone.ContextMenuStrip?.BeginInvoke(new Action(AoSessaoExpirar));

        try { _icone.Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { _icone.Icon = SystemIcons.Information; }
        var menu = new ContextMenuStrip();
        var abrir = new ToolStripMenuItem("Abrir o SGI no navegador");
        abrir.Click += (_, _) => AbrirNoNavegador(null);
        var sair = new ToolStripMenuItem("Sair");
        sair.Click += (_, _) => Encerrar();
        _entrar.Click += (_, _) => PedirLogin();
        menu.Items.AddRange([_situacao, _pendentes, new ToolStripSeparator(), abrir, _entrar, new ToolStripSeparator(), sair]);
        _icone.ContextMenuStrip = menu;
        _icone.DoubleClick += (_, _) => AbrirNoNavegador("/mensagens");
        AtualizarSituacao("Aguardando login");

        _consulta.Interval = _configuracao.IntervaloSegundos * 1000;
        _consulta.Tick += async (_, _) => await ConsultarAsync();

        // No início da sessão do Windows, a janela de login abre no centro da tela
        _inicio.Tick += (_, _) =>
        {
            _inicio.Stop();
            PedirLogin();
        };
        _inicio.Start();
    }

    private void AtualizarSituacao(string texto)
    {
        _situacao.Text = texto;
        // O texto do ícone aceita no máximo 63 caracteres
        var dica = $"SGI SPI · {texto}";
        _icone.Text = dica.Length > 63 ? dica[..63] : dica;
        _entrar.Text = _api.Autenticado ? "Trocar usuário…" : "Entrar…";
    }

    private void PedirLogin()
    {
        if (_loginAberto) return;
        _loginAberto = true;
        try
        {
            using var janela = new FormLogin(_api);
            if (janela.ShowDialog() != DialogResult.OK || _api.Usuario is null)
            {
                AtualizarSituacao(_api.Autenticado ? $"Conectado como {_api.Usuario!.Login}" : "Aguardando login");
                return;
            }
            _vistos = Vistos.Carregar(_api.Usuario.Login);
            AtualizarSituacao($"Conectado como {_api.Usuario.Login}");
            _consulta.Start();
            _ = ConsultarAsync();
        }
        finally
        {
            _loginAberto = false;
        }
    }

    private void AoSessaoExpirar()
    {
        _consulta.Stop();
        AtualizarSituacao("Sessão expirada");
        PedirLogin();
    }

    private async Task ConsultarAsync()
    {
        if (_consultando || !_api.Autenticado || _vistos is null) return;
        _consultando = true;
        try
        {
            // Uma consulta por ciclo; o resumo (que diz quais avisos abrem em janela) só é pedido quando há mensagem nova
            var pagina = await _api.PendentesAsync();
            if (pagina is null) return;

            _pendentes.Text = $"Mensagens pendentes: {pagina.Total}";
            AtualizarSituacao($"Conectado como {_api.Usuario!.Login}");
            if (pagina.Itens.Any(m => !_vistos.Contem(m.Id)))
                ProcessarNovas(pagina.Itens, pagina.Total, await _api.ResumoAsync());
        }
        catch (SemConexaoException erro)
        {
            AtualizarSituacao(erro.Message);
        }
        catch (Exception erro)
        {
            Debug.WriteLine(erro);
            AtualizarSituacao("Erro ao consultar o SGI");
        }
        finally
        {
            _consultando = false;
        }
    }

    private void ProcessarNovas(List<MensagemResumo> pendentes, int totalPendentes, ResumoCaixa? resumo)
    {
        var novas = pendentes.Where(m => !_vistos!.Contem(m.Id)).ToList();
        if (novas.Count == 0) return;

        // Primeira vez neste computador: um aviso só, para não despejar a caixa inteira de uma vez
        if (_vistos!.PrimeiraVez && novas.Count > 1)
        {
            _alertas.Mostrar("SGI SPI · Mensagens", $"Você tem {totalPendentes} mensagem(ns) pendente(s)", "Clique para abrir a caixa de mensagens",
                persistente: false, _configuracao.SegundosAlerta, () => AbrirNoNavegador("/mensagens"));
            _vistos.Adicionar(novas.Select(m => m.Id));
            return;
        }

        // Do mais antigo para o mais novo; passando de 3, o restante vira um aviso resumido
        var individuais = novas.OrderBy(m => m.Id).Take(3).ToList();
        foreach (var m in individuais)
        {
            var importante = m.Prioridade is "alta" or "critica" || resumo?.Janela?.Id == m.Id;
            _alertas.Mostrar($"SGI SPI · {RotuloCategoria(m.Categoria)}", m.Assunto, $"De {m.AutorNome} · clique para abrir", importante,
                _configuracao.SegundosAlerta, () => AbrirNoNavegador(m.Link ?? "/mensagens"));
        }
        if (novas.Count > individuais.Count)
            _alertas.Mostrar("SGI SPI · Mensagens", $"Mais {novas.Count - individuais.Count} mensagem(ns) nova(s)", "Clique para abrir a caixa de mensagens",
                persistente: false, _configuracao.SegundosAlerta, () => AbrirNoNavegador("/mensagens"));
        _vistos.Adicionar(novas.Select(m => m.Id));
    }

    private static string RotuloCategoria(string categoria) => categoria switch
    {
        "prazo" => "Prazo",
        "pendencia" => "Pendência",
        "revisao" => "Revisão",
        "atribuicao" => "Atribuição",
        "indisponibilidade" => "Indisponibilidade",
        "normativo" => "Normativo",
        _ => "Comunicado",
    };

    /// <summary>Abre o SGI no navegador padrão. Aceita caminho do portal (/mensagens) ou endereço completo.</summary>
    private void AbrirNoNavegador(string? caminho)
    {
        var destino = caminho switch
        {
            null or "" => _configuracao.UrlBase,
            _ when caminho.StartsWith("http", StringComparison.OrdinalIgnoreCase) => caminho,
            _ => _configuracao.UrlBase + (caminho.StartsWith('/') ? caminho : "/" + caminho),
        };
        try { Process.Start(new ProcessStartInfo(destino) { UseShellExecute = true }); } catch { /* sem navegador padrão */ }
    }

    private void Encerrar()
    {
        _consulta.Stop();
        _alertas.FecharTodos();
        _icone.Visible = false;
        _icone.Dispose();
        _api.Dispose();
        ExitThread();
    }
}
