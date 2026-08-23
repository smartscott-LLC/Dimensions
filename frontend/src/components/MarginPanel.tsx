import { Activity, CircleAlert } from "lucide-react";
import type { MarginReport, Profile } from "@/lib/types";

interface Props {
  report?: MarginReport;
  profile?: Profile;
}

/** Lattice health: slack of every facet at the profile's nominal centre. */
export default function MarginPanel({ report, profile }: Props) {
  const rows = report?.rows ?? [];
  const coupling = rows.filter(
    (r) => r.label.includes("leads") || r.label.includes("sum <="),
  );
  const axis = rows.length - coupling.length;
  const worst = rows.length
    ? rows.reduce((a, b) => (a.normalized <= b.normalized ? a : b))
    : null;

  return (
    <section
      className="border border-[#1E293B] bg-[#090F1E] p-4"
      data-testid="margin-panel"
    >
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="flex items-center gap-2 font-heading text-sm text-[#F8FAFC]">
          <Activity className="size-4 text-[#D4AF37]" /> Lattice margins at nominal centre
        </h3>
        <span className="label-mono text-[#64748B]" data-testid="facet-census">
          {rows.length} facets · {axis} axis-aligned · {coupling.length} coupling
        </span>
      </div>

      {rows.length === 0 ? (
        <p className="font-mono text-xs text-[#64748B]">no margin data available</p>
      ) : (
        <>
          <div className="mb-3 grid gap-2 sm:grid-cols-3">
            <div className="border border-[#1E293B] bg-[#030712] p-3">
              <p className="label-mono text-[#64748B]">centre feasible</p>
              <p
                className={`font-heading text-base ${report?.feasible ? "text-[#10B981]" : "text-[#EF4444]"}`}
                data-testid="center-feasible"
              >
                {report?.feasible ? "YES — interior point" : "NO — centre is outside P"}
              </p>
            </div>
            <div className="border border-[#1E293B] bg-[#030712] p-3">
              <p className="label-mono text-[#64748B]">tightest margin</p>
              <p
                className="font-heading text-base text-[#D4AF37]"
                data-testid="min-margin"
              >
                {(report?.min_margin ?? 0).toFixed(4)}
              </p>
              <p className="mt-0.5 truncate font-mono text-[10px] text-[#64748B]">
                {report?.tightest ?? "—"}
              </p>
            </div>
            <div className="border border-[#1E293B] bg-[#030712] p-3">
              <p className="label-mono text-[#64748B]">coupling slack</p>
              <p className="font-heading text-base text-[#495AAD]">
                {coupling.length > 0
                  ? `${Math.min(...coupling.map((c) => c.slack)).toFixed(2)} – ${Math.max(...coupling.map((c) => c.slack)).toFixed(2)}`
                  : "—"}
              </p>
              <p className="mt-0.5 font-mono text-[10px] text-[#64748B]">
                raw slack b − a·centre
              </p>
            </div>
          </div>

          {worst && worst.normalized < 0.02 && (
            <p
              className="mb-3 flex items-center gap-2 border border-[#F59E0B]/40 bg-[#F59E0B]/10 p-2 font-mono text-[11px] text-[#F59E0B]"
              data-testid="margin-warning"
            >
              <CircleAlert className="size-3.5" /> `{worst.label}` is nearly binding at the
              centre — small drift will start projecting.
            </p>
          )}

          <div className="max-h-72 overflow-auto border border-[#1E293B]">
            <table className="w-full border-collapse text-left">
              <thead className="sticky top-0 bg-[#002147]">
                <tr className="label-mono text-[#CBD5E1]">
                  <th className="p-2">facet</th>
                  <th className="p-2">kind</th>
                  <th className="p-2">slack</th>
                  <th className="p-2">distance</th>
                  <th className="p-2">headroom</th>
                </tr>
              </thead>
              <tbody data-testid="margin-table-body">
                {rows.map((r) => {
                  const isCoupling =
                    r.label.includes("leads") || r.label.includes("sum <=");
                  const pct = Math.max(
                    0,
                    Math.min(100, (r.normalized / Math.max(0.3, report?.min_margin ?? 0.3 + 0.3)) * 100),
                  );
                  return (
                    <tr
                      key={r.constraint_id}
                      className="border-t border-[#1E293B] font-mono text-[11px] transition-colors duration-150 hover:bg-[#0B1324]"
                      data-testid={`margin-row-${r.constraint_id}`}
                    >
                      <td className="max-w-72 truncate p-2 text-[#CBD5E1]">{r.label}</td>
                      <td className="p-2">
                        <span className={isCoupling ? "text-[#D4AF37]" : "text-[#495AAD]"}>
                          {isCoupling ? "coupling" : "axis"}
                        </span>
                      </td>
                      <td
                        className={`p-2 ${r.violated ? "text-[#EF4444]" : r.binding ? "text-[#F59E0B]" : "text-[#10B981]"}`}
                      >
                        {r.slack.toFixed(4)}
                      </td>
                      <td className="p-2 text-[#94A3B8]">{r.normalized.toFixed(4)}</td>
                      <td className="p-2">
                        <div className="h-1.5 w-24 bg-[#0B1324]">
                          <div
                            className="h-full transition-[width] duration-500"
                            style={{
                              width: `${pct}%`,
                              background: r.violated
                                ? "#EF4444"
                                : r.normalized < 0.05
                                  ? "#F59E0B"
                                  : "#10B981",
                            }}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="mt-3 border border-[#1E293B] bg-[#030712] p-3">
            <p className="label-mono text-[#64748B]">nominal centre</p>
            <div className="mt-2 grid gap-x-4 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
              {(report?.center ?? []).map((v, i) => (
                <p
                  key={i}
                  className="flex justify-between font-mono text-[11px]"
                  data-testid={`center-axis-${i}`}
                >
                  <span className="truncate text-[#64748B]">
                    x{i + 1} · {profile?.dimensions[i]?.label ?? ""}
                  </span>
                  <span className="text-[#D4AF37]">{v.toFixed(2)}</span>
                </p>
              ))}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
