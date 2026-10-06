// Criado por José Eduardo Santana Martins
// Este arquivo serve para empilhar os alertas no canto inferior direito da área de trabalho (acima da barra de tarefas).

using System.Drawing;
using System.Media;

namespace SgiSpi.Alertas;

internal sealed class GerenciadorAlertas
{
    private const int Margem = 12;
    private const int Espaco = 8;
    private const int MaximoNaTela = 4;

    private readonly List<FormAlerta> _abertos = [];

    /// <summary>Mostra um alerta (chamar sempre na thread da interface).</summary>
    public void Mostrar(string sobretitulo, string assunto, string rodape, bool persistente, int segundos, Action aoAbrir)
    {
        // Passou do limite: fecha o mais antigo que não seja persistente
        while (_abertos.Count >= MaximoNaTela && _abertos.FirstOrDefault(a => !a.Tag!.Equals("persistente")) is { } antigo)
            antigo.Close();

        var alerta = new FormAlerta(sobretitulo, assunto, rodape, persistente, segundos) { Tag = persistente ? "persistente" : "comum" };
        alerta.Abrir += a =>
        {
            aoAbrir();
            a.Close();
        };
        alerta.FormClosed += (_, _) =>
        {
            _abertos.Remove(alerta);
            Reposicionar();
        };
        _abertos.Add(alerta);
        Reposicionar();
        alerta.Show();
        try { SystemSounds.Asterisk.Play(); } catch { /* sem som */ }
    }

    public void FecharTodos()
    {
        foreach (var alerta in _abertos.ToList()) alerta.Close();
    }

    /// <summary>Alinha os alertas à direita, de baixo para cima, na área útil da tela principal (fora da barra de tarefas).</summary>
    private void Reposicionar()
    {
        var area = Screen.PrimaryScreen?.WorkingArea ?? new Rectangle(0, 0, 1280, 720);
        var y = area.Bottom - Margem;
        foreach (var alerta in _abertos.AsEnumerable().Reverse())
        {
            y -= alerta.Height;
            alerta.Location = new Point(area.Right - alerta.Width - Margem, y);
            y -= Espaco;
        }
    }
}
