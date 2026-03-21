# flin-linkedin-ads-mcp

`flin-linkedin-ads-mcp` ist ein strikt read-only MCP Server für LinkedIn Ads.
Er ist dafür gebaut, direkt in Claude über MCP eingebunden und getestet zu werden.

## Features

- Read-only Zugriff auf LinkedIn Ads Daten
- Ad Accounts lesen
- Campaign Groups lesen
- Campaigns lesen
- Creatives lesen
- Insights/Analytics lesen
- Keine Schreiboperationen in `v0.1.x`

## Scope `v0.1.x` (strict read-only)

- Kein Create/Update/Delete
- Kein Pause/Resume
- Kein generischer Proxy-Endpunkt
- Kein eingebauter OAuth-Refresh-Flow im MCP selbst

## Direkt in Claude testen

### Variante A: Lokal aus diesem Repo (empfohlen zum Entwickeln)

In Claude:
1. `Settings` öffnen
2. `Developer` öffnen
3. MCP Config bearbeiten
4. Diesen Server eintragen:

```json
{
  "mcpServers": {
    "flin-linkedin-ads-mcp-local": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/nicolasg/Antigravity/flin-linkedin-ads-mcp",
        "flin-linkedin-ads-mcp"
      ],
      "env": {
        "LINKEDIN_ACCESS_TOKEN": "AQX...",
        "LINKEDIN_API_VERSION": "202602",
        "LINKEDIN_RESTLI_PROTOCOL_VERSION": "2.0.0"
      }
    }
  }
}
```

Danach Claude neu starten.

### Variante B: Via `uvx` (wenn Paket publiziert ist)

```json
{
  "mcpServers": {
    "flin-linkedin-ads-mcp": {
      "command": "uvx",
      "args": ["--refresh", "flin-linkedin-ads-mcp"],
      "env": {
        "LINKEDIN_ACCESS_TOKEN": "AQX...",
        "LINKEDIN_API_VERSION": "202602",
        "LINKEDIN_RESTLI_PROTOCOL_VERSION": "2.0.0"
      }
    }
  }
}
```

## 2-Minuten Smoke Test in Claude

Nach dem Restart in Claude diese Calls testen:

1. `list_ad_accounts`
2. `list_campaigns`
3. `get_insights` mit `pivot=campaign`

Wenn `list_campaigns` eine Auswahl zurückgibt, den Call mit einem vorgeschlagenen `ad_account_id` wiederholen.

## LinkedIn Access Token generieren (Schritt für Schritt)

Voraussetzung:
- LinkedIn Developer App vorhanden
- Marketing API Zugriff für die App freigeschaltet
- Scope `r_ads` für Entities (Accounts/Campaigns/Creatives)
- Scope `r_ads_reporting` für `get_insights`
- Die Ad Accounts sind in der Developer App unter `Products -> View Ad Accounts` gemappt
- Der authentifizierte User hat eine Ad-Account-Rolle (mind. `VIEWER`)

### 1) App in LinkedIn Developer Portal vorbereiten

- In der App unter `Auth`:
  - `Client ID` und `Client Secret` notieren
  - Redirect URL hinzufügen, z. B. `http://localhost:9876/callback`
- In der App sicherstellen, dass die Marketing/Ads Berechtigungen aktiviert sind (`r_ads` + `r_ads_reporting`)

### 2) Authorization Code holen

Im Browser öffnen (Werte ersetzen, `redirect_uri` URL-encoden).

Für diesen MCP müssen im Scope mindestens enthalten sein:

- `r_ads` (Accounts/Campaigns/Creatives)
- `r_ads_reporting` (`get_insights`)

Optional (nur wenn deine App dafür freigeschaltet ist):

- `offline_access` (für Refresh-Token-Flow)

Empfohlene URL für den MCP (ohne Refresh-Token):

```text
https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=DEIN_CLIENT_ID&redirect_uri=http%3A%2F%2Flocalhost%3A9876%2Fcallback&scope=r_ads%20r_ads_reporting&state=dein_csrf_state
```

Variante mit optionalem `offline_access`:

```text
https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=DEIN_CLIENT_ID&redirect_uri=http%3A%2F%2Flocalhost%3A9876%2Fcallback&scope=r_ads%20r_ads_reporting%20offline_access&state=dein_csrf_state
```

Nach Login/Consent leitet LinkedIn auf deine Redirect-URL zurück:

```text
http://localhost:9876/callback?code=AUTH_CODE&state=dein_csrf_state
```

Den `code` aus der URL kopieren.

