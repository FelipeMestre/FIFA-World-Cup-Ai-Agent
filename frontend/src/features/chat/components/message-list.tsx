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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length]);

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
