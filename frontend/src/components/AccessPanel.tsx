import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { KeyRound, Loader2, ShieldPlus, UserPlus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiGet, apiPost } from "@/lib/api";
import type { AuthUser } from "@/lib/types";

const usersKey = ["auth-users"];

export default function AccessPanel() {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("operator");
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");

  const usersQ = useQuery({
    queryKey: usersKey,
    queryFn: () => apiGet<AuthUser[]>("/auth/users"),
  });
  const users = usersQ.isError ? [] : (usersQ.data ?? []);

  const createUser = useMutation({
    mutationFn: () => apiPost<AuthUser>("/auth/users", { email, name, password, role }),
    onSuccess: (u) => {
      setEmail("");
      setName("");
      setPassword("");
      void qc.invalidateQueries({ queryKey: usersKey });
      void qc.invalidateQueries({ queryKey: ["audit"] });
      toast.success(`${u.role} account created for ${u.email}`);
    },
    onError: () => toast.error("Could not create the account (duplicate email or weak password)"),
  });

  const toggleUser = useMutation({
    mutationFn: (id: string) => apiPost<AuthUser>(`/auth/users/${id}/toggle`),
    onSuccess: (u) => {
      void qc.invalidateQueries({ queryKey: usersKey });
      void qc.invalidateQueries({ queryKey: ["audit"] });
      toast.success(`${u.email} ${u.active ? "reactivated" : "deactivated"}`);
    },
    onError: () => toast.error("Could not change that account"),
  });

  const changePassword = useMutation({
    mutationFn: () =>
      apiPost<AuthUser>("/auth/password", {
        current_password: currentPw,
        new_password: newPw,
      }),
    onSuccess: () => {
      setCurrentPw("");
      setNewPw("");
      toast.success("Password updated");
    },
    onError: () => toast.error("Current password incorrect, or new password too short"),
  });

  return (
    <>
      <section
        className="col-span-12 border border-[#1E293B] bg-[#090F1E] p-4 lg:col-span-4"
        data-testid="access-invite"
      >
        <h3 className="mb-3 flex items-center gap-2 font-heading text-sm text-[#F8FAFC]">
          <UserPlus className="size-4 text-[#D4AF37]" /> Issue console account
        </h3>
        <div className="space-y-2">
          <div>
            <Label className="label-mono text-[#64748B]">email</Label>
            <Input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 h-8 font-mono text-xs"
              data-testid="new-user-email-input"
            />
          </div>
          <div>
            <Label className="label-mono text-[#64748B]">display name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 h-8 font-mono text-xs"
              data-testid="new-user-name-input"
            />
          </div>
          <div>
            <Label className="label-mono text-[#64748B]">temporary password (8+ chars)</Label>
            <Input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 h-8 font-mono text-xs"
              data-testid="new-user-password-input"
            />
          </div>
          <div>
            <Label className="label-mono text-[#64748B]">role</Label>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger
                className="mt-1 h-8 font-mono text-xs"
                data-testid="new-user-role-select"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="operator">operator — run gate, chat, simulator</SelectItem>
                <SelectItem value="admin">admin — full configuration</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button
            onClick={() => createUser.mutate()}
            disabled={createUser.isPending || !email.trim() || password.length < 8}
            className="h-8 w-full bg-[#D4AF37] font-mono text-xs text-[#002147] transition-colors duration-200 hover:bg-[#e0be4d]"
            data-testid="create-user-button"
          >
            {createUser.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <ShieldPlus className="size-3.5" />
            )}
            Create account
          </Button>
        </div>

        <div className="mt-5 border-t border-[#1E293B] pt-4">
          <h4 className="mb-2 flex items-center gap-2 font-heading text-xs text-[#F8FAFC]">
            <KeyRound className="size-3.5 text-[#495AAD]" /> Change my password
          </h4>
          <Input
            type="password"
            value={currentPw}
            onChange={(e) => setCurrentPw(e.target.value)}
            placeholder="current password"
            className="mb-2 h-8 font-mono text-xs"
            data-testid="current-password-input"
          />
          <Input
            type="password"
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
            placeholder="new password (8+ chars)"
            className="mb-2 h-8 font-mono text-xs"
            data-testid="new-password-input"
          />
          <Button
            variant="outline"
            onClick={() => changePassword.mutate()}
            disabled={changePassword.isPending || !currentPw || newPw.length < 8}
            className="h-8 w-full font-mono text-xs"
            data-testid="change-password-button"
          >
            Update password
          </Button>
        </div>
      </section>

      <section
        className="col-span-12 border border-[#1E293B] bg-[#090F1E] p-4 lg:col-span-8"
        data-testid="access-users"
      >
        <h3 className="mb-3 font-heading text-sm text-[#F8FAFC]">Console accounts</h3>
        <div className="overflow-x-auto border border-[#1E293B]">
          <table className="w-full border-collapse text-left">
            <thead className="bg-[#002147]">
              <tr className="label-mono text-[#CBD5E1]">
                <th className="p-2">email</th>
                <th className="p-2">name</th>
                <th className="p-2">role</th>
                <th className="p-2">state</th>
                <th className="p-2">last login</th>
                <th className="p-2">actions</th>
              </tr>
            </thead>
            <tbody data-testid="users-table-body">
              {users.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-6 text-center font-mono text-xs text-[#64748B]">
                    no accounts loaded
                  </td>
                </tr>
              )}
              {users.map((u) => (
                <tr
                  key={u.id}
                  className="border-t border-[#1E293B] font-mono text-[11px] transition-colors duration-150 hover:bg-[#0B1324]"
                  data-testid={`user-row-${u.id}`}
                >
                  <td className="p-2 text-[#F8FAFC]">{u.email}</td>
                  <td className="p-2 text-[#94A3B8]">{u.name || "—"}</td>
                  <td className="p-2">
                    <Badge
                      variant="outline"
                      className="label-mono"
                      style={{
                        color: u.role === "admin" ? "#D4AF37" : "#495AAD",
                        borderColor: u.role === "admin" ? "#D4AF3766" : "#495AAD66",
                      }}
                    >
                      {u.role}
                    </Badge>
                  </td>
                  <td className="p-2">
                    <span className={u.active ? "text-[#10B981]" : "text-[#EF4444]"}>
                      {u.active ? "active" : "deactivated"}
                    </span>
                  </td>
                  <td className="p-2 text-[#64748B]">
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "never"}
                  </td>
                  <td className="p-2">
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => toggleUser.mutate(u.id)}
                      className="font-mono text-[11px]"
                      data-testid={`toggle-user-${u.id}-button`}
                    >
                      {u.active ? "deactivate" : "reactivate"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 font-mono text-[10px] leading-relaxed text-[#475569]">
          Operators can run the gate, chat coach and simulator; constraint, client and engine
          settings changes are admin-only and enforced server-side (403).
        </p>
      </section>
    </>
  );
}
