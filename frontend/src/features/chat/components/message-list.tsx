"use client";

import { useEffect, useRef } from "react";
import { AlertCircle } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AssistantBubble,
  ClarificationNote,
  ReasoningBlock,
  ToolCallIndicator,
  UserBubble,
} from "@/features/chat/components/chat-bubble";
import { MessagePartView } from "@/features/chat/components/message-part-renderer";
import type { ChatMessage, EntityRef } from "@/features/chat/types";

export function MessageList({
  messages,
  openEntity,
  onOpenEntity,
}: {
  messages: ChatMessage[];
  openEntity: EntityRef | null;
  onOpenEntity: (ref: EntityRef, sourceMessageId: string) => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length]);

  return (
    <div className="flex w-full max-w-[720px] flex-col gap-ds-6">
      {messages.map((message) => (
        <div key={message.id} id={message.id} className="flex flex-col gap-ds-6 scroll-mt-6">
          {message.role === "user" ? (
            <UserBubble>
              {message.parts[0]?.type === "text" ? message.parts[0].content : ""}
            </UserBubble>
          ) : (
            <AssistantBubble>
              {message.error ? (
                <Alert variant="destructive" className="max-w-[640px] border-data-negative/40 bg-data-negative/10">
                  <AlertCircle className="size-4" />
                  <AlertDescription className="text-body-md text-ink-primary">
                    {message.error}
                  </AlertDescription>
                </Alert>
              ) : (
                <>
                  <ReasoningBlock
                    content={message.reasoning ?? ""}
                    isStreaming={message.isStreaming}
                  />
                  {message.activeToolName ? (
                    <ToolCallIndicator name={message.activeToolName} />
                  ) : null}
                  {message.parts.map((part, index) => (
                    <MessagePartView
                      key={`${message.id}-${index}`}
                      part={part}
                      openEntity={openEntity}
                      onOpenEntity={(ref) => onOpenEntity(ref, message.id)}
                    />
                  ))}
                  {message.clarification ? (
                    <ClarificationNote>{message.clarification}</ClarificationNote>
                  ) : null}
                </>
              )}
            </AssistantBubble>
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
