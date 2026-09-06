import {mountProfile} from "../vendor/regent_ui/profile.mjs"
import {loadProfileAction} from "../vendor/regent_identity/profile_client.mjs"
import {installProfileTools} from "../vendor/regent_identity/profile_tools.mjs"

export function installSharedProfile() {
  const root = document.querySelector("[data-regent-profile]")
  if (!root) return // Privy is permitted only on the private profile document.
  let loading
  const bridge = () => {
    if (loading) return loading
    const id = document.querySelector("meta[name=privy-app-id]")?.content
    const source = document.querySelector("meta[name=privy-bridge-src]")?.content
    if (!id || !/^\/assets\/js\/privy_bridge(?:-[a-f0-9]+)?\.js$/.test(source || "")) return Promise.reject(new Error("profile_unconfigured"))
    loading = import(source).then(module => module.startPrivyBridge(id))
    loading.catch(() => { loading = null })
    return loading
  }
  const profile = (...args) => loadProfileAction(async () => (await bridge()).profile, ...args)
  installProfileTools(profile)
  mountProfile(root, {
    profile,
    signIn: async () => (await bridge()).signIn(),
    async linkX() {
      const account = await bridge()
      await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => finish(false), 120_000)
        const changed = event => finish(event.detail?.ok === true)
        const finish = ok => {
          clearTimeout(timeout)
          window.removeEventListener("regent:profile-link", changed)
          if (ok) resolve()
          else reject(new Error("profile_link_failed"))
        }
        window.addEventListener("regent:profile-link", changed)
        void account.linkX().catch(() => finish(false))
      })
    },
    onIdentityChange(callback) {
      window.addEventListener("regent:profile-identity", callback)
      window.addEventListener("regent:profile-link", callback)
      return () => {
        window.removeEventListener("regent:profile-identity", callback)
        window.removeEventListener("regent:profile-link", callback)
      }
    },
  })
  document.querySelector("[data-profile-sign-out]")?.addEventListener("click", async () => {
    try { await (await bridge()).signOut() }
    catch { root.querySelector("[data-profile-status]").textContent = "Sign out could not be completed." }
  })
}
