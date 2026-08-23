import { History } from "lucide-react";
import type { AuditEntry } from "@/lib/types";

const TONE: Record<string, string> = {
  "profile.activate": "#D4AF37",
  "profile.update": "#495AAD",
  "profile.create": "#10B981",
  "engine.bootstrap": "#514B23",
};

export default function AuditTrail({ entries }: { entries: AuditEntry[] }) {
  return (
    <section
      className="col-span-12 border border-[#1E293B] bg-[#090F1E] p-4"
      data-testid="audit-trail"
    >
      <h3 className="flex items-center gap-2 font-heading text-sm text-[#F8FAFC]">
        <History className="size-4 text-[#495AAD]" /> Configuration audit trail
      </h3>
      <p className="label-mono mt-1 text-[#64748B]">
        immutable record of every geometry change
      </p>

      {entries.length === 0 ? (
        <p className="py-8 text-center font-mono text-xs text-[#64748B]">
          no configuration changes recorded
        </p>
      ) : (
        <ol className="mt-4 space-y-0">
          {entries.map((entry) => (
            <li
              key={entry.id}
              className="relative border-l border-[#1E293B] pb-4 pl-5 last:pb-0"
              data-testid={`audit-row-${entry.id}`}
            >
              <span
                className="absolute -left-[5px] top-1 size-2.5 rounded-full"
                style={{ background: TONE[entry.action] ?? "#64748B" }}
              />
              <div className="flex flex-wrap items-baseline gap-x-3">
                <span
                  className="font-heading text-xs"
                  style={{ color: TONE[entry.action] ?? "#94A3B8" }}
                >
                  {entry.action}
                </span>
                <span className="font-mono text-[10px] text-[#64748B]">
                  {new Date(entry.created_at).toLocaleString()} · {entry.actor}
                </span>
              </div>
              <p className="mt-0.5 font-mono text-[11px] text-[#CBD5E1]">{entry.detail}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
