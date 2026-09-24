import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MessagePartView } from "@/features/chat/components/message-part-renderer";
import { sampleTeam } from "@/features/chat/sample-data";
import type { EntityRef, MessagePart } from "@/features/chat/types";

describe("MessagePartView", () => {
  it("renders plain text parts as assistant text", () => {
    const part: MessagePart = { type: "text", content: "Spain won 2-1." };
    render(<MessagePartView part={part} openEntity={null} onOpenEntity={() => {}} />);

    expect(screen.getByText("Spain won 2-1.")).toBeInTheDocument();
  });

  it("renders markdown in text parts (headings, emphasis, lists)", () => {
    const part: MessagePart = {
      type: "text",
      content: "## Spain\n\nThey won **2-1**.\n\n- Pedri\n- Olmo",
    };
    render(<MessagePartView part={part} openEntity={null} onOpenEntity={() => {}} />);

    expect(screen.getByRole("heading", { level: 2, name: "Spain" })).toBeInTheDocument();
    expect(screen.getByText("2-1").tagName).toBe("STRONG");
    expect(screen.getByText("Pedri").tagName).toBe("LI");
    expect(screen.getByText("Olmo").tagName).toBe("LI");
  });

  it("renders a team_widget part as the team widget, showing 'View full details' when inactive", () => {
    const part: MessagePart = { type: "team_widget", data: sampleTeam };
    render(<MessagePartView part={part} openEntity={null} onOpenEntity={() => {}} />);

    expect(screen.getByText(sampleTeam.name)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view full details/i })).toBeInTheDocument();
  });

  it("shows 'Showing in panel' instead when the widget's entity is the open one", () => {
    const part: MessagePart = { type: "team_widget", data: sampleTeam };
    const openEntity: EntityRef = { type: "team", id: sampleTeam.id };
    render(<MessagePartView part={part} openEntity={openEntity} onOpenEntity={() => {}} />);

    expect(screen.getByRole("button", { name: /showing in panel/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /view full details/i })).not.toBeInTheDocument();
  });

  it("calls onOpenEntity with the widget's type and id when 'View full details' is clicked", async () => {
    const user = userEvent.setup();
    const onOpenEntity = vi.fn();
    const part: MessagePart = { type: "team_widget", data: sampleTeam };
    render(<MessagePartView part={part} openEntity={null} onOpenEntity={onOpenEntity} />);

    await user.click(screen.getByRole("button", { name: /view full details/i }));

    expect(onOpenEntity).toHaveBeenCalledWith({ type: "team", id: sampleTeam.id });
  });
});
