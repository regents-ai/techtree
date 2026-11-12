// Invariant: after Disconnect, only a sign-in the visitor makes now signs them in.
// A Privy session the browser still remembers completes at once with
// wasAlreadyAuthenticated, even when a link carries privy_oauth_code; it must not
// sign the previous person back in or clear the Disconnect note (Sentinel,
// 12 Oct 2026). A real redirect return arrives signed out and still signs in.
import {beforeEach, expect, it, vi} from "vitest"
import type {PrivyEvents} from "@privy-io/react-auth"

vi.mock("@privy-io/react-auth", () => ({}))
vi.mock("react-dom/client", () => ({}))

const {accountActiveWallet, accountLinkedWallets, accountWalletSelection, createConnectWalletRequest, createPrivyLoginCallbacks, signOutOfProvider} =
  await import("../js/privy_bridge")

const disconnected = "regent:wallet-disconnected:v1"
const stored = new Map<string, string>()

beforeEach(() => {
  stored.clear()
  stored.set(disconnected, "true")
  const storage = {
    getItem: (key: string) => stored.get(key) ?? null,
    setItem: (key: string, value: string) => void stored.set(key, value),
    removeItem: (key: string) => void stored.delete(key),
  }
  vi.stubGlobal("window", {localStorage: storage, sessionStorage: storage})
  vi.stubGlobal("localStorage", storage)
  vi.stubGlobal("sessionStorage", storage)
})

function complete(wasAlreadyAuthenticated: boolean) {
  const completeLogin = vi.fn(async () => undefined)
  // A link carrying privy_oauth_code starts the page as if it opened sign-in.
  const callbacks = createPrivyLoginCallbacks({
    completeLogin,
    loginOpen: {current: true},
    showFailure: vi.fn(),
    reportFailure: vi.fn(),
  })
  const done = callbacks.onComplete as NonNullable<PrivyEvents["login"]["onComplete"]>
  done({
    user: {id: "did:privy:person"},
    isNewUser: false,
    wasAlreadyAuthenticated,
    loginMethod: "google",
    loginAccount: null,
  } as unknown as Parameters<typeof done>[0])
  return completeLogin
}

it("a remembered session never signs back in after Disconnect", () => {
  expect(complete(true)).not.toHaveBeenCalled()
  expect(stored.get(disconnected)).toBe("true")
})

it("a real redirect return after Disconnect signs in", () => {
  expect(complete(false)).toHaveBeenCalledOnce()
  expect(stored.has(disconnected)).toBe(false)
})

// Invariant (Sean, 21 Oct 2026): a sign-in shows only its own account's wallets,
// and signing out lets go of every wallet, so nothing carries to the next person.
it("signed in, a wallet app left from before is never the account's wallet", () => {
  const zerion = {address: "0x0cB2000000000000000000000000000000003C37"}
  const regents = {address: "0x2c95000000000000000000000000000000008cf6"}
  const held = [zerion, regents]

  expect(accountActiveWallet(zerion, held, true, [regents.address])).toBeNull()
  expect(accountActiveWallet(regents, held, true, [regents.address])).toBe(regents)
  expect(accountActiveWallet(zerion, held, true, [zerion.address.toLowerCase()])).toBe(zerion)
  expect(accountActiveWallet(zerion, held, false, [])).toBe(zerion)
  expect(accountActiveWallet(zerion, [regents], false, [])).toBeNull()
})

it("the account's linked wallets are unknown until Privy has loaded the user, and empty when it links none", () => {
  const wallet = {type: "wallet", chainType: "ethereum", address: "0x2C95000000000000000000000000000000008cf6"}

  expect(accountLinkedWallets(null)).toBeNull()
  expect(accountLinkedWallets({linkedAccounts: [{type: "google_oauth"}]})).toEqual([])
  expect(accountLinkedWallets({linkedAccounts: [
    {type: "google_oauth"},
    {type: "wallet", chainType: "solana", address: "So1ana"},
    wallet,
  ]})).toEqual([wallet.address])
})

it("signed in, a wallet picked in the connect window counts only once the account's wallets are known and link it", () => {
  const zerion = {address: "0x0cb2000000000000000000000000000000003c37"}
  const regents = {address: "0x2c95000000000000000000000000000000008cf6"}

  expect(accountWalletSelection(zerion, true, null)).toEqual({use: null, forget: false})
  expect(accountWalletSelection(zerion, true, [])).toEqual({use: null, forget: true})
  expect(accountWalletSelection(zerion, true, [regents.address])).toEqual({use: null, forget: true})
  expect(accountWalletSelection(regents, true, [regents.address])).toEqual({use: regents, forget: false})
  expect(accountWalletSelection(zerion, false, null)).toEqual({use: zerion, forget: false})
  expect(accountWalletSelection(null, true, [regents.address])).toEqual({use: null, forget: false})
})

it("signing out lets go of every wallet before Privy signs out, even one that refuses", async () => {
  const order: string[] = []
  const zerion = {disconnect: vi.fn(() => { order.push("zerion"); throw new Error("refused") })}
  const regents = {disconnect: vi.fn(() => { order.push("regents") })}

  await signOutOfProvider([zerion, regents], async () => { order.push("logout") })

  expect(order).toEqual(["zerion", "regents", "logout"])
})

it("a wallet that never answers its disconnect does not hold the sign-out open", async () => {
  const silent = {disconnect: vi.fn(() => new Promise<void>(() => {}))}
  const logout = vi.fn(async () => undefined)

  await signOutOfProvider([silent], logout)

  expect(silent.disconnect).toHaveBeenCalledOnce()
  expect(logout).toHaveBeenCalledOnce()
}, 1000)

// Invariant (regents.sh security note, 23 Oct 2026): when Privy's logout failed
// at sign-out, a wallet connected on the signed-out page must not sign the
// previous person back in. Their remembered session is logged out first, and if
// that fails too the connect window never opens.
function connectRequest(signedOut: boolean, logout: () => Promise<void>) {
  const order: string[] = []
  const request = createConnectWalletRequest({
    isCurrent: () => true,
    signedOut: () => signedOut,
    authenticated: () => true,
    providerLogout: async () => { order.push("logout"); await logout() },
    openConnect: async () => { order.push("connect") },
  })
  return {order, request}
}

it("signed out, a remembered Privy session is logged out before a wallet connects", async () => {
  const {order, request} = connectRequest(true, async () => undefined)
  await request()
  expect(order).toEqual(["logout", "connect"])
})

it("signed out, a logout that fails never opens the connect window", async () => {
  const {order, request} = connectRequest(true, async () => { throw new Error("logout failed") })
  await expect(request()).rejects.toThrow("logout failed")
  expect(order).toEqual(["logout"])
})

it("signed in, connecting a wallet keeps the visitor's own Privy session", async () => {
  const {order, request} = connectRequest(false, async () => undefined)
  await request()
  expect(order).toEqual(["connect"])
})
