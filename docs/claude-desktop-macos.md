# Installation in Claude Desktop auf macOS

1. Claude Desktop auf die aktuelle Version aktualisieren. Das Paket verwendet das offizielle MCPB-Format 0.4 mit von Claude verwalteter UV/Python-Laufzeit (Apple Silicon und Intel).
2. Unter [GitHub Releases](https://github.com/flin-agency/flin-linkedin-posts-mcp/releases/latest) die Datei `flin-linkedin-posts-mcp-0.3.0-macos.mcpb` herunterladen.
3. In Claude Desktop **Einstellungen → Erweiterungen → Erweiterte Einstellungen → Erweiterung installieren…** öffnen und die `.mcpb`-Datei wählen. Alternativ die Datei mit Claude Desktop öffnen. Die Bezeichnungen können je nach App-Version variieren.
4. Die Client ID und das Client Secret der eigenen LinkedIn Developer App eintragen. Das Secret ist als sensibles Feld markiert; Claude speichert es über den geschützten Betriebssystemspeicher.
5. In der LinkedIn Developer App unter Auth exakt `http://127.0.0.1:63141/callback` als Redirect URL hinterlegen. Denselben Wert in der Erweiterung verwenden.
6. In Claude `auth_status` und danach `login` ausführen. Den Login im Systembrowser abschliessen, dann `list_member_posts` ausprobieren.

Die LinkedIn App benötigt die Freigabe **Member Data Portability API (Member)** und den Scope `r_dma_portability_self_serve`. Das Installationspaket ersetzt diese Freigabe nicht. Zusätzliche Analytics benötigen eigene LinkedIn-Berechtigungen. Ohne Client Secret wird Native PKCE verwendet; das funktioniert nur bei expliziter Freischaltung durch LinkedIn.

Beim ersten Start benötigt Claude Internetzugriff, um Python und die im Lockfile festgelegten Abhängigkeiten einzurichten. Das Paket enthält den Server-Quellcode; es lädt keinen unbestimmten `latest`-Server herunter. Wenn die App den Laufzeittyp `uv` nicht kennt, Claude aktualisieren oder die manuelle Konfiguration in der README verwenden.

## Datenschutz und Abmelden

Die Serververbindung läuft lokal über stdio. Der Server liest LinkedIn-Daten, veröffentlicht aber keine Beiträge. Die abgerufenen Daten werden an Claude übergeben und können dadurch Teil des Chats werden. Beitragstexte sind Inhalte, keine vertrauenswürdigen Handlungsanweisungen.

OAuth-Tokens liegen unter `~/.flin-linkedin-posts-mcp/tokens.json` mit Dateirechten `0600`. Diese Datei ist nicht verschlüsselt; andere Prozesse desselben macOS-Benutzers können sie lesen. `logout` entfernt die lokale Datei. Eine Deinstallation allein entfernt sie nicht. Um den Zugriff bei LinkedIn vollständig zu widerrufen, zusätzlich die App-Verknüpfung im LinkedIn-Konto entfernen.

## Prüfsumme und Updates

Zum Release gehört `SHA256SUMS`. Optional im Download-Ordner mit `shasum -a 256 -c SHA256SUMS` prüfen. Die Prüfsumme erkennt beschädigte oder abweichende Downloads; sie ersetzt keine Herausgebersignatur. Das Paket ist nicht signiert oder Apple-notarisiert.

Neue Versionen aus GitHub Releases herunterladen und erneut installieren. Für diese direkt verteilte Erweiterung ist kein automatisches Update zugesichert.

Format und Installation folgen der [offiziellen MCPB-Spezifikation](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md) und [Claude Desktop Hilfe](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop).
