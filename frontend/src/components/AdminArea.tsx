import { ArrowLeft, ChartBar, Check, ClipboardText, MagnifyingGlass, Plus, UsersThree, WarningCircle, X } from "@phosphor-icons/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { AdminUser, Agent, AgentRequest } from "../types";
import { UsageDashboard } from "./UsageDashboard";

export function AdminArea({ onBack }: { onBack: () => void }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [requests, setRequests] = useState<AgentRequest[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [draft, setDraft] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"usage" | "access" | "requests">("usage");
  const reportError = useCallback((message?: string) => setError(message), []);

  const selected = users.find((user) => user.id === selectedId);
  const filteredUsers = useMemo(() => users.filter((user) => user.email.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())), [query, users]);
  const dirty = selected ? [...draft].sort().join() !== [...selected.agent_ids].sort().join() : false;

  useEffect(() => {
    Promise.all([api.adminUsers(), api.adminAgents(), api.adminAgentRequests()])
      .then(([nextUsers, nextAgents, nextRequests]) => {
        setUsers(nextUsers);
        setAgents(nextAgents);
        setRequests(nextRequests);
        if (nextUsers[0]) {
          setSelectedId(nextUsers[0].id);
          setDraft(nextUsers[0].agent_ids);
        }
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  const chooseUser = (user: AdminUser) => {
    setSelectedId(user.id);
    setDraft(user.agent_ids);
    setSaved(false);
    setError(undefined);
  };

  const resolveRequest = async (requestId: string, status: "fulfilled" | "rejected") => {
    setError(undefined);
    try {
      const updated = await api.updateAgentRequest(requestId, status);
      setRequests((current) => current.map((request) => request.id === updated.id ? updated : request));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível atualizar a solicitação.");
    }
  };

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    setError(undefined);
    try {
      const updated = await api.assignAgents(selected.id, draft);
      setUsers((current) => current.map((user) => user.id === updated.id ? updated : user));
      setSaved(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível salvar as permissões.");
    } finally {
      setSaving(false);
    }
  };

  const createAgent = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setCreating(true);
    setError(undefined);
    try {
      const agent = await api.createAgent(String(data.get("name")), String(data.get("secret")));
      setAgents((current) => [...current, agent]);
      const nextUsers = await api.adminUsers();
      setUsers(nextUsers);
      const refreshedSelection = nextUsers.find((user) => user.id === selectedId);
      if (refreshedSelection) setDraft(refreshedSelection.agent_ids);
      form.reset();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível adicionar o agente.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <main className="admin-shell">
      <header className="admin-header">
        <button className="admin-back" onClick={onBack}><ArrowLeft size={18} /> Voltar às conversas</button>
        <div><p className="eyebrow">Administração</p><h1>{view === "usage" ? "Monitor de uso" : view === "access" ? "Diretório de acesso" : "Solicitações de agentes"}</h1></div>
        <p>{view === "usage" ? "Veja como cada agente conectado está sendo usado." : view === "access" ? "Escolha quais agentes cada pessoa pode usar." : "Avalie as necessidades enviadas pelas pessoas da equipe."}</p>
      </header>
      <nav className="admin-tabs" aria-label="Seções da administração"><button className={view === "usage" ? "is-active" : ""} onClick={() => setView("usage")}><ChartBar size={17} />Monitor de uso</button><button className={view === "access" ? "is-active" : ""} onClick={() => setView("access")}><UsersThree size={17} />Diretório de acesso</button><button className={view === "requests" ? "is-active" : ""} onClick={() => setView("requests")}><ClipboardText size={17} />Solicitações{requests.filter((request) => request.status === "pending").length > 0 && <span className="request-count">{requests.filter((request) => request.status === "pending").length}</span>}</button></nav>
      {error && <div className="admin-error" role="alert"><WarningCircle size={18} />{error}</div>}
      {view === "usage" ? <UsageDashboard onError={reportError} /> : view === "requests" ? <section className="request-queue">
        <div className="request-queue-heading"><div><p className="eyebrow">Fila de análise</p><h2>Pedidos da equipe</h2></div><span>{requests.filter((request) => request.status === "pending").length} pendentes</span></div>
        {requests.length ? <div className="request-list">{requests.map((request) => <article key={request.id} className={request.status !== "pending" ? "is-resolved" : ""}>
          <div className="request-meta"><span>{request.user_email.slice(0, 1).toUpperCase()}</span><div><strong>{request.user_email}</strong><small>{new Date(request.created_at * 1000).toLocaleDateString("pt-BR")}</small></div><i>{request.status === "pending" ? "Pendente" : request.status === "fulfilled" ? "Concluída" : "Recusada"}</i></div>
          <h3>{request.name}</h3><p>{request.reason}</p>
          {request.status === "pending" && <div className="request-actions"><button className="request-reject" onClick={() => void resolveRequest(request.id, "rejected")}><X size={16} /> Recusar</button><button onClick={() => void resolveRequest(request.id, "fulfilled")}><Check size={16} /> Marcar como concluída</button></div>}
        </article>)}</div> : <div className="usage-empty"><ClipboardText size={28} /><h2>Nenhuma solicitação</h2><p>Os pedidos de novos agentes aparecerão aqui.</p></div>}
      </section> : <div className="admin-grid">
        <section className="admin-users" aria-label="Usuários">
          <div className="admin-section-heading"><UsersThree size={20} /><h2>Pessoas</h2><span>{users.length}</span></div>
          <label className="admin-search"><MagnifyingGlass size={16} /><input aria-label="Buscar pessoa" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por e-mail" /></label>
          <div className="admin-user-list">
          {loading ? <p className="admin-muted">Carregando diretório…</p> : filteredUsers.length ? filteredUsers.map((user) => (
            <button key={user.id} className={`admin-user ${selectedId === user.id ? "is-selected" : ""}`} aria-current={selectedId === user.id ? "true" : undefined} onClick={() => chooseUser(user)}>
              <span>{user.email.slice(0, 1).toUpperCase()}</span>
              <span><strong>{user.email}</strong><small>{user.role === "admin" ? "Administrador" : `${user.agent_ids.length} ${user.agent_ids.length === 1 ? "agente" : "agentes"}`}</small></span>
            </button>
          )) : <p className="admin-empty compact">Nenhuma pessoa encontrada.</p>}
          </div>
        </section>
        <section className="admin-assignments">
          <div className="assignment-heading"><div><p className="eyebrow">Acesso aos agentes</p><h2>{selected?.email ?? "Selecione um usuário"}</h2></div>{selected && <span>{draft.length} de {agents.length}</span>}</div>
          {selected && <>
            {agents.length > 0 && <div className="assignment-toolbar"><p>Defina quais assistentes esta pessoa pode abrir.</p><div><button type="button" onClick={() => { setDraft(agents.map((agent) => agent.id)); setSaved(false); }} disabled={draft.length === agents.length}>Selecionar todos</button><button type="button" onClick={() => { setDraft([]); setSaved(false); }} disabled={!draft.length}>Limpar</button></div></div>}
            <div className="assignment-list">
              {agents.length ? agents.map((agent) => {
                const checked = draft.includes(agent.id);
                return <label key={agent.id} className={`assignment-row ${checked ? "is-checked" : ""}`}><span className="assignment-avatar">{agent.name.slice(0, 1).toUpperCase()}</span><span><strong>{agent.name}</strong><small>{checked ? "Tem acesso" : "Sem acesso"}</small></span><input type="checkbox" checked={checked} onChange={() => { setSaved(false); setDraft((current) => checked ? current.filter((id) => id !== agent.id) : [...current, agent.id]); }} /><i aria-hidden="true">{checked && <Check size={15} weight="bold" />}</i></label>;
              }) : <p className="admin-empty">Ainda não há agentes. Adicione o primeiro abaixo.</p>}
            </div>
            <div className="assignment-actions"><span aria-live="polite">{saved ? <><Check size={15} /> Alterações salvas</> : dirty ? "Há alterações não salvas" : "Tudo atualizado"}</span><div>{dirty && <button className="assignment-reset" onClick={() => { setDraft(selected.agent_ids); setSaved(false); }}>Descartar</button>}<button onClick={() => void save()} disabled={saving || !dirty}>{saving ? "Salvando…" : "Salvar acesso"}</button></div></div>
          </>}
        </section>
        <aside className="admin-create">
          <p className="eyebrow">Catálogo de agentes</p><h2>Adicionar um agente</h2><p>O segredo do Direct Line permanece criptografado no servidor.</p>
          <form onSubmit={(event) => void createAgent(event)}><label>Nome<input name="name" required maxLength={200} /></label><label>Segredo do Direct Line<input name="secret" type="password" required /></label><button type="submit" disabled={creating}><Plus size={17} />{creating ? "Adicionando…" : "Adicionar agente"}</button></form>
        </aside>
      </div>}
    </main>
  );
}
