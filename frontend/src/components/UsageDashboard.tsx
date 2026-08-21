import { ArrowClockwise, ChatCircleDots, Clock, Database, Paperclip, UsersThree } from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { UsageDashboard as UsageData } from "../types";

const number = new Intl.NumberFormat("pt-BR");

function bytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 ** 2).toFixed(1)} MB`;
}

function date(value?: number) {
  return value ? new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short" }).format(value * 1000) : "Nunca";
}

function eventLabel(value: string) {
  return ({ conversation: "Conversa aberta", message: "Mensagem enviada", activity: "Ação enviada", attachment: "Arquivos enviados" } as Record<string, string>)[value] ?? value;
}

export function UsageDashboard({ onError }: { onError: (message?: string) => void }) {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<UsageData>();
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    onError(undefined);
    api.adminUsage(days)
      .then(setData)
      .catch((reason: Error) => onError(reason.message))
      .finally(() => setLoading(false));
  }, [days, onError]);

  useEffect(load, [load]);

  if (loading && !data) return <div className="usage-loading" aria-label="Carregando dados de uso"><i /><i /><i /></div>;
  if (!data) return <div className="usage-empty"><Database size={28} /><h2>Os dados de uso estão indisponíveis</h2><button onClick={load}>Tentar novamente</button></div>;

  const maxInteractions = Math.max(...data.agents.map((agent) => agent.interactions), 1);
  return <section className={`usage-dashboard ${loading ? "is-refreshing" : ""}`}>
    <div className="usage-toolbar">
      <div><p className="eyebrow">Telemetria operacional</p><h2>Uso dos agentes</h2><p>Atividades registradas de forma durável por este hub. Dados de tokens e custos do provedor não estão disponíveis.</p></div>
      <div className="usage-controls"><label>Período<select value={days} onChange={(event) => setDays(Number(event.target.value))}><option value={7}>7 dias</option><option value={30}>30 dias</option><option value={90}>90 dias</option><option value={365}>1 ano</option></select></label><button onClick={load} aria-label="Atualizar dados de uso"><ArrowClockwise size={18} /></button></div>
    </div>
    <div className="usage-metrics">
      <article><ChatCircleDots size={20} /><span>Conversas</span><strong>{number.format(data.total_conversations)}</strong><small>{number.format(data.total_interactions)} eventos monitorados</small></article>
      <article><UsersThree size={20} /><span>Pessoas ativas</span><strong>{number.format(data.active_users)}</strong><small>Em {data.agents.filter((agent) => agent.interactions).length} agentes</small></article>
      <article><Database size={20} /><span>Itens de resposta</span><strong>{number.format(data.output_items)}</strong><small>{number.format(data.input_chars)} caracteres de entrada</small></article>
      <article><Paperclip size={20} /><span>Enviado</span><strong>{bytes(data.attachment_bytes)}</strong><small>Armazenado somente como volume</small></article>
    </div>
    <div className="usage-layout">
      <section className="usage-agents">
        <div className="usage-section-title"><div><p className="eyebrow">Comparação</p><h3>Agentes</h3></div><span>{data.agents.length} no total</span></div>
        {data.agents.length === 0 ? <div className="usage-empty"><Database size={28} /><h2>Nenhum agente conectado</h2><p>Adicione um agente no diretório de acesso para começar.</p></div> : <div className="agent-usage-list">{data.agents.map((agent, index) => <article key={agent.agent_id}>
          <span className="usage-rank">{String(index + 1).padStart(2, "0")}</span>
          <div className="usage-agent-copy"><strong>{agent.agent_name}</strong><small>{agent.users} {agent.users === 1 ? "usuário" : "usuários"} · último uso em {date(agent.last_used_at)}</small><i><span style={{ width: `${agent.interactions / maxInteractions * 100}%` }} /></i></div>
          <div className="usage-agent-stat"><strong>{number.format(agent.interactions)}</strong><small>eventos</small></div>
          <div className="usage-agent-stat"><strong>{agent.average_duration_ms ? `${(agent.average_duration_ms / 1000).toFixed(1)}s` : "—"}</strong><small>resposta média</small></div>
        </article>)}</div>}
      </section>
      <aside className="usage-recent">
        <div className="usage-section-title"><div><p className="eyebrow">Trilha de auditoria</p><h3>Atividade recente</h3></div><Clock size={18} /></div>
        {data.recent.length === 0 ? <div className="usage-empty compact"><p>Nenhum uso registrado neste período.</p></div> : <ol>{data.recent.map((event) => <li key={event.id}><span>{event.agent_name.slice(0, 1).toUpperCase()}</span><div><strong>{eventLabel(event.event_type)}</strong><p>{event.agent_name} · {event.user_email}</p><small>{date(event.created_at)}{event.duration_ms ? ` · ${(event.duration_ms / 1000).toFixed(1)}s` : ""}</small></div></li>)}</ol>}
      </aside>
    </div>
  </section>;
}
