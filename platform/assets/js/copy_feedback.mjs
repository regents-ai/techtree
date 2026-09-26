function copyStatusFor(button) {
  const status = button.nextElementSibling
  return status?.matches("[data-copy-status]") ? status : null
}

function resetCopyFeedback(hook, label, idleLabel, status) {
  window.clearTimeout(hook.copyFeedbackTimer)
  window.cancelAnimationFrame(hook.copyAnnouncementFrame)
  label.textContent = idleLabel
  hook.el.classList.remove("is-copied")
  if (status) status.textContent = ""
}

function announceCopyStatus(hook, status, message) {
  if (!status) return
  hook.copyAnnouncementFrame = window.requestAnimationFrame(() => {
    status.textContent = message
  })
}

function scheduleCopyFeedbackReset(hook, label, idleLabel, status, delay) {
  hook.copyFeedbackTimer = window.setTimeout(() => {
    label.textContent = idleLabel
    hook.el.classList.remove("is-copied")
    if (status) status.textContent = ""
  }, delay)
}

function mountCopyButton(
  hook,
  {
    copyValue,
    idleLabel,
    successMessage,
    failureMessage,
    refuse,
    writeText = value => navigator.clipboard.writeText(value),
  },
) {
  hook.el.addEventListener("click", async () => {
    if (hook.copyInFlight) return
    hook.copyInFlight = true

    const label = hook.el.querySelector("[data-copy-label]")
    const status = copyStatusFor(hook.el)
    resetCopyFeedback(hook, label, idleLabel, status)

    try {
      await writeText(copyValue())
      label.textContent = "Copied"
      hook.el.classList.add("is-copied")
      announceCopyStatus(hook, status, successMessage)
      scheduleCopyFeedbackReset(hook, label, idleLabel, status, 1800)
    } catch (_error) {
      label.textContent = "Copy failed"
      refuse(hook.el)
      announceCopyStatus(hook, status, failureMessage)
      scheduleCopyFeedbackReset(hook, label, idleLabel, status, 4000)
    } finally {
      hook.copyInFlight = false
    }
  })
}

// `refuse` answers a copy that could not happen, beside the words that say so.
export function mountCommandCopyButton(hook, copyValue, {refuse, writeText}) {
  mountCopyButton(hook, {
    copyValue,
    idleLabel: "Copy",
    successMessage: "Copied.",
    failureMessage: "Copy failed. Select the text and copy it manually.",
    refuse,
    writeText,
  })
}

export function mountPageCopyButton(hook, copyValue, {refuse, writeText}) {
  mountCopyButton(hook, {
    copyValue,
    idleLabel: "Copy page",
    successMessage: "Page copied as Markdown.",
    failureMessage:
      "Copy failed. Use View as Markdown to open the Markdown, then copy it manually.",
    refuse,
    writeText,
  })
}
