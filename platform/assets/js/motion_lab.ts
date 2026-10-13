/**
 * The motion lab at /animations: every version of each kind of movement that
 * was tried, side by side, so a site can compare them before it changes the
 * standard. The standard versions come straight from the kit the real pages
 * use; the lab adds only the others and the islands that show them off.
 * Loaded on the lab page only.
 */
import {
  animate,
  createDrawable,
  createScope,
  random,
  spring,
  splitText,
  stagger,
  type JSAnimation,
  type LayoutAnimationParams,
  type TextSplitter,
} from "animejs"
import type {Hook} from "./hook_composition"
import {LAYOUTS, ROLLS, countHook, listHook} from "./hooks/motion/moments"
import {nope, squish} from "./hooks/motion/press"
import {GRIDS, HEADLINES, TABS, onFirstSight, tabsHook} from "./hooks/motion/reveals"
import {BASE, CLIPPED_WORD, EASE_IN_OUT, EASE_OUT, FAST, SLOW, byPointer, play, still} from "./hooks/motion/shared"
import {drawer, menu, sheet} from "./hooks/motion/slides"

// Replay buttons dispatch this, so one press can restart every island.
const REPLAY = "lab:replay"

// The two accent colours sparks, stitches and rings are drawn in.
const SPARK_COLORS = ["var(--palette-tangerine-tango)", "var(--palette-powder-blue)"]

/*
 * Sparks, rings and stitches are drawn in `#motion-lab-fx`, a layer over the
 * page that the page never patches and that no press can land on. Each bit
 * carries the id of the island that drew it, so an island that goes away
 * takes its bits with it.
 */
const layer = () => document.getElementById("motion-lab-fx")!

function spawn(owner: HTMLElement, count: number, kind: string, x: number, y: number) {
  return Array.from({length: count}, (_, i) => {
    const bit = document.createElement("span")
    bit.className = `motion-lab__fx-${kind}`
    bit.dataset.fxOwner = owner.id
    bit.style.left = `${x}px`
    bit.style.top = `${y}px`
    bit.style.setProperty("--fx-color", SPARK_COLORS[i % SPARK_COLORS.length])
    layer().append(bit)
    return bit
  })
}

const sweep = (bits: Iterable<Element>) => () => {
  for (const bit of bits) bit.remove()
}

const sweepAll = (owner: HTMLElement) => sweep(layer().querySelectorAll(`[data-fx-owner="${owner.id}"]`))()

function centre(el: Element) {
  const box = el.getBoundingClientRect()
  return [box.left + box.width / 2, box.top + box.height / 2]
}

type Island = {el: HTMLElement; scope?: ReturnType<typeof createScope>}

/*
 * Presses, named with `data-press`. Squish and nope are the standard ones;
 * the rest squish too and throw something in the air.
 */
type Press = (owner: HTMLElement, button: HTMLElement, x: number, y: number) => void

const PRESSES: Record<string, Press> = {
  squish: (_owner, button) => squish(button),
  nope: (_owner, button) => nope(button),

  jelly: (_owner, button) =>
    play(button, {
      scaleX: [1, 1.2, 0.9, 1.05, 0.98, 1],
      scaleY: [1, 0.82, 1.1, 0.96, 1.02, 1],
      duration: 560,
      ease: "inOut(2)",
    }),

  sparks: (owner, button, x, y) => {
    squish(button)
    const sparks = spawn(owner, 10, "spark", x, y)
    const flights = sparks.map((_spark, i) => {
      const angle = (i / sparks.length) * Math.PI * 2 + random(-0.25, 0.25, 2)
      const reach = random(26, 54)
      return {x: Math.cos(angle) * reach, y: Math.sin(angle) * reach}
    })
    animate(sparks, {
      x: (_el: unknown, i = 0) => flights[i].x,
      y: (_el: unknown, i = 0) => flights[i].y,
      scale: [1, 0],
      duration: 520,
      ease: "out(4)",
      onComplete: sweep(sparks),
    })
  },

  ping: (owner, button, x, y) => {
    squish(button)
    const rings = spawn(owner, 2, "ring", x, y)
    animate(rings, {
      scale: [0.2, 3.2],
      opacity: [0.7, 0],
      delay: stagger(110),
      duration: 560,
      ease: EASE_OUT,
      onComplete: sweep(rings),
    })
  },

  stitches: (owner, button, x, y) => {
    squish(button)
    const stitches = spawn(owner, 5, "stitch", x, y)
    for (const stitch of stitches) stitch.textContent = "+"
    animate(stitches, {
      x: () => random(-28, 28),
      y: () => random(-64, -34),
      rotate: () => random(-120, 120),
      scale: [0.2, 1.2, 0.7],
      opacity: [1, 1, 0],
      delay: stagger(35),
      duration: 700,
      ease: "out(3)",
      onComplete: sweep(stitches),
    })
  },
}

