import type {ValuePanel} from "../panel"

/** Repo2RLEnv: the repo panel, lines of code arriving from two sides. */
export const repo: ValuePanel = {
  colours: ["#0b2e33", "#2fc4c4", "#d6fff4"],
  pitch: [8, 10],
  stillAt: 2,
  body: /* wgsl */ `
  let below = g.count.y - 1.0 - g.id.y;
  let m = floor(t * 0.8) - below;
  let msg = floor(m / 3.0);
  let part = m - msg * 3.0;
  let right = step(0.5, hash(vec2f(msg, 1.0)));
  let width = (0.28 + 0.42 * hash(vec2f(msg, 2.0))) * mix(1.0, 0.45 + 0.5 * hash(vec2f(msg, 3.0)), step(0.5, part));
  let start = mix(0.03, 0.97 - width, right);
  let inside = step(start, x) * step(x, start + width) * step(part, 1.5);
  let mine = p.z * (1.0 - abs(right - step(0.5, p.x)));
  let amount = inside * (0.42 + 0.4 * (1.0 - below / g.count.y) + 0.18 * mine);
  return emit(g, sdBox(g.local, vec2f(3.6, 4.4), 1.6), ramp(mix(0.42, 0.95, right)), amount);
`,
}
