import { useMemo, useState, useRef, useCallback } from "react";
import { Boxes } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ContainEvent, Profile } from "@/lib/types";

interface Props {
  profile?: Profile;
  events: ContainEvent[];
}

type Pt = { x: number; y: number };

const PAD = 46;
const SIZE = 460;
const MIN_ZOOM = 0.2;
const MAX_ZOOM = 10;
const ZOOM_FACTOR = 1.08;

function clientToSvg(
  svgEl: SVGSVGElement,
  clientX: number,
  clientY: number,
): { x: number; y: number } {
  const pt = svgEl.createSVGPoint();
  pt.x = clientX;
  pt.y = clientY;
  const ctm = svgEl.getScreenCTM();
  if (!ctm) return { x: clientX, y: clientY };
  const svgPt = pt.matrixTransform(ctm.inverse());
  return { x: svgPt.x, y: svgPt.y };
}

/** Trims binary floating-point noise: 0.30000000000000004 -> "0.3" */
const fmt = (v: number) => String(Number(v.toFixed(6)));

function clipHalfPlane(poly: Pt[], ai: number, aj: number, b: number): Pt[] {
  if (poly.length === 0) return poly;
  const value = (p: Pt) => ai * p.x + aj * p.y - b;
  const out: Pt[] = [];
  for (let i = 0; i < poly.length; i += 1) {
    const cur = poly[i];
    const nxt = poly[(i + 1) % poly.length];
    const vc = value(cur);
    const vn = value(nxt);
    if (vc <= 0) out.push(cur);
    if ((vc <= 0 && vn > 0) || (vc > 0 && vn <= 0)) {
      const t = vc / (vc - vn);
      out.push({ x: cur.x + t * (nxt.x - cur.x), y: cur.y + t * (nxt.y - cur.y) });
    }
  }
  return out;
}

