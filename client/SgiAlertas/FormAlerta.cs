// Criado por José Eduardo Santana Martins
// Este arquivo serve para desenhar um alerta no canto inferior direito da tela, perto do relógio, sem roubar o foco.

using System.Drawing;

namespace SgiSpi.Alertas;

/// <summary>Cartão de alerta: faixa vermelha, assunto e remetente. Clicar abre a mensagem; o "×" fecha.</summary>
internal sealed class FormAlerta : Form
{
    private const int WS_EX_NOACTIVATE = 0x08000000;
    private const int WS_EX_TOOLWINDOW = 0x00000080;
    private const int WS_EX_TOPMOST = 0x00000008;

    private static readonly Color Vermelho = Color.FromArgb(176, 34, 46);

    private readonly System.Windows.Forms.Timer _relogio = new();

    public event Action<FormAlerta>? Abrir;

    public FormAlerta(string sobretitulo, string assunto, string rodape, bool persistente, int segundos)
    {
        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.Manual;
        ShowInTaskbar = false;
        TopMost = true;
        BackColor = Color.White;
        Size = new Size(380, 104);
        Font = new Font("Segoe UI", 9.5f);
        Cursor = Cursors.Hand;
        Padding = new Padding(1);

        var faixa = new Panel { Dock = DockStyle.Left, Width = 6, BackColor = Vermelho, Cursor = Cursors.Hand };
        var topo = new Label
        {
            Text = sobretitulo.ToUpperInvariant(), Font = new Font("Segoe UI", 8f, FontStyle.Bold), ForeColor = Vermelho,
            Left = 18, Top = 10, Width = 300, Height = 16, Cursor = Cursors.Hand,
        };
        var titulo = new Label
        {
            Text = assunto, Font = new Font("Segoe UI", 10.5f, FontStyle.Bold), ForeColor = Color.FromArgb(31, 38, 45),
            Left = 18, Top = 28, Width = 340, Height = 44, AutoEllipsis = true, Cursor = Cursors.Hand,
        };
        var pe = new Label
        {
            Text = rodape, ForeColor = Color.FromArgb(91, 101, 112), Left = 18, Top = 76, Width = 340, Height = 18,
            AutoEllipsis = true, Cursor = Cursors.Hand,
        };
        var fechar = new Label
        {
            Text = "×", Font = new Font("Segoe UI", 13f), ForeColor = Color.FromArgb(91, 101, 112), Left = 350, Top = 4,
            Width = 24, Height = 24, TextAlign = ContentAlignment.MiddleCenter, Cursor = Cursors.Hand,
        };
        fechar.Click += (_, _) => Close();
        Controls.AddRange([faixa, topo, titulo, pe, fechar]);

        // Clicar em qualquer parte do cartão (menos no ×) abre a mensagem
        foreach (var controle in new Control[] { this, faixa, topo, titulo, pe })
            controle.Click += (_, _) => Abrir?.Invoke(this);

        // Alerta comum some sozinho; o importante (persistente) fica até alguém fechar ou abrir
        if (!persistente)
        {
            _relogio.Interval = segundos * 1000;
            _relogio.Tick += (_, _) => Close();
            Shown += (_, _) => _relogio.Start();
        }
        FormClosed += (_, _) => _relogio.Dispose();
        Paint += (_, e) => e.Graphics.DrawRectangle(new Pen(Color.FromArgb(205, 210, 216)), 0, 0, Width - 1, Height - 1);
    }

    // Não ativa a janela: o alerta aparece sem tirar o foco do que a pessoa está digitando
    protected override bool ShowWithoutActivation => true;

    protected override CreateParams CreateParams
    {
        get
        {
            var parametros = base.CreateParams;
            parametros.ExStyle |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST;
            return parametros;
        }
    }
}
