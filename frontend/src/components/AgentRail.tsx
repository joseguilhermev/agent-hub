import { ChatCircle, Check, Plus, Sparkle, X } from "@phosphor-icons/react";
import type { Agent } from "../types";

interface Props {
  agents: Agent[];
  activeId?: string;
  mobileOpen: boolean;
  onClose: () => void;
  onSelect: (agent: Agent) => void;
  onNew: () => void;
  onRequest: () => void;
}

function AgentRow({
  agent,
  selected,
  onSelect,
}: {
  agent: Agent;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button className={`agent-row ${selected ? "is-selected" : ""}`} onClick={onSelect}>
      <span className="agent-avatar" aria-hidden="true">
        {agent.name.slice(0, 1).toUpperCase()}
      </span>
      <span className="agent-row-copy">
        <strong>{agent.name}</strong>
        <small><span className="status-dot" /> Disponível</small>
      </span>
      {selected && <Check size={19} weight="bold" aria-label="Selecionado" />}
    </button>
  );
}

export function AgentRail({ agents, activeId, mobileOpen, onClose, onSelect, onNew, onRequest }: Props) {
  return (
    <>
      <button
        className={`sheet-scrim ${mobileOpen ? "is-visible" : ""}`}
        aria-label="Fechar menu de agentes"
        onClick={onClose}
      />
      <aside className={`agent-rail ${mobileOpen ? "is-open" : ""}`} aria-label="Agentes">
        <div className="rail-brand">
          <div className="brand-lockup">
            <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
            <span><strong>Agent Hub</strong><small>workspace</small></span>
          </div>
          <button className="icon-button rail-close" onClick={onClose} aria-label="Fechar menu de agentes">
            <X size={22} />
          </button>
        </div>
        <div className="rail-content">
          <div className="rail-heading"><p className="rail-label">Seus agentes</p><span>{String(agents.length).padStart(2, "0")}</span></div>
          <div className="agent-list">
            {agents.map((agent) => (
              <AgentRow
                key={agent.id}
                agent={agent}
                selected={agent.id === activeId}
                onSelect={() => onSelect(agent)}
              />
            ))}
          </div>
        </div>
        <button className="request-agent" onClick={onRequest}><Sparkle size={18} /> Solicitar novo agente</button>
        <button className="new-conversation" onClick={onNew} disabled={!activeId}>
          {activeId ? <Plus size={20} /> : <ChatCircle size={20} />}
          Nova conversa
        </button>
      </aside>
    </>
  );
}
