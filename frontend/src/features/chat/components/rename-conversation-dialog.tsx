"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import { CONVERSATION_TITLE_MAX_LENGTH } from "@/features/chat/conversation-id";

export function RenameConversationDialog({
  conversationId,
  currentTitle,
  open,
  onOpenChange,
  onSave,
}: {
  conversationId: string | null;
  currentTitle: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (conversationId: string, title: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState(currentTitle);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setDraft(currentTitle);
      setError(null);
    }
  }, [open, currentTitle]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!conversationId) return;
    const title = draft.trim();
    if (title.length === 0) {
      setError("Title is required");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      await onSave(conversationId, title);
      onOpenChange(false);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Couldn't rename this chat");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-surface-800 text-ink-primary ring-border-strong">
        <form onSubmit={handleSubmit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Rename chat</DialogTitle>
            <DialogDescription className="text-ink-secondary">
              This name appears in the sidebar. You can change it anytime.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="conversation-title">Title</Label>
            <Input
              id="conversation-title"
              value={draft}
              maxLength={CONVERSATION_TITLE_MAX_LENGTH}
              onChange={(event) => setDraft(event.target.value)}
              aria-invalid={error !== null}
              className="h-10 border-border-strong bg-surface-900 text-ink-primary"
            />
            {error && <p className="text-label-sm text-data-negative">{error}</p>}
          </div>
          <DialogFooter className="border-border-subtle bg-surface-800">
            <Button
              type="button"
              variant="outline"
              disabled={isSaving}
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSaving || !conversationId}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
