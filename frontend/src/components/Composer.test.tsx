import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Composer } from "./Composer";

describe("Composer", () => {
  it("sends on Enter and clears immediately", async () => {
    let finishSend: (sent: boolean) => void = () => undefined;
    const onSend = vi.fn().mockImplementation(() => new Promise<boolean>((resolve) => { finishSend = resolve; }));
    render(<Composer agentName="Support" disabled={false} sending={false} onSend={onSend} />);
    const input = screen.getByLabelText("Mensagem para Support");
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("Hello", []);
    expect(input).toHaveValue("");
    finishSend(true);
  });

  it("keeps a failed message in the composer", async () => {
    const onSend = vi.fn().mockResolvedValue(false);
    render(<Composer agentName="Support" disabled={false} sending={false} onSend={onSend} />);
    const input = screen.getByLabelText("Mensagem para Support");
    fireEvent.change(input, { target: { value: "Try again" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(onSend).toHaveBeenCalled());
    expect(input).toHaveValue("Try again");
  });
});
