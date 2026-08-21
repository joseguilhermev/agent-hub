import { useEffect, useRef } from "react";

interface Props {
  card: Record<string, unknown>;
  onAction: (kind: "submit" | "execute", data: unknown) => void;
}

function safeOpen(url: string) {
  const parsed = new URL(url, window.location.origin);
  if (!["http:", "https:"].includes(parsed.protocol)) return;
  window.open(parsed.href, "_blank", "noopener,noreferrer");
}

export function AdaptiveCardView({ card, onAction }: Props) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;
    let cancelled = false;
    void import("adaptivecards").then((AdaptiveCards) => {
    if (!container.current || cancelled) return;
    const adaptiveCard = new AdaptiveCards.AdaptiveCard();
    adaptiveCard.hostConfig = new AdaptiveCards.HostConfig({
      fontFamily: "Geist Variable, sans-serif",
      spacing: { small: 8, default: 12, medium: 16, large: 22, extraLarge: 28, padding: 18 },
      containerStyles: {
        default: { backgroundColor: "#ffffff", foregroundColors: {} },
        emphasis: { backgroundColor: "#f7f6f3", foregroundColors: {} },
      },
      actions: { actionsOrientation: 0, actionAlignment: 0, buttonSpacing: 8 },
    });
    adaptiveCard.onExecuteAction = (action) => {
      if (action instanceof AdaptiveCards.OpenUrlAction) {
        if (action.url) safeOpen(action.url);
      } else if (action instanceof AdaptiveCards.ExecuteAction) {
        onAction("execute", { verb: action.verb, data: action.data });
      } else if (action instanceof AdaptiveCards.SubmitAction) {
        onAction("submit", action.data);
      }
    };
    try {
      adaptiveCard.parse(card);
      const rendered = adaptiveCard.render();
      if (rendered) container.current.replaceChildren(rendered);
    } catch {
      container.current.textContent = "Não foi possível exibir este cartão.";
    }
    });
    return () => {
      cancelled = true;
      container.current?.replaceChildren();
    };
  }, [card, onAction]);

  return <div ref={container} className="adaptive-card" />;
}
