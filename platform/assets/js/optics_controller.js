// A small lifecycle shell shared by both optical demos. The page owns the
// server-rendered copy; the canvas island is loaded only when it can be seen,
// draws on demand, and then sleeps until resize or pointer input changes it.

const MAX_DEVICE_PIXEL_RATIO = 1.5
const MAX_DRAWING_BUFFER_PIXELS = 1_500_000
const EASING_FRAME_LIMIT = 24
const scriptLoads = new Map()
const clampUnit = value => Math.min(1, Math.max(0, value))

function drawingBufferSize(width, height) {
  const ratio = Math.min(MAX_DEVICE_PIXEL_RATIO, Math.max(1, window.devicePixelRatio || 1))
  const requested = width * height * ratio * ratio
  const fit = requested > MAX_DRAWING_BUFFER_PIXELS
    ? Math.sqrt(MAX_DRAWING_BUFFER_PIXELS / requested)
    : 1

  return [
    Math.max(1, Math.floor(width * ratio * fit)),
    Math.max(1, Math.floor(height * ratio * fit)),
  ]
}

function loadRenderer(kind, source, module) {
  const loaded = window.TechtreeOptics && window.TechtreeOptics[kind]
  if (loaded) return Promise.resolve(loaded)

  const key = `${kind}:${source}:${module ? "module" : "script"}`
  if (scriptLoads.has(key)) return scriptLoads.get(key)

  const pending = new Promise((resolve, reject) => {
    const script = document.createElement("script")
    script.async = true
    script.src = source
    if (module) script.type = "module"
    script.dataset.opticsLoader = kind
    script.addEventListener("load", () => {
      const renderer = window.TechtreeOptics && window.TechtreeOptics[kind]
      if (renderer) resolve(renderer)
      else reject(new Error(`Optics loader ${kind} did not register a renderer.`))
    }, {once: true})
    script.addEventListener("error", () => {
      reject(new Error(`Optics loader ${kind} could not be loaded.`))
    }, {once: true})
    document.head.appendChild(script)
  })

  scriptLoads.set(key, pending)
  return pending
}

function opticsVariant(root, canvas) {
  if (root.dataset.opticsKind === "crown") {
    return `${canvas.dataset.crownVariant || ""}:${canvas.dataset.backgroundPreset || "10"}`
  }
  if (root.dataset.opticsKind === "background") {
    return `${canvas.dataset.backgroundTheme || "orange"}:${canvas.dataset.backgroundPreset || "10"}`
  }
}

