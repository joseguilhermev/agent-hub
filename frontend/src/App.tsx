import { List, SignOut, SlidersHorizontal, WarningCircle } from "@phosphor-icons/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, api, hasAuthToken, setAuthToken, streamProtocols, streamUrl } from "./api";
import { ActivityView } from "./components/ActivityView";
import { AdminArea } from "./components/AdminArea";
import { AgentRail } from "./components/AgentRail";
import { Composer } from "./components/Composer";
import { EmptyState } from "./components/EmptyState";
import { RequestAgentDialog } from "./components/RequestAgentDialog";
import type { Activity, Agent, LocalMessage, User } from "./types";

interface Session {
  conversationId: string;
  messages: LocalMessage[];
  watermark?: string;
}

const STORAGE_KEY = "agent-hub:sessions:v1";

function localMessage(activity: Activity, role: LocalMessage["role"]): LocalMessage {
  return {
    ...activity,
    localId: activity.id ?? crypto.randomUUID(),
    role,
  };
}

function readSessions(): Record<string, Session> {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? "{}") as Record<string, Session>;
  } catch {
    return {};
  }
}

function Hub({ user, onLogout, onAdmin }: { user: User; onLogout: () => void; onAdmin: () => void }) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [activeId, setActiveId] = useState<string>();
  const [sessions, setSessions] = useState<Record<string, Session>>(readSessions);
  const [loadingAgents, setLoadingAgents] = useState(true);
  const [opening, setOpening] = useState(false);
  const [sending, setSending] = useState(false);
  const [typing, setTyping] = useState(false);
  const [error, setError] = useState<string>();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [requestOpen, setRequestOpen] = useState(false);
  const timeline = useRef<HTMLDivElement>(null);
  const activeAgent = agents.find((agent) => agent.id === activeId);
  const activeSession = activeId ? sessions[activeId] : undefined;

  useEffect(() => {
    api.agents()
      .then(setAgents)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoadingAgents(false));
  }, []);

  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  }, [sessions]);

  const addActivities = useCallback((agentId: string, activities: Activity[], streaming = true) => {
    setSessions((current) => {
      const session = current[agentId];
      if (!session) return current;
      const known = new Set(session.messages.map((message) => message.id).filter(Boolean));
      const incoming = activities
        .filter((activity) => !activity.id || !known.has(activity.id))
        .filter((activity) => activity.type !== "typing")
        .map((activity) => ({ ...localMessage(activity, "agent"), streaming }));
      if (!incoming.length) return current;
      return { ...current, [agentId]: { ...session, messages: [...session.messages, ...incoming] } };
    });
  }, []);

  const finishStreaming = useCallback((agentId: string, localId: string) => {
    setSessions((current) => {
      const session = current[agentId];
      if (!session) return current;
      return {
        ...current,
        [agentId]: {
          ...session,
          messages: session.messages.map((message) =>
            message.localId === localId ? { ...message, streaming: false } : message,
          ),
        },
      };
    });
  }, []);

  const selectAgent = useCallback(async (agent: Agent) => {
    setActiveId(agent.id);
    setMobileOpen(false);
    setError(undefined);
    if (sessions[agent.id]) return;
    setOpening(true);
    try {
      const conversation = await api.createConversation(agent.id);
      setSessions((current) => ({
        ...current,
        [agent.id]: {
          conversationId: conversation.id,
          messages: conversation.messages.map((activity) => localMessage(activity, "agent")),
        },
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível iniciar a conversa.");
    } finally {
      setOpening(false);
    }
  }, [sessions]);

  useEffect(() => {
    if (!activeId || !activeSession) return;
    let socket: WebSocket | undefined;
    let reconnectTimer: number | undefined;
    let pollTimer: number | undefined;
    let failures = 0;
    let stopped = false;

    const poll = async () => {
      if (stopped) return;
      try {
        const result = await api.activities(activeSession.conversationId, activeSession.watermark);
        addActivities(activeId, result.activities);
        setSessions((current) => ({ ...current, [activeId]: { ...current[activeId], watermark: result.watermark } }));
      } finally {
        if (!stopped) pollTimer = window.setTimeout(poll, 1500);
      }
    };
    const connect = () => {
      socket = new WebSocket(streamUrl(activeSession.conversationId), streamProtocols());
      socket.onopen = () => { failures = 0; setError(undefined); };
      socket.onmessage = (event) => {
        const payload = JSON.parse(String(event.data)) as { activities?: Activity[]; watermark?: string };
        const activities = payload.activities ?? [];
        setTyping(activities.some((activity) => activity.type === "typing"));
        addActivities(activeId, activities);
        if (payload.watermark) {
          setSessions((current) => ({ ...current, [activeId]: { ...current[activeId], watermark: payload.watermark } }));
        }
      };
      socket.onclose = () => {
        if (stopped) return;
        failures += 1;
        if (failures >= 3) void poll();
        else reconnectTimer = window.setTimeout(connect, Math.min(8000, 700 * 2 ** failures));
      };
      socket.onerror = () => socket?.close();
    };
    connect();
    return () => {
      stopped = true;
      socket?.close();
      window.clearTimeout(reconnectTimer);
      window.clearTimeout(pollTimer);
      setTyping(false);
    };
  }, [activeId, activeSession?.conversationId, addActivities]);

  useEffect(() => {
    const element = timeline.current;
    if (!element) return;
    const nearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 220;
    if (nearBottom) element.scrollTo({ top: element.scrollHeight, behavior: "smooth" });
  }, [activeSession?.messages.length, typing]);

  const sendActivity = useCallback(async (activity: Activity) => {
    if (!activeSession) return;
    try {
      await api.sendActivity(activeSession.conversationId, activity);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível enviar a ação.");
    }
  }, [activeSession]);

  const send = useCallback(async (text: string, files: File[]) => {
    if (!activeId || !activeSession) return false;
    const optimistic = text ? localMessage({ type: "message", text, timestamp: new Date().toISOString() }, "user") : undefined;
    if (optimistic) {
      optimistic.status = "sending";
      setSessions((current) => ({ ...current, [activeId]: { ...current[activeId], messages: [...current[activeId].messages, optimistic] } }));
    }
    setSending(true);
    setError(undefined);
    try {
      const sendTo = (conversationId: string) => files.length
        ? api.upload(conversationId, files, text || undefined)
        : api.sendMessage(conversationId, text);
      let response;
      try {
        response = await sendTo(activeSession.conversationId);
      } catch (reason) {
        if (!(reason instanceof ApiError) || reason.status !== 404 || !activeAgent) throw reason;
        const conversation = await api.createConversation(activeAgent.id);
        setSessions((current) => ({
          ...current,
          [activeId]: {
            conversationId: conversation.id,
            messages: [
              ...current[activeId].messages,
              ...conversation.messages.map((activity) => localMessage(activity, "agent")),
            ],
          },
        }));
        response = await sendTo(conversation.id);
      }
      if (optimistic) {
        setSessions((current) => ({ ...current, [activeId]: { ...current[activeId], messages: current[activeId].messages.map((message) => message.localId === optimistic.localId ? { ...message, status: "sent" } : message) } }));
      }
      addActivities(activeId, response.messages);
      return true;
    } catch (reason) {
      if (optimistic) {
        setSessions((current) => ({ ...current, [activeId]: { ...current[activeId], messages: current[activeId].messages.map((message) => message.localId === optimistic.localId ? { ...message, status: "failed" } : message) } }));
      }
      setError(reason instanceof Error ? reason.message : "Não foi possível enviar a mensagem.");
      return false;
    } finally {
      setSending(false);
    }
  }, [activeAgent, activeId, activeSession, addActivities]);

  const newConversation = useCallback(async () => {
    if (!activeId || !activeAgent) return;
    const previous = sessions[activeId];
    setOpening(true);
    setError(undefined);
    if (previous) void api.endConversation(previous.conversationId).catch(() => undefined);
    try {
      const conversation = await api.createConversation(activeAgent.id);
      setSessions((current) => ({
        ...current,
        [activeAgent.id]: {
          conversationId: conversation.id,
          messages: conversation.messages.map((activity) => localMessage(activity, "agent")),
        },
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível iniciar uma nova conversa.");
    } finally {
      setOpening(false);
    }
  }, [activeAgent, activeId, sessions]);

  const messages = useMemo(() => activeSession?.messages ?? [], [activeSession?.messages]);

  return (
    <main className="app-shell">
      <a className="skip-link" href="#main-workspace">Pular para a conversa</a>
      <AgentRail agents={agents} activeId={activeId} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} onSelect={(agent) => void selectAgent(agent)} onNew={() => void newConversation()} onRequest={() => { setMobileOpen(false); setRequestOpen(true); }} />
      <section className="workspace" id="main-workspace">
        <header className="workspace-header">
          <button className="icon-button mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Escolher um agente"><List size={24} /></button>
          {activeAgent ? <><span className="header-avatar">{activeAgent.name.slice(0, 1).toUpperCase()}</span><div><h1>{activeAgent.name}</h1><p><span className="status-dot" /> Disponível</p></div></> : <div><h1>Agent Hub</h1><p>{loadingAgents ? "Carregando agentes" : "Seu espaço de especialistas"}</p></div>}
          <div className="header-actions">{user.role === "admin" && <button className="admin-link" onClick={onAdmin}><SlidersHorizontal size={18} /> Administração</button>}<button className="icon-button" aria-label="Sair" onClick={onLogout}><SignOut size={21} /></button></div>
        </header>
        {error && <div className="error-banner" role="alert"><WarningCircle size={19} />{error}<button onClick={() => setError(undefined)}>Fechar</button></div>}
        {!activeAgent || opening ? agents.length === 0 && !loadingAgents ? <form className="agent-setup" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); void api.createAgent(String(data.get("name")), String(data.get("secret"))).then((agent) => { setAgents([agent]); setError(undefined); }).catch((reason: Error) => setError(reason.message)); }}><p className="eyebrow">Primeiro agente</p><h2>Conecte um agente</h2><p>O segredo do Direct Line é criptografado antes de ser armazenado.</p><label>Nome do agente<input name="name" required maxLength={200} /></label><label>Segredo do Direct Line<input name="secret" type="password" required /></label><button className="auth-primary" type="submit">Adicionar agente</button></form> : <EmptyState loading={opening || loadingAgents} /> : (
          <>
            <div className="timeline" ref={timeline} aria-live="polite">
              <div className="timeline-inner">
                {messages.length === 0 && !opening && <div className="conversation-start"><span>{activeAgent.name.slice(0, 1).toUpperCase()}</span><h2>Como posso ajudar?</h2><p>Envie uma mensagem ou anexe um arquivo para começar.</p></div>}
                {messages.map((message) => <ActivityView key={message.localId} activity={message} agentName={activeAgent.name} onTextAction={(text) => void send(text, [])} onActivity={(activity) => void sendActivity(activity)} onStreamingComplete={() => finishStreaming(activeAgent.id, message.localId)} />)}
                {typing && <div className="typing-indicator"><span className="message-avatar">{activeAgent.name.slice(0, 1)}</span><p>{activeAgent.name} está digitando <i /><i /><i /></p></div>}
              </div>
            </div>
            <footer className="composer-area"><Composer agentName={activeAgent.name} disabled={!activeSession} sending={sending} onSend={send} /></footer>
          </>
        )}
      </section>
      {requestOpen && <RequestAgentDialog onClose={() => setRequestOpen(false)} />}
    </main>
  );
}

export function App() {
  const [authenticated, setAuthenticated] = useState(hasAuthToken);
  const [checkingSession, setCheckingSession] = useState(hasAuthToken);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authError, setAuthError] = useState<string>();
  const [user, setUser] = useState<User>();
  const [adminOpen, setAdminOpen] = useState(false);

  useEffect(() => {
    if (!authenticated) return;
    api.me()
      .then(setUser)
      .catch(() => {
        setAuthToken();
        setAuthenticated(false);
      })
      .finally(() => setCheckingSession(false));
  }, [authenticated]);

  const authenticate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setAuthError(undefined);
    try {
      const result = await api[authMode](String(data.get("email")), String(data.get("password")));
      setAuthToken(result.token);
      setUser(result.user);
      sessionStorage.removeItem(STORAGE_KEY);
      setCheckingSession(false);
      setAuthenticated(true);
    } catch (reason) {
      setAuthError(reason instanceof Error ? reason.message : "Falha na autenticação.");
    }
  };

  if (checkingSession) return <main className="auth-shell"><p>Verificando sessão…</p></main>;
  if (authenticated && user) return adminOpen && user.role === "admin" ? <AdminArea onBack={() => setAdminOpen(false)} /> : <Hub user={user} onAdmin={() => setAdminOpen(true)} onLogout={() => { void api.logout().catch(() => undefined); setAuthToken(); setUser(undefined); sessionStorage.removeItem(STORAGE_KEY); setAuthenticated(false); }} />;
  return <main className="auth-shell"><form className="auth-panel" onSubmit={(event) => void authenticate(event)}><p className="eyebrow">Agent Hub</p><h1>{authMode === "login" ? "Boas-vindas de volta" : "Crie sua conta"}</h1><p>Seus agentes e as credenciais deles permanecem privados na sua conta.</p>{authError && <div className="auth-error" role="alert">{authError}</div>}<label>E-mail<input name="email" type="email" autoComplete="email" required /></label><label>Senha<input name="password" type="password" autoComplete={authMode === "login" ? "current-password" : "new-password"} minLength={12} required /></label><button type="submit" className="auth-primary">{authMode === "login" ? "Entrar" : "Criar conta"}</button><button type="button" className="auth-switch" onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}>{authMode === "login" ? "Não tem uma conta? Cadastre-se" : "Já tem cadastro? Entre"}</button></form></main>;
}
