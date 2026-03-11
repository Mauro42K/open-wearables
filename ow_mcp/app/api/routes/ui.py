"""Minimal onboarding UI routes."""

from html import escape

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api.dependencies import DbSession
from app.repositories.connection_repository import ConnectionRepository
from app.services.session_resolver import SessionResolverError, resolve_authenticated_user_from_request

router = APIRouter(tags=["ui"])


def _page(title: str, body: str) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)}</title>
    <style>
      :root {{
        color-scheme: light;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      body {{
        margin: 0;
        background: #f5f5f5;
        color: #111;
      }}
      main {{
        max-width: 720px;
        margin: 48px auto;
        padding: 24px;
      }}
      .card {{
        background: #fff;
        border: 1px solid #ddd;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.04);
      }}
      h1 {{
        margin-top: 0;
        font-size: 28px;
      }}
      p, li {{
        line-height: 1.5;
      }}
      label {{
        display: block;
        font-weight: 600;
        margin-bottom: 8px;
      }}
      input {{
        width: 100%;
        box-sizing: border-box;
        padding: 12px;
        border: 1px solid #bbb;
        border-radius: 8px;
        font-size: 16px;
        margin-bottom: 12px;
      }}
      button, a.button {{
        display: inline-block;
        border: 0;
        border-radius: 8px;
        padding: 10px 14px;
        background: #111;
        color: #fff;
        text-decoration: none;
        font-size: 15px;
        cursor: pointer;
      }}
      button.secondary, a.secondary {{
        background: #e9e9e9;
        color: #111;
      }}
      .actions {{
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin-top: 16px;
      }}
      .message {{
        margin: 0 0 16px;
        padding: 12px;
        border-radius: 8px;
        background: #f0f4f8;
      }}
      .message.error {{
        background: #fdecec;
        color: #7f1d1d;
      }}
      .message.success {{
        background: #ecfdf3;
        color: #14532d;
      }}
      dl {{
        display: grid;
        grid-template-columns: 160px 1fr;
        gap: 10px 12px;
      }}
      dt {{
        font-weight: 600;
      }}
      code {{
        background: #f2f2f2;
        padding: 2px 6px;
        border-radius: 6px;
      }}
    </style>
  </head>
  <body>
    <main>{body}</main>
  </body>
</html>"""
    return HTMLResponse(content=html)


def _message_html(kind: str | None, text: str | None) -> str:
    if not kind or not text:
        return ""
    return f'<div class="message {escape(kind)}" id="page-message">{escape(text)}</div>'


def _query_message(request: Request) -> tuple[str | None, str | None]:
    if "error" in request.query_params:
        return "error", request.query_params.get("error")
    if "message" in request.query_params:
        return "success", request.query_params.get("message")
    return None, None


@router.get("/connect", response_class=HTMLResponse, response_model=None)
async def connect_page(request: Request, db: DbSession):
    """Render the connect API key page."""
    try:
        authenticated_user = resolve_authenticated_user_from_request(request)
    except SessionResolverError:
        return RedirectResponse(url="/auth/google/start")

    repository = ConnectionRepository(db)
    connection = repository.get_by_google_user_id(authenticated_user.google_user_id)

    message_kind, message_text = _query_message(request)
    current_state = ""
    if connection is not None and connection.status == "connected" and connection.encrypted_api_key:
        current_state = f"""
        <div class="message success">
          Connected with <code>{escape(connection.api_key_masked or 'masked')}</code>.
          You can replace the key below or go to <a href="/status">status</a>.
        </div>
        """

    body = f"""
    <div class="card">
      <h1>Connect Open Wearables API Key</h1>
      {_message_html(message_kind, message_text)}
      {current_state}
      <p>Signed in as <strong>{escape(authenticated_user.google_email)}</strong>.</p>
      <p>Paste an API key created in <a href="https://ow.mauro42k.com" target="_blank" rel="noreferrer">Open Wearables</a>.</p>
      <form id="connect-form">
        <label for="api_key">API key</label>
        <input id="api_key" name="api_key" type="password" placeholder="sk-..." required />
        <div class="actions">
          <button type="submit">Validate and Connect</button>
          <button id="logout-button" class="secondary" type="button">Sign out</button>
        </div>
      </form>
      <div id="form-message"></div>
    </div>
    <script>
      const form = document.getElementById('connect-form');
      const message = document.getElementById('form-message');
      const logoutButton = document.getElementById('logout-button');
      form.addEventListener('submit', async (event) => {{
        event.preventDefault();
        message.innerHTML = '';
        const apiKey = new FormData(form).get('api_key');
        const response = await fetch('/api/connection/validate', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ api_key: apiKey }})
        }});
        const payload = await response.json();
        const text = payload.message || 'Connected.';
        const klass = response.ok ? 'success' : 'error';
        message.innerHTML = `<div class="message ${{klass}}">${{text}}</div>`;
        if (response.ok) {{
          setTimeout(() => window.location.href = '/status?message=connected', 400);
        }}
      }});
      logoutButton.addEventListener('click', async () => {{
        await fetch('/auth/logout', {{ method: 'POST' }});
        window.location.href = '/auth/google/start';
      }});
    </script>
    """
    return _page("Connect Open Wearables API Key", body)


@router.get("/status", response_class=HTMLResponse, response_model=None)
async def status_page(request: Request, db: DbSession):
    """Render the current connection status page."""
    try:
        authenticated_user = resolve_authenticated_user_from_request(request)
    except SessionResolverError:
        return RedirectResponse(url="/auth/google/start")

    repository = ConnectionRepository(db)
    connection = repository.get_by_google_user_id(authenticated_user.google_user_id)
    if connection is None or connection.status == "not_connected" or not connection.encrypted_api_key:
        return RedirectResponse(url="/connect")

    message_kind, message_text = _query_message(request)
    validated_at = connection.validated_at.isoformat() if connection.validated_at else "Never"
    last_error = connection.last_error_code or "None"

    body = f"""
    <div class="card">
      <h1>Connection Status</h1>
      {_message_html(message_kind, message_text)}
      <p>Signed in as <strong>{escape(authenticated_user.google_email)}</strong>.</p>
      <dl>
        <dt>Status</dt><dd>{escape(connection.status)}</dd>
        <dt>API key</dt><dd><code>{escape(connection.api_key_masked or 'Not available')}</code></dd>
        <dt>Validated at</dt><dd>{escape(validated_at)}</dd>
        <dt>Last error</dt><dd>{escape(last_error)}</dd>
      </dl>
      <div class="actions">
        <a class="button secondary" href="/connect">Update API key</a>
        <button id="disconnect-button" type="button">Disconnect</button>
      </div>
      <div id="status-message"></div>
    </div>
    <script>
      const button = document.getElementById('disconnect-button');
      const message = document.getElementById('status-message');
      button.addEventListener('click', async () => {{
        message.innerHTML = '';
        const response = await fetch('/api/connection/disconnect', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{}})
        }});
        const payload = await response.json();
        const text = payload.message || 'Disconnected.';
        const klass = response.ok ? 'success' : 'error';
        message.innerHTML = `<div class="message ${{klass}}">${{text}}</div>`;
        if (response.ok) {{
          setTimeout(() => window.location.href = '/connect?message=disconnected', 400);
        }}
      }});
    </script>
    """
    return _page("Connection Status", body)
