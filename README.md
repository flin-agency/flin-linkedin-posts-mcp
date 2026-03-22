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
      "args": ["--refresh", "flin-linkedin-posts-mcp"],
      "env": {
        "LINKEDIN_ACCESS_TOKEN": "AQX...",
        "LINKEDIN_API_VERSION": "202603",
        "LINKEDIN_RESTLI_PROTOCOL_VERSION": "2.0.0"
      }
    }
  }
}
```

## Entwicklung

```bash
pytest -q
ruff check .
```

## Hinweise

- Wenn `author_urn` fehlt, versucht der Server den aktuell authentifizierten Nutzer über `https://api.linkedin.com/v2/userinfo` aufzulösen.
- Dafür braucht das Token in der Praxis meist passende OpenID-/Userinfo-Berechtigungen.
- Die Post-Analyse ist heuristisch und basiert auf Text, Hashtags und Erwähnungen der geladenen Posts.