const LabPress: Hook = {
  mounted(this: Island) {
    const scope = createScope({root: this.el})

    this.scope = scope.add(() => {
      const onClick = (event: MouseEvent) => {
        const button = event.target instanceof Element ? event.target.closest<HTMLElement>("[data-press]") : null
        if (button === null || !byPointer(event) || still(this.el)) return
        PRESSES[button.dataset.press ?? ""](this.el, button, event.clientX, event.clientY)
      }

      this.el.addEventListener("click", onClick)
      return () => {
        this.el.removeEventListener("click", onClick)
        sweepAll(this.el)
      }
    })
  },

  destroyed(this: Island) {
    this.scope?.revert()
  },
}

/*
 * Panels the lab opens and closes itself. Each version opens with its own
 * move, the standard one straight from the kit, and closes to where it waits
 * while hidden. The island owns the panels outright (the page never patches
 * inside it); which version each uses is read from `data-<panel>` on the
 * island, which the page keeps current.
 */
type Panel = {away: Record<string, number | string>; open: (el: HTMLElement) => JSAnimation}

const PANELS: Record<string, {shade: boolean; versions: Record<string, Panel>}> = {
  drawer: {
    shade: true,
    versions: {
      glide: {away: {x: "-100%"}, open: el => play(el, {x: ["-100%", "0%"], duration: SLOW, ease: EASE_OUT})},
      spring: {away: {x: "-100%"}, open: drawer},
      lean: {
        away: {x: "-100%", rotate: -7},
        open: el => play(el, {x: ["-100%", "0%"], rotate: [-7, 0], duration: 460, ease: "outBack(1.4)"}),
      },
    },
  },
  sheet: {
    shade: true,
    versions: {
      rise: {away: {y: "100%"}, open: el => play(el, {y: ["100%", "0%"], duration: SLOW, ease: EASE_OUT})},
      spring: {away: {y: "100%"}, open: sheet},
    },
  },
  menu: {
    shade: false,
    versions: {
      pop: {away: {y: -6, scale: 0.9, opacity: 0}, open: menu},
      drop: {
        away: {y: -14, opacity: 0},
        open: el => play(el, {y: {from: -14}, opacity: {from: 0}, duration: BASE, ease: EASE_OUT}),
      },
    },
  },
  note: {
    shade: false,
    versions: {
      peel: {
        away: {x: -30, y: 24, rotate: -16, scale: 0.6, opacity: 0},
        open: el =>
          play(el, {
            x: {from: -30},
            y: {from: 24},
            rotate: {from: -16},
            scale: {from: 0.6},
            opacity: {from: 0},
            duration: 420,
            ease: "outBack(2)",
          }),
      },
      toss: {
        away: {x: -160, y: -40, rotate: -40, opacity: 0},
        open: el =>
          play(el, {
            x: {from: -160},
            y: {from: -40},
            rotate: {from: -40},
            opacity: {from: 0},
            ease: spring({bounce: 0.4, duration: 460}),
          }),
      },
    },
  },
}

type SlidesIsland = Island & {moving: Map<Element, JSAnimation>; openers: Map<string, HTMLElement>}

