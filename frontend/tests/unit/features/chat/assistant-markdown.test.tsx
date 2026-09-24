import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AssistantMarkdown } from "@/features/chat/components/assistant-markdown";

describe("AssistantMarkdown", () => {
  it("renders GFM tables and links without executing raw HTML", () => {
    render(
      <AssistantMarkdown
        content={[
          "| Player | Goals |",
          "| --- | --- |",
          "| Yamal | 1 |",
          "",
          "See [FIFA](https://www.fifa.com).",
          "",
          "<script>window.__xss = true</script>",
        ].join("\n")}
      />,
    );

    expect(screen.getByRole("columnheader", { name: "Player" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Yamal" })).toBeInTheDocument();

    const link = screen.getByRole("link", { name: "FIFA" });
    expect(link).toHaveAttribute("href", "https://www.fifa.com");
    expect(link).toHaveAttribute("target", "_blank");

    expect(screen.getByText("<script>window.__xss = true</script>")).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
  });
});
