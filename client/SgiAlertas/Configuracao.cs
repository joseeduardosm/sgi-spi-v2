// Criado por José Eduardo Santana Martins
// Este arquivo serve para ler as configurações do aplicativo (appsettings.json, ao lado do .exe).

using System.Text.Json;

namespace SgiSpi.Alertas;

/// <summary>Configurações do cliente. Os valores padrão valem se o arquivo não existir.</summary>
internal sealed class Configuracao
{
    /// <summary>Nome DNS do portal (HTTPS).</summary>
    public string Servidor { get; set; } = "portal.spi.sp.gov.br";

    /// <summary>IP usado só para conectar quando o DNS falha; o certificado continua sendo conferido pelo nome do portal.</summary>
    public string? IpAlternativo { get; set; } = "10.23.0.254";

    /// <summary>De quantos em quantos segundos consulta as mensagens.</summary>
    public int IntervaloSegundos { get; set; } = 60;

    /// <summary>Por quantos segundos um alerta comum fica na tela.</summary>
    public int SegundosAlerta { get; set; } = 15;

    public string UrlBase => $"https://{Servidor}";

    public static Configuracao Carregar()
    {
        try
        {
            var caminho = Path.Combine(AppContext.BaseDirectory, "appsettings.json");
            if (File.Exists(caminho))
            {
                var lida = JsonSerializer.Deserialize<Configuracao>(File.ReadAllText(caminho), new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                if (lida is not null)
                {
                    lida.IntervaloSegundos = Math.Clamp(lida.IntervaloSegundos, 10, 600);
                    lida.SegundosAlerta = Math.Clamp(lida.SegundosAlerta, 5, 120);
                    return lida;
                }
            }
        }
        catch
        {
            // Arquivo ilegível: segue com os padrões
        }
        return new Configuracao();
    }
}