### 3) Authorization Code gegen Access Token tauschen

```bash
curl -X POST 'https://www.linkedin.com/oauth/v2/accessToken' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=authorization_code' \
  --data-urlencode 'code=AUTH_CODE' \
  --data-urlencode 'redirect_uri=http://localhost:9876/callback' \
  --data-urlencode 'client_id=DEIN_CLIENT_ID' \
  --data-urlencode 'client_secret=DEIN_CLIENT_SECRET'
```

Beispiel-Response:

```json
{
  "access_token": "AQX...",
  "expires_in": 5183999
}
```

`access_token` als `LINKEDIN_ACCESS_TOKEN` in die Claude MCP Config übernehmen.

Wichtig: Bei diesem MCP erfolgt Authentifizierung über `env` in der MCP Config.
Es gibt hier keinen eingebauten OAuth-Refresh-Flow im Server selbst.
Wenn der Token abläuft, musst du einen neuen Token erzeugen und in der Config ersetzen.

### 4) Ablauf / Erneuerung

- Access Tokens laufen typischerweise nach ca. 60 Tagen ab.
- Dann OAuth-Flow erneut durchführen.
- Falls deine App für programmatic refresh tokens freigeschaltet ist, kannst du stattdessen per Refresh Token erneuern.

### 5) 401/403 schnell diagnostizieren

Token gegen Ads-Account-Endpunkt testen:

```bash
curl -i 'https://api.linkedin.com/rest/adAccounts?q=search&pageSize=1' \
  -H 'Authorization: Bearer DEIN_ACCESS_TOKEN' \
  -H 'Linkedin-Version: 202602' \
  -H 'X-Restli-Protocol-Version: 2.0.0'
```

Interpretation:

- `401 Unauthorized`: Token abgelaufen, widerrufen oder falscher Scope-Set wurde neu konsentiert
- `403 Forbidden`: Token ist gültig, aber Scope/Rolle/App-Mapping fehlt
- `200 OK`: Auth grundsätzlich korrekt

## Environment Variablen

Pflicht:

- `LINKEDIN_ACCESS_TOKEN`

Optional:

- `LINKEDIN_API_VERSION` (Default: `202602`)
- `LINKEDIN_RESTLI_PROTOCOL_VERSION` (Default: `2.0.0`)
- `LINKEDIN_TIMEOUT_SECONDS` (Default: `30`)
- `LINKEDIN_MAX_RETRIES` (Default: `3`)

## Lokale Entwicklung

```bash
cd /Users/nicolasg/Antigravity/flin-linkedin-ads-mcp
python -m pip install -e ".[dev]"
pytest -q
ruff check .
mypy src
```

## Sicherheit (wichtig)

- Niemals `LINKEDIN_ACCESS_TOKEN` oder OAuth Secrets ins Repo committen
- `.env` ist bereits in `.gitignore`
- Token nur über MCP `env` in Claude oder über lokale Shell-Umgebung setzen
- Vor jedem Push prüfen:

```bash
git status
git diff -- .env
```

Wenn eine Datei mit Secrets auftaucht: Commit abbrechen und Secrets rotieren.

## GitHub Actions & Release (PyPI-ready)

Dieses Repo enthält:

- CI Workflow: `.github/workflows/ci.yml`
- Release Workflow: `.github/workflows/release.yml`

Der Release-Workflow macht bei `v*` Tags:

1. Lint + Typecheck + Tests
2. Build + `twine check`
3. Trusted Publishing zu PyPI
4. GitHub Release mit `dist/*` Artefakten

Node-20-Deprecation-Warnungen sind abgefangen durch:

- aktuelle Actions-Majors (`checkout@v6`, `setup-python@v6`)
- `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` in beiden Workflows

### PyPI Trusted Publisher einmalig einrichten

- PyPI Project: `flin-linkedin-ads-mcp`
- Owner: `flin-agency`
- Repository: `flin-linkedin-ads-mcp`
- Workflow: `release.yml`
- Environment: `pypi`

### Release auslösen

```bash
git add -A
git commit -m "release: v0.1.0"
git tag v0.1.0
git push origin main --tags
```

## Offizielle Referenzen

- LinkedIn OAuth Overview:
  - https://learn.microsoft.com/en-us/linkedin/shared/authentication/authentication
- Authorization Code Flow (native clients):
  - https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow-native
- Marketing Ads API Permissions (`r_ads` / `rw_ads`):
  - https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads/account-structure/create-and-manage-creatives?view=li-lms-2026-02
- Programmatic Refresh Tokens:
  - https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens
