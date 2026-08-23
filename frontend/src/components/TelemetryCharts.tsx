import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TelemetrySummary } from "@/lib/types";

const AXIS = { fill: "#94A3B8", fontSize: 10, fontFamily: "IBM Plex Mono" };
const TOOLTIP = {
  contentStyle: {
    background: "#030712",
    border: "1px solid #495AAD",
    borderRadius: 2,
    fontFamily: "IBM Plex Mono",
    fontSize: 11,
    color: "#F8FAFC",
  },
};

function Panel({
  title,
  hint,
  testId,
  children,
}: {
  title: string;
  hint: string;
  testId: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className="border border-[#1E293B] bg-[#090F1E] p-4"
      data-testid={testId}
    >
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="font-heading text-sm text-[#F8FAFC]">{title}</h3>
        <span className="label-mono text-[#64748B]">{hint}</span>
      </div>
      {children}
    </section>
  );
}

export default function TelemetryCharts({ summary }: { summary?: TelemetrySummary }) {
  const trend = summary?.violation_trend ?? [];
  const hist = summary?.latency_histogram ?? [];
  const top = summary?.top_constraints ?? [];

  return (
    <div className="col-span-12 grid gap-3 lg:grid-cols-12">
      <div className="lg:col-span-7">
        <Panel title="Violation trend" hint="12 h / hourly" testId="chart-violation-trend">
          <div className="h-56">
            {trend.length === 0 ? (
              <p className="pt-16 text-center font-mono text-xs text-[#64748B]">
                no telemetry in window
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend}>
                  <defs>
                    <linearGradient id="gTotal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#495AAD" stopOpacity={0.55} />
                      <stop offset="100%" stopColor="#495AAD" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="gCorrected" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#D4AF37" stopOpacity={0.6} />
                      <stop offset="100%" stopColor="#D4AF37" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#1E293B" vertical={false} />
                  <XAxis dataKey="bucket" tick={AXIS} stroke="#1E293B" />
                  <YAxis tick={AXIS} stroke="#1E293B" allowDecimals={false} />
                  <Tooltip {...TOOLTIP} />
                  <Area
                    type="monotone"
                    dataKey="total"
                    stroke="#495AAD"
                    fill="url(#gTotal)"
                    strokeWidth={2}
                    name="verified"
                  />
                  <Area
                    type="monotone"
                    dataKey="corrected"
                    stroke="#D4AF37"
                    fill="url(#gCorrected)"
                    strokeWidth={2}
                    strokeDasharray="5 3"
                    name="corrected"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>
      </div>

      <div className="lg:col-span-5">
        <Panel title="Projection latency" hint="histogram" testId="chart-latency-histogram">
          <div className="h-56">
            {hist.length === 0 ? (
              <p className="pt-16 text-center font-mono text-xs text-[#64748B]">no samples</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hist}>
                  <CartesianGrid stroke="#1E293B" vertical={false} />
                  <XAxis dataKey="label" tick={{ ...AXIS, fontSize: 9 }} stroke="#1E293B" />
                  <YAxis tick={AXIS} stroke="#1E293B" allowDecimals={false} />
                  <Tooltip {...TOOLTIP} />
                  <Bar dataKey="count" name="samples">
                    {hist.map((bucket, i) => (
                      <Cell key={bucket.label} fill={i > 3 ? "#EF4444" : "#10B981"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>
      </div>

      <div className="lg:col-span-12">
        <Panel title="Attribution by client" hint="permitted vs corrected" testId="chart-by-client">
          <div className="h-64">
            {(summary?.by_client ?? []).length === 0 ? (
              <p className="pt-20 text-center font-mono text-xs text-[#64748B]">
                no attributed traffic yet
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={summary?.by_client ?? []} layout="vertical">
                  <CartesianGrid stroke="#1E293B" horizontal={false} />
                  <XAxis type="number" tick={AXIS} stroke="#1E293B" allowDecimals={false} />
                  <YAxis
                    type="category"
                    dataKey="client_name"
                    tick={{ ...AXIS, fontSize: 10 }}
                    stroke="#1E293B"
                    width={130}
                  />
                  <Tooltip {...TOOLTIP} />
                  <Bar dataKey="permitted" stackId="a" fill="#10B981" name="permitted" />
                  <Bar dataKey="corrected" stackId="a" fill="#EF4444" name="corrected" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>
      </div>

      <div className="lg:col-span-12">
        <Panel title="Most-breached half-spaces" hint="a·x > b" testId="chart-top-constraints">
          {top.length === 0 ? (
            <p className="font-mono text-xs text-[#64748B]">no breaches recorded</p>
          ) : (
            <ul className="space-y-2">
              {top.map((hit) => {
                const pct = Math.round((hit.count / top[0].count) * 100);
                return (
                  <li key={hit.label} data-testid={`top-constraint-${hit.label}`}>
                    <div className="flex items-baseline justify-between font-mono text-xs">
                      <span className="text-[#CBD5E1]">{hit.label}</span>
                      <span className="text-[#D4AF37]">{hit.count}</span>
                    </div>
                    <div className="mt-1 h-1.5 bg-[#0B1324]">
                      <div
                        className="h-full bg-[#495AAD] transition-[width] duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
