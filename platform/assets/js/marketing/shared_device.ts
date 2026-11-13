/**
 * One GPU device for every moving picture on a page. A page holds several
 * small pictures, so the first asks for the device, the rest draw on the same
 * one, and the last to go gives it back. When the browser takes the device
 * away every picture on it is told, and the next one to ask gets a new one.
 */

/** What sharing needs of a device: to hear that it is lost, and to give it back. */
export type Shareable = {readonly lost: Promise<unknown>; dispose(): void}

export type Shared<Gpu extends Shareable> = {
  readonly gpu: Gpu
  /** What each panel drawing on this device wants to hear when it is lost. */
  readonly panels: Set<() => void>
  /** True once the browser took it away or the last panel gave it back. */
  gone: boolean
}

export const shareDevice = <Gpu extends Shareable>(open: () => Promise<Gpu>) => {
  let current: Promise<Shared<Gpu>> | undefined

  /** The page's one device, with this panel counted on it. */
  const join = async (onLost: () => void, again = true): Promise<Shared<Gpu>> => {
    const asked: Promise<Shared<Gpu>> = (current ??= open().then(gpu => {
      const shared: Shared<Gpu> = {gpu, panels: new Set(), gone: false}
      void gpu.lost.then(() => {
        // Giving the device back resolves the same promise: nothing is left to do then.
        if (shared.gone) return
        shared.gone = true
        if (current === asked) current = undefined
        // Taken before any panel drew on it: no panel will leave it, so it is given back here.
        if (shared.panels.size === 0) gpu.dispose()
        for (const tell of [...shared.panels]) tell()
      })
      return shared
    }))
    let shared: Shared<Gpu>
    try {
      shared = await asked
    } catch (error) {
      if (current === asked) current = undefined
      throw error
    }
    // A device that went while this panel waited for it is no use: ask for the next one, once.
    if (shared.gone) {
      if (!again) throw new Error("The device was lost as it opened, twice over.")
      return join(onLost, false)
    }
    shared.panels.add(onLost)
    return shared
  }

  /** This panel is done with the device; the last one to leave gives it back. */
  const leave = (shared: Shared<Gpu>, onLost: () => void) => {
    shared.panels.delete(onLost)
    if (shared.panels.size > 0) return
    // Nothing draws on it now. Unless the browser already took it, the page stops handing it out.
    if (!shared.gone) {
      shared.gone = true
      current = undefined
    }
    shared.gpu.dispose()
  }

  return {join, leave}
}
