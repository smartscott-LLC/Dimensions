import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Plus, Save, SlidersHorizontal, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { apiPost, apiPut } from "@/lib/api";
import { activeProfileKey, profilesKey } from "@/lib/queries";
import type { Constraint, Dimension, Profile } from "@/lib/types";
import { DIMENSIONS } from "@/lib/types";

interface Props {
  profile?: Profile;
  profiles: Profile[];
}

export default function ConstraintEditor({ profile, profiles }: Props) {
  const qc = useQueryClient();
  const [dims, setDims] = useState<Dimension[]>([]);
  const [cons, setCons] = useState<Constraint[]>([]);
  const [editing, setEditing] = useState<number | null>(null);

  useEffect(() => {
    if (profile) {
      setDims(profile.dimensions.map((d) => ({ ...d })));
      setCons(profile.constraints.map((c) => ({ ...c, coeffs: [...c.coeffs] })));
    }
  }, [profile]);

  const save = useMutation({
    mutationFn: () =>
      apiPut<Profile>(`/profiles/${profile?.id}`, { dimensions: dims, constraints: cons }),
    onSuccess: () => {
      toast.success("Constraint geometry committed — polytope recompiled");
      void qc.invalidateQueries({ queryKey: activeProfileKey });
      void qc.invalidateQueries({ queryKey: profilesKey });
      void qc.invalidateQueries({ queryKey: ["margins"] });
      void qc.invalidateQueries({ queryKey: ["audit"] });
    },
    onError: () => toast.error("Could not persist constraint changes"),
  });

  const activate = useMutation({
    mutationFn: (id: string) => apiPost<Profile>(`/profiles/${id}/activate`),
    onSuccess: (data) => {
      toast.success(`Activated ${data.name}`);
      void qc.invalidateQueries({ queryKey: activeProfileKey });
      void qc.invalidateQueries({ queryKey: profilesKey });
      void qc.invalidateQueries({ queryKey: ["margins"] });
      void qc.invalidateQueries({ queryKey: ["telemetry-summary"] });
      void qc.invalidateQueries({ queryKey: ["audit"] });
    },
    onError: () => toast.error("Activation failed"),
  });

  const addConstraint = () => {
    setCons((prev) => [
      ...prev,
      {
        id: `new-${Date.now()}`,
        label: `Constraint ${prev.length + 1}`,
        coeffs: Array(DIMENSIONS).fill(0),
        b: 1,
      },
    ]);
  };

  return (
    <div className="col-span-12 grid gap-3 lg:grid-cols-12">
      <section
        className="border border-[#1E293B] bg-[#090F1E] p-4 lg:col-span-4"
        data-testid="profile-panel"
      >
        <h3 className="font-heading text-sm text-[#F8FAFC]">Constraint profiles</h3>
        <p className="label-mono mt-1 text-[#64748B]">one active polytope at a time</p>
        <ul className="mt-3 space-y-2">
          {profiles.length === 0 && (
            <li className="font-mono text-xs text-[#64748B]">no profiles available</li>
          )}
          {profiles.map((p) => (
            <li
              key={p.id}
              className={`border p-3 transition-colors duration-150 ${p.active ? "border-[#D4AF37] bg-[#002147]/60" : "border-[#1E293B] bg-[#030712] hover:border-[#495AAD]"}`}
              data-testid={`profile-card-${p.id}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-heading text-xs text-[#F8FAFC]">{p.name}</p>
                  <p className="mt-1 font-mono text-[10px] leading-snug text-[#64748B]">
                    {p.description}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-[#495AAD]">
                    {p.constraints.length} half-spaces · 14 axes
                  </p>
                </div>
                {p.active ? (
                  <CheckCircle2 className="size-4 shrink-0 text-[#D4AF37]" />
                ) : (
                  <Button
                    size="xs"
                    variant="outline"
                    onClick={() => activate.mutate(p.id)}
                    data-testid={`activate-profile-${p.id}-button`}
                  >
                    activate
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section
        className="border border-[#1E293B] bg-[#090F1E] p-4 lg:col-span-8"
        data-testid="constraint-editor"
      >
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="flex items-center gap-2 font-heading text-sm text-[#F8FAFC]">
            <SlidersHorizontal className="size-4 text-[#D4AF37]" /> Constraint matrix — A x ≤ b
          </h3>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={addConstraint}
              data-testid="add-constraint-button"
            >
              <Plus className="size-3.5" /> half-space
            </Button>
            <Button
              size="sm"
              onClick={() => save.mutate()}
              disabled={!profile || save.isPending}
              className="bg-[#D4AF37] text-[#002147] transition-colors duration-150 hover:bg-[#e6c455]"
              data-testid="save-constraints-button"
            >
              <Save className="size-3.5" /> {save.isPending ? "committing…" : "commit geometry"}
            </Button>
          </div>
        </div>

        <div className="max-h-80 overflow-y-auto border border-[#1E293B]">
          <table className="w-full border-collapse text-left">
            <thead className="sticky top-0 bg-[#002147]">
              <tr className="label-mono text-[#CBD5E1]">
                <th className="p-2">label</th>
                <th className="p-2">a · x (non-zero terms)</th>
                <th className="w-24 p-2">b</th>
                <th className="w-24 p-2">edit</th>
              </tr>
            </thead>
            <tbody>
              {cons.map((c, idx) => (
                <tr
                  key={c.id}
                  className="border-t border-[#1E293B] transition-colors duration-150 hover:bg-[#0B1324]"
                  data-testid={`constraint-row-${idx}`}
                >
                  <td className="p-2">
                    <Input
                      value={c.label}
                      onChange={(e) =>
                        setCons((prev) =>
                          prev.map((x, i) => (i === idx ? { ...x, label: e.target.value } : x)),
                        )
                      }
                      className="h-8 border-[#1E293B] bg-[#030712] font-mono text-xs"
                      data-testid={`constraint-label-input-${idx}`}
                    />
                  </td>
                  <td className="p-2 font-mono text-[11px] text-[#94A3B8]">
                    {c.coeffs
                      .map((v, i) => (v !== 0 ? `${v}·x${i + 1}` : null))
                      .filter(Boolean)
                      .slice(0, 5)
                      .join(" + ") || "0"}
                    {c.coeffs.filter((v) => v !== 0).length > 5 && " …"}
                  </td>
                  <td className="p-2">
                    <Input
                      value={String(c.b)}
                      onChange={(e) =>
                        setCons((prev) =>
                          prev.map((x, i) =>
                            i === idx ? { ...x, b: Number(e.target.value) || 0 } : x,
                          ),
                        )
                      }
                      className="h-8 border-[#1E293B] bg-[#030712] font-mono text-xs text-[#D4AF37]"
                      data-testid={`constraint-b-input-${idx}`}
                    />
                  </td>
                  <td className="p-2">
                    <div className="flex gap-1">
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => setEditing(idx)}
                        data-testid={`edit-constraint-${idx}-button`}
                      >
                        A row
                      </Button>
                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={() => setCons((prev) => prev.filter((_, i) => i !== idx))}
                        data-testid={`delete-constraint-${idx}-button`}
                      >
                        <Trash2 className="size-3.5 text-[#EF4444]" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h4 className="mt-5 font-heading text-xs text-[#F8FAFC]">Dimension semantics (R¹⁴)</h4>
        <div className="mt-2 grid gap-2 sm:grid-cols-2" data-testid="dimension-editor">
          {dims.map((d, idx) => (
            <div key={d.index} className="flex items-center gap-2">
              <span className="label-mono w-8 shrink-0 text-[#D4AF37]">x{d.index + 1}</span>
              <Input
                value={d.label}
                onChange={(e) =>
                  setDims((prev) =>
                    prev.map((x, i) => (i === idx ? { ...x, label: e.target.value } : x)),
                  )
                }
                className="h-8 border-[#1E293B] bg-[#030712] font-mono text-xs"
                data-testid={`dimension-label-input-${idx}`}
              />
            </div>
          ))}
        </div>
      </section>

      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent
          className="max-w-2xl border border-[#495AAD] shadow-2xl shadow-black/60"
          style={{ backgroundColor: "#090F1E" }}
        >
          <DialogHeader>
            <DialogTitle className="font-heading text-sm">
              Normal vector aᵀ — {editing !== null ? cons[editing]?.label : ""}
            </DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {editing !== null &&
              cons[editing]?.coeffs.map((v, i) => (
                <label key={i} className="block">
                  <span className="label-mono block truncate text-[#64748B]">
                    a{i + 1} · {dims[i]?.label ?? ""}
                  </span>
                  <Input
                    value={String(v)}
                    onChange={(e) =>
                      setCons((prev) =>
                        prev.map((c, ci) =>
                          ci === editing
                            ? {
                                ...c,
                                coeffs: c.coeffs.map((cv, k) =>
                                  k === i ? Number(e.target.value) || 0 : cv,
                                ),
                              }
                            : c,
                        ),
                      )
                    }
                    className="mt-1 h-8 border-[#1E293B] bg-[#030712] font-mono text-xs"
                    data-testid={`coeff-input-${i}`}
                  />
                </label>
              ))}
          </div>
          <DialogFooter>
            <Button
              onClick={() => setEditing(null)}
              className="bg-[#495AAD] text-white"
              data-testid="close-coeff-dialog-button"
            >
              done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
