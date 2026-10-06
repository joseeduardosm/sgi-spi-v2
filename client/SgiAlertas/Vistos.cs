// Criado por José Eduardo Santana Martins
// Este arquivo serve para lembrar, por usuário, quais mensagens já viraram alerta (para não repetir a cada abertura do programa).

using System.Text.Json;

namespace SgiSpi.Alertas;

internal sealed class Vistos
{
    private const int Maximo = 400;

    private readonly string _caminho;
    private readonly List<string> _ids;

    /// <summary>Primeira vez deste usuário neste computador (nunca houve arquivo).</summary>
    public bool PrimeiraVez { get; }

    private Vistos(string caminho, List<string> ids, bool primeiraVez)
    {
        _caminho = caminho;
        _ids = ids;
        PrimeiraVez = primeiraVez;
    }

    public static Vistos Carregar(string login)
    {
        var pasta = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SgiSpiAlertas");
        var seguro = string.Concat(login.Select(c => char.IsLetterOrDigit(c) || c is '.' or '-' or '_' ? c : '_'));
        var caminho = Path.Combine(pasta, $"vistos-{seguro}.json");
        try
        {
            Directory.CreateDirectory(pasta);
            if (File.Exists(caminho))
                return new Vistos(caminho, JsonSerializer.Deserialize<List<string>>(File.ReadAllText(caminho)) ?? [], false);
        }
        catch
        {
            // Arquivo corrompido: recomeça sem repetir alertas antigos
        }
        return new Vistos(caminho, [], true);
    }

    public bool Contem(string id) => _ids.Contains(id);

    public void Adicionar(IEnumerable<string> ids)
    {
        foreach (var id in ids)
            if (!_ids.Contains(id)) _ids.Add(id);
        if (_ids.Count > Maximo) _ids.RemoveRange(0, _ids.Count - Maximo);
        try { File.WriteAllText(_caminho, JsonSerializer.Serialize(_ids)); } catch { /* sem permissão de escrita: só não persiste */ }
    }
}
