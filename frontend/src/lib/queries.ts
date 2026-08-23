import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type {
  AuditEntry,
  ChatSession,
  ChatTurn,
  Client,
  ClientStatsResponse,
  ContainEvent,
  EngineSettings,
  MarginReport,
  Profile,
  TelemetrySummary,
} from "@/lib/types";

export const summaryKey = ["telemetry-summary"];
export const eventsKey = (limit: number, status: string, clientId: string) => [
  "events",
  limit,
  status,
  clientId,
];
export const profilesKey = ["profiles"];
export const activeProfileKey = ["profile-active"];
export const auditKey = ["audit"];
export const clientsKey = ["clients"];
export const clientStatsKey = ["client-stats"];
export const settingsKey = ["engine-settings"];

export function useSummary() {
  return useQuery({
    queryKey: summaryKey,
    queryFn: () => apiGet<TelemetrySummary>("/telemetry/summary"),
    refetchInterval: 6000,
  });
}

export function useEvents(limit = 60, status = "all", clientId = "all") {
  return useQuery({
    queryKey: eventsKey(limit, status, clientId),
    queryFn: () =>
      apiGet<ContainEvent[]>(
        `/events?limit=${limit}${status !== "all" ? `&status=${status}` : ""}${
          clientId !== "all" ? `&client_id=${encodeURIComponent(clientId)}` : ""
        }`,
      ),
    refetchInterval: 5000,
  });
}

export function useProfiles() {
  return useQuery({ queryKey: profilesKey, queryFn: () => apiGet<Profile[]>("/profiles") });
}

export function useActiveProfile() {
  return useQuery({
    queryKey: activeProfileKey,
    queryFn: () => apiGet<Profile>("/profiles/active"),
  });
}

export function useAudit() {
  return useQuery({
    queryKey: auditKey,
    queryFn: () => apiGet<AuditEntry[]>("/audit?limit=100"),
    refetchInterval: 15000,
  });
}

export function useClients() {
  return useQuery({ queryKey: clientsKey, queryFn: () => apiGet<Client[]>("/clients") });
}

export function useClientStats() {
  return useQuery({
    queryKey: clientStatsKey,
    queryFn: () => apiGet<ClientStatsResponse>("/clients/stats"),
    refetchInterval: 8000,
  });
}

export function useSettings() {
  return useQuery({
    queryKey: settingsKey,
    queryFn: () => apiGet<EngineSettings>("/settings"),
  });
}

export const marginsKey = (profileId: string) => ["margins", profileId];

export const chatSessionsKey = ["chat-sessions"];
export const chatTurnsKey = (sessionId: string) => ["chat-turns", sessionId];

export function useChatSessions() {
  return useQuery({
    queryKey: chatSessionsKey,
    queryFn: () => apiGet<ChatSession[]>("/chat/sessions"),
  });
}

export function useChatTurns(sessionId?: string) {
  return useQuery({
    queryKey: chatTurnsKey(sessionId ?? "none"),
    queryFn: () => apiGet<ChatTurn[]>(`/chat/sessions/${sessionId}/turns`),
    enabled: Boolean(sessionId),
  });
}

export function useMargins(profileId?: string) {
  return useQuery({
    queryKey: marginsKey(profileId ?? "none"),
    queryFn: () => apiGet<MarginReport>(`/profiles/${profileId}/margins`),
    enabled: Boolean(profileId),
  });
}
