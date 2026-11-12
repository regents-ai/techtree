import type {ValuePanel} from "../panel"

/** Evaluate & Climb: the compare panel, two columns of tasks filling, without the Skill and with it. */
export const compare: ValuePanel = {
  colours: ["#0f2e1f", "#3fbf7f", "#d9f99d"],
  pitch: [9, 9],
  stillAt: 9,
  body: /* wgsl */ `
  let e = min(min(g.id.x, g.count.x - 1.0 - g.id.x), min(g.id.y, g.count.y - 1.0 - g.id.y));
  let border = 1.0 - step(0.5, e);
  let q = (g.at - vec2f(0.5)) * aspect();
  let clock = fract(t * 0.04);
  let spent = step(fract(atan2(q.x, q.y) / TAU + 1.0), clock);
  let after = step(0.5, x);
  let gap = 1.0 - step(1.2 / g.count.x, abs(x - 0.5));
  let lean = p.z * (step(0.5, p.x) * 2.0 - 1.0) * 0.12;
  let h = mix(0.16 + 0.32 * clock + 0.07 * sin(t * 0.7 + 2.0) - lean, 0.2 + 0.5 * clock + 0.07 * sin(t * 0.9) + lean, after);
  let filled = step(y, h) * step(1.5, e) * (1.0 - gap);
  let top = filled * step(h - 1.5 / g.count.y, y);
  let amount = max(border * mix(0.22, 0.9, spent), filled * (0.62 + 0.38 * top));
  return emit(g, sdBox(g.local, vec2f(3.3, 3.3), 0.5), ramp(mix(mix(0.45, 0.92, after) + 0.08 * top, 0.5, border)), amount);
`,
}
