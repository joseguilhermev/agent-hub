import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ActivityView } from "./ActivityView";

describe("ActivityView", () => {
  afterEach(() => vi.useRealTimers());

  it("does not render protocol events as blank messages", () => {
    const { container } = render(<ActivityView activity={{ localId: "event", role: "agent", type: "event", name: "turn.complete" }} agentName="Support" onTextAction={() => undefined} onActivity={() => undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders rich text and sends a suggested action", () => {
    const onTextAction = vi.fn();
    render(<ActivityView activity={{ localId: "1", role: "agent", type: "message", text: "**Key finding**", suggestedActions: { actions: [{ type: "imBack", title: "Ask more", value: "Explain" }] } }} agentName="Support" onTextAction={onTextAction} onActivity={() => undefined} />);
    expect(screen.getByText("Key finding")).toHaveProperty("tagName", "STRONG");
    fireEvent.click(screen.getByRole("button", { name: "Ask more" }));
    expect(onTextAction).toHaveBeenCalledWith("Explain");
  });

  it("rejects unsafe attachment links", () => {
    render(<ActivityView activity={{ localId: "2", role: "agent", type: "message", attachments: [{ contentType: "text/plain", contentUrl: "javascript:alert(1)", name: "Unsafe" }] }} agentName="Support" onTextAction={() => undefined} onActivity={() => undefined} />);
    expect(screen.queryByRole("link", { name: /unsafe/i })).not.toBeInTheDocument();
  });

  it("progressively reveals a newly received agent message", () => {
    vi.useFakeTimers();
    const onStreamingComplete = vi.fn();
    const { container } = render(<ActivityView activity={{ localId: "3", role: "agent", type: "message", text: "Streaming response", streaming: true }} agentName="Support" onTextAction={() => undefined} onActivity={() => undefined} onStreamingComplete={onStreamingComplete} />);

    expect(screen.queryByText("Streaming response")).not.toBeInTheDocument();
    expect(container.querySelector(".message-copy-streaming")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByText("Streaming response")).toBeInTheDocument();
    expect(onStreamingComplete).toHaveBeenCalled();
  });
});
