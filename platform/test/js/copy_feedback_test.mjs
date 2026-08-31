import assert from "node:assert/strict"
import test from "node:test"

import {
  mountCommandCopyButton,
  mountPageCopyButton,
} from "../../assets/js/copy_feedback.mjs"

class TestClassList {
  constructor() {
    this.values = new Set()
  }

  add(value) {
    this.values.add(value)
  }

  remove(value) {
    this.values.delete(value)
  }

  contains(value) {
    return this.values.has(value)
  }
}

class TestStatus {
  constructor() {
    this.values = []
    this.value = ""
  }

  matches(selector) {
    return selector === "[data-copy-status]"
  }

  get textContent() {
    return this.value
  }

  set textContent(value) {
    this.value = value
    this.values.push(value)
  }
}

class TestButton {
  constructor(idleLabel) {
    this.label = {textContent: idleLabel}
    this.nextElementSibling = new TestStatus()
    this.classList = new TestClassList()
    this.listeners = []
  }

  addEventListener(type, listener) {
    if (type === "click") this.listeners.push(listener)
  }

  querySelector(selector) {
    return selector === "[data-copy-label]" ? this.label : null
  }

  click() {
    return Promise.all(this.listeners.map(listener => listener({target: this})))
  }
}

function installWindow() {
  let nextId = 0
  const frames = new Map()
  const timers = new Map()
  const timerHistory = new Map()

  globalThis.window = {
    requestAnimationFrame(callback) {
      const id = ++nextId
      frames.set(id, callback)
      return id
    },
    cancelAnimationFrame(id) {
      frames.delete(id)
    },
    setTimeout(callback, delay) {
      const id = ++nextId
      const timer = {callback, delay}
      timers.set(id, timer)
      timerHistory.set(id, timer)
      return id
    },
    clearTimeout(id) {
      timers.delete(id)
    },
  }

  return {
    pendingFrameIds: () => [...frames.keys()],
    pendingTimerIds: () => [...timers.keys()],
    timerDelay: id => timerHistory.get(id)?.delay,
    runFrame(id) {
      const callback = frames.get(id)
      if (!callback) return false
      frames.delete(id)
      callback()
      return true
    },
    runTimer(id) {
      const timer = timers.get(id)
      if (!timer) return false
      timers.delete(id)
      timer.callback()
      return true
    },
  }
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return {promise, resolve, reject}
}

test("command copy blocks overlap and reannounces repeated success", async () => {
  const clock = installWindow()
  const button = new TestButton("Copy")
  const firstWrite = deferred()
  const writes = []

  mountCommandCopyButton({el: button}, () => "techtree climb", value => {
    writes.push(value)
    return writes.length === 1 ? firstWrite.promise : Promise.resolve()
  })

  const firstClick = button.click()
  await button.click()
  assert.deepEqual(writes, ["techtree climb"])

  firstWrite.resolve()
  await firstClick
  const [firstFrameId] = clock.pendingFrameIds()
  const [firstTimerId] = clock.pendingTimerIds()

  assert.equal(button.nextElementSibling.textContent, "")
  assert.equal(clock.timerDelay(firstTimerId), 1800)

  await button.click()
  const [secondFrameId] = clock.pendingFrameIds()
  const [secondTimerId] = clock.pendingTimerIds()

  assert.notEqual(secondFrameId, firstFrameId)
  assert.notEqual(secondTimerId, firstTimerId)
  assert.equal(clock.runFrame(firstFrameId), false)
  assert.equal(clock.runTimer(firstTimerId), false)
  assert.equal(button.nextElementSibling.textContent, "")
  assert.equal(button.label.textContent, "Copied")
  assert.equal(clock.runFrame(secondFrameId), true)
  assert.equal(button.nextElementSibling.textContent, "Command copied.")

  await button.click()
  const [thirdFrameId] = clock.pendingFrameIds()
  const [thirdTimerId] = clock.pendingTimerIds()

  assert.notEqual(thirdFrameId, secondFrameId)
  assert.notEqual(thirdTimerId, secondTimerId)
  assert.equal(clock.runTimer(secondTimerId), false)
  assert.equal(button.nextElementSibling.textContent, "")
  assert.equal(clock.runFrame(thirdFrameId), true)

  assert.deepEqual(writes, ["techtree climb", "techtree climb", "techtree climb"])
  assert.equal(button.label.textContent, "Copied")
  assert.equal(button.classList.contains("is-copied"), true)
  assert.deepEqual(button.nextElementSibling.values, [
    "",
    "",
    "Command copied.",
    "",
    "Command copied.",
  ])
  assert.deepEqual(clock.pendingTimerIds(), [thirdTimerId])
  assert.equal(clock.timerDelay(thirdTimerId), 1800)
  assert.equal(clock.runTimer(thirdTimerId), true)
  assert.equal(button.label.textContent, "Copy")
  assert.equal(button.nextElementSibling.textContent, "")
})

test("page copy blocks overlap and reannounces repeated Markdown failure", async () => {
  const clock = installWindow()
  const button = new TestButton("Copy page")
  const firstWrite = deferred()
  const writes = []
  const failureMessage =
    "Copy failed. Use View as Markdown to open the Markdown, then copy it manually."

  mountPageCopyButton({el: button}, () => "# Techtree\n", value => {
    writes.push(value)
    return writes.length === 1 ? firstWrite.promise : Promise.reject(new Error("denied"))
  })

  const firstClick = button.click()
  await button.click()
  assert.deepEqual(writes, ["# Techtree\n"])

  firstWrite.reject(new Error("denied"))
  await firstClick
  const [firstFrameId] = clock.pendingFrameIds()
  const [firstTimerId] = clock.pendingTimerIds()

  assert.equal(button.nextElementSibling.textContent, "")
  assert.equal(clock.timerDelay(firstTimerId), 4000)

  await button.click()
  const [secondFrameId] = clock.pendingFrameIds()
  const [secondTimerId] = clock.pendingTimerIds()

  assert.notEqual(secondFrameId, firstFrameId)
  assert.notEqual(secondTimerId, firstTimerId)
  assert.equal(clock.runFrame(firstFrameId), false)
  assert.equal(clock.runTimer(firstTimerId), false)
  assert.equal(button.nextElementSibling.textContent, "")
  assert.equal(button.label.textContent, "Copy failed")
  assert.equal(clock.runFrame(secondFrameId), true)
  assert.equal(button.nextElementSibling.textContent, failureMessage)

  await button.click()
  const [thirdFrameId] = clock.pendingFrameIds()
  const [thirdTimerId] = clock.pendingTimerIds()

  assert.notEqual(thirdFrameId, secondFrameId)
  assert.notEqual(thirdTimerId, secondTimerId)
  assert.equal(clock.runTimer(secondTimerId), false)
  assert.equal(button.nextElementSibling.textContent, "")
  assert.equal(clock.runFrame(thirdFrameId), true)

  assert.deepEqual(writes, ["# Techtree\n", "# Techtree\n", "# Techtree\n"])
  assert.equal(button.label.textContent, "Copy failed")
  assert.deepEqual(button.nextElementSibling.values, ["", "", failureMessage, "", failureMessage])
  assert.deepEqual(clock.pendingTimerIds(), [thirdTimerId])
  assert.equal(clock.timerDelay(thirdTimerId), 4000)
  assert.equal(clock.runTimer(thirdTimerId), true)
  assert.equal(button.label.textContent, "Copy page")
  assert.equal(button.nextElementSibling.textContent, "")
})
