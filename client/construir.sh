#!/usr/bin/env bash
# Gera o instalador do SGI SPI Alertas (projeto/client/SgiSpiAlertas-<versão>.msi).
# Requisitos neste servidor: .NET 8 SDK da Microsoft em ~/.dotnet (dotnet-install.sh) e `wixl` (apt install wixl msitools).
set -euo pipefail
cd "$(dirname "$0")"

export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
export PATH="$DOTNET_ROOT:$PATH"
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1

VERSAO="$(grep -oP '(?<=<Version>)[^<]+' SgiAlertas/SgiAlertas.csproj)"

echo "==> Publicando o aplicativo (win-x64, autossuficiente) versão ${VERSAO}"
rm -rf publicar
dotnet publish SgiAlertas/SgiAlertas.csproj -c Release -r win-x64 -o publicar -p:Version="${VERSAO}"

echo "==> Gerando o MSI"
sed -i "s/\(<Product [^>]*Version=\"\)[^\"]*/\1${VERSAO}/" Instalador/SgiSpiAlertas.wxs
rm -f SgiSpiAlertas-*.msi
(cd Instalador && wixl -a x64 -o "../SgiSpiAlertas-${VERSAO}.msi" SgiSpiAlertas.wxs)

echo "==> Pronto: $(pwd)/SgiSpiAlertas-${VERSAO}.msi"
rm -rf Icon Instalador/Icon publicar SgiAlertas/bin SgiAlertas/obj  # sobras do wixl e da compilação