export function createOpticsController(root) {
  const canvas = root.querySelector("[data-optics-canvas]")
  const viewportPointer = root.dataset.opticsPointer === "viewport"
  const pointerHost = viewportPointer
    ? window
    : root.dataset.opticsPointer === "parent" ? root.parentElement : root
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)")
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)")

  let mounted = false
  let awake = true
  let onscreen = false
  let visible = !document.hidden
  let retired = false
  let generation = 0
  let renderer
  let rendererVariant
  let starting = false
  let frameHandle
  let pendingSize
  let pendingPresent = false
  let easingFrames = 0
  let confirming = false
  let release
  let mobileAimX = 0.5

  const active = () => mounted && awake && onscreen && visible && !retired

  const measure = () => {
    const bounds = canvas.getBoundingClientRect()
    return drawingBufferSize(bounds.width, bounds.height)
  }

  const stopFrame = () => {
    if (frameHandle !== undefined) window.cancelAnimationFrame(frameHandle)
    frameHandle = undefined
  }

  const schedule = () => {
    if (frameHandle !== undefined || !renderer || !active()) return
    frameHandle = window.requestAnimationFrame(tick)
  }

  const invalidate = () => {
    pendingPresent = true
    schedule()
  }

  const retreat = () => {
    generation += 1
    stopFrame()
    renderer?.dispose()
    renderer = undefined
    rendererVariant = undefined
    starting = false
    confirming = false
    pendingPresent = false
    easingFrames = 0
    delete root.dataset.opticsReady
  }

  const retire = () => {
    retired = true
    root.dataset.opticsFailed = "true"
    retreat()
  }

  const confirmFirstFrame = () => {
    confirming = true
    const drawn = generation
    void renderer.settled().then(
      () => {
        if (drawn === generation) root.dataset.opticsReady = "true"
      },
      () => {
        if (drawn === generation) retire()
      },
    )
  }

  function tick() {
    frameHandle = undefined
    if (!renderer || !active()) return

    if (pendingSize) {
      renderer.resize(pendingSize[0], pendingSize[1])
      pendingSize = undefined
      pendingPresent = true
    }

    easingFrames += 1
    const last = easingFrames >= EASING_FRAME_LIMIT
    const moved = renderer.step(last)
    if (!moved && !pendingPresent) return

    pendingPresent = false
    renderer.present()
    if (!confirming) confirmFirstFrame()
    if (moved && !last) schedule()
  }

  const mobileCrownActive = () =>
    root.dataset.opticsKind === "crown" && !finePointer.matches && !motion.matches

  const aimCrownFromScroll = () => {
    if (!renderer || !mobileCrownActive()) return

    const bounds = canvas.getBoundingClientRect()
    const travel = window.innerHeight + bounds.height
    if (travel <= 0) return

    renderer.aim(mobileAimX, clampUnit((window.innerHeight - bounds.top) / travel))
    easingFrames = 0
    invalidate()
  }

  const start = async () => {
    if (starting || renderer || !active()) return
    starting = true
    const started = generation

    try {
      // Two paint opportunities keep GPU setup out of the server hero's first
      // frame without introducing an idle loop after the scene settles.
      await new Promise(resolve => window.requestAnimationFrame(() =>
        window.requestAnimationFrame(resolve),
      ))
      if (started !== generation || !active()) {
        if (started === generation) starting = false
        return
      }

      const createRenderer = await loadRenderer(
        root.dataset.opticsKind,
        root.dataset.opticsSource,
        root.hasAttribute("data-optics-module"),
      )
      if (started !== generation || !active()) {
        if (started === generation) starting = false
        return
      }

      const loaded = await createRenderer(canvas, measure(), () => {
        if (started === generation) retire()
      })
      if (started !== generation) {
        loaded.dispose()
        return
      }

      renderer = loaded
      rendererVariant = opticsVariant(root, canvas)
      starting = false
      if (mobileCrownActive()) aimCrownFromScroll()
      else invalidate()
    } catch (_error) {
      if (started === generation) retire()
    }
  }

  const sync = () => {
    if (!active()) {
      stopFrame()
      return
    }
    if (renderer) invalidate()
    else void start()
  }

  const attach = () => {
    const resizeObserver = new ResizeObserver(() => {
      pendingSize = measure()
      invalidate()
    })
    const intersectionObserver = new IntersectionObserver(entries => {
      onscreen = entries.at(-1)?.isIntersecting ?? onscreen
      sync()
    })
    const onVisibility = () => {
      visible = !document.hidden
      sync()
    }
    const onPointerMove = event => {
      if (!renderer || event.isPrimary === false || motion.matches) return

      const touchDriven = event.pointerType === "touch" || !finePointer.matches
      if (touchDriven && root.dataset.opticsKind !== "crown") return

      const bounds = canvas.getBoundingClientRect()
      const width = viewportPointer ? document.documentElement.clientWidth : bounds.width
      const left = viewportPointer ? 0 : bounds.left
      if (width <= 0 || bounds.height <= 0) return

      const x = clampUnit((event.clientX - left) / width)
      const y = clampUnit((event.clientY - bounds.top) / bounds.height)
      if (touchDriven) mobileAimX = x

      renderer.aim(x, y)
      easingFrames = 0
      invalidate()
    }
    const onPointerLeave = () => {
      renderer?.rest()
      easingFrames = 0
      invalidate()
    }
    const onMotionChange = () => {
      renderer?.rest()
      easingFrames = 0
      invalidate()
    }
    const onThemeChange = event => {
      const kind = root.dataset.opticsKind
      const theme = event.detail?.theme
      const crownVariant = event.detail?.crownVariant
      const backgroundPreset = event.detail?.backgroundPreset || "10"
      if (kind === "crown" && crownVariant) {
        root.dataset.crownVariant = crownVariant
        canvas.dataset.crownVariant = crownVariant
      } else if (kind === "background" && theme) {
        root.dataset.backgroundTheme = theme
        canvas.dataset.backgroundTheme = theme
      } else {
        return
      }
      root.dataset.backgroundPreset = backgroundPreset
      canvas.dataset.backgroundPreset = backgroundPreset

      const variant = opticsVariant(root, canvas)
      if (rendererVariant === variant) return
      retired = false
      delete root.dataset.opticsFailed
      retreat()
      sync()
    }

    resizeObserver.observe(canvas)
    intersectionObserver.observe(root)
    document.addEventListener("visibilitychange", onVisibility)
    window.addEventListener("scroll", aimCrownFromScroll, {passive: true})
    pointerHost.addEventListener("pointerdown", onPointerMove, {passive: true, capture: viewportPointer})
    pointerHost.addEventListener("pointermove", onPointerMove, {passive: true, capture: viewportPointer})
    if (viewportPointer) window.addEventListener("blur", onPointerLeave)
    else pointerHost.addEventListener("pointerleave", onPointerLeave, {passive: true})
    motion.addEventListener("change", onMotionChange)
    document.addEventListener("techtree:themechange", onThemeChange)

    return () => {
      resizeObserver.disconnect()
      intersectionObserver.disconnect()
      document.removeEventListener("visibilitychange", onVisibility)
      window.removeEventListener("scroll", aimCrownFromScroll)
      pointerHost.removeEventListener("pointerdown", onPointerMove, {capture: viewportPointer})
      pointerHost.removeEventListener("pointermove", onPointerMove, {capture: viewportPointer})
      if (viewportPointer) window.removeEventListener("blur", onPointerLeave)
      else pointerHost.removeEventListener("pointerleave", onPointerLeave)
      motion.removeEventListener("change", onMotionChange)
      document.removeEventListener("techtree:themechange", onThemeChange)
    }
  }

  return {
    mount() {
      if (!canvas || !root.dataset.opticsKind || !root.dataset.opticsSource || !navigator.gpu) return
      mounted = true
      awake = true
      visible = !document.hidden
      release = attach()
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
      release?.()
      release = undefined
      retreat()
    },
  }
}

export const Optics = {
  mounted() {
    this.controller = createOpticsController(this.el)
    this.controller.mount()
  },
  disconnected() {
    this.controller?.pause()
  },
  reconnected() {
    this.controller?.resume()
  },
  destroyed() {
    this.controller?.destroy()
    this.controller = undefined
  },
}
