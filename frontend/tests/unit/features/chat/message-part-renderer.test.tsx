import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MessagePartView } from "@/features/chat/components/message-part-renderer";
import { sampleRanking, sampleTeam } from "@/features/chat/sample-data";
import type { EntityRef, MessagePart } from "@/features/chat/types";

describe("MessagePartView", () => {
  it("renders plain text parts as assistant text", () => {
    const part: MessagePart = { type: "text", content: "Spain won 2-1." };
    render(<MessagePartView part={part} openEntity={null} onOpenEntity={() => {}} />);

    expect(screen.getByText("Spain won 2-1.")).toBeInTheDocument();
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

  it("renders a ranking_widget part and opens the ranking entity", async () => {
    const user = userEvent.setup();
    const onOpenEntity = vi.fn();
    const part: MessagePart = { type: "ranking_widget", data: sampleRanking };
    render(<MessagePartView part={part} openEntity={null} onOpenEntity={onOpenEntity} />);

    expect(screen.getByLabelText(/player ranking: goals/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /view full details/i }));
    expect(onOpenEntity).toHaveBeenCalledWith({ type: "ranking", id: sampleRanking.id });
  });
});
