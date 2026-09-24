import type { PlayerClubProfile } from "@/features/chat/types";

export function formatEur(amount: number): string {
  const sign = amount < 0 ? "-" : "";
  const abs = Math.abs(amount);
  if (abs >= 1_000_000) {
    const millions = abs / 1_000_000;
    const text =
      millions >= 10 ? String(Math.round(millions)) : millions.toFixed(1).replace(/\.0$/, "");
    return `${sign}€${text}M`;
  }
  if (abs >= 1_000) {
    return `${sign}€${Math.round(abs / 1_000)}k`;
  }
  return `${sign}€${abs}`;
}

export function formatClubDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  if (!year || !month || !day) {
    return isoDate;
  }
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, day)));
}

function formatFoot(foot: string): string {
  return foot.charAt(0).toUpperCase() + foot.slice(1);
}

export function clubProfileFacts(profile: PlayerClubProfile): { label: string; value: string }[] {
  const facts: { label: string; value: string | null }[] = [
    { label: "Preferred foot", value: profile.preferredFoot ? formatFoot(profile.preferredFoot) : null },
    { label: "Sub-position", value: profile.subPosition },
    { label: "Height", value: profile.heightCm == null ? null : `${profile.heightCm} cm` },
    {
      label: "Date of birth",
      value: profile.dateOfBirth ? formatClubDate(profile.dateOfBirth) : null,
    },
    { label: "Citizenship", value: profile.citizenship },
    { label: "Current club", value: profile.currentClub },
    {
      label: "Market value",
      value: profile.marketValueEur == null ? null : formatEur(profile.marketValueEur),
    },
    {
      label: "Career high",
      value:
        profile.highestMarketValueEur == null ? null : formatEur(profile.highestMarketValueEur),
    },
    {
      label: "International caps",
      value: profile.internationalCaps == null ? null : String(profile.internationalCaps),
    },
    {
      label: "International goals",
      value: profile.internationalGoals == null ? null : String(profile.internationalGoals),
    },
  ];
  return facts.flatMap((fact) => (fact.value == null ? [] : [{ label: fact.label, value: fact.value }]));
}

export function formatTransferMonth(isoDate: string): string {
  const [year, month] = isoDate.split("-").map(Number);
  if (!year || !month) {
    return isoDate;
  }
  return new Intl.DateTimeFormat("en-GB", {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, 1)));
}

export function formatTransferFee(feeEur: number | null): string {
  if (feeEur == null) {
    return "—";
  }
  if (feeEur === 0) {
    return "Free";
  }
  return formatEur(feeEur);
}

export function formatTransferValue(valueEur: number | null): string {
  if (valueEur == null) {
    return "—";
  }
  return formatEur(valueEur);
}
