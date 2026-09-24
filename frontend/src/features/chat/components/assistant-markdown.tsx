import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

/**
 * Renders LLM text parts as Markdown. react-markdown does not interpret raw
 * HTML unless rehype-raw is added, so assistant markup stays as text rather
 * than executing in the page.
 */
const markdownComponents: Components = {
  h1: ({ node: _node, ...props }) => (
    <h1 className="text-heading-lg text-ink-primary" {...props} />
  ),
  h2: ({ node: _node, ...props }) => (
    <h2 className="text-heading-md text-ink-primary" {...props} />
  ),
  h3: ({ node: _node, ...props }) => (
    <h3 className="text-heading-sm text-ink-primary" {...props} />
  ),
  h4: ({ node: _node, ...props }) => (
    <h4 className="text-heading-sm text-ink-primary" {...props} />
  ),
  h5: ({ node: _node, ...props }) => (
    <h5 className="text-label-md text-ink-primary" {...props} />
  ),
  h6: ({ node: _node, ...props }) => (
    <h6 className="text-label-sm text-ink-muted" {...props} />
  ),
  p: ({ node: _node, ...props }) => <p {...props} />,
  ul: ({ node: _node, ...props }) => (
    <ul className="flex list-disc flex-col gap-ds-1 pl-ds-5" {...props} />
  ),
  ol: ({ node: _node, ...props }) => (
    <ol className="flex list-decimal flex-col gap-ds-1 pl-ds-5" {...props} />
  ),
  li: ({ node: _node, ...props }) => <li className="pl-ds-1" {...props} />,
  blockquote: ({ node: _node, ...props }) => (
    <blockquote
      className="border-l-2 border-brand pl-ds-3 text-ink-muted italic"
      {...props}
    />
  ),
  a: ({ node: _node, ...props }) => (
    <a
      className="text-accent-live underline underline-offset-2 hover:text-accent-live-strong"
      target="_blank"
      rel="noreferrer noopener"
      {...props}
    />
  ),
  strong: ({ node: _node, ...props }) => (
    <strong className="font-semibold text-ink-primary" {...props} />
  ),
  em: ({ node: _node, ...props }) => <em {...props} />,
  del: ({ node: _node, ...props }) => <del className="text-ink-muted" {...props} />,
  hr: ({ node: _node, ...props }) => (
    <hr className="border-border-subtle" {...props} />
  ),
  pre: ({ node: _node, ...props }) => (
    <pre
      className="overflow-x-auto rounded-md bg-surface-900 p-ds-3 font-mono text-body-md text-ink-primary"
      {...props}
    />
  ),
  code: ({ node: _node, className, ...props }) => (
    <code
      className={cn(
        "rounded-sm bg-surface-900 px-ds-1 font-mono text-body-sm text-ink-primary",
        className,
      )}
      {...props}
    />
  ),
  table: ({ node: _node, ...props }) => (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-body-md" {...props} />
    </div>
  ),
  thead: ({ node: _node, ...props }) => <thead {...props} />,
  tbody: ({ node: _node, ...props }) => <tbody {...props} />,
  tr: ({ node: _node, ...props }) => (
    <tr className="border-b border-border-subtle" {...props} />
  ),
  th: ({ node: _node, ...props }) => (
    <th className="px-ds-2 py-ds-1 text-left text-label-md text-ink-primary" {...props} />
  ),
  td: ({ node: _node, ...props }) => (
    <td className="px-ds-2 py-ds-1 text-ink-secondary" {...props} />
  ),
  img: ({ node: _node, alt, ...props }) => (
    <img alt={alt ?? ""} className="max-w-full rounded-md" {...props} />
  ),
};

export function AssistantMarkdown({ content }: { content: string }) {
  return (
    <Markdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {content}
    </Markdown>
  );
}
