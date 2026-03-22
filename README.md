# flin-linkedin-posts-mcp

`flin-linkedin-posts-mcp` ist ein read-only MCP-Server für persönliche LinkedIn-Posts eines Nutzers.

## Features

- Aktuelles LinkedIn-Mitglied über `https://api.linkedin.com/v2/userinfo` aus dem Access-Token auflösen
- Eigene Posts oder Posts eines bestimmten Mitglieds laden
- Einzelne Posts normalisiert abrufen
- Posts automatisch analysieren: Textlänge, Hashtags, Erwähnungen und Top-Begriffe

## Verfügbare MCP-Tools

1. `get_member_profile`
2. `list_member_posts`
3. `get_post`
4. `analyze_member_posts`

## Benötigte Umgebungsvariablen

- `LINKEDIN_ACCESS_TOKEN`
- `LINKEDIN_API_VERSION` (Default: `202603`)
- `LINKEDIN_RESTLI_PROTOCOL_VERSION` (Default: `2.0.0`)
- `LINKEDIN_TIMEOUT_SECONDS` (Default: `30`)
- `LINKEDIN_MAX_RETRIES` (Default: `3`)

## LinkedIn Access Token korrekt erzeugen

Dieser MCP-Server nutzt:
- `GET https://api.linkedin.com/v2/userinfo`
- `GET https://api.linkedin.com/rest/posts` (mit `q=author`)

Damit ein Token für den Server funktioniert:
1. In der LinkedIn Developer App unter `Products` aktivieren:
   - `Sign In with LinkedIn using OpenID Connect` (Scopes: `openid profile email`)
2. Für das Lesen von Posts ist zusätzlich `r_member_social` nötig.
   - Laut LinkedIn Posts API ist `r_member_social` für das Abrufen von Member-Posts erforderlich und als restricted markiert.
3. In `Auth` eine gültige Redirect URL eintragen.

### OAuth 2.0 (Authorization Code Flow)

1. Nutzer zu LinkedIn weiterleiten (Scopes anpassen):

```text
https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=<CLIENT_ID>&redirect_uri=<URL_ENCODED_REDIRECT_URI>&state=<RANDOM_STATE>&scope=openid%20profile%20email%20r_member_social
```

2. `code` aus dem Redirect entgegennehmen und gegen Token tauschen:

```bash
curl -X POST "https://www.linkedin.com/oauth/v2/accessToken" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=authorization_code" \
  --data-urlencode "code=<AUTH_CODE>" \
  --data-urlencode "redirect_uri=<REDIRECT_URI>" \
  --data-urlencode "client_id=<CLIENT_ID>" \
  --data-urlencode "client_secret=<CLIENT_SECRET>"
```

3. `access_token` als `LINKEDIN_ACCESS_TOKEN` verwenden.

### Token vor Claude testen

```bash
# Userinfo muss funktionieren (OIDC-Scopes)
curl -sS "https://api.linkedin.com/v2/userinfo" \
  -H "Authorization: Bearer $LINKEDIN_ACCESS_TOKEN"

# Posts-Abfrage prüfen (erfordert r_member_social)
curl -sS -G "https://api.linkedin.com/rest/posts" \
  -H "Authorization: Bearer $LINKEDIN_ACCESS_TOKEN" \
  -H "Linkedin-Version: 202603" \
  -H "X-Restli-Protocol-Version: 2.0.0" \
  --data-urlencode "q=author" \
  --data-urlencode "author=urn:li:person:<YOUR_MEMBER_ID>" \
  --data-urlencode "count=1"
```

## Installation

```bash
python -m pip install -e '.[dev]'
```

## Beispiel Claude Desktop Konfiguration

```json
{
  "mcpServers": {
    "flin-linkedin-posts-mcp": {
      "command": "uvx",
      "args": ["--refresh", "flin-linkedin-posts-mcp@latest"],
      "env": {
        "LINKEDIN_ACCESS_TOKEN": "AQX...",
        "LINKEDIN_API_VERSION": "202603",
        "LINKEDIN_RESTLI_PROTOCOL_VERSION": "2.0.0"
      }
    }
  }
}
```

Für reproduzierbare Setups lieber auf eine feste Version pinnen, z. B. `flin-linkedin-posts-mcp@0.1.1`.

## Veröffentlichung auf PyPI (direkt über GitHub)

1. PyPI Trusted Publishing für dieses Repo einrichten:
   - PyPI Projekt: `flin-linkedin-posts-mcp`
   - Publisher: GitHub Actions
   - Repository: `flin-agency/flin-linkedin-posts-mcp`
   - Workflow: `.github/workflows/release.yml`
   - Environment: `pypi`
2. Version in `pyproject.toml` erhöhen.
3. Tag im Format `vX.Y.Z` erstellen und pushen:

```bash
git tag v0.1.1
git push origin v0.1.1
```

4. Der Release-Workflow prüft automatisch:
   - Tag-Version == `project.version` in `pyproject.toml`
   - `ruff`, `mypy`, `pytest`
   - Build + `twine check`
5. Danach publiziert GitHub Actions direkt nach PyPI und erstellt ein GitHub Release.

## Claude-Test mit veröffentlichtem Paket (`uvx`)

Nach erfolgreichem PyPI-Release in Claude Desktop:

```json
{
  "mcpServers": {
    "flin-linkedin-posts-mcp": {
      "command": "uvx",
      "args": ["--refresh", "flin-linkedin-posts-mcp@latest"],
      "env": {
        "LINKEDIN_ACCESS_TOKEN": "AQX...",
        "LINKEDIN_API_VERSION": "202603",
        "LINKEDIN_RESTLI_PROTOCOL_VERSION": "2.0.0"
      }
    }
  }
}
```

Claude Desktop danach komplett neu starten.

Wenn du eine bestimmte Release-Version testen willst, nutze statt `@latest` eine feste Version, z. B. `flin-linkedin-posts-mcp@0.1.1`.

## Entwicklung

```bash
pytest -q
ruff check .
```

## Hinweise

- Wenn `author_urn` fehlt, versucht der Server den aktuell authentifizierten Nutzer über `https://api.linkedin.com/v2/userinfo` aufzulösen.
- Dafür braucht das Token in der Praxis meist passende OpenID-/Userinfo-Berechtigungen.
- Für `list_member_posts` und `analyze_member_posts` muss das Token Posts lesen dürfen (`r_member_social`), sonst liefert LinkedIn typischerweise `403`.
- Die Post-Analyse ist heuristisch und basiert auf Text, Hashtags und Erwähnungen der geladenen Posts.

## Referenzen

- Sign In with LinkedIn using OpenID Connect: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2
- OAuth 2.0 Authorization Code Flow: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow-native
- Posts API (Permissions): https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
- Getting Access to LinkedIn APIs (Open Permissions): https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access
