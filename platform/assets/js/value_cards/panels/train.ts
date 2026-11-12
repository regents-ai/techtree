import type {ValuePanel} from "../panel"

/** Train: the train panel, steps that rise as a model improves. */
export const train: ValuePanel = {
  colours: ["#0c3550", "#38b2e0", "#d8fbe8"],
  pitch: [12, 8],
  stillAt: 5.2,
  body: /* wgsl */ `
  let steps = 6.0;
  let k = floor(x * steps);
  let h = (k + 1.0) / (steps + 1.0) * 0.94;
  let walk = fract(t * 0.11) * (steps + 1.0) - 0.5;
  let held = p.z > 0.5;
  let climber = select(floor(walk), floor(clamp(p.x, 0.0, 0.999) * steps), held);
  let rowH = 1.0 / g.count.y;
  let filled = step(y, h);
  let tread = step(h - rowH, y) * filled;
  let done = step(k + 0.5, climber);
  let here = 1.0 - step(0.5, abs(k - climber));
  let walked = step(fract(x * steps), select(fract(walk), 1.0, held));
  var amount = filled * mix(0.12, 0.86, done);
  amount = max(amount, tread * mix(0.34, 1.0, done));
  amount = max(amount, here * filled * 0.42);
  amount = max(amount, here * tread * walked);
  let colour = mix(ramp(y * 0.9), params.c.rgb, here * tread * walked);
  return emit(g, sdBox(g.local, vec2f(5.0, 3.0), 0.8), colour, amount);
`,
}
