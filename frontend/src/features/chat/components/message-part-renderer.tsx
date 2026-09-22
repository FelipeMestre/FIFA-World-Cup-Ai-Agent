import { AssistantText } from "@/features/chat/components/chat-bubble";
import { WidgetCompare } from "@/features/chat/components/widget-compare";
import { WidgetMatch } from "@/features/chat/components/widget-match";
import { WidgetPlayer } from "@/features/chat/components/widget-player";
import { WidgetTeam } from "@/features/chat/components/widget-team";
import type { EntityRef, MessagePart } from "@/features/chat/types";

function isActive(ref: EntityRef, openEntity: EntityRef | null): boolean {
  return openEntity != null && openEntity.type === ref.type && openEntity.id === ref.id;
}

/**
 * Switches on `part.type` to render the right bubble/widget. "team_widget",
 * "match_widget", and "player_widget" arrive live from the backend's
 * `get_team_analysis`, `get_match_analysis`, and `get_player_analysis`
 * tools; "compare_widget" remains forward-compat until its tool exists, and
 * is exercised today only by `/design-preview`.
 */
export function MessagePartView({
  part,
  openEntity,
  onOpenEntity,
}: {
  part: MessagePart;
  openEntity: EntityRef | null;
  onOpenEntity: (ref: EntityRef) => void;
}) {
  switch (part.type) {
    case "text":
      return <AssistantText>{part.content}</AssistantText>;
    case "team_widget": {
      const ref: EntityRef = { type: "team", id: part.data.id };
      return (
        <WidgetTeam
          team={part.data}
          active={isActive(ref, openEntity)}
          onViewDetails={() => onOpenEntity(ref)}
        />
      );
    }
    case "match_widget": {
      const ref: EntityRef = { type: "match", id: part.data.id };
      return (
        <WidgetMatch
          match={part.data}
          active={isActive(ref, openEntity)}
          onViewDetails={() => onOpenEntity(ref)}
        />
      );
    }
    case "player_widget": {
      const ref: EntityRef = { type: "player", id: part.data.id };
      return (
        <WidgetPlayer
          player={part.data}
          active={isActive(ref, openEntity)}
          onViewDetails={() => onOpenEntity(ref)}
        />
      );
    }
    case "compare_widget": {
      const ref: EntityRef = { type: "compare", id: part.data.id };
      return (
        <WidgetCompare
          comparison={part.data}
          active={isActive(ref, openEntity)}
          onViewDetails={() => onOpenEntity(ref)}
        />
      );
    }
    default:
      return null;
  }
}
