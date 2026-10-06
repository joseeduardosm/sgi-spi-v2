// Criado por José Eduardo Santana Martins
// Este arquivo serve para pedir login e senha no centro da tela, no início de cada sessão do Windows.

using System.Drawing;

namespace SgiSpi.Alertas;

/// <summary>
/// Janela de entrada. O Windows não entrega a senha de quem já está logado, e o SGI não confia em credencial do Windows
/// sem a configuração de Kerberos no servidor; por isso o usuário digita login e senha (o login já vem preenchido).
/// </summary>
internal sealed class FormLogin : Form
{
    private static readonly Color Vermelho = Color.FromArgb(176, 34, 46);

    private readonly ClienteApi _api;
    private readonly TextBox _login = new();
    private readonly TextBox _senha = new() { UseSystemPasswordChar = true };
    private readonly Button _entrar = new() { Text = "Entrar" };
    private readonly Button _depois = new() { Text = "Agora não" };
    private readonly Label _aviso = new() { ForeColor = Vermelho, AutoSize = false };

    public FormLogin(ClienteApi api)
    {
        _api = api;
        Text = "SGI SPI · Entrar";
        Font = new Font("Segoe UI", 9.5f);
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = MinimizeBox = false;
        TopMost = true;
        ShowInTaskbar = true;
        ClientSize = new Size(380, 292);
        BackColor = Color.White;
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { /* sem ícone */ }

        var faixa = new Panel { Dock = DockStyle.Top, Height = 6, BackColor = Vermelho };
        var titulo = new Label { Text = "SGI SPI · Mensagens", Font = new Font("Segoe UI", 14f, FontStyle.Bold), Left = 24, Top = 22, Width = 332, Height = 30 };
        var subtitulo = new Label
        {
            Text = "Entre com o login e a senha do seu computador para receber os avisos do SGI.",
            ForeColor = Color.FromArgb(91, 101, 112), Left = 24, Top = 54, Width = 332, Height = 38,
        };
        var rotuloLogin = new Label { Text = "Login", Left = 24, Top = 100, Width = 332, Height = 20 };
        _login.SetBounds(24, 122, 332, 27);
        _login.Text = Environment.UserName;
        var rotuloSenha = new Label { Text = "Senha", Left = 24, Top = 156, Width = 332, Height = 20 };
        _senha.SetBounds(24, 178, 332, 27);
        _aviso.SetBounds(24, 210, 332, 36);
        _entrar.SetBounds(180, 248, 84, 30);
        _entrar.BackColor = Vermelho;
        _entrar.ForeColor = Color.White;
        _entrar.FlatStyle = FlatStyle.Flat;
        _entrar.FlatAppearance.BorderSize = 0;
        _depois.SetBounds(272, 248, 84, 30);

        Controls.AddRange([faixa, titulo, subtitulo, rotuloLogin, _login, rotuloSenha, _senha, _aviso, _entrar, _depois]);
        AcceptButton = _entrar;
        CancelButton = _depois;
        _depois.DialogResult = DialogResult.Cancel;
        _entrar.Click += async (_, _) => await EntrarAsync();

        // Abre já com o foco na senha e à frente das outras janelas (é o primeiro contato da sessão)
        Shown += (_, _) =>
        {
            Activate();
            (_login.Text.Length > 0 ? _senha : _login).Focus();
        };
    }

    private async Task EntrarAsync()
    {
        var login = _login.Text.Trim();
        if (login.Length == 0 || _senha.Text.Length == 0)
        {
            _aviso.Text = "Informe o login e a senha.";
            return;
        }
        SetOcupado(true);
        _aviso.ForeColor = Color.FromArgb(91, 101, 112);
        _aviso.Text = "Entrando…";
        try
        {
            await _api.EntrarAsync(login, _senha.Text);
            _senha.Clear();
            DialogResult = DialogResult.OK;
        }
        catch (Exception erro) when (erro is LoginRecusadoException or SemConexaoException)
        {
            _aviso.ForeColor = Vermelho;
            _aviso.Text = erro.Message;
            _senha.SelectAll();
            _senha.Focus();
        }
        finally
        {
            if (!IsDisposed) SetOcupado(false);
        }
    }

    private void SetOcupado(bool ocupado)
    {
        _login.Enabled = _senha.Enabled = _entrar.Enabled = !ocupado;
        UseWaitCursor = ocupado;
    }
}
