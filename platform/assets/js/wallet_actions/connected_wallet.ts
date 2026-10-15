export type EthereumProvider = {
  request(args: {method: string; params?: unknown[]}): Promise<unknown>
}

/**
 * One wallet Privy currently holds: the provider this page sends through, and
 * Privy's own way of letting go of it.
 */
export type ConnectedEthereumWallet = {provider: EthereumProvider; disconnect: () => void}

export type SelectedWallet = {address: string; provider: EthereumProvider}

// A visitor who chose Disconnect stays disconnected across reloads, whatever
// the wallet app still reports to Privy afterwards.
const disconnectedKey = "regent:wallet-disconnected:v1"
export const walletDisconnectedStorageKey = disconnectedKey
const pendingSelectionKey = "regent:wallet-selection-pending:v1"
// This module already lives for one document, just like the provider maps below.
let disconnectedInDocument = false
let workEpoch = 0
export function walletWorkEpoch(): number { return workEpoch }
export function invalidateWalletWork(): void { workEpoch += 1 }

type WalletSelection = {address: string; walletClientType: string; expiresAt: number}

// Login can replace the document before connected-wallet hooks hydrate. Carry
// only that tab's explicit choice across the transition, never a provider or proof.
// The bridge must still match it to one real connected wallet; this grants no
// server authority. Privy owns persistence after setActiveWallet accepts it.
export function rememberEthereumWalletSelection(wallet: {address: string; walletClientType?: string}): void {
  if (!/^0x[0-9a-f]{40}$/i.test(wallet.address) || !wallet.walletClientType) return
  try {
    window.sessionStorage.setItem(pendingSelectionKey, JSON.stringify({
      address: wallet.address.toLowerCase(), walletClientType: wallet.walletClientType,
      expiresAt: Date.now() + 120_000,
    }))
  } catch {
    // Refused browser storage never authorizes a substitute wallet.
  }
}

export function pendingEthereumWalletSelection(): WalletSelection | null {
  try {
    const raw = window.sessionStorage.getItem(pendingSelectionKey)
    if (!raw || raw.length > 1024) return null
    const value = JSON.parse(raw) as Partial<WalletSelection> | null
    return value && typeof value.address === "string" && /^0x[0-9a-f]{40}$/i.test(value.address) &&
      typeof value.walletClientType === "string" && typeof value.expiresAt === "number" &&
      value.expiresAt > Date.now() && value.expiresAt <= Date.now() + 120_000
      ? value as WalletSelection : null
  } catch {
    return null
  }
}

export function forgetEthereumWalletSelection(): void {
  try { window.sessionStorage.removeItem(pendingSelectionKey) } catch {}
}

let connectedWallets = new Map<string, ConnectedEthereumWallet>()
let activeWallet: SelectedWallet | null = null

export function replaceConnectedEthereumWallets(
  wallets: ReadonlyArray<readonly [string, ConnectedEthereumWallet]>,
): void {
  connectedWallets = new Map(wallets.map(([address, wallet]) => [address.toLowerCase(), wallet]))
}

export function connectedEthereumWallet(expectedSigner?: string): SelectedWallet | null {
  if (walletDisconnected()) return null
  if (expectedSigner) {
    return selectConnectedEthereumWallet([...connectedWallets.entries()], expectedSigner)
  }

  const first = connectedWallets.entries().next().value as
    | [string, ConnectedEthereumWallet]
    | undefined
  return first ? {address: first[0], provider: first[1].provider} : null
}

export function selectConnectedEthereumWallet(
  wallets: ReadonlyArray<readonly [string, ConnectedEthereumWallet]>,
  expectedSigner: string,
): SelectedWallet | null {
  const expected = expectedSigner.toLowerCase()
  const selected = wallets.find(([address]) => address.toLowerCase() === expected)
  return selected ? {address: selected[0], provider: selected[1].provider} : null
}

/**
 * The wallet Privy currently has selected, when that selection is an Ethereum
 * wallet that is still connected. Wallet actions read this and nothing else: an absent,
 * Solana or stale selection is no wallet, never a substitute one.
 */
export function replaceActiveEthereumWallet(wallet: SelectedWallet | null): void {
  activeWallet = wallet ? {address: wallet.address.toLowerCase(), provider: wallet.provider} : null
}

export function activeEthereumWallet(): SelectedWallet | null {
  if (walletDisconnected()) return null
  return activeWallet
}

/**
 * Whether Privy's selected wallet is an Ethereum wallet that is still among the
 * connected ones. A Solana selection and a selection the provider has dropped
 * are both ineligible rather than a reason to pick another wallet.
 */
export function eligibleActiveWallet<W extends {address: string; type?: string}>(
  active: W | null | undefined,
  wallets: ReadonlyArray<{address: string}>,
): W | null {
  if (!active || active.type !== "ethereum") return null
  const address = active.address.toLowerCase()
  return wallets.some(wallet => wallet.address.toLowerCase() === address) ? active : null
}

/**
 * Every wallet Privy holds stops being this page's wallet, and the wallet apps
 * themselves are asked to drop the site. The releases are sent before this page
 * forgets them, and the page is disconnected from that point whatever any of
 * them answers, so a wallet app that never answers cannot hold Disconnect open.
 */
export async function disconnectEveryEthereumWallet(walletEvents: EventTarget): Promise<void> {
  const released = [...connectedWallets.values()].flatMap(wallet => [
    Promise.resolve().then(() => wallet.disconnect()),
    Promise.resolve().then(() => revokeSitePermissions(wallet.provider)),
  ])

  replaceConnectedEthereumWallets([])
  replaceActiveEthereumWallet(null)
  forgetEthereumWalletSelection()
  rememberWalletDisconnected()
  walletEvents.dispatchEvent(new CustomEvent("ash:wallet-state"))

  await Promise.allSettled(released)
}

// EIP-2255: the site asks the wallet app itself to take back the accounts it
// exposed. An app that refuses the request, or has never heard of it, is
// revoked as far as this page can take it.
function revokeSitePermissions(provider: EthereumProvider): Promise<unknown> {
  return provider.request({method: "wallet_revokePermissions", params: [{eth_accounts: {}}]})
}

export function walletDisconnected(): boolean {
  if (disconnectedInDocument) return true
  try {
    return disconnectedStorage()?.getItem(disconnectedKey) === "true"
  } catch {
    return false
  }
}

export function rememberWalletDisconnected(): void {
  disconnectedInDocument = true
  invalidateWalletWork()
  try {
    disconnectedStorage()?.setItem(disconnectedKey, "true")
  } catch {
    // A browser that refuses storage still disconnected everything above.
  }
}

export function forgetWalletDisconnected(): void {
  disconnectedInDocument = false
  try {
    disconnectedStorage()?.removeItem(disconnectedKey)
  } catch {
    // Nothing was remembered, so there is nothing to forget.
  }
}

function disconnectedStorage(): Pick<Storage, "getItem" | "setItem" | "removeItem"> | null {
  try {
    return window.localStorage ?? null
  } catch {
    return null
  }
}