export default function PolytopeExplorer({ profile, events }: Props) {
  const [xi, setXi] = useState("0");
  const [yi, setYi] = useState("3");
  const ix = Number(xi);
  const iy = Number(yi);

  const svgRef = useRef<SVGSVGElement>(null);
  const [viewOrigin, setViewOrigin] = useState<[number, number]>([0, 0]);
  const [zoom, setZoom] = useState(1);
  const isPanningRef = useRef(false);
  const lastMouseRef = useRef<{ x: number; y: number } | null>(null);

  const resetView = useCallback(() => {
    setViewOrigin([0, 0]);
    setZoom(1);
  }, []);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (e.button !== 0) return;
      isPanningRef.current = true;
      lastMouseRef.current = { x: e.clientX, y: e.clientY };
    },
    [],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!isPanningRef.current || !lastMouseRef.current) return;
      const dx = e.clientX - lastMouseRef.current.x;
      const dy = e.clientY - lastMouseRef.current.y;
      lastMouseRef.current = { x: e.clientX, y: e.clientY };
      setViewOrigin((prev) => [prev[0] - dx / zoom, prev[1] - dy / zoom]);
    },
    [zoom],
  );

  const handleMouseUp = useCallback(() => {
    isPanningRef.current = false;
    lastMouseRef.current = null;
  }, []);

  const handleWheel = useCallback(
    (e: React.WheelEvent<SVGSVGElement>) => {
      e.preventDefault();
      const svgEl = svgRef.current;
      if (!svgEl) return;

      const fwd = clientToSvg(svgEl, e.clientX, e.clientY);
      const factor = e.deltaY < 0 ? ZOOM_FACTOR : 1 / ZOOM_FACTOR;
      const nextZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom * factor));
      const actualFactor = nextZoom / zoom;

      const newOrigin: [number, number] = [
        fwd.x - actualFactor * (fwd.x - viewOrigin[0]),
        fwd.y - actualFactor * (fwd.y - viewOrigin[1]),
      ];

      setZoom(nextZoom);
      setViewOrigin(newOrigin);
    },
    [zoom, viewOrigin],
  );

  const zoomIn = useCallback(() => {
    const cx = SIZE / 2;
    const cy = SIZE / 2;
    const nextZoom = Math.min(MAX_ZOOM, zoom * ZOOM_FACTOR);
    const factor = nextZoom / zoom;
    setViewOrigin([
      cx - factor * (cx - viewOrigin[0]),
      cy - factor * (cy - viewOrigin[1]),
    ]);
    setZoom(nextZoom);
  }, [zoom, viewOrigin]);

  const zoomOut = useCallback(() => {
    const cx = SIZE / 2;
    const cy = SIZE / 2;
    const nextZoom = Math.max(MIN_ZOOM, zoom / ZOOM_FACTOR);
    const factor = nextZoom / zoom;
    setViewOrigin([
      cx - factor * (cx - viewOrigin[0]),
      cy - factor * (cy - viewOrigin[1]),
    ]);
    setZoom(nextZoom);
  }, [zoom, viewOrigin]);

  const dims = profile?.dimensions ?? [];
  const dimX = dims[ix];
  const dimY = dims[iy];

  const domain = useMemo(() => {
    const spanX = dimX ? Math.max(dimX.max - dimX.min, 0.001) : 1;
    const spanY = dimY ? Math.max(dimY.max - dimY.min, 0.001) : 1;
    return {
      x0: dimX ? dimX.min : 0,
      x1: (dimX ? dimX.min : 0) + spanX * 1.4,
      y0: dimY ? dimY.min : 0,
      y1: (dimY ? dimY.min : 0) + spanY * 1.4,
    };
  }, [dimX, dimY]);

  // Base coordinate mappers (no pan/zoom)
  const sx = (v: number) =>
    PAD + ((v - domain.x0) / (domain.x1 - domain.x0)) * (SIZE - PAD * 2);
  const sy = (v: number) =>
    SIZE - PAD - ((v - domain.y0) / (domain.y1 - domain.y0)) * (SIZE - PAD * 2);

  // Pan/zoom-aware coordinate mappers
  const sxz = useCallback(
    (v: number) => (sx(v) - viewOrigin[0]) * zoom,
    [sx, viewOrigin, zoom],
  );
  const syz = useCallback(
    (v: number) => (sy(v) - viewOrigin[1]) * zoom,
    [sy, viewOrigin, zoom],
  );

  const slice = useMemo(() => {
    if (!profile) return [];
    const center = profile.center ?? [];
    // Facets that touch other axes are still real constraints on this slice: fold the
    // held-constant contribution of every other axis into the threshold.
    return profile.constraints
      .map((c) => {
        let offset = 0;
        for (let k = 0; k < c.coeffs.length; k += 1) {
          if (k !== ix && k !== iy) offset += c.coeffs[k] * (center[k] ?? 0);
        }
        return {
          label: c.label,
          ai: c.coeffs[ix] ?? 0,
          aj: c.coeffs[iy] ?? 0,
          b: c.b - offset,
        };
      })
      .filter((c) => Math.abs(c.ai) > 1e-9 || Math.abs(c.aj) > 1e-9);
  }, [profile, ix, iy]);

  const region = useMemo(() => {
    let poly: Pt[] = [
      { x: domain.x0, y: domain.y0 },
      { x: domain.x1, y: domain.y0 },
      { x: domain.x1, y: domain.y1 },
      { x: domain.x0, y: domain.y1 },
    ];
    slice.forEach((c) => {
      poly = clipHalfPlane(poly, c.ai, c.aj, c.b);
    });
    return poly;
  }, [slice, domain]);

  const plotted = events.slice(0, 45);

  return (
    <section
      className="col-span-12 border border-[#1E293B] bg-[#090F1E] p-4"
      data-testid="polytope-explorer"
    >
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 font-heading text-sm text-[#F8FAFC]">
            <Boxes className="size-4 text-gold" /> Polytope explorer — 2D slice of R
            <sup>14</sup>
          </h3>
          <p className="label-mono mt-1 text-[#64748B]">
            remaining 12 axes held at the profile centre
          </p>
        </div>
        <div className="flex gap-2">
          <div>
            <span className="label-mono block text-[#64748B]">axis X</span>
            <Select value={xi} onValueChange={(v: string) => setXi(v)}>
              <SelectTrigger
                size="sm"
                className="mt-1 w-52 border-[#1E293B] bg-[#030712] font-mono text-xs"
                data-testid="slice-x-select"
              >
                <SelectValue>
                  {(v) => {
                    const d = dims[Number(v)];
                    return d ? `x${d.index + 1} · ${d.label}` : "—";
                  }}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {dims.map((d) => (
                  <SelectItem key={d.index} value={String(d.index)}>
                    x{d.index + 1} · {d.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <span className="label-mono block text-[#64748B]">axis Y</span>
            <Select value={yi} onValueChange={(v: string) => setYi(v)}>
              <SelectTrigger
                size="sm"
                className="mt-1 w-52 border-[#1E293B] bg-[#030712] font-mono text-xs"
                data-testid="slice-y-select"
              >
                <SelectValue>
                  {(v) => {
                    const d = dims[Number(v)];
                    return d ? `x${d.index + 1} · ${d.label}` : "—";
                  }}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {dims.map((d) => (
                  <SelectItem key={d.index} value={String(d.index)}>
                    x{d.index + 1} · {d.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <div className="grid-etch border border-[#1E293B] bg-[#030712]">
          <div className="relative">
              <svg
                ref={svgRef}
                viewBox={`0 0 ${SIZE} ${SIZE}`}
                preserveAspectRatio="xMidYMid meet"
                className="block h-115 w-full cursor-grab"
                style={{ cursor: isPanningRef.current ? "grabbing" : "grab" }}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                onWheel={handleWheel}
                role="img"
                aria-label="polytope slice"
              >
                <g transform={`translate(${viewOrigin[0]}, ${viewOrigin[1]}) scale(${zoom})`}>
              {region.length > 2 && (
                <polygon
                  points={region.map((p) => `${sxz(p.x)},${syz(p.y)}`).join(" ")}
                  fill="#10B981"
                  fillOpacity={0.13}
                  stroke="#10B981"
                  strokeWidth={1.5}
                  data-testid="feasible-region"
                />
              )}

              {slice.map((c) => {
                const cand: Pt[] = [];
                if (Math.abs(c.aj) > 1e-9) {
                  cand.push({ x: domain.x0, y: (c.b - c.ai * domain.x0) / c.aj });
                  cand.push({ x: domain.x1, y: (c.b - c.ai * domain.x1) / c.aj });
                }
                if (Math.abs(c.ai) > 1e-9) {
                  cand.push({ x: (c.b - c.aj * domain.y0) / c.ai, y: domain.y0 });
                  cand.push({ x: (c.b - c.aj * domain.y1) / c.ai, y: domain.y1 });
                }
                const inside = cand.filter(
                  (p) =>
                    p.x >= domain.x0 - 1e-6 &&
                    p.x <= domain.x1 + 1e-6 &&
                    p.y >= domain.y0 - 1e-6 &&
                    p.y <= domain.y1 + 1e-6,
                );
                if (inside.length < 2) return null;
                return (
                  <line
                    key={c.label}
                    x1={sxz(inside[0].x)}
                    y1={syz(inside[0].y)}
                    x2={sxz(inside[1].x)}
                    y2={syz(inside[1].y)}
                    stroke="#D4AF37"
                    strokeWidth={1}
                    strokeDasharray="4 4"
                    strokeOpacity={0.7}
                  />
                );
              })}

              {plotted.map((ev) => {
                const px = ev.vector[ix] ?? 0;
                const py = ev.vector[iy] ?? 0;
                const proj = ev.projected_vector;
                return (
                  <g key={ev.id} data-testid={`slice-point-${ev.id}`}>
                    {proj && (
                      <line
                        x1={sxz(px)}
                        y1={syz(py)}
                        x2={sxz(proj[ix] ?? 0)}
                        y2={syz(proj[iy] ?? 0)}
                        stroke="#F59E0B"
                        strokeWidth={0.8}
                      />
                    )}
                    <circle
                      cx={sxz(px)}
                      cy={syz(py)}
                      r={3}
                      fill={ev.status === "permitted" ? "#10B981" : "#EF4444"}
                      fillOpacity={0.9}
                    />
                    {proj && (
                      <circle
                        cx={sxz(proj[ix] ?? 0)}
                        cy={syz(proj[iy] ?? 0)}
                        r={2.5}
                        fill="#D4AF37"
                      />
                    )}
                  </g>
                );
              })}

              {/* Axes */}
              <line x1={PAD} y1={SIZE - PAD} x2={SIZE - PAD} y2={SIZE - PAD} stroke="#334155" />
              <line x1={PAD} y1={PAD} x2={PAD} y2={SIZE - PAD} stroke="#334155" />
              <text x={SIZE / 2} y={SIZE - 12} fill="#94A3B8" fontSize={11} textAnchor="middle" fontFamily="IBM Plex Mono">
                {`x${ix + 1} · ${dimX?.label ?? "—"}`}
              </text>
              <text
                x={18}
                y={SIZE / 2}
                fill="#94A3B8"
                fontSize={11}
                textAnchor="middle"
                fontFamily="IBM Plex Mono"
                transform={`rotate(-90 18 ${SIZE / 2})`}
              >
                {`x${iy + 1} · ${dimY?.label ?? "—"}`}
              </text>
            </g>
              </svg>

              <div className="absolute bottom-2 right-2 flex flex-col gap-1">
                <button
                  onClick={zoomIn}
                  className="grid-etch size-7 flex items-center justify-center text-[#94A3B8] hover:text-[#F8FAFC] rounded text-xs font-mono transition-colors"
                  aria-label="zoom in"
                  title="Zoom in"
                >
                  +
                </button>
                <button
                  onClick={zoomOut}
                  className="grid-etch size-7 flex items-center justify-center text-[#94A3B8] hover:text-[#F8FAFC] rounded text-xs font-mono transition-colors"
                  aria-label="zoom out"
                  title="Zoom out"
                >
                  −
                </button>
                <button
                  onClick={resetView}
                  className="grid-etch size-7 flex items-center justify-center text-[#94A3B8] hover:text-[#F8FAFC] rounded text-xs font-mono transition-colors"
                  aria-label="reset view"
                  title="Reset view"
                >
                  ⟲
                </button>
              </div>
              {/* Zoom indicator */}
              <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-[#030712]/80 text-[10px] font-mono text-[#64748B]">
                {Math.round(zoom * 100)}%
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-3 lg:col-span-4">
          <div className="border border-[#1E293B] bg-[#030712] p-3">
            <p className="label-mono text-[#64748B]">Legend</p>
            <ul className="mt-2 space-y-1.5 font-mono text-[11px] text-[#CBD5E1]">
              <li><span className="mr-2 inline-block size-2 bg-pass" />permitted vector</li>
              <li><span className="mr-2 inline-block size-2 bg-violation" />violating vector</li>
              <li><span className="mr-2 inline-block size-2 bg-gold" />projected point</li>
              <li><span className="mr-2 inline-block h-0.5 w-4 bg-gold align-middle" />hyperplane a·x = b</li>
              <li><span className="mr-2 inline-block size-2 bg-pass/30" />feasible chamber</li>
            </ul>
          </div>
          <div className="border border-[#1E293B] bg-[#030712] p-3" data-testid="slice-constraints">
            <p className="label-mono text-[#64748B]">
              half-spaces active on this slice ({slice.length})
            </p>
            <ul className="mt-2 max-h-60 space-y-1 overflow-y-auto font-mono text-[11px] text-[#94A3B8]">
              {slice.length === 0 && <li>none — slice is unconstrained</li>}
              {slice.map((c) => (
                <li key={c.label} className="truncate">
                  {fmt(c.ai) !== "0" && `${fmt(c.ai)}·x${ix + 1}`}
                  {fmt(c.ai) !== "0" && fmt(c.aj) !== "0" && " + "}
                  {fmt(c.aj) !== "0" && `${fmt(c.aj)}·x${iy + 1}`} ≤ {fmt(c.b)}
                  <span className="text-[#475569]"> — {c.label}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
