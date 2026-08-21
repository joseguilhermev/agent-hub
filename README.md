# Agent Hub API

Minimal FastAPI backend for choosing and chatting with Copilot Studio agents over
Direct Line 3.0. Administrators manage agents and assign them to user accounts.
Direct Line secrets and tokens remain server-side.

On first start, the app creates `data/agent-hub.db` and a private local encryption
key. For production, provide a stable Fernet key through the environment and keep
it in a secrets manager, separate from database backups:

```dotenv
AGENT_HUB_DATABASE=/var/lib/agent-hub/agent-hub.db
AGENT_HUB_ENCRYPTION_KEY=your-fernet-key
```

Generate a Fernet key with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
Losing or changing this key makes stored agent secrets unreadable.

Start the API:

```sh
uv sync
uv run agent-hub-api
```

The production build includes the React frontend at `http://localhost:8000`.
Interactive API documentation remains available at `http://localhost:8000/docs`.

## Frontend development

Run FastAPI in one terminal:

```sh
uv run agent-hub-api
```

Run the Vite development server in another:

```sh
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies HTTP and WebSocket traffic to FastAPI.

Build the single-deployment frontend:

```sh
cd frontend
npm run build
cd ..
uv run agent-hub-api
```

Frontend verification:

```sh
cd frontend
npm test
npm run typecheck
npm run test:e2e
```

The browser interface supports agent switching, independent per-agent sessions,
real-time messages and typing, Markdown, Adaptive and Hero cards, suggested
actions, OAuth prompts, images, audio/video, downloads, and multi-file uploads.
Conversation IDs and local transcripts are kept in `sessionStorage`; the backend
still owns every Direct Line secret, token, and stream URL.

Basic chat flow:

```sh
TOKEN=$(curl -s -X POST http://localhost:8000/auth/register \
  -H 'content-type: application/json' \
  -d '{"email":"user@example.com","password":"a-long-unique-password"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["token"])')
curl http://localhost:8000/agents -H "authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/agents \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"name":"Support","secret":"your-direct-line-secret"}'
curl -X POST http://localhost:8000/conversations \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"agent_id":"AGENT_ID","user_name":"José"}'
curl -X POST http://localhost:8000/conversations/CONVERSATION_ID/messages \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"text":"Hello"}'
```

Passwords are salted and hashed with scrypt. Session tokens are random, stored
only as SHA-256 hashes, expire after 30 days, and are revoked by `/auth/logout`.
Agent secrets use authenticated encryption at rest. The first registered account
is the administrator; later accounts only see agents assigned to them in the
administration area. Run behind HTTPS in production so credentials and bearer tokens are
encrypted in transit.

## Direct Line features

The backend exposes the complete Direct Line activity transport while keeping the
Direct Line secret, conversation token, and WebSocket stream URL private.

### Rich activities and actions

Incoming activities preserve all Bot Framework fields, including Adaptive Cards,
OAuth cards, Hero Cards, suggested actions, speech fields, `channelData`, events,
invoke activities, reactions, and custom fields. Send any activity supported by
your agent:

```sh
curl -X POST http://localhost:8000/conversations/CONVERSATION_ID/activities \
  -H 'content-type: application/json' \
  -d '{"type":"event","name":"location","value":{"latitude":-23.5,"longitude":-46.6}}'
```

The backend sets the activity sender from the server-side conversation and ignores
any client-supplied `from` identity.

### Receive activities

Poll with a Direct Line watermark:

```sh
curl 'http://localhost:8000/conversations/CONVERSATION_ID/activities?watermark=WATERMARK'
```

Or connect to the backend WebSocket for real-time activities, including `typing`:

```text
ws://localhost:8000/conversations/CONVERSATION_ID/stream
```

Only one Direct Line WebSocket may be connected to a conversation at a time. The
backend requests a fresh private stream URL when the frontend connects.

### Upload attachments

Upload one or several files, optionally with message text:

```sh
curl -X POST http://localhost:8000/conversations/CONVERSATION_ID/attachments \
  -F 'text=Review these files' \
  -F 'files=@document.docx' \
  -F 'files=@image.png'
```

Direct Line can transport arbitrary attachments. Whether Copilot Studio reads a
particular file depends on the agent's file-input settings and supported formats.

Attachments can also be sent by public HTTPS or data URL through the generic
activity endpoint using the Bot Framework `attachments` field.

### End a conversation

```sh
curl -X DELETE http://localhost:8000/conversations/CONVERSATION_ID
```

Direct Line may forward or drop `endOfConversation`; the backend always removes
its local conversation state after successfully sending it.

Tokens are refreshed automatically before expiration. Conversations are stored
in memory and are cleared when the process restarts.

## Channel boundaries

Direct Line provides the conversation transport, not the Microsoft Teams client.
Adaptive Cards, suggested actions, file input, speech metadata, custom events, and
agent-generated attachments can be carried through this API. Teams-specific
meeting/channel context, Teams app installation, Microsoft 365 Copilot integration,
native Teams SSO, and live-agent routing are separate platform integrations.

OAuth cards are preserved for the frontend. Completing OAuth or SSO requires the
frontend and identity-provider configuration; the backend cannot manufacture an
end-user access token. Generic OAuth cards expose their secure token-post resource
inside the returned attachment for an authenticated client to handle.

The existing command-line smoke test remains available:

```sh
uv run agent-hub
```

Documentation:

- [Direct Line API 3.0 reference](https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-direct-line-3-0-api-reference?view=azure-bot-service-4.0)
- [Direct Line authentication](https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-direct-line-3-0-authentication?view=azure-bot-service-4.0)
- [Send activities](https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-direct-line-3-0-send-activity?view=azure-bot-service-4.0)
- [Receive activities and watermarks](https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-direct-line-3-0-receive-activities?view=azure-bot-service-4.0)
- [Reconnect a WebSocket](https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-direct-line-3-0-reconnect-to-conversation?view=azure-bot-service-4.0)
- [Copilot Studio file input](https://learn.microsoft.com/en-us/microsoft-copilot-studio/image-input-analysis)
- [Copilot Studio generic OAuth SSO](https://learn.microsoft.com/en-us/microsoft-copilot-studio/configure-sso-3p)
- [Connect a Copilot Studio agent to a custom app](https://learn.microsoft.com/en-us/microsoft-copilot-studio/publication-connect-bot-to-custom-application)
