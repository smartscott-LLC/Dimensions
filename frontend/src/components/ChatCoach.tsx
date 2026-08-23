import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";
import { Ban, Download, Loader2, MessageSquarePlus, Send, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiGet, apiPost } from "@/lib/api";
import { chatSessionsKey, chatTurnsKey } from "@/lib/queries";
import type { ChatExport, ChatSession, ChatTurn } from "@/lib/types";

interface Props {
  sessions: ChatSession[];
  turns: ChatTurn[];
  sessionId?: string;
  onSelectSession: (id: string) => void;
  loadingTurns: boolean;
}

const DECISION_COLOR: Record<string, string> = {
  permitted: "#10B981",
  corrected: "#D4AF37",
  revised: "#495AAD",
  withheld: "#EF4444",
};

export default function ChatCoach({
  sessions,
  turns,
  sessionId,
  onSelectSession,
  loadingTurns,
}: Props) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const [title, setTitle] = useState("");
  const [mode, setMode] = useState("inherit");
  const [selectedTurn, setSelectedTurn] = useState<string | null>(null);

  useEffect(() => {
    if (turns.length) setSelectedTurn(turns[turns.length - 1].id);
  }, [turns]);

  const createSession = useMutation({
    mutationFn: () =>
      apiPost<ChatSession>("/chat/sessions", {
        title: title.trim() || "Config coaching session",
        mode: mode === "inherit" ? null : mode,
      }),
    onSuccess: (s) => {
      setTitle("");
      void qc.invalidateQueries({ queryKey: chatSessionsKey });
      onSelectSession(s.id);
      toast.success(`Session opened · ${s.profile_name}`);
    },
    onError: () => toast.error("Could not open a chat session"),
  });

  const sendMessage = useMutation({
    mutationFn: (text: string) =>
      apiPost<ChatTurn>(`/chat/sessions/${sessionId}/message`, { text }),
    onSuccess: (t) => {
      setDraft("");
      void qc.invalidateQueries({ queryKey: chatTurnsKey(sessionId ?? "none") });
      void qc.invalidateQueries({ queryKey: chatSessionsKey });
      void qc.invalidateQueries({ queryKey: ["events"] });
      void qc.invalidateQueries({ queryKey: ["telemetry-summary"] });
      if (t.decision === "withheld") toast.error("Reply withheld by the engine");
    },
    onError: () => toast.error("Turn failed — model or engine unavailable"),
  });

  const active = sessions.find((s) => s.id === sessionId);
  const [exporting, setExporting] = useState(false);

  async function exportSession() {
    if (!sessionId) return;
    setExporting(true);
    try {
      const artifact = await apiGet<ChatExport>(`/chat/sessions/${sessionId}/export`);
      const url = URL.createObjectURL(
        new Blob([artifact.content], { type: "text/markdown" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = artifact.filename;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`Exported ${artifact.turns} turn(s) as an audit artifact`);
    } catch {
      toast.error("Export failed");
    } finally {
      setExporting(false);
    }
  }

  const inspected = useMemo(
    () => turns.find((t) => t.id === selectedTurn) ?? turns[turns.length - 1],
    [turns, selectedTurn],
  );

  const radarData = useMemo(() => {
    if (!inspected) return [];
    return inspected.encoded_vector.map((v, i) => ({
      axis: inspected.dimension_names[i] ?? `x${i + 1}`,
      draft: Number(v.toFixed(3)),
      released: Number((inspected.final_vector?.[i] ?? 0).toFixed(3)),
    }));
  }, [inspected]);

  return (
    <>
      {/* ---------------------------------------------------------- sessions */}
      <section
        className="col-span-12 border border-[#1E293B] bg-[#090F1E] p-4 lg:col-span-3"
        data-testid="chat-sessions"
      >
        <h3 className="mb-3 flex items-center gap-2 font-heading text-sm text-[#F8FAFC]">
          <MessageSquarePlus className="size-4 text-[#D4AF37]" /> Coaching sessions
        </h3>

        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="session name"
          className="mb-2 h-8 font-mono text-xs"
          data-testid="chat-session-title-input"
        />
        <Select value={mode} onValueChange={setMode}>
          <SelectTrigger
            className="mb-2 h-8 font-mono text-xs"
            data-testid="chat-session-mode-select"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="inherit">inherit engine mode</SelectItem>
            <SelectItem value="projection">projection</SelectItem>
            <SelectItem value="refusal">refusal</SelectItem>
          </SelectContent>
        </Select>
        <Button
          onClick={() => createSession.mutate()}
          disabled={createSession.isPending}
          className="mb-3 h-8 w-full bg-[#D4AF37] font-mono text-xs text-[#002147] transition-colors duration-200 hover:bg-[#e0be4d]"
          data-testid="chat-new-session-button"
        >
          {createSession.isPending ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <Sparkles className="size-3.5" />
          )}
          New session
        </Button>

        <div className="max-h-[520px] space-y-1 overflow-auto" data-testid="chat-session-list">
          {sessions.length === 0 && (
            <p className="font-mono text-[11px] text-[#64748B]">no sessions yet</p>
          )}
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => onSelectSession(s.id)}
              className={`w-full border p-2 text-left transition-colors duration-150 ${
                s.id === sessionId
                  ? "border-[#D4AF37]/60 bg-[#D4AF37]/10"
                  : "border-[#1E293B] bg-[#030712] hover:border-[#495AAD]/60"
              }`}
              data-testid={`chat-session-item-${s.id}`}
            >
              <p className="truncate font-mono text-[11px] text-[#F8FAFC]">{s.title}</p>
              <p className="mt-0.5 font-mono text-[10px] text-[#64748B]">
                {s.turns} turns · {s.withheld} withheld · {s.mode ?? "inherit"}
              </p>
              <p className="truncate font-mono text-[10px] text-[#495AAD]">
                {s.profile_name}
              </p>
            </button>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------------ thread */}
      <section
        className="col-span-12 flex flex-col border border-[#1E293B] bg-[#090F1E] p-4 lg:col-span-5"
        data-testid="chat-thread"
      >
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="font-heading text-sm text-[#F8FAFC]">
            {active ? active.title : "Gated agent chat"}
          </h3>
          <span className="label-mono text-[#64748B]" data-testid="chat-model-label">
            {active ? `${active.model} · ${active.mode ?? "inherit"}` : "no session"}
          </span>
          {active && (
            <Button
              size="xs"
              variant="outline"
              disabled={exporting}
              onClick={() => void exportSession()}
              className="font-mono text-[11px]"
              data-testid="chat-export-button"
            >
              {exporting ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <Download className="size-3" />
              )}
              Export transcript
            </Button>
          )}
        </div>

        <div
          className="mb-3 max-h-[460px] min-h-[240px] flex-1 space-y-2 overflow-auto"
          data-testid="chat-messages"
        >
          {!active && (
            <p className="font-mono text-xs text-[#64748B]" data-testid="chat-no-session">
              Open a session to chat with the gated agent. Every reply is encoded to 14D and
              verified before release.
            </p>
          )}
          {active && turns.length === 0 && !loadingTurns && (
            <p className="font-mono text-xs text-[#64748B]" data-testid="chat-empty">
              Ask how to tighten a facet, why a prompt tripped the lattice, or what refusal
              mode changes.
            </p>
          )}
          {turns.map((t) => (
            <div key={t.id} className="space-y-1">
              <div className="ml-8 border border-[#495AAD]/40 bg-[#495AAD]/10 p-2">
                <p className="label-mono mb-1 text-[#495AAD]">operator</p>
                <p
                  className="font-mono text-[11px] leading-relaxed text-[#E2E8F0]"
                  data-testid={`chat-user-${t.id}`}
                >
                  {t.user_text}
                </p>
              </div>
              <button
                onClick={() => setSelectedTurn(t.id)}
                className={`mr-8 w-full border p-2 text-left transition-colors duration-150 ${
                  t.id === inspected?.id ? "border-[#D4AF37]/60" : "border-[#1E293B]"
                } bg-[#030712] hover:border-[#D4AF37]/40`}
                data-testid={`chat-turn-${t.id}`}
              >
                <div className="mb-1 flex items-center gap-2">
                  <span className="label-mono text-[#64748B]">agent</span>
                  <Badge
                    variant="outline"
                    className="label-mono"
                    style={{
                      color: DECISION_COLOR[t.decision],
                      borderColor: `${DECISION_COLOR[t.decision]}66`,
                    }}
                    data-testid={`chat-decision-${t.id}`}
                  >
                    {t.decision}
                  </Badge>
                  <span className="font-mono text-[10px] text-[#64748B]">
                    align {t.alignment_score.toFixed(2)} · r_max {t.max_residual.toFixed(3)}
                  </span>
                </div>
                {t.released_text ? (
                  <p className="font-mono text-[11px] leading-relaxed text-[#CBD5E1]">
                    {t.released_text}
                  </p>
                ) : (
                  <p className="flex items-center gap-2 font-mono text-[11px] text-[#EF4444]">
                    <Ban className="size-3.5" /> Reply withheld — the draft never entered the
                    polytope.
                  </p>
                )}
              </button>
            </div>
          ))}
          {sendMessage.isPending && (
            <p
              className="flex items-center gap-2 font-mono text-[11px] text-[#D4AF37]"
              data-testid="chat-pending"
            >
              <Loader2 className="size-3.5 animate-spin" /> generating, then gating…
            </p>
          )}
        </div>

        <div className="flex items-end gap-2">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={2}
            placeholder={
              active ? "ask about facets, margins, prompt wording…" : "open a session first"
            }
            disabled={!active || sendMessage.isPending}
            className="font-mono text-xs"
            data-testid="chat-input"
          />
          <Button
            onClick={() => sendMessage.mutate(draft)}
            disabled={!active || sendMessage.isPending || draft.trim().length === 0}
            className="h-9 bg-[#495AAD] font-mono text-xs transition-colors duration-200 hover:bg-[#5a6bc0]"
            data-testid="chat-send-button"
          >
            {sendMessage.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Send className="size-3.5" />
            )}
            Send
          </Button>
        </div>
      </section>

      {/* --------------------------------------------------------- inspector */}
      <section
        className="col-span-12 border border-[#1E293B] bg-[#090F1E] p-4 lg:col-span-4"
        data-testid="chat-inspector"
      >
        <h3 className="mb-3 font-heading text-sm text-[#F8FAFC]">Turn inspector</h3>
        {!inspected ? (
          <p className="font-mono text-xs text-[#64748B]" data-testid="chat-inspector-empty">
            Select an agent reply to see its 14D signature, the facets it tripped and the
            reflection rewrite.
          </p>
        ) : (
          <div className="space-y-3">
            <div className="h-64 border border-[#1E293B] bg-[#030712] p-1">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData} outerRadius="72%">
                  <PolarGrid stroke="#1E293B" />
                  <PolarAngleAxis
                    dataKey="axis"
                    tick={{ fill: "#64748B", fontSize: 8, fontFamily: "monospace" }}
                  />
                  <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
                  <Radar
                    name="draft"
                    dataKey="draft"
                    stroke="#EF4444"
                    fill="#EF4444"
                    fillOpacity={0.18}
                  />
                  <Radar
                    name="released"
                    dataKey="released"
                    stroke="#D4AF37"
                    fill="#D4AF37"
                    fillOpacity={0.22}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: 9, fontFamily: "monospace", color: "#64748B" }}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            <div className="grid grid-cols-3 gap-2">
              {[
                { k: "decision", v: inspected.decision, c: DECISION_COLOR[inspected.decision] },
                { k: "attempts", v: String(inspected.attempts), c: "#CBD5E1" },
                { k: "‖Δx‖", v: inspected.correction_magnitude.toFixed(3), c: "#495AAD" },
              ].map((m) => (
                <div key={m.k} className="border border-[#1E293B] bg-[#030712] p-2">
                  <p className="label-mono text-[#64748B]">{m.k}</p>
                  <p className="font-heading text-xs" style={{ color: m.c }}>
                    {m.v}
                  </p>
                </div>
              ))}
            </div>

            <div className="border border-[#1E293B] bg-[#030712] p-3">
              <p className="label-mono mb-1 text-[#64748B]">why it tripped</p>
              {inspected.why.length === 0 ? (
                <p className="font-mono text-[11px] text-[#10B981]" data-testid="chat-why">
                  no facet violated — the reply was already inside P
                </p>
              ) : (
                <ul className="space-y-1" data-testid="chat-why">
                  {inspected.why.map((w, i) => (
                    <li key={i} className="font-mono text-[10px] leading-relaxed text-[#F59E0B]">
                      · {w}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {inspected.suggested_rewrite && (
              <div className="border border-[#495AAD]/40 bg-[#495AAD]/10 p-3">
                <p className="label-mono mb-1 text-[#495AAD]">
                  reflection rewrite (attempt {inspected.attempts - 1})
                </p>
                <p
                  className="font-mono text-[10px] leading-relaxed text-[#CBD5E1]"
                  data-testid="chat-suggested-rewrite"
                >
                  {inspected.suggested_rewrite}
                </p>
              </div>
            )}

            {inspected.withheld_reason && (
              <p
                className="border border-[#EF4444]/40 bg-[#EF4444]/10 p-2 font-mono text-[10px] text-[#EF4444]"
                data-testid="chat-withheld-reason"
              >
                {inspected.withheld_reason}
              </p>
            )}

            <div className="border border-[#1E293B] bg-[#030712] p-3">
              <p className="label-mono mb-1 text-[#64748B]">raw model draft</p>
              <p
                className="max-h-32 overflow-auto font-mono text-[10px] leading-relaxed text-[#94A3B8]"
                data-testid="chat-raw-draft"
              >
                {inspected.draft_text}
              </p>
            </div>

            {inspected.wisdom.length > 0 && (
              <ul className="space-y-1" data-testid="chat-wisdom">
                {inspected.wisdom.map((w, i) => (
                  <li key={i} className="font-mono text-[10px] text-[#F59E0B]">
                    · {w}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>
    </>
  );
}
