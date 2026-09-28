"use client";

import { useEffect, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";
import { X } from "lucide-react";

/** Generic search-result shape every `EntityChipSelector` instance shares. */
export interface EntityOption {
  id: string;
  name: string;
}

const DEBOUNCE_MS = 250;

/**
 * A chip button that opens a small search dropdown for picking one or more
 * entities (matches, players, teams, ...) by free-text name. Opens with the
 * full unfiltered list already loaded (an empty query returns everything --
 * see `searchMatches`) so picking one never requires typing first; typing
 * just narrows it further. Debounces the caller's `searchFn` from the
 * input's own `onChange` handler with a plain `setTimeout` -- not a
 * `useEffect` watching the query state, which this repo's
 * `react-hooks/set-state-in-effect` ESLint rule flags as an error.
 *
 * Stays open across selections until `selected.length` reaches `maxSelected`
 * (for a single-select chip, `maxSelected={1}`, it closes right after the
 * first pick).
 */
export function EntityChipSelector({
  label,
  placeholder,
  maxSelected,
  selected,
  onChange,
  searchFn,
}: {
  label: string;
  placeholder: string;
  maxSelected: number;
  selected: EntityOption[];
  onChange: (next: EntityOption[]) => void;
  searchFn: (query: string) => Promise<EntityOption[]>;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<EntityOption[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const requestIdRef = useRef(0);

  const isFull = selected.length >= maxSelected;

  useEffect(() => {
    if (!open) return;
    function handleMouseDown(event: globalThis.MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, [open]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  function runSearch(value: string) {
    const requestId = ++requestIdRef.current;
    setIsSearching(true);
    searchFn(value)
      .then((options) => {
        if (requestId !== requestIdRef.current) return;
        setResults(options);
        setIsSearching(false);
      })
      .catch(() => {
        if (requestId !== requestIdRef.current) return;
        setResults([]);
        setIsSearching(false);
      });
  }

  function handleQueryChange(value: string) {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runSearch(value), DEBOUNCE_MS);
  }

  function handleOpen() {
    if (isFull) return;
    setOpen(true);
    runSearch(query);
    window.requestAnimationFrame(() => inputRef.current?.focus());
  }

  function handleSelect(option: EntityOption) {
    const next = [...selected, option];
    onChange(next);
    if (next.length >= maxSelected) {
      setOpen(false);
      setQuery("");
      setResults([]);
    }
  }

  function handleClear(event: MouseEvent) {
    event.stopPropagation();
    onChange([]);
  }

  function handleClearKeyDown(event: KeyboardEvent) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    event.stopPropagation();
    onChange([]);
  }

  const chipText = selected.length > 0 ? selected.map((option) => option.name).join(", ") : label;

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={handleOpen}
        className="focus-ring flex h-8 items-center gap-1.5 rounded-full border border-border-strong bg-surface-700 px-ds-3 text-label-md text-ink-secondary hover:bg-surface-800 hover:cursor-pointer"
      >
        <span className="max-w-[220px] truncate">{chipText}</span>
        {selected.length > 0 ? (
          <span
            role="button"
            tabIndex={0}
            onClick={handleClear}
            onKeyDown={handleClearKeyDown}
            aria-label={`Clear ${label}`}
            className="flex size-4 items-center justify-center rounded-full hover:bg-surface-900 hover:cursor-pointer"
          >
            <X className="size-3" aria-hidden />
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute bottom-full left-0 z-30 mb-ds-2 w-[320px] rounded-xl border border-border-strong bg-surface-800 p-ds-2 shadow-[0_24px_60px_rgba(2,3,5,0.6)]">
          <label htmlFor={`entity-chip-search-${label}`} className="sr-only">
            {placeholder}
          </label>
          <input
            id={`entity-chip-search-${label}`}
            ref={inputRef}
            type="text"
            value={query}
            onChange={(event) => handleQueryChange(event.target.value)}
            placeholder={placeholder}
            className="w-full rounded-lg border border-border-subtle bg-surface-900 px-ds-3 py-ds-2 text-body-md text-ink-primary placeholder:text-ink-muted focus:outline-none"
          />
          <div className="mt-ds-2 max-h-[320px] overflow-y-auto overscroll-contain">
            {isSearching ? (
              <div className="px-ds-2 py-ds-2 text-body-sm text-ink-muted">Searching…</div>
            ) : results.length === 0 ? (
              <div className="px-ds-2 py-ds-2 text-body-sm text-ink-muted">No results</div>
            ) : (
              <ul className="flex flex-col gap-ds-1">
                {results.map((option) => (
                  <li key={option.id}>
                    <button
                      type="button"
                      onClick={() => handleSelect(option)}
                      className="w-full rounded-lg px-ds-2 py-ds-2 text-left text-body-sm text-ink-primary hover:bg-surface-700 hover:cursor-pointer"
                    >
                      {option.name}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
