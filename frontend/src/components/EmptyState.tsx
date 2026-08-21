import { ChatCircleDots, Sparkle } from "@phosphor-icons/react";

export function EmptyState({ loading }: { loading?: boolean }) {
  return (
    <section className="empty-state" aria-live="polite">
      <div className="empty-illustration" aria-hidden="true">
        <ChatCircleDots size={42} weight="light" />
        <Sparkle className="empty-spark" size={18} weight="fill" />
      </div>
      <p className="empty-kicker">Seu time de especialistas</p>
      <h1>{loading ? "Abrindo uma conversa" : "Escolha um agente"}</h1>
      <p className="empty-copy">{loading ? "Conectando você ao especialista certo." : "Selecione um especialista na barra lateral para começar uma conversa focada, com arquivos e contexto no mesmo lugar."}</p>
      {!loading && <div className="empty-guide" aria-label="Como começar"><span><b>01</b> Escolha um agente</span><span><b>02</b> Conte o que precisa</span><span><b>03</b> Continue com contexto</span></div>}
      <span className={`quiet-loader ${loading ? "is-active" : ""}`} aria-hidden="true" />
    </section>
  );
}