const LabSlides: Hook = {
  mounted(this: SlidesIsland) {
    const scope = createScope({root: this.el})
    this.moving = new Map()
    this.openers = new Map()

    const panel = (name: string) => this.el.querySelector<HTMLElement>(`[data-lab-panel="${name}"]`)!
    const shade = () => this.el.querySelector<HTMLElement>("[data-shade]")!
    const version = (name: string) => PANELS[name].versions[this.el.dataset[name] ?? ""]
    // A panel still sliding shut already counts as closed, so pressing its
    // button again opens it rather than closing it twice.
    const opened = () =>
      Object.keys(PANELS).filter(name => this.openers.get(name)?.getAttribute("aria-expanded") === "true")

    // One move per element at a time: a new one takes over from wherever the
    // last one left it.
    const move = (el: Element, animation: JSAnimation) => {
      this.moving.get(el)?.pause()
      this.moving.set(el, animation)
    }
    const settle = (el: HTMLElement) => {
      this.moving.get(el)?.pause()
      this.moving.delete(el)
      el.removeAttribute("style")
    }

    this.scope = scope.add(() => {
      const open = (name: string, opener: HTMLElement, animated: boolean) => {
        const el = panel(name)
        settle(el)
        el.hidden = false

        // A shade still fading out stays for the panel opening over it.
        if (PANELS[name].shade) {
          const arriving = shade().hidden
          settle(shade())
          shade().hidden = false
          if (animated && arriving) move(shade(), play(shade(), {opacity: {from: 0}, duration: BASE, ease: EASE_OUT}))
        }
        if (animated) move(el, version(name).open(el))

        const items = [...el.querySelectorAll("[data-item]")]
        if (animated && items.length > 0) {
          play(items, {opacity: {from: 0}, y: {from: 10}, delay: stagger(40, {start: 80}), duration: SLOW, ease: EASE_OUT})
        }

        this.openers.set(name, opener)
        opener.setAttribute("aria-expanded", "true")
        el.querySelector<HTMLElement>("[data-close]")?.focus({preventScroll: true})
      }

      const close = (name: string, animated: boolean) => {
        const el = panel(name)
        const put = () => {
          el.hidden = true
          settle(el)
        }

        const others = opened().some(other => other !== name && PANELS[other].shade)
        if (PANELS[name].shade && !others) {
          const hide = () => {
            shade().hidden = true
            settle(shade())
          }
          if (animated) move(shade(), animate(shade(), {opacity: 0, duration: FAST, ease: "in(2)", onComplete: hide}))
          else hide()
        }

        if (animated) move(el, animate(el, {...version(name).away, duration: BASE, ease: "in(3)", onComplete: put}))
        else put()

        const opener = this.openers.get(name)
        opener?.setAttribute("aria-expanded", "false")
        opener?.focus({preventScroll: true})
      }

      const onClick = (event: MouseEvent) => {
        if (!(event.target instanceof Element)) return
        const animated = byPointer(event) && !still(this.el)
        const opener = event.target.closest<HTMLElement>("[data-open]")
        const closer = event.target.closest("[data-close]")

        if (opener !== null) {
          const name = opener.dataset.open ?? ""
          if (opened().includes(name)) close(name, animated)
          else open(name, opener, animated)
        } else if (closer !== null) {
          close(closer.closest<HTMLElement>("[data-lab-panel]")?.dataset.labPanel ?? "", animated)
        } else if (event.target.closest("[data-shade]") !== null) {
          for (const name of opened()) if (PANELS[name].shade) close(name, animated)
        }
      }

      const onKey = (event: KeyboardEvent) => {
        if (event.key !== "Escape") return
        const last = opened().at(-1)
        if (last !== undefined) close(last, false)
      }

      this.el.addEventListener("click", onClick)
      this.el.addEventListener("keydown", onKey)
      return () => {
        this.el.removeEventListener("click", onClick)
        this.el.removeEventListener("keydown", onKey)
      }
    })
  },

  destroyed(this: SlidesIsland) {
    this.scope?.revert()
  },
}

