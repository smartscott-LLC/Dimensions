import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import CommandHeader from "@/components/CommandHeader";
import KpiBar from "@/components/KpiBar";
import TelemetryCharts from "@/components/TelemetryCharts";
import LiveMonitor from "@/components/LiveMonitor";
import PolytopeExplorer from "@/components/PolytopeExplorer";
import ConstraintEditor from "@/components/ConstraintEditor";
import EventLog from "@/components/EventLog";
import AuditTrail from "@/components/AuditTrail";
import ClientsPanel from "@/components/ClientsPanel";
import GatePanel from "@/components/GatePanel";
import ChatCoach from "@/components/ChatCoach";
import AccessPanel from "@/components/AccessPanel";
import { useAuth } from "@/lib/auth";
import MarginPanel from "@/components/MarginPanel";
import { apiPost } from "@/lib/api";
import {
  useActiveProfile,
  useAudit,
  useChatSessions,
  useChatTurns,
  useClientStats,
  useClients,
  useEvents,
  useMargins,
  useProfiles,
  useSettings,
  useSummary,
} from "@/lib/queries";
import type { SimulateResult } from "@/lib/types";

const TABS = [
  { value: "overview", label: "Overview" },
  { value: "monitor", label: "Live monitor" },
  { value: "gate", label: "Gate" },
  { value: "chat", label: "Chat coach" },
  { value: "polytope", label: "Polytope" },
  { value: "constraints", label: "Constraints" },
  { value: "clients", label: "Clients", adminOnly: true },
  { value: "access", label: "Access", adminOnly: true },
  { value: "events", label: "Event log" },
  { value: "audit", label: "Audit" },
];

