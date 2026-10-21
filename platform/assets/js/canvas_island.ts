/**
 * A decorative canvas the browser owns, and every reason not to draw on it.
 *
 * Each holographic card is one of these. What lives here is everything the card
 * does not draw itself: the canvas box, when a frame is worth drawing, and the
 * still face the visitor sees until one really lands.
 */

type RequestFrame = (callback: FrameRequestCallback) => number
type CancelFrame = (handle: number) => void

export type MediaQuery = {
  readonly matches: boolean
  addEventListener(type: "change", listener: () => void): void
  removeEventListener(type: "change", listener: () => void): void
}

/** What an island asks of the renderer behind it: a size, a frame, and a way out. */
export type IslandRenderer = {
  resize(width: number, height: number): void
  /** Advances the easing one frame, or snaps it home. True when the picture moved. */
  step(snap: boolean): boolean
  present(): void
  /** Resolves once the work submitted so far has finished on the GPU. */
  settled(): Promise<void>
  dispose(): void
}

export type LoadRenderer<Renderer extends IslandRenderer> = (
  canvas: HTMLCanvasElement,
  size: readonly [number, number],
  onDeviceLost: () => void,
) => Promise<Renderer>

export type CanvasIslandOptions<Renderer extends IslandRenderer> = {
  cancelFrame?: CancelFrame
  devicePixelRatio?: () => number
  loadRenderer?: LoadRenderer<Renderer>
  motionQuery?: () => MediaQuery
  requestFrame?: RequestFrame
  supportsWebGpu?: () => boolean
}

export type CanvasIslandController = {
  mount(): void
  pause(): void
  resume(): void
  destroy(): void
}

/** What the island lends to whatever wants to steer the picture inside it. */
type IslandInteraction<Renderer extends IslandRenderer> = {
  readonly root: HTMLElement
  canvas(): HTMLCanvasElement
  renderer(): Renderer | undefined
  /** Gives the easing its full budget again and asks for a frame. */
  nudge(): void
  /** Registers work to run each time a renderer lands, before its first frame. */
  onReady(compose: () => void): void
}

type IslandKind<Renderer extends IslandRenderer> = {
  /** The canvas inside the island root. */
  readonly canvasSelector: string
  /**
   * Dataset flag on the root: "true" once a first frame really landed, "false" once
   * the island knows it will not draw here, and absent while that is still open.
   */
  readonly readyFlag: string
  readonly browserLoad: LoadRenderer<Renderer>
  /** A picture that moves is never drawn for a visitor who asked for less of it. */
  readonly motionSensitive: boolean
  /** A picture that keeps moving by itself never runs out of frames to settle in. */
  readonly continuous: boolean
  /** Listeners the island keeps for as long as it is watching. */
  interact?(island: IslandInteraction<Renderer>): () => void
}

/** Resolution ceilings. The picture is decorative; a 4K backing store is not. */
export const MAX_DEVICE_PIXEL_RATIO = 1.5
export const MAX_DRAWING_BUFFER_PIXELS = 1_500_000

/** Frames the easing may spend settling after the pointer stops moving. */
export const EASING_FRAME_LIMIT = 24

/**
 * Devices the island will ask for again after one it was drawing on is lost.
 *
 * A browser takes the GPU device back for its own reasons — a backgrounded tab,
 * a GPU process restart, a driver reset, a machine saving power — and hands out
 * a new one the moment it is asked. So a loss is answered by asking again. The
 * budget is what separates that from a device that fails as fast as it is
 * granted, and a frame that lands spends none of it.
 */
export const DEVICE_RECOVERY_LIMIT = 3

/**
 * Backing-store size for a CSS box, capped on both device pixel ratio and total
 * pixels. Both axes take the same scale, so the picture never stretches.
 */
export function drawingBufferSize(
  width: number,
  height: number,
  devicePixelRatio: number,
): readonly [number, number] {
  const ratio = Math.min(MAX_DEVICE_PIXEL_RATIO, Math.max(1, devicePixelRatio))
  const requested = width * height * ratio * ratio
  const fit =
    requested > MAX_DRAWING_BUFFER_PIXELS ? Math.sqrt(MAX_DRAWING_BUFFER_PIXELS / requested) : 1
  return [
    Math.max(1, Math.floor(width * ratio * fit)),
    Math.max(1, Math.floor(height * ratio * fit)),
  ]
}