// Lists and notes: the kit's bounce and pop, and the others that were tried.
const LAB_LAYOUTS: Record<string, () => LayoutAnimationParams> = {
  ...LAYOUTS,
  rise: () => ({
    duration: SLOW,
    ease: EASE_OUT,
    enterFrom: {opacity: 0, transform: "translateY(18px) scale(.96)"},
    leaveTo: {opacity: 0, transform: "translateY(-10px) scale(.96)"},
  }),
  side: () => ({
    duration: SLOW,
    ease: EASE_IN_OUT,
    enterFrom: {opacity: 0, transform: "translateX(64px)"},
    leaveTo: {opacity: 0, transform: "translateX(64px)"},
  }),
  glide: () => ({
    duration: 360,
    ease: EASE_IN_OUT,
    enterFrom: {opacity: 0, transform: "scale(.9)"},
    leaveTo: {opacity: 0, transform: "scale(.9)"},
  }),
  ripple: () => ({
    duration: SLOW,
    ease: EASE_IN_OUT,
    delay: stagger(35),
    enterFrom: {opacity: 0, transform: "translateX(-16px)"},
    leaveTo: {opacity: 0, transform: "translateX(16px)"},
  }),
}

// Figures: the kit's roll, and the others that were tried.
const LAB_ROLLS = {
  ...ROLLS,
  tick: {
    clip: true,
    move: (up: boolean) => ({y: [up ? "60%" : "-60%", "0%"], opacity: {from: 0}, ease: spring({bounce: 0.55, duration: 300})}),
  },
  pop: {clip: false, move: () => ({scale: {from: 1.9}, opacity: {from: 0}, duration: SLOW, ease: EASE_OUT})},
}

// Tabs: the kit's glide, and the others that were tried.
const LAB_TABS = {
  ...TABS,
  // The underline stretches to cover both tabs, then lets go of the old one.
  stretch: {
    ink: (from: {x: number; scaleX: number}, to: {x: number; scaleX: number}, base: number) => {
      const left = Math.min(from.x, to.x)
      const right = Math.max(from.x + from.scaleX * base, to.x + to.scaleX * base)
      return {
        x: [{to: left, duration: 140}, {to: to.x, duration: 180}],
        scaleX: [{to: (right - left) / base, duration: 140}, {to: to.scaleX, duration: 180}],
        ease: "inOut(2)",
      }
    },
    panel: () => ({y: {from: 10}, opacity: {from: 0}, duration: SLOW, ease: EASE_OUT}),
  },
  spring: {
    ink: (_from: unknown, to: {x: number; scaleX: number}) => ({...to, ease: spring({bounce: 0.35, duration: 360})}),
    panel: () => ({scale: {from: 0.96}, opacity: {from: 0}, ease: spring({bounce: 0.3, duration: 320})}),
  },
}

// How the stamp lands once the server has marked the work done. Each returns
// when the tick starts drawing.
const STAMPS: Record<string, (card: HTMLElement, stamp: HTMLElement) => number> = {
  thunk: (card, stamp) => {
    play(stamp, {scale: {from: 2.4}, rotate: {from: -24}, opacity: {from: 0}, duration: 240, ease: "in(3)"})
    play(card, {y: [0, 5, -1, 0], delay: 220, duration: 260, ease: "out(2)"})
    return 260
  },
  ink: (_card, stamp) => {
    play(stamp, {scale: {from: 1.15}, opacity: {from: 0}, duration: BASE, ease: EASE_OUT})
    return 120
  },
  party: (card, stamp) => {
    play(stamp, {scale: {from: 0}, rotate: {from: 40}, ease: spring({bounce: 0.5, duration: 420})})
    const [x, y] = centre(stamp)
    const stitches = spawn(card, 8, "stitch", x, y)
    for (const stitch of stitches) stitch.textContent = "+"
    animate(stitches, {
      x: (_el: unknown, i = 0) => Math.cos((i / stitches.length) * Math.PI * 2) * 70,
      y: (_el: unknown, i = 0) => Math.sin((i / stitches.length) * Math.PI * 2) * 48,
      rotate: (_el: unknown, i = 0) => (i % 2 ? 1 : -1) * 90,
      scale: [0.2, 1.1, 0.6],
      opacity: [1, 1, 0],
      delay: 80,
      duration: 640,
      ease: "out(3)",
      onComplete: sweep(stitches),
    })
    return 180
  },
}

/*
 * A card stamped done. The page renders the stamp, then tells the island it
 * was just done, so a page opened on finished work shows the stamp without
 * any fuss.
 */
