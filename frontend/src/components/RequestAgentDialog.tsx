import { CheckCircle, X } from "@phosphor-icons/react";
import { useState } from "react";
import { api } from "../api";

export function RequestAgentDialog({ onClose }: { onClose: () => void }) {
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string>();

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setSending(true);
    setError(undefined);
    try {
      await api.requestAgent(String(data.get("name")), String(data.get("reason")));
      setSent(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível enviar a solicitação.");
    } finally {
      setSending(false);
    }
  };

  return <div className="request-scrim" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <section className="request-panel" role="dialog" aria-modal="true" aria-labelledby="request-title">
      <button className="icon-button request-close" onClick={onClose} aria-label="Fechar"><X size={20} /></button>
      {sent ? <div className="request-success"><CheckCircle size={34} /><p className="eyebrow">Solicitação enviada</p><h2 id="request-title">Seu pedido está em análise</h2><p>O administrador recebeu o contexto e poderá conectar o agente ao seu acesso.</p><button onClick={onClose}>Voltar ao Agent Hub</button></div> : <>
        <p className="eyebrow">Novo especialista</p><h2 id="request-title">Solicite um agente</h2><p className="request-intro">Conte o que você precisa. O administrador avaliará o pedido e fará a conexão com segurança.</p>
        {error && <div className="auth-error" role="alert">{error}</div>}
        <form onSubmit={(event) => void submit(event)}>
          <label>Nome ou função do agente<input name="name" required maxLength={200} placeholder="Ex.: Analista de contratos" autoFocus /></label>
          <label>Como ele ajudaria você?<textarea name="reason" required maxLength={2000} rows={5} placeholder="Descreva a tarefa, quem usará e o resultado esperado." /></label>
          <div><button type="button" className="request-cancel" onClick={onClose}>Cancelar</button><button type="submit" disabled={sending}>{sending ? "Enviando…" : "Enviar solicitação"}</button></div>
        </form>
      </>}
    </section>
  </div>;
}
