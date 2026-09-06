import React, {useEffect} from "react"
import {createRoot} from "react-dom/client"
import {PrivyProvider, getIdentityToken, usePrivy, useLogin, useLinkAccount} from "@privy-io/react-auth"
import {createProfileClient} from "../vendor/regent_identity/profile_client.mjs"
import {createXLinkIntent} from "../vendor/regent_identity/x_link_intent.mjs"

// Techtree's publication keys remain separate. This island only proves the
// person's private shared profile; it never signs or submits publications.
let current = null
let appId = null
let generation = 0
let linkNonce = null
const waiters = new Set()
const intent = () => {
  let storage = null
  try { storage = window.sessionStorage } catch {}
  return createXLinkIntent(storage, appId)
}
const notifyLink = ok => window.dispatchEvent(new CustomEvent("regent:profile-link", {detail: {ok}}))

function Bridge() {
  const privy = usePrivy()
  const {login} = useLogin({onError: () => notifyLink(false)})
  const {linkTwitter} = useLinkAccount({
    onSuccess: payload => {
      const expected = intent().claim(payload)
      if (expected) void profileFor(expected)("sync").then(result => notifyLink(result.ok))
    },
    onError: () => { intent().cancel(linkNonce); notifyLink(false) },
  })
  useEffect(() => {
    const changed = current?.user?.id !== privy.user?.id || current?.authenticated !== privy.authenticated
    current = {...privy, login, linkTwitter}
    if (changed) {
      generation += 1
      window.dispatchEvent(new Event("regent:profile-identity"))
    }
    for (const waiter of [...waiters]) waiter()
  })
  return null
}

function ready(expected) {
  return new Promise((resolve, reject) => {
    const check = () => {
      if (!current?.ready || (expected && current.user?.id !== expected)) return
      clearTimeout(timeout)
      waiters.delete(check)
      resolve(current)
    }
    const timeout = setTimeout(() => { waiters.delete(check); reject(new Error("profile_unavailable")) }, 10_000)
    waiters.add(check)
    check()
  })
}

const profileFor = expected => createProfileClient({
  async acquireProof({signal}) {
    const state = await ready(expected)
    signal.throwIfAborted()
    if (!state.authenticated || !state.user?.id) return null
    const observed = generation
    const subject = state.user.id
    const identityToken = await getIdentityToken()
    const accessToken = await state.getAccessToken()
    return {accessToken, identityToken, subject, isCurrent: () =>
      current?.authenticated && current.user?.id === subject && generation === observed}
  },
})

export function startPrivyBridge(id) {
  if (appId && appId !== id) throw new Error("privy_application_changed")
  if (!appId) {
    if (!id) throw new Error("profile_unconfigured")
    appId = id
    const host = document.createElement("div")
    host.hidden = true
    document.body.append(host)
    createRoot(host).render(<PrivyProvider appId={appId} config={{loginMethods: ["wallet"]}}><Bridge /></PrivyProvider>)
  }
  return {
    profile: profileFor(),
    async signIn() {
      const state = await ready()
      if (!state.authenticated) state.login()
    },
    async signOut() {
      const state = await ready()
      if (state.authenticated) await state.logout()
    },
    async linkX() {
      const state = await ready()
      if (!state.authenticated || !state.user?.id) throw new Error("authentication_required")
      const nonce = intent().begin(state.user.id)
      linkNonce = nonce
      try { await state.linkTwitter() }
      catch (error) { intent().cancel(nonce); throw error }
    },
  }
}