const browserRequestFrame: RequestFrame = callback => window.requestAnimationFrame(callback)
const browserCancelFrame: CancelFrame = handle => window.cancelAnimationFrame(handle)

/**
 * Watches one canvas and draws on it only when that is worth doing.
 *
 * What a frame contains is the renderer's business, and the chunk holding it is
 * only ever imported once the picture is actually wanted.
 */
export const createCanvasIsland = <Renderer extends IslandRenderer>(
  root: HTMLElement,
  options: CanvasIslandOptions<Renderer>,
  kind: IslandKind<Renderer>,
): CanvasIslandController => {
  const cancelFrame = options.cancelFrame ?? browserCancelFrame
  const devicePixelRatio = options.devicePixelRatio ?? (() => window.devicePixelRatio || 1)
  const loadRenderer = options.loadRenderer ?? kind.browserLoad
  const motionQuery =
    options.motionQuery ?? (() => window.matchMedia("(prefers-reduced-motion: reduce)"))
  const requestFrame = options.requestFrame ?? browserRequestFrame
  const supportsWebGpu = options.supportsWebGpu ?? (() => Boolean(navigator.gpu))

  const canvas = () => root.querySelector<HTMLCanvasElement>(kind.canvasSelector)!

  const motion = motionQuery()

  let generation = 0
  let renderer: Renderer | undefined
  let release: (() => void) | undefined
  let startFrame: number | undefined
  let startingGeneration: number | undefined
  let renderFrame: number | undefined
  let pendingSize: readonly [number, number] | undefined
  let pendingPresent = false
  let confirming = false
  let easingFrames = 0
  let recoveries = 0
  let compose: (() => void) | undefined

  // Every reason the island may work is tracked apart from every other one, because
  // they come back independently: an island scrolling into view while the tab is hidden
  // is worth exactly as much as a tab returning while the island is still offscreen.
  let mounted = false
  let retired = false
  let awake = true
  let onscreen = false
  let visible = true
  let motionAllowed = true

  /** Nothing is scheduled, imported or drawn unless all of these hold. */
  const active = () => mounted && !retired && awake && visible && onscreen && motionAllowed

  const motionPermits = () => !kind.motionSensitive || !motion.matches

  const measure = (): readonly [number, number] => {
    const {width, height} = canvas().getBoundingClientRect()
    return drawingBufferSize(width, height, devicePixelRatio())
  }

  const stopFrame = () => {
    if (renderFrame !== undefined) cancelFrame(renderFrame)
    renderFrame = undefined
  }

  const stopStart = () => {
    if (startFrame !== undefined) cancelFrame(startFrame)
    startFrame = undefined
  }

  const schedule = () => {
    if (renderFrame !== undefined || !renderer || !active()) return
    renderFrame = requestFrame(tick)
  }

  const invalidate = () => {
    pendingPresent = true
    schedule()
  }

  /**
   * Two frames of headroom before the renderer chunk is even asked for. The first
   * callback still runs before what the server rendered paints; the second runs after it.
   *
   * A start still waiting on the chunk has no renderer to point at yet, so the generation
   * it belongs to is what says one is already coming. Only a newer one may ask again.
   */
  const scheduleStart = () => {
    if (startFrame !== undefined || startingGeneration === generation || renderer) return
    const started = generation
    startFrame = requestFrame(() => {
      startFrame = requestFrame(() => {
        startFrame = undefined
        startingGeneration = started
        void start(started)
      })
    })
  }

  /**
   * The one place the island decides whether it should be doing anything at all. Every
   * condition is read fresh, so a return on one axis while another still says no
   * queues no work of any kind.
   */
  const sync = () => {
    if (!active()) {
      stopStart()
      stopFrame()
      // A start that was in flight belongs to a generation that no longer wants it;
      // whatever it produces is disposed when it lands.
      if (!renderer) generation += 1
      return
    }
    if (renderer) invalidate()
    else scheduleStart()
  }

  /**
   * Back to what the server rendered: the renderer is dropped and the reveal undone.
   * Bumping the generation is what makes an import or a frame confirmation still in
   * flight land on the floor instead of on a disposed renderer.
   */
  const retreat = () => {
    generation += 1
    confirming = false
    pendingPresent = false
    easingFrames = 0
    delete root.dataset[kind.readyFlag]
    stopStart()
    stopFrame()
    renderer?.dispose()
    renderer = undefined
  }

  /**
   * A retreat the island does not come back from: the GPU is not going to draw this,
   * so everything the island watches with, and whatever steers the picture, lets go
   * now, and the flag says so, so the page can show what the server rendered.
   */
  const retire = () => {
    retired = true
    release?.()
    release = undefined
    retreat()
    root.dataset[kind.readyFlag] = "false"
  }

  /**
   * The device the island was drawing on is gone. Every one of these is answered
   * the same way, whether it arrived as a lost device or as GPU work that never
   * finished, because they are the same event reaching the island by two routes.
   *
   * The renderer is dropped and another device asked for, which is what the
   * visitor means by the picture coming back. A device that keeps going before it
   * has drawn anything is not going to start now, and the island stops asking.
   */
  const deviceLost = () => {
    if (recoveries >= DEVICE_RECOVERY_LIMIT) {
      retire()
      return
    }
    recoveries += 1
    retreat()
    sync()
  }

  /** The fallback stays until real GPU work for the first frame has finished. */
  const confirmFirstFrame = () => {
    confirming = true
    const drawn = generation
    void renderer!.settled().then(
      () => {
        if (drawn !== generation) return
        root.dataset[kind.readyFlag] = "true"
        // This device drew. Whatever it cost to reach is spent, and a loss an hour
        // from now is answered with a full budget of its own.
        recoveries = 0
      },
      () => {
        if (drawn === generation) deviceLost()
      },
    )
  }

  function tick(): void {
    renderFrame = undefined
    if (!renderer) return
    if (pendingSize) {
      renderer.resize(pendingSize[0], pendingSize[1])
      pendingSize = undefined
      pendingPresent = true
    }
    easingFrames += 1
    // The last frame the easing is allowed snaps home, so there is never a frame after
    // it with nothing left to do.
    const last = !kind.continuous && easingFrames >= EASING_FRAME_LIMIT
    const moved = renderer.step(last)
    if (!moved && !pendingPresent) return
    pendingPresent = false
    renderer.present()
    if (!confirming) confirmFirstFrame()
    if (moved && !last) schedule()
  }

  const attach = (): (() => void) => {
    const resizeObserver = new ResizeObserver(() => {
      pendingSize = measure()
      invalidate()
    })
    // One element is observed, so the last entry is the island's current standing.
    const intersectionObserver = new IntersectionObserver(entries => {
      onscreen = entries.at(-1)?.isIntersecting ?? onscreen
      sync()
    })
    const onVisibilityChange = () => {
      visible = !document.hidden
      sync()
    }

    resizeObserver.observe(canvas())
    intersectionObserver.observe(root)
    document.addEventListener("visibilitychange", onVisibilityChange)
    const releaseInteraction = kind.interact?.({
      root,
      canvas,
      renderer: () => renderer,
      nudge: () => {
        easingFrames = 0
        invalidate()
      },
      onReady: work => void (compose = work),
    })

    return () => {
      resizeObserver.disconnect()
      intersectionObserver.disconnect()
      document.removeEventListener("visibilitychange", onVisibilityChange)
      releaseInteraction?.()
      compose = undefined
    }
  }

  const start = async (started: number) => {
    const loaded = await loadRenderer(canvas(), measure(), () => {
      if (started === generation) deviceLost()
    }).catch(() => undefined)
    if (started !== generation) {
      loaded?.dispose()
      return
    }
    if (!loaded) {
      // The chunk or the device is not coming. What the server rendered is the picture.
      retire()
      return
    }
    renderer = loaded
    compose?.()
    invalidate()
  }

  const onMotionChange = () => {
    motionAllowed = motionPermits()
    if (!motionAllowed) retreat()
    sync()
  }

  return {
    mount() {
      if (release) return
      if (!supportsWebGpu()) {
        root.dataset[kind.readyFlag] = "false"
        return
      }
      mounted = true
      retired = false
      recoveries = 0
      awake = true
      // The fresh observer, not the last lifetime, says where the island stands now.
      onscreen = false
      visible = !document.hidden
      motionAllowed = motionPermits()
      if (kind.motionSensitive) motion.addEventListener("change", onMotionChange)
      // Watching comes before loading: an island the visitor cannot see never asks
      // for the chunk it could not show them.
      release = attach()
      sync()
    },
    pause() {
      awake = false
      sync()
    },
    resume() {
      awake = true
      sync()
    },
    destroy() {
      mounted = false
      if (kind.motionSensitive) motion.removeEventListener("change", onMotionChange)
      release?.()
      release = undefined
      retreat()
    },
  }
}
