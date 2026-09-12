"use client";

/**
 * The ambient layer behind the whole dashboard.
 *
 * Two things are drawn: slow aurora blooms that drift on their own, and a
 * constellation of nodes that repel the cursor and link to their neighbours.
 * It reads as a market graph without pretending to be one — the intent is
 * depth behind the content, not another chart.
 *
 * Cost control, since this sits under every page:
 *   - node count scales with viewport area and is hard-capped,
 *   - neighbour linking runs over a uniform grid, not every pair,
 *   - the loop stops entirely when the tab is hidden or the reader has asked
 *     for reduced motion,
 *   - the canvas is backed at device pixel ratio, capped at 2.
 */

import { useEffect, useRef } from "react";

type Node = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  /** Individual twinkle phase, so the field never pulses in unison. */
  phase: number;
};

const LINK_DIST = 132;
const CURSOR_RADIUS = 168;
const MAX_NODES = 92;

export function AuroraCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const pointer = { x: -9999, y: -9999 };
    let nodes: Node[] = [];
    let w = 0;
    let h = 0;
    let raf = 0;
    let running = false;
    let t = 0;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // One node per ~17k css pixels keeps the density even between a laptop
      // and an ultrawide without ever running away.
      const target = Math.min(MAX_NODES, Math.max(26, Math.round((w * h) / 17000)));
      nodes = Array.from({ length: target }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.17,
        vy: (Math.random() - 0.5) * 0.17,
        r: Math.random() * 1.5 + 0.7,
        phase: Math.random() * Math.PI * 2,
      }));
    };

    /** Aurora blooms: three offset radial gradients on slow lissajous paths. */
    const drawAurora = () => {
      const blooms: [number, number, number, string][] = [
        [
          w * (0.18 + Math.sin(t * 0.00021) * 0.1),
          h * (0.08 + Math.cos(t * 0.00017) * 0.09),
          Math.max(w, h) * 0.52,
          "109,141,255",
        ],
        [
          w * (0.84 + Math.cos(t * 0.00019) * 0.09),
          h * (0.16 + Math.sin(t * 0.00023) * 0.1),
          Math.max(w, h) * 0.44,
          "167,139,250",
        ],
        [
          w * (0.55 + Math.sin(t * 0.00013) * 0.14),
          h * (0.95 + Math.cos(t * 0.00015) * 0.06),
          Math.max(w, h) * 0.58,
          "34,211,238",
        ],
      ];

      for (const [x, y, r, rgb] of blooms) {
        const g = ctx.createRadialGradient(x, y, 0, x, y, r);
        g.addColorStop(0, `rgba(${rgb},0.085)`);
        g.addColorStop(0.55, `rgba(${rgb},0.028)`);
        g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
      }
    };

    /**
     * Neighbour links via a uniform grid. Each node only tests the nine cells
     * around it, which turns an O(n²) sweep into something that stays flat as
     * the field grows.
     */
    const drawLinks = () => {
      const cell = LINK_DIST;
      const cols = Math.max(1, Math.ceil(w / cell));
      const buckets = new Map<number, number[]>();

      nodes.forEach((n, i) => {
        const key = Math.floor(n.y / cell) * cols + Math.floor(n.x / cell);
        const b = buckets.get(key);
        if (b) b.push(i);
        else buckets.set(key, [i]);
      });

      ctx.lineWidth = 1;
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        const cx = Math.floor(a.x / cell);
        const cy = Math.floor(a.y / cell);
        for (let ox = -1; ox <= 1; ox++) {
          for (let oy = -1; oy <= 1; oy++) {
            const b = buckets.get((cy + oy) * cols + (cx + ox));
            if (!b) continue;
            for (const j of b) {
              if (j <= i) continue; // each pair once
              const o = nodes[j];
              const dx = a.x - o.x;
              const dy = a.y - o.y;
              const d2 = dx * dx + dy * dy;
              if (d2 > LINK_DIST * LINK_DIST) continue;
              const alpha = (1 - Math.sqrt(d2) / LINK_DIST) * 0.16;
              ctx.strokeStyle = `rgba(150,175,255,${alpha.toFixed(3)})`;
              ctx.beginPath();
              ctx.moveTo(a.x, a.y);
              ctx.lineTo(o.x, o.y);
              ctx.stroke();
            }
          }
        }
      }
    };

    const step = () => {
      t += 16;
      ctx.clearRect(0, 0, w, h);
      drawAurora();

      for (const n of nodes) {
        n.x += n.vx;
        n.y += n.vy;

        // Wrap rather than bounce: a bounce reads as a wall, a wrap reads as
        // an endless field.
        if (n.x < -20) n.x = w + 20;
        if (n.x > w + 20) n.x = -20;
        if (n.y < -20) n.y = h + 20;
        if (n.y > h + 20) n.y = -20;

        // Gentle repulsion, so the field parts around the cursor.
        const dx = n.x - pointer.x;
        const dy = n.y - pointer.y;
        const d2 = dx * dx + dy * dy;
        if (d2 < CURSOR_RADIUS * CURSOR_RADIUS && d2 > 0.01) {
          const d = Math.sqrt(d2);
          const push = ((CURSOR_RADIUS - d) / CURSOR_RADIUS) * 0.55;
          n.x += (dx / d) * push;
          n.y += (dy / d) * push;
        }
      }

      drawLinks();

      for (const n of nodes) {
        const twinkle = 0.42 + Math.sin(t * 0.0016 + n.phase) * 0.26;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(178,198,255,${twinkle.toFixed(3)})`;
        ctx.fill();
      }

      raf = requestAnimationFrame(step);
    };

    const start = () => {
      if (running || reduce.matches || document.hidden) return;
      running = true;
      raf = requestAnimationFrame(step);
    };
    const stop = () => {
      running = false;
      cancelAnimationFrame(raf);
    };

    /** One static frame, so a reduced-motion reader still gets the depth. */
    const paintStill = () => {
      ctx.clearRect(0, 0, w, h);
      drawAurora();
      drawLinks();
      for (const n of nodes) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(178,198,255,.4)";
        ctx.fill();
      }
    };

    const onResize = () => {
      resize();
      if (reduce.matches) paintStill();
    };
    const onPointer = (e: PointerEvent) => {
      pointer.x = e.clientX;
      pointer.y = e.clientY;
    };
    const onLeave = () => {
      pointer.x = -9999;
      pointer.y = -9999;
    };
    const onVisibility = () => (document.hidden ? stop() : start());
    const onMotionPref = () => {
      if (reduce.matches) {
        stop();
        paintStill();
      } else start();
    };

    resize();
    if (reduce.matches) paintStill();
    else start();

    window.addEventListener("resize", onResize);
    window.addEventListener("pointermove", onPointer, { passive: true });
    window.addEventListener("pointerleave", onLeave);
    document.addEventListener("visibilitychange", onVisibility);
    reduce.addEventListener("change", onMotionPref);

    return () => {
      stop();
      window.removeEventListener("resize", onResize);
      window.removeEventListener("pointermove", onPointer);
      window.removeEventListener("pointerleave", onLeave);
      document.removeEventListener("visibilitychange", onVisibility);
      reduce.removeEventListener("change", onMotionPref);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 h-full w-full"
      style={{ maskImage: "radial-gradient(ellipse 130% 95% at 50% 0%, #000 45%, transparent 92%)" }}
    />
  );
}
