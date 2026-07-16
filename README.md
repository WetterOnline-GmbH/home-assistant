# WetterOnline Home Assistant Integration

Custom Integration zur lokalen Anbindung von WetterOnline-Home-Stationen an Home Assistant.

## Funktionen

- Automatische Erkennung kompatibler Stationen über Zeroconf (`_woh4._tcp.local.`)
- Bildschirm ein- und ausschalten sowie aktuellen Bildschirmzustand anzeigen
- Temperatur, Luftfeuchtigkeit und Umgebungshelligkeit als Sensoren bereitstellen
- Home-Assistant-Dashboard pro Station auswählen und an die Station übertragen
- Unterstützung mehrerer Stationen innerhalb einer Home-Assistant-Installation

## Voraussetzungen

- Home Assistant 2026.3 oder neuer
- WoHome-Station und Home Assistant im selben lokalen Netzwerk
- Aktiviertes Home-Assistant-Feature in den WoHome-Entwicklereinstellungen

Die lokale Geräte-API verwendet derzeit keine Authentifizierung und sollte nur in einem vertrauenswürdigen Netzwerk eingesetzt werden.

## Installation

1. Den Ordner `custom_components/wohome` nach `/config/custom_components/wohome` auf dem Home-Assistant-System kopieren.
2. Home Assistant neu starten.
3. Die automatisch erkannte WetterOnline-Home-Station unter **Einstellungen → Geräte & Dienste** hinzufügen.

Nach der Einrichtung kann das Dashboard über die `Dashboard`-Select-Entität im Konfigurationsbereich des jeweiligen Geräts geändert werden.

## Entwicklung

Die Integration kommuniziert über die lokale WoHome API v1 auf Port `8080`. Vor einer Installation können Syntax und Home-Assistant-Konfiguration beispielsweise so geprüft werden:

```shell
python3 -m compileall -q custom_components/wohome
ha core check
```
