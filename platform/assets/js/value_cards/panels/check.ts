import type {ValuePanel} from "../panel"

/** Offline check: the check panel, columns of checks that fill and settle. */
export const check: ValuePanel = {
  colours: ["#26310b", "#b5d94a", "#f7ffe0"],
  pitch: [9, 9],
  stillAt: 4,
  body: /* wgsl */ `
  let cq = x * 3.0;
  let ci = min(floor(cq), 2.0);
  let cf = cq - ci;
  let inCol = step(0.07, cf) * step(cf, 0.93);
  let slot = floor(g.id.y / 4.0);
  let card = step(g.id.y - slot * 4.0, 2.5);
  let has = step(0.3 + 0.12 * ci, hash(vec2f(ci, slot)));
  let cycle = t * 0.09;
  let phase = fract(cycle) * 3.0;
  let pick = floor(hash(vec2f(floor(cycle), 5.0)) * floor(g.count.y / 4.0));
  let mover = (1.0 - step(0.5, abs(ci - floor(phase)))) * (1.0 - step(0.5, abs(slot - pick)));
  let fill = step(cf, 0.07 + 0.86 * fract(phase));
  let over = p.z * (1.0 - step(0.5, abs(ci - min(floor(p.x * 3.0), 2.0)))) * (1.0 - step(0.5, abs(slot - floor((1.0 - p.y) * g.count.y / 4.0))));
  let amount = max(max(has * (0.28 + 0.24 * ci), mover * (0.35 + 0.6 * fill)), over * 0.96);
  let tone = max(max(has * (0.12 + 0.24 * ci), mover * (0.5 + 0.5 * fill)), over);
  return emit(g, mix(9.0, sdBox(g.local, vec2f(3.4, 3.4), 0.5), inCol * card), ramp(tone), amount);
`,
}
