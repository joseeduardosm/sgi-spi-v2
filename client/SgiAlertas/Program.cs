// Criado por José Eduardo Santana Martins
// Este arquivo serve para iniciar o SGI SPI Alertas: uma instância por sessão do Windows, rodando na bandeja.

namespace SgiSpi.Alertas;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        // "Local\" = uma instância por sessão do Windows (cada usuário tem a sua)
        using var exclusivo = new Mutex(true, @"Local\SgiSpiAlertas", out bool primeira);
        if (!primeira) return;

        ApplicationConfiguration.Initialize();
        Application.Run(new AplicativoBandeja());
    }
}
