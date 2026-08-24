import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";

// Hand-written mirror of the StatusCheck Pydantic model in backend/server.py — nothing infers across the HTTP boundary.
interface StatusCheck {
  id: string;
  client_name: string;
  timestamp: string;
}

// queryFn calls the typed fetch layer directly — Query + apiGet composed together.
const fetchStatusChecks = () => apiGet<StatusCheck[]>("/status");

export default function Home() {
  // Result discarded on purpose: this splash must render identically with no backend.
  useQuery({ queryKey: ["status"], queryFn: fetchStatusChecks, retry: false });

  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-[#0f0f10] text-[calc(10px+2vmin)] text-white">
      <p className="mt-5">Building something incredible ~!</p>
    </div>
  );
}