const LabStamp: Hook = {
  mounted(this: Island & {handleEvent: (event: string, callback: () => void) => void}) {
    const scope = createScope({root: this.el})

    this.scope = scope.add(() => {
      scope.add("stamp", () => {
        const stamp = this.el.querySelector<HTMLElement>("[data-stamp]")!
        const inkAt = STAMPS[this.el.dataset.variant ?? ""](this.el, stamp)
        const [tick] = createDrawable(stamp.querySelector("[data-tick]")!)
        animate(tick, {draw: ["0 0", "0 1"], delay: inkAt, duration: SLOW, ease: EASE_OUT})
      })

      return () => sweepAll(this.el)
    })

    this.handleEvent("motion:done", () => {
      if (!still(this.el)) this.scope?.methods.stamp()
    })
  },

  destroyed(this: Island) {
    this.scope?.revert()
  },
}

// Headlines and cards: the kit's rise and cascade, and the others that were tried.
const LAB_HEADLINES: Record<string, (split: TextSplitter) => JSAnimation> = {
  ...HEADLINES,
  cascade: split =>
    play(split.chars, {
      y: ["-100%", "0%"],
      rotate: {from: -20},
      opacity: {from: 0},
      delay: stagger(16),
      duration: SLOW,
      ease: "outBack(1.8)",
    }),
  type: split => play(split.chars, {opacity: {from: 0}, delay: stagger(24), duration: 60, ease: "linear"}),
}

const LAB_GRIDS: Record<string, (cards: Element[]) => JSAnimation> = {
  ...GRIDS,
  bloom: cards =>
    play(cards, {
      scale: {from: 0.8},
      opacity: {from: 0},
      delay: stagger(60, {grid: [3, Math.ceil(cards.length / 3)], from: "center"}),
      ease: spring({bounce: 0.4, duration: 360}),
    }),
  drop: cards =>
    play(cards, {
      y: {from: -40},
      rotate: {from: (_el: unknown, i = 0) => (i % 2 ? 6 : -6)},
      opacity: {from: 0},
      delay: stagger(40, {from: "random"}),
      duration: 420,
      ease: "outBack(1.6)",
    }),
}

type EntranceIsland = Island & {variant?: string}

/*
 * An entrance the island owns outright: the page never patches inside it and
 * only keeps `data-variant` current. It plays once the first time it scrolls
 * into view (`onFirstSight`), and again when the version changes, when its own
 * replay button is pressed and when the page asks every island to replay.
 */
const entrance = <T>(versions: Record<string, (targets: T) => unknown>, pieces: (el: HTMLElement) => T): Hook => ({
  mounted(this: EntranceIsland) {
    const scope = createScope({root: this.el})
    this.variant = this.el.dataset.variant

    this.scope = scope.add(() => {
      const targets = pieces(this.el)

      scope.add("play", () => {
        if (!still(this.el)) versions[this.el.dataset.variant ?? ""](targets)
      })

      const onClick = (event: MouseEvent) => {
        if (event.target instanceof Element && event.target.closest("[data-replay]")) scope.methods.play()
      }
      const onReplay = () => scope.methods.play()

      const stopWatching = onFirstSight(this.el, () => scope.methods.play())
      this.el.addEventListener("click", onClick)
      window.addEventListener(REPLAY, onReplay)
      return () => {
        stopWatching()
        this.el.removeEventListener("click", onClick)
        window.removeEventListener(REPLAY, onReplay)
      }
    })
  },

  updated(this: EntranceIsland) {
    if (this.el.dataset.variant === this.variant) return
    this.variant = this.el.dataset.variant
    this.scope?.methods.play()
  },

  destroyed(this: EntranceIsland) {
    this.scope?.revert()
  },
})

export const hooks = {
  LabPress,
  LabSlides,
  LabList: listHook(LAB_LAYOUTS),
  LabCount: countHook(LAB_ROLLS),
  LabStamp,
  LabTabs: tabsHook(LAB_TABS),
  LabHeadline: entrance(LAB_HEADLINES, el =>
    splitText(el.querySelector<HTMLElement>("[data-headline]")!, {words: CLIPPED_WORD, chars: true}),
  ),
  LabCascade: entrance(LAB_GRIDS, el => [...el.querySelectorAll("[data-card]")]),
}
