/**
 * Every value card's panel, by the name its card carries in `data-value-card`.
 * The home page's Products row shows all six, in this order.
 */
import {check} from "./panels/check"
import {compare} from "./panels/compare"
import {repo} from "./panels/repo"
import {train} from "./panels/train"
import {wallet} from "./panels/wallet"
import {watch} from "./panels/watch"
import type {ValuePanel} from "./panel"

export const panels: Record<string, ValuePanel> = {
  compare,
  wallet,
  train,
  check,
  repo,
  watch,
}
