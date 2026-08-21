import { ArrowSquareOut, File, SignIn } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import type { Activity, Attachment, CardAction, LocalMessage } from "../types";
import { AdaptiveCardView } from "./AdaptiveCardView";

interface Props {
  activity: LocalMessage;
  agentName: string;
  onTextAction: (text: string) => void;
  onActivity: (activity: Activity) => void;
  onStreamingComplete?: () => void;
}

function StreamingText({ text, active, onComplete }: { text: string; active: boolean; onComplete?: () => void }) {
  const reduceMotion = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const [visibleLength, setVisibleLength] = useState(active && !reduceMotion ? 0 : text.length);
  const streaming = visibleLength < text.length;

  useEffect(() => {
    if (!active) {
      setVisibleLength(text.length);
      return;
    }
    if (reduceMotion) {
      setVisibleLength(text.length);
      onComplete?.();
      return;
    }

    const chunkSize = Math.max(1, Math.ceil(text.length / 100));
    const timer = window.setInterval(() => {
      setVisibleLength((current) => Math.min(text.length, current + chunkSize));
    }, 24);
    return () => window.clearInterval(timer);
  }, [active, onComplete, reduceMotion, text]);

  useEffect(() => {
    if (active && !reduceMotion && !streaming) onComplete?.();
  }, [active, onComplete, reduceMotion, streaming]);

  return (
    <div className={`message-copy${streaming ? " message-copy-streaming" : ""}`}>
      <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{text.slice(0, visibleLength)}</ReactMarkdown>
    </div>
  );
}

function safeUrl(url?: string): string | undefined {
  if (!url) return;
  try {
    const parsed = new URL(url, location.origin);
    return ["http:", "https:", "data:"].includes(parsed.protocol) ? parsed.href : undefined;
  } catch {
    return;
  }
}

function formatFileSize(size?: number): string | undefined {
  if (size === undefined) return;
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function CardAttachment({ attachment, onActivity }: { attachment: Attachment; onActivity: Props["onActivity"] }) {
  const contentType = attachment.contentType ?? "";
  const content = attachment.content ?? {};
  if (contentType === "application/vnd.microsoft.card.adaptive") {
    return (
      <AdaptiveCardView
        card={content}
        onAction={(kind, data) =>
          onActivity(
            kind === "execute"
              ? {
                  type: "invoke",
                  name: "adaptiveCard/action",
                  value: {
                    action: {
                      type: "Action.Execute",
                      ...(data as Record<string, unknown>),
                    },
                  },
                }
              : { type: "message", value: data },
          )
        }
      />
    );
  }
  if (["application/vnd.microsoft.card.hero", "application/vnd.microsoft.card.thumbnail"].includes(contentType)) {
    const buttons = (content.buttons as CardAction[] | undefined) ?? [];
    const images = (content.images as { url?: string; alt?: string }[] | undefined) ?? [];
    return (
      <div className="content-card rich-card">
        {safeUrl(images[0]?.url) && <img src={safeUrl(images[0].url)} alt={images[0].alt ?? ""} />}
        <div className="rich-card-copy">
          {typeof content.title === "string" && <strong>{content.title}</strong>}
          {typeof content.subtitle === "string" && <small>{content.subtitle}</small>}
          {typeof content.text === "string" && <p>{content.text}</p>}
          {buttons.length > 0 && <div className="suggested-actions">{buttons.map((button, index) => {
            const href = button.type === "openUrl" ? safeUrl(String(button.value ?? "")) : undefined;
            return href
              ? <a key={index} href={href} target="_blank" rel="noreferrer">{button.title ?? "Abrir"}</a>
              : <button key={index} onClick={() => onActivity({ type: "message", text: String(button.value ?? button.title ?? "") })}>{button.title ?? "Continuar"}</button>;
          })}</div>}
        </div>
      </div>
    );
  }
  if (contentType === "application/vnd.microsoft.card.oauth") {
    const signIn = content.buttons as CardAction[] | undefined;
    const href = safeUrl(String(signIn?.[0]?.value ?? ""));
    return (
      <div className="content-card oauth-card">
        <SignIn size={22} />
        <div><strong>{String(content.title ?? "É necessário entrar")}</strong><p>{String(content.text ?? "Continue com segurança para entrar.")}</p></div>
        {href && <a href={href} target="_blank" rel="noreferrer">Continuar <ArrowSquareOut size={16} /></a>}
      </div>
    );
  }
  const url = safeUrl(attachment.contentUrl);
  if (contentType.startsWith("image/") && url) {
    return <a className="image-attachment" href={url} target="_blank" rel="noreferrer"><img src={url} alt={attachment.name ?? "Anexo do agente"} /></a>;
  }
  if (contentType.startsWith("audio/") && url) return <audio className="media-attachment" controls src={url} />;
  if (contentType.startsWith("video/") && url) return <video className="media-attachment" controls src={url} />;
  if (url) {
    return <a className="file-attachment" href={url} target="_blank" rel="noreferrer"><File size={21} /><span>{attachment.name ?? "Baixar anexo"}</span><ArrowSquareOut size={16} /></a>;
  }
  return <div className="file-attachment"><File size={21} /><span>{attachment.name ?? contentType ?? "Anexo"}{attachment.size !== undefined && <small>{formatFileSize(attachment.size)}</small>}</span></div>;
}

export function ActivityView({ activity, agentName, onTextAction, onActivity, onStreamingComplete }: Props) {
  if (activity.type !== "message") return null;
  const isUser = activity.role === "user";
  const actions = activity.suggestedActions?.actions ?? [];
  return (
    <article className={`message ${isUser ? "message-user" : "message-agent"}`}>
      {!isUser && <span className="message-avatar" aria-hidden="true">{agentName.slice(0, 1).toUpperCase()}</span>}
      <div className="message-body">
        <div className="message-meta">
          <strong>{isUser ? "Você" : agentName}</strong>
          {activity.timestamp && <time>{new Date(activity.timestamp).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</time>}
          {activity.status === "failed" && <span className="message-error">Não enviada</span>}
        </div>
        {activity.text && <StreamingText text={activity.text} active={!isUser && Boolean(activity.streaming)} onComplete={onStreamingComplete} />}
        {activity.attachments?.map((attachment, index) => <CardAttachment key={`${attachment.contentType}-${index}`} attachment={attachment} onActivity={onActivity} />)}
        {actions.length > 0 && (
          <div className="suggested-actions" aria-label="Respostas sugeridas">
            {actions.map((action, index) => (
              <button key={`${action.title}-${index}`} onClick={() => onTextAction(String(action.value ?? action.title ?? ""))}>{action.title ?? String(action.value)}</button>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
