"use client";

import { useEffect, useRef } from "react";
import { AlertCircle } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AnswerActions,
  AssistantBubble,
  ClarificationNote,
  ReasoningBlock,
  ToolCallIndicator,
  UserBubble,
} from "@/features/chat/components/chat-bubble";
import { MessagePartView } from "@/features/chat/components/message-part-renderer";
import type { ChatMessage, EntityRef } from "@/features/chat/types";

interface Turn {
  id: string;
  question?: ChatMessage;
  answer?: ChatMessage;
}

/**
 * HomeActive.dc.html renders the thread as question/answer turns rather than
 * a flat message list, which is what gives it the wider gap between turns
 * than within one. A user message opens a turn; the assistant reply that
 * follows closes it.
 */
function groupIntoTurns(messages: ChatMessage[]): Turn[] {
  const turns: Turn[] = [];
  for (const message of messages) {
    const current = turns[turns.length - 1];
    if (message.role === "user" || !current || current.answer) {
      turns.push({
        id: message.id,
        question: message.role === "user" ? message : undefined,
        answer: message.role === "user" ? undefined : message,
      });
    } else {
      current.answer = message;
    }
  }
  return turns;
}

function textOf(message: ChatMessage | undefined): string {
  if (!message) return "";
  return message.parts
    .map((part) => (part.type === "text" ? part.content : ""))
    .join("")
    .trim();
}

/**
 * How close to the bottom (in px) counts as "at the bottom" -- both for
 * deciding the user hasn't scrolled away, and for deciding a manual scroll
 * back down re-engages auto-follow.
 */
const STICK_TO_BOTTOM_THRESHOLD_PX = 48;

export function MessageList({
  messages,
  openEntity,
  onOpenEntity,
  onRegenerate,
}: {
  messages: ChatMessage[];
  openEntity: EntityRef | null;
  onOpenEntity: (ref: EntityRef, sourceMessageId: string) => void;
  onRegenerate?: (question: string) => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  // Whether the view should keep following new content. Starts true (land
  // at the bottom of an existing thread / follow a fresh reply), flips to
  // false the moment the user scrolls away from the bottom, and only flips
  // back once they scroll back down themselves -- sending another message
  // does NOT re-enable it, so a reply that streams in while the user is
  // reading something above never yanks them back down.
  const stickToBottomRef = useRef(true);

  useEffect(() => {
    const container = bottomRef.current?.closest<HTMLElement>(
      "[data-chat-scroll-container]",
    );
    if (!container) return;

    const handleScroll = () => {
      const distanceFromBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight;
      stickToBottomRef.current = distanceFromBottom <= STICK_TO_BOTTOM_THRESHOLD_PX;
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  // Depends on `messages` itself, not `messages.length` -- a streaming
  // reply's content grows in place (same array length, new array/message
  // references on every delta, since state updates are immutable), so
  // keying off length alone only scrolls once per turn, at the moment the
  // empty draft message is appended. Only follows when the user hasn't
  // scrolled away (see `stickToBottomRef` above).
  useEffect(() => {
    if (!stickToBottomRef.current) return;
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  return (
    <div className="flex w-full flex-col gap-9">
      {groupIntoTurns(messages).map((turn) => {
        const answer = turn.answer;
        const questionText = textOf(turn.question);

        return (
          <div key={turn.id} className="flex flex-col gap-5">
            {turn.question ? (
              <div id={turn.question.id} className="scroll-mt-6">
                <UserBubble>{questionText}</UserBubble>
              </div>
            ) : null}

            {answer ? (
              <div id={answer.id} className="scroll-mt-6">
                <AssistantBubble>
                  {answer.error ? (
                    <Alert
                      variant="destructive"
                      className="max-w-[640px] border-data-negative/40 bg-data-negative/10"
                    >
                      <AlertCircle className="size-4" />
                      <AlertDescription className="text-body-md text-ink-primary">
                        {answer.error}
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <>
                      <ReasoningBlock
                        content={answer.reasoning ?? ""}
                        isStreaming={answer.isStreaming}
                      />
                      {answer.activeToolName ? (
                        <ToolCallIndicator name={answer.activeToolName} />
                      ) : null}
                      {answer.parts.map((part, index) => (
                        <MessagePartView
                          key={`${answer.id}-${index}`}
                          part={part}
                          openEntity={openEntity}
                          onOpenEntity={(ref) => onOpenEntity(ref, answer.id)}
                        />
                      ))}
                      {answer.clarification ? (
                        <ClarificationNote>{answer.clarification}</ClarificationNote>
                      ) : null}
                      {!answer.isStreaming ? (
                        <AnswerActions
                          answerText={textOf(answer)}
                          onRegenerate={
                            onRegenerate && questionText
                              ? () => onRegenerate(questionText)
                              : undefined
                          }
                        />
                      ) : null}
                    </>
                  )}
                </AssistantBubble>
              </div>
            ) : null}
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
