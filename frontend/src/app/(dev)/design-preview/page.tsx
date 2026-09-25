"use client";

/**
 * Dev-only visual QA route -- NOT linked from any real nav. Renders all
 * eight widget/panel components against the illustrative sample data from
 * design/artboards/*.dc.html's own `renderVals()` scripts, since the live
 * backend never sends real widget data yet (see design/README.md). This
 * exists purely to visually verify these components before the backend
 * sends this data for real.
 */
import { useState } from "react";

import { AssistantText } from "@/features/chat/components/chat-bubble";
import { PanelCompare } from "@/features/chat/components/panel-compare";
import { PanelMatch } from "@/features/chat/components/panel-match";
import { PanelPlayer } from "@/features/chat/components/panel-player";
import { PanelRanking } from "@/features/chat/components/panel-ranking";
import { PanelTeamCompare } from "@/features/chat/components/panel-team-compare";
import { PanelTeam } from "@/features/chat/components/panel-team";
import { SidePanel } from "@/features/chat/components/side-panel";
import { WidgetCompare } from "@/features/chat/components/widget-compare";
import { WidgetMatch } from "@/features/chat/components/widget-match";
import { WidgetPlayer } from "@/features/chat/components/widget-player";
import { WidgetRanking } from "@/features/chat/components/widget-ranking";
import { WidgetTeamCompare } from "@/features/chat/components/widget-team-compare";
import { WidgetTeam } from "@/features/chat/components/widget-team";
import { useChatPanel } from "@/features/chat/hooks/use-chat-panel";
import {
  sampleComparison,
  sampleMatch,
  samplePlayerForward,
  samplePlayerGoalkeeper,
  sampleRanking,
  sampleTeam,
  sampleTeamComparison,
} from "@/features/chat/sample-data";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-heading-md text-ink-primary">{title}</h2>
      <div className="flex flex-wrap items-start gap-6">{children}</div>
    </section>
  );
}

