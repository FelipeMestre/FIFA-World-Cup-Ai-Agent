import type { PlayerSeasonStat } from "@/features/chat/types";

const COLUMNS = [
  { key: "appearances", label: "App" },
  { key: "minutes", label: "Min" },
  { key: "goals", label: "G" },
  { key: "assists", label: "A" },
  { key: "yellowCards", label: "Y" },
  { key: "redCards", label: "R" },
] as const satisfies ReadonlyArray<{ key: keyof PlayerSeasonStat; label: string }>;

interface SeasonGroup {
  season: string;
  team: string | null;
  rows: PlayerSeasonStat[];
}

function groupBySeason(seasons: PlayerSeasonStat[]): SeasonGroup[] {
  const groups: SeasonGroup[] = [];
  for (const row of seasons) {
    const current = groups.at(-1);
    if (current?.season === row.season && current.team === row.team) {
      current.rows.push(row);
      continue;
    }
    groups.push({ season: row.season, team: row.team, rows: [row] });
  }
  return groups;
}

/** Club career in the player side panel: year and club, then indented competitions. */
export function PlayerSeasonTable({ seasons }: { seasons: PlayerSeasonStat[] }) {
  if (seasons.length === 0) {
    return null;
  }
  const groups = groupBySeason(seasons);

  return (
    <section className="flex shrink-0 flex-col gap-3 p-5">
      <h3 className="text-heading-sm">Club career</h3>
      <div className="max-h-96 overflow-auto rounded-lg border border-border-strong">
        <table className="w-full border-separate border-spacing-0 bg-surface-800">
          <thead>
            <tr className="h-9">
              <th
                scope="col"
                className="sticky top-0 z-10 border-b border-border-strong bg-surface-800 px-3 text-left text-label-sm text-ink-muted"
              >
                Competition
              </th>
              {COLUMNS.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className="sticky top-0 z-10 border-b border-border-strong bg-surface-800 px-2 text-right text-label-sm text-ink-muted last:pr-3"
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {groups.map((group) => (
              <SeasonGroupRows key={`${group.season}-${group.team ?? ""}`} group={group} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SeasonGroupRows({ group }: { group: SeasonGroup }) {
  const heading = group.team ? `${group.season} · ${group.team}` : group.season;
  return (
    <>
      <tr className="h-11">
        <th
          scope="colgroup"
          className="border-b border-border-strong bg-surface-700 px-3 text-left text-heading-sm text-ink-primary"
        >
          {heading}
        </th>
        {COLUMNS.map((column) => (
          <td key={column.key} className="border-b border-border-strong bg-surface-700" />
        ))}
      </tr>
      {group.rows.map((row) => (
        <tr
          key={`${row.season}-${row.competitionId}`}
          className="h-10"
        >
          <th
            scope="row"
            className="max-w-40 truncate border-b border-border-subtle bg-surface-800 py-2 pr-3 pl-7 text-left text-body-sm font-normal text-ink-secondary"
            title={row.competition}
          >
            {row.competition}
          </th>
          {COLUMNS.map((column) => (
            <td
              key={column.key}
              className="border-b border-border-subtle bg-surface-800 px-2 text-right text-body-sm text-ink-muted last:pr-3"
            >
              {row[column.key]}
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
