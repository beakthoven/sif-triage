/* The lazy chart chunk. THIS module (and therefore recharts) is imported only
 * via dynamic import() from index.tsx, so recharts never lands in the initial
 * bundle. recharts is the one sanctioned chart library
 * (frontend-stack-decision §3) — chosen because ErrorBar makes Wilson CI
 * whiskers first-class.
 * Motion policy: isAnimationActive={false} on every animated element — charts
 * clarify state change, they never decorate (design-system-spec §1.3). */

import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  ErrorBar,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Lang } from "@/lib/phrasebook";
import {
  fmtPer100,
  formatBucketLabel,
  type DensityStat,
  type Granularity,
  type TrendBucket,
} from "./lib/stats";
import { MONTHS, t } from "./phrases";

/* Token usage: flagged rate (the quantity being judged) is the amber
 * --verdict-high everywhere; report volume is slate --verdict-uncertain;
 * furniture (grid/axes) uses the border/content tokens. No ad-hoc colors. */

/* ---- Time series: bars = report counts, line = flagged per 100 with 95%
 * Wilson CI whiskers (ErrorBar, direction y). Rate is null for empty periods —
 * the line breaks instead of inventing a 0%. ---- */

export function TimeSeriesChart({
  buckets,
  granularity,
  lang,
}: {
  buckets: TrendBucket[];
  granularity: Granularity;
  lang: Lang;
}) {
  const months = MONTHS[lang];
  const data = buckets.map((b) => ({ ...b, label: formatBucketLabel(b, granularity, months) }));
  return (
    <div role="img" aria-label={t(lang, "trendSub")} className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 12, fill: "var(--content-secondary)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--border-strong)" }}
            minTickGap={18}
          />
          <YAxis
            yAxisId="rate"
            domain={[0, 100]}
            width={34}
            tick={{ fontSize: 12, fill: "var(--content-secondary)" }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            yAxisId="n"
            orientation="right"
            width={30}
            tick={{ fontSize: 12, fill: "var(--content-muted)" }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            isAnimationActive={false}
            cursor={false}
            content={<TrendTooltip lang={lang} granularity={granularity} months={months} />}
          />
          <Bar
            yAxisId="n"
            dataKey="n"
            name={t(lang, "reportsAxis")}
            fill="var(--verdict-uncertain-fill)"
            fillOpacity={0.3}
            radius={[2, 2, 0, 0]}
            isAnimationActive={false}
          />
          <Line
            yAxisId="rate"
            type="monotone"
            dataKey="ratePer100"
            name={t(lang, "rateAxis")}
            stroke="var(--verdict-high-fill)"
            strokeWidth={2}
            dot={{ r: 2, fill: "var(--verdict-high-fill)" }}
            connectNulls={false}
            isAnimationActive={false}
          >
            <ErrorBar
              dataKey="ciErr"
              direction="y"
              width={4}
              strokeWidth={1.25}
              stroke="var(--content-secondary)"
              isAnimationActive={false}
            />
          </Line>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ---- Density comparison: top-ranked entities, flag rate per 100 with 95%
 * Wilson CI whiskers (ErrorBar, direction x in vertical layout). This is the
 * comparative visualization the stack decision adopted recharts for. ---- */

const DENSITY_CHART_ROWS = 12;

export function DensityChart({
  rows,
  lang,
}: {
  rows: DensityStat[];
  lang: Lang;
}) {
  const top = rows.slice(0, DENSITY_CHART_ROWS);
  if (top.length === 0) return null;
  const data = top.map((r) => ({
    key: r.key,
    rate: r.rate * 100,
    ciErr: [(r.rate - r.ciLow) * 100, (r.ciHigh - r.rate) * 100] as [number, number],
    n: r.nReports,
    flagged: r.nFlagged,
  }));
  return (
    <div role="img" aria-label={t(lang, "densityChartTitle")}>
      <p className="text-caption font-medium tracking-wide text-content-secondary uppercase">
        {t(lang, "densityChartTitle")}
      </p>
      <ResponsiveContainer width="100%" height={top.length * 34 + 48}>
        <BarChart layout="vertical" data={data} margin={{ top: 4, right: 24, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="var(--border-subtle)" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={{ fontSize: 12, fill: "var(--content-secondary)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--border-strong)" }}
          />
          <YAxis
            type="category"
            dataKey="key"
            width={200}
            tick={{ fontSize: 12, fill: "var(--content-secondary)" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: string) => (value.length > 26 ? `${value.slice(0, 25)}…` : value)}
          />
          <Tooltip
            isAnimationActive={false}
            cursor={false}
            content={<DensityTooltip lang={lang} />}
          />
          <Bar
            dataKey="rate"
            name={t(lang, "rateAxis")}
            fill="var(--verdict-uncertain-fill)"
            radius={[0, 2, 2, 0]}
            isAnimationActive={false}
          >
            <ErrorBar
              dataKey="ciErr"
              direction="x"
              width={4}
              strokeWidth={1.25}
              stroke="var(--content-primary)"
              isAnimationActive={false}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ---- Custom tooltips (token-styled; localized strings from the phrasebook). ---- */

interface TipPayload<T> {
  active?: boolean;
  label?: string | number;
  payload?: ReadonlyArray<{ payload?: T }>;
}

function TrendTooltip({
  active,
  payload,
  lang,
  granularity,
  months,
}: TipPayload<TrendBucket> & { lang: Lang; granularity: Granularity; months: string[] }) {
  if (!active || !payload || payload.length === 0) return null;
  const b = payload[0]?.payload;
  if (!b) return null;
  return (
    <div className="rounded-md border border-border-default bg-surface-raised px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-content-primary">
        {formatBucketLabel(b, granularity, months)}
      </p>
      <p className="mt-1 font-mono text-content-secondary">
        {t(lang, "reportsShort")}: {b.n} · {t(lang, "flaggedShort")}: {b.flagged}
      </p>
      {b.ratePer100 !== null && b.ci ? (
        <p className="font-mono text-content-primary">
          {fmtPer100(b.ratePer100 / 100)} {t(lang, "rateAxis")} · {t(lang, "ciOfFlagRate")}: [
          {fmtPer100(b.ci[0] / 100)}, {fmtPer100(b.ci[1] / 100)}]
        </p>
      ) : (
        <p className="text-content-secondary">n = 0</p>
      )}
    </div>
  );
}

function DensityTooltip({
  active,
  payload,
  lang,
}: TipPayload<{ key: string; rate: number; n: number; flagged: number }> & { lang: Lang }) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div className="max-w-80 rounded-md border border-border-default bg-surface-raised px-3 py-2 text-xs shadow-lg">
      <p className="truncate font-medium text-content-primary">{d.key}</p>
      <p className="mt-1 font-mono text-content-secondary">
        {t(lang, "reportsShort")}: {d.n} · {t(lang, "flaggedShort")}: {d.flagged}
      </p>
      <p className="font-mono text-content-primary">
        {d.rate.toFixed(1)} {t(lang, "rateAxis")}
      </p>
    </div>
  );
}