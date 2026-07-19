// Escape for HTML built as strings (Leaflet popups); Svelte templates escape themselves.
export const esc = (s: unknown): string =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );

export const cap = (s: string): string =>
  s ? s[0].toUpperCase() + s.slice(1) : "";

export const fmt = (iso: string): string => {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
};

// Whole-day offset between an ISO timestamp and now, measured between local
// midnights (so 0 = the viewer's current calendar day, 1 = tomorrow, -1 =
// yesterday) rather than as a 24-hour window. Shared so the "Today" label and
// the home digest's same-day filter can't drift apart.
export const localDayDiff = (iso: string): number => {
  const d = new Date(iso);
  const now = new Date();
  const dMidnight = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const nowMidnight = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  );
  return Math.round((dMidnight.getTime() - nowMidnight.getTime()) / 86400000);
};

// True when the timestamp falls on the viewer's current local calendar day.
export const isLocalToday = (iso: string): boolean => localDayDiff(iso) === 0;

// Full "when" line for an event card: a natural-language start date relative to
// the viewer's local calendar day, then a seconds-free time (end time appended
// when present). fmt() above is deliberately left alone — the timeseries feature
// uses it for observation timestamps, where relative-day language would mislead.
export const fmtEventDate = (
  startsAt: string,
  endsAt: string | null,
): string => {
  try {
    const start = new Date(startsAt);
    const now = new Date();
    // Diff in whole days between local midnights, so "Today" tracks the calendar
    // day rather than a 24-hour window.
    const days = localDayDiff(startsAt);

    let datePart: string;
    if (days === 0) {
      datePart = "Today";
    } else if (days === 1) {
      datePart = "Tomorrow";
    } else if (days >= 2 && days <= 6) {
      datePart = start.toLocaleDateString(undefined, { weekday: "long" });
    } else {
      // 7+ days out (or past — possible only transiently, since the API filters
      // to upcoming): a formatted date, with the year only when it differs.
      datePart = start.toLocaleDateString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
        ...(start.getFullYear() !== now.getFullYear()
          ? { year: "numeric" }
          : {}),
      });
    }

    const timeOpts: Intl.DateTimeFormatOptions = {
      hour: "numeric",
      minute: "2-digit",
    };
    let timePart = start.toLocaleTimeString(undefined, timeOpts);
    if (endsAt) {
      timePart += ` – ${new Date(endsAt).toLocaleTimeString(undefined, timeOpts)}`;
    }

    return `${datePart} · ${timePart}`;
  } catch {
    return startsAt;
  }
};

export const timeAgo = (iso: string): string => {
  const mins = Math.max(0, (Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return Math.round(mins) + "m ago";
  if (mins < 1440) return Math.round(mins / 60) + "h ago";
  return Math.round(mins / 1440) + "d ago";
};
