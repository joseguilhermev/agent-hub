import { ChatCircleDots, Sparkle } from "@phosphor-icons/react";

export function EmptyState({ loading }: { loading?: boolean }) {
  return (
    <section className="empty-state" aria-live="polite">
      <div className="empty-illustration" aria-hidden="true">
        <ChatCircleDots size={42} weight="light" />
        <Sparkle className="empty-spark" size={18} weight="fill" />
      </div>
      <h1>{loading ? "Abrindo uma conversa" : "Escolha um agente"}</h1>
      <p>{loading ? "Conectando você ao especialista certo." : "Comece com o especialista certo."}</p>
      <span className={`quiet-loader ${loading ? "is-active" : ""}`} aria-hidden="true" />
    </section>
  );
}
