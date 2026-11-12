import type {ValuePanel} from "../panel"

/** Wallet Bench: the wallet panel, an agent and a wallet meeting. */
export const wallet: ValuePanel = {
  colours: ["#4fd18b", "#f4f2ea", "#e9b949"],
  pitch: [9, 9],
  stillAt: 2,
  body: /* wgsl */ `
  let asp = aspect();
  let sep = 0.15 + 0.06 * sin(t * 0.6);
  let one = vec2f(0.5 - sep, 0.5 + 0.03 * sin(t * 0.8));
  let two = mix(vec2f(0.5 + sep, 0.5 - 0.03 * sin(t * 0.8)), p.xy, p.z);
  let d1 = length((g.at - one) * asp);
  let d2 = length((g.at - two) * asp);
  let in1 = 1.0 - smoothstep(0.24, 0.28, d1);
  let in2 = 1.0 - smoothstep(0.24, 0.28, d2);
  let rim = max(exp(-sq((d1 - 0.26) * 16.0)), exp(-sq((d2 - 0.26) * 16.0)));
  let value = sat(max(in1, in2) * 0.5 + in1 * in2 * 0.5 + rim * 0.3);
  return emit(g, length(g.local) - mix(0.9, 4.0, value), ramp((in2 - in1) * 0.42 + 0.5), value);
`,
}
