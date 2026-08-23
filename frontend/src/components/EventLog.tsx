import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Client, ContainEvent, Profile } from "@/lib/types";

interface Props {
  events: ContainEvent[];
  profile?: Profile;
  status: string;
  onStatusChange: (status: string) => void;
  clients: Client[];
  clientId: string;
  onClientChange: (clientId: string) => void;
}

const FILTERS = ["all", "permitted", "corrected", "revised", "withheld"];

export default function EventLog({
  events,
  profile,
  status,
  onStatusChange,
  clients,
  clientId,
  onClientChange,
}: Props) {
  const [term, setTerm] = useState("");
  const [selected, setSelected] = useState<ContainEvent | null>(null);

  const rows = useMemo(() => {
    const q = term.trim().toLowerCase();
    if (!q) return events;
    return events.filter(
      (e) =>
        e.label.toLowerCase().includes(q) ||
        e.source.toLowerCase().includes(q) ||
        (e.client_name ?? "unattributed").toLowerCase().includes(q) ||
        e.violated_constraints.some((c) => c.toLowerCase().includes(q)),
    );
  }, [events, term]);

  return (
    <section
      className="col-span-12 border border-[#1E293B] bg-[#090F1E] p-4"
      data-testid="event-log"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-heading text-sm text-[#F8FAFC]">Containment event log</h3>
        <div className="flex flex-wrap items-center gap-2">
          {FILTERS.map((f) => (
            <Button
              key={f}
              size="xs"
              variant={status === f ? "default" : "outline"}
              className={status === f ? "bg-[#D4AF37] text-[#002147]" : ""}
              onClick={() => onStatusChange(f)}
              data-testid={`event-filter-${f}-button`}
            >
              {f}
            </Button>
          ))}
          <Select value={clientId} onValueChange={onClientChange}>
            <SelectTrigger
              size="sm"
              className="w-48 border-[#1E293B] bg-[#030712] font-mono text-xs"
              data-testid="event-client-filter"
            >
              <SelectValue>
                {(v) => {
                  if (v === "all") return "all clients";
                  if (v === "unattributed") return "unattributed";
                  return clients.find((c) => c.id === v)?.name ?? "all clients";
                }}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">all clients</SelectItem>
              <SelectItem value="unattributed">unattributed</SelectItem>
              {clients.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="relative">
            <Search className="absolute left-2 top-2 size-3.5 text-[#64748B]" />
            <Input
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder="search label / constraint"
              className="h-8 w-56 border-[#1E293B] bg-[#030712] pl-7 font-mono text-xs"
              data-testid="event-search-input"
            />
          </div>
        </div>
      </div>

      <div className="max-h-[520px] overflow-auto border border-[#1E293B]">
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 bg-[#002147]">
            <tr className="label-mono text-[#CBD5E1]">
              <th className="p-2">timestamp</th>
              <th className="p-2">label</th>
              <th className="p-2">client</th>
              <th className="p-2">source</th>
              <th className="p-2">status</th>
              <th className="p-2">r max</th>
              <th className="p-2">‖Δx‖</th>
              <th className="p-2">latency</th>
              <th className="p-2">breached</th>
            </tr>
          </thead>
          <tbody data-testid="event-log-body">
            {rows.length === 0 && (
              <tr>
                <td colSpan={9} className="p-6 text-center font-mono text-xs text-[#64748B]">
                  no events match this filter
                </td>
              </tr>
            )}
            {rows.map((ev) => (
              <tr
                key={ev.id}
                onClick={() => setSelected(ev)}
                className="cursor-pointer border-t border-[#1E293B] font-mono text-[11px] text-[#CBD5E1] transition-colors duration-150 hover:bg-[#0B1324]"
                data-testid={`event-row-${ev.id}`}
              >
                <td className="p-2 text-[#94A3B8]">
                  {new Date(ev.created_at).toLocaleString()}
                </td>
                <td className="p-2">{ev.label || "—"}</td>
                <td className="p-2 text-[#D4AF37]">{ev.client_name ?? "unattributed"}</td>
                <td className="p-2 text-[#495AAD]">{ev.source}</td>
                <td className="p-2">
                  <Badge
                    variant="outline"
                    className={
                      ev.status === "permitted"
                        ? "border-[#10B981]/50 text-[#10B981]"
                        : "border-[#EF4444]/50 text-[#EF4444]"
                    }
                  >
                    {ev.status}
                  </Badge>
                </td>
                <td className="p-2">{ev.max_residual.toFixed(4)}</td>
                <td className="p-2 text-[#D4AF37]">{ev.correction_magnitude.toFixed(4)}</td>
                <td className="p-2">{ev.latency_ms.toFixed(3)} ms</td>
                <td className="max-w-56 truncate p-2 text-[#94A3B8]">
                  {ev.violated_constraints.join(", ") || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent
          className="max-w-3xl border border-[#495AAD] shadow-2xl shadow-black/60"
          style={{ backgroundColor: "#090F1E" }}
        >
          <DialogHeader>
            <DialogTitle className="font-heading text-sm">
              Event {selected?.id.slice(0, 8)} — {selected?.status}
            </DialogTitle>
          </DialogHeader>
          {selected && (
            <div className="space-y-3" data-testid="event-detail">
              <p className="font-mono text-[11px] text-[#94A3B8]">
                profile {selected.profile_name} · {new Date(selected.created_at).toLocaleString()} ·{" "}
                {selected.latency_ms.toFixed(3)} ms · {selected.iterations} projection iterations
              </p>
              <div className="max-h-72 overflow-auto border border-[#1E293B]">
                <table className="w-full text-left">
                  <thead className="sticky top-0 bg-[#002147]">
                    <tr className="label-mono text-[#CBD5E1]">
                      <th className="p-2">axis</th>
                      <th className="p-2">generated</th>
                      <th className="p-2">projected</th>
                      <th className="p-2">Δ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.vector.map((v, i) => {
                      const p = selected.projected_vector?.[i];
                      const delta = p === undefined ? 0 : p - v;
                      return (
                        <tr
                          key={i}
                          className="border-t border-[#1E293B] font-mono text-[11px]"
                          data-testid={`event-detail-axis-${i}`}
                        >
                          <td className="p-2 text-[#94A3B8]">
                            x{i + 1} · {profile?.dimensions[i]?.label ?? ""}
                          </td>
                          <td className="p-2 text-[#F8FAFC]">{v.toFixed(4)}</td>
                          <td className="p-2 text-[#D4AF37]">
                            {p === undefined ? "—" : p.toFixed(4)}
                          </td>
                          <td
                            className={`p-2 ${Math.abs(delta) > 1e-6 ? "text-[#F59E0B]" : "text-[#475569]"}`}
                          >
                            {delta === 0 ? "0" : delta.toFixed(4)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {selected.violated_constraints.length > 0 && (
                <p className="font-mono text-[11px] text-[#EF4444]">
                  breached half-spaces: {selected.violated_constraints.join(", ")}
                </p>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