export default function DesignPreviewPage() {
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const toggle = (key: string) =>
    setActiveKey((prev) => (prev === key ? null : key));
  const demoPanel = useChatPanel();

  return (
    <div className="min-h-dvh bg-surface-950 p-8 text-ink-primary">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-10">
        <div className="flex flex-col gap-1">
          <span className="text-label-sm text-ink-muted">
            Dev-only · not linked from real nav
          </span>
          <h1 className="text-display-md">Design preview</h1>
          <p className="text-body-md text-ink-secondary">
            All four widgets and their matching side panels, rendered with the
            illustrative sample data from each artboard&apos;s own renderVals()
            script. Click &quot;View full details&quot; to toggle a
            widget&apos;s active/&quot;Showing in panel&quot; state.
          </p>
        </div>

        <Section title="Assistant markdown">
          <AssistantText>{`## Spain vs Germany

They won **2-1**. Key notes:

- Pedri controlled midfield
- Olmo finished the winner

See [FIFA](https://www.fifa.com).`}</AssistantText>
        </Section>

        <Section title="Widgets — 640px desktop / full width mobile">
          <WidgetTeam
            team={sampleTeam}
            active={activeKey === "team"}
            onViewDetails={() => toggle("team")}
          />
          <WidgetMatch
            match={sampleMatch}
            active={activeKey === "match"}
            onViewDetails={() => toggle("match")}
          />
          <WidgetPlayer
            player={samplePlayerGoalkeeper}
            active={activeKey === "player"}
            onViewDetails={() => toggle("player")}
          />
          <WidgetCompare
            comparison={sampleComparison}
            active={activeKey === "compare"}
            onViewDetails={() => toggle("compare")}
          />
          <WidgetRanking
            ranking={sampleRanking}
            active={activeKey === "ranking"}
            onViewDetails={() => toggle("ranking")}
          />
          <WidgetTeamCompare
            comparison={sampleTeamComparison}
            active={activeKey === "team-compare"}
            onViewDetails={() => toggle("team-compare")}
          />
        </Section>

        <Section title="Panels — 560px desktop">
          <div className="h-[1360px] w-[560px] overflow-y-auto rounded-lg border border-border-strong">
            <PanelTeam
              team={sampleTeam}
              fromMessage="How did Argentina perform defensively?"
              onClose={() => {}}
              onJumpToMessage={() => {}}
            />
          </div>
          <div className="h-[1360px] w-[560px] overflow-y-auto rounded-lg border border-border-strong">
            <PanelMatch
              match={sampleMatch}
              fromMessage="Show me the France vs Spain semifinal breakdown"
              onClose={() => {}}
              onJumpToMessage={() => {}}
            />
          </div>
          <div className="h-[1360px] w-[560px] overflow-y-auto rounded-lg border border-border-strong">
            <PanelPlayer
              player={samplePlayerForward}
              fromMessage="What about Mbappé's tournament?"
              onClose={() => {}}
              onJumpToMessage={() => {}}
            />
          </div>
          <div className="h-[1360px] w-[560px] overflow-y-auto rounded-lg border border-border-strong">
            <PanelCompare
              comparison={sampleComparison}
              fromMessage="Compare Messi vs Mbappé"
              onClose={() => {}}
              onJumpToMessage={() => {}}
            />
          </div>
          <div className="h-[1360px] w-[560px] overflow-y-auto rounded-lg border border-border-strong">
            <PanelRanking
              ranking={sampleRanking}
              fromMessage="Rank the forwards by goals"
              onClose={() => {}}
              onJumpToMessage={() => {}}
            />
          </div>
          <div className="h-[1360px] w-[560px] overflow-y-auto rounded-lg border border-border-strong">
            <PanelTeamCompare
              comparison={sampleTeamComparison}
              fromMessage="Compare Argentina and Brazil"
              onClose={() => {}}
              onJumpToMessage={() => {}}
            />
          </div>
        </Section>

        <Section title="Panels — mobile sheet (isSheet, no collapse control)">
          <div className="h-[700px] w-[390px] overflow-y-auto rounded-lg border border-border-strong">
            <PanelTeam
              team={sampleTeam}
              isSheet
              fromMessage="How did Argentina perform defensively?"
              onClose={() => {}}
              onJumpToMessage={() => {}}
            />
          </div>
        </Section>

        <section className="flex flex-col gap-4">
          <h2 className="text-heading-md text-ink-primary">
            Live SidePanel — desktop drawer / mobile sheet switch
          </h2>
          <p className="max-w-[640px] text-body-md text-ink-secondary">
            The actual SidePanel component (not a static copy): a 64px toggle
            rail plus 560px of content
            at desktop widths, a full-height sheet over a scrim with a grab
            handle at mobile widths, switching via the same media query the real
            chat page uses. Resize the viewport to see it switch.
          </p>
          <button
            type="button"
            onClick={() =>
              demoPanel.openEntity(
                { type: "team", id: sampleTeam.id },
                "demo-message",
              )
            }
            className="focus-ring w-fit rounded-md border border-border-strong bg-surface-800 px-4 py-2.5 text-label-md text-ink-primary hover:bg-surface-700"
          >
            Open Argentina in the side panel
          </button>
          <button
            type="button"
            onClick={() =>
              demoPanel.openEntity(
                { type: "team_compare", id: sampleTeamComparison.id },
                "demo-compare",
              )
            }
            className="focus-ring w-fit rounded-md border border-border-strong bg-surface-800 px-4 py-2.5 text-label-md text-ink-primary hover:bg-surface-700"
          >
            Open Argentina vs Brazil in the side panel
          </button>
        </section>
      </div>

      <SidePanel
        panelState={demoPanel.state}
        resolveEntity={(ref) =>
          ref.type === "team_compare" ? sampleTeamComparison : sampleTeam
        }
        fromMessagePreview="How did Argentina perform defensively?"
        onCollapse={demoPanel.collapse}
        onExpand={demoPanel.expand}
        onClose={demoPanel.close}
        onJumpToMessage={demoPanel.jumpToMessage}
      />
    </div>
  );
}
