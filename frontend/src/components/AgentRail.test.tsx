import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AgentRail } from "./AgentRail";

const agents = [
  { id: "support", name: "Support" },
  { id: "sales", name: "Sales" },
];

describe("AgentRail", () => {
  it("lists agents and selects one", () => {
    const onSelect = vi.fn();
    render(<AgentRail agents={agents} activeId="support" mobileOpen={false} onClose={() => undefined} onSelect={onSelect} onNew={() => undefined} onRequest={() => undefined} />);
    expect(screen.getByRole("img", { name: "Grant Thornton" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /sales/i }));
    expect(onSelect).toHaveBeenCalledWith(agents[1]);
    expect(screen.getByLabelText("Selecionado")).toBeInTheDocument();
  });
});
