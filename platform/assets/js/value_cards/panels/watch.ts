import type {ValuePanel} from "../panel"

/** Watchdog: the watch panel, a sweep spreading out from one place. */
export const watch: ValuePanel = {
  colours: ["#3d2406", "#f0a531", "#fff4d6"],
  pitch: [10, 10],
  stillAt: 2,
  body: /* wgsl */ `
  let src = mix(vec2f(0.5 + 0.1 * sin(t * 0.3), 0.46), p.xy, p.z);
  let r = length((g.at - src) * aspect());
  let v = smoothstep(0.0, 1.0, sin(r * 24.0 - t * 2.4)) * exp(-r * 2.0);
  let value = max(v, exp(-sq(r * 10.0)));
  return emit(g, length(g.local) - mix(0.9, 4.5, value), ramp(0.08 + 0.92 * value), value);
`,
}