export default function Dashboard() {
  const qc = useQueryClient();
  const { user, isAdmin, signOut } = useAuth();
  const [streaming, setStreaming] = useState(false);
  const [ticking, setTicking] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [clientFilter, setClientFilter] = useState("all");
  const inFlight = useRef(false);

  const summaryQ = useSummary();
  const eventsQ = useEvents(120, statusFilter, clientFilter);
  const profilesQ = useProfiles();
  const activeQ = useActiveProfile();
  const auditQ = useAudit();
  const clientsQ = useClients();
  const clientStatsQ = useClientStats();
  const settingsQ = useSettings();
  const marginsQ = useMargins(activeQ.data?.id);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const chatSessionsQ = useChatSessions();
  const turnsQ = useChatTurns(sessionId);
  const chatSessions = chatSessionsQ.isError ? [] : (chatSessionsQ.data ?? []);
  const chatTurns = turnsQ.isError ? [] : (turnsQ.data ?? []);

  const offline = summaryQ.isError;
  const summary = summaryQ.isError ? undefined : summaryQ.data;
  const events = eventsQ.isError ? [] : (eventsQ.data ?? []);
  const profiles = profilesQ.isError ? [] : (profilesQ.data ?? []);
  const activeProfile = activeQ.isError ? undefined : activeQ.data;
  const audit = auditQ.isError ? [] : (auditQ.data ?? []);
  const clients = clientsQ.isError ? [] : (clientsQ.data ?? []);
  const clientStats = clientStatsQ.isError ? undefined : clientStatsQ.data;
  const settings = settingsQ.isError ? undefined : settingsQ.data;
  const margins = marginsQ.isError ? undefined : marginsQ.data;

  useEffect(() => {
    if (!streaming) return;
    const tick = async () => {
      if (inFlight.current) return;
      inFlight.current = true;
      setTicking(true);
      try {
        await apiPost<SimulateResult>("/simulate", {
          count: 4,
          violation_probability: 0.35,
        });
        void qc.invalidateQueries({ queryKey: ["events"] });
        void qc.invalidateQueries({ queryKey: ["telemetry-summary"] });
        void qc.invalidateQueries({ queryKey: ["client-stats"] });
        void qc.invalidateQueries({ queryKey: ["clients"] });
      } catch {
        setStreaming(false);
        toast.error("Simulator halted — engine unreachable");
      } finally {
        inFlight.current = false;
        setTicking(false);
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 4000);
    return () => window.clearInterval(id);
  }, [streaming, qc]);

  return (
    <div className="min-h-screen bg-[#030712]">
      <Toaster position="bottom-right" richColors />
      <CommandHeader
        summary={summary}
        offline={offline}
        streaming={streaming}
        ticking={ticking}
        onToggleStream={() => setStreaming((s) => !s)}
      />

      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#1E293B] bg-[#050B18] px-5 py-1.5">
        <span className="font-mono text-[10px] text-[#64748B]" data-testid="session-chip">
          signed in as{" "}
          <span className="text-[#D4AF37]">{user?.email ?? "—"}</span> ·{" "}
          <span className={isAdmin ? "text-[#D4AF37]" : "text-[#495AAD]"}>
            {user?.role ?? "operator"}
          </span>
        </span>
        <button
          onClick={signOut}
          className="label-mono text-[#94A3B8] transition-colors duration-150 hover:text-[#EF4444]"
          data-testid="sign-out-button"
        >
          sign out
        </button>
      </div>

      {offline && (
        <div
          className="border-b border-[#F59E0B]/40 bg-[#F59E0B]/10 px-5 py-2 font-mono text-[11px] text-[#F59E0B]"
          data-testid="offline-banner"
        >
          Containment engine unreachable — showing static console shell. Telemetry will resume
          automatically.
        </div>
      )}

      <main className="mx-auto max-w-[1600px] px-5 py-5">
        <Tabs defaultValue="overview">
          <TabsList variant="line" className="mb-5 flex-wrap" data-testid="dashboard-tabs">
            {TABS.filter((t) => isAdmin || !t.adminOnly).map((t) => (
              <TabsTrigger
                key={t.value}
                value={t.value}
                className="label-mono"
                data-testid={`tab-${t.value}`}
              >
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value="overview">
            <div className="grid grid-cols-12 gap-3">
              <KpiBar summary={summary} offline={offline} />
              <TelemetryCharts summary={summary} />
            </div>
          </TabsContent>

          <TabsContent value="monitor">
            <div className="grid grid-cols-12 gap-3">
              <KpiBar summary={summary} offline={offline} />
              <LiveMonitor events={events} profile={activeProfile} offline={offline} />
            </div>
          </TabsContent>

          <TabsContent value="gate">
            <div className="grid grid-cols-12 gap-3">
              <GatePanel settings={settings} profile={activeProfile} />
            </div>
          </TabsContent>

          <TabsContent value="chat">
            <div className="grid grid-cols-12 gap-3">
              <ChatCoach
                sessions={chatSessions}
                turns={chatTurns}
                sessionId={sessionId}
                onSelectSession={setSessionId}
                loadingTurns={turnsQ.isFetching}
              />
            </div>
          </TabsContent>

          <TabsContent value="polytope">
            <div className="grid grid-cols-12 gap-3">
              <PolytopeExplorer profile={activeProfile} events={events} />
            </div>
          </TabsContent>

          <TabsContent value="constraints">
            <div className="grid grid-cols-12 gap-3">
              {!isAdmin && (
                <p
                  className="col-span-12 border border-[#F59E0B]/40 bg-[#F59E0B]/10 p-2 font-mono text-[11px] text-[#F59E0B]"
                  data-testid="readonly-banner"
                >
                  Read-only: your operator role can inspect the lattice but not change it.
                  Constraint, client and settings writes are admin-only.
                </p>
              )}
              <div
                className={`col-span-12 grid grid-cols-12 gap-3 ${!isAdmin ? "pointer-events-none opacity-70" : ""}`}
              >
                <ConstraintEditor profile={activeProfile} profiles={profiles} />
                <div className="col-span-12">
                  <MarginPanel report={margins} profile={activeProfile} />
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="access">
            <div className="grid grid-cols-12 gap-3">
              <AccessPanel />
            </div>
          </TabsContent>

          <TabsContent value="clients">
            <div className="grid grid-cols-12 gap-3">
              <ClientsPanel
                clients={clients}
                stats={clientStats}
                settings={settings}
                profiles={profiles}
              />
            </div>
          </TabsContent>

          <TabsContent value="events">
            <div className="grid grid-cols-12 gap-3">
              <EventLog
                events={events}
                profile={activeProfile}
                status={statusFilter}
                onStatusChange={setStatusFilter}
                clients={clients}
                clientId={clientFilter}
                onClientChange={setClientFilter}
              />
            </div>
          </TabsContent>

          <TabsContent value="audit">
            <div className="grid grid-cols-12 gap-3">
              <AuditTrail entries={audit} />
            </div>
          </TabsContent>
        </Tabs>

        <footer className="mt-8 border-t border-[#1E293B] pt-4 font-mono text-[10px] leading-relaxed text-[#475569]">
          Geometric Constraint Framework · verification r = Ax − b, violation iff max(r) &gt; 0 ·
          correction x* = argmin<sub>x∈P</sub> ‖x − x<sub>gen</sub>‖² via Dykstra cyclic
          projection onto the intersection of half-spaces.
        </footer>
      </main>
    </div>
  );
}
