import {
  PrivyProvider,
  type ConnectedWallet,
  type PrivyEvents,
  getIdentityToken,
  useActiveWallet,
  useConnectWallet,
  useLogin,
  useLinkAccount,
  usePrivy,
  useToken,
  useUnlinkFarcaster,
  useUnlinkOAuth,
  useWallets,
} from "@privy-io/react-auth"
import React from "react"
import {createRoot} from "react-dom/client"

import {
  AccountAuthFailure,
  acrossCookieRotation,
  announceCsrfRotation,
  browserSessionMutations,
  clearLocalSession,
  finishWalletSignOut,
  csrfToken,
  recoverOnce,
  reportSignInFailure,
  reloadDocumentOnce,
  returnedFromOAuth,
  sessionLifecycleError,
  showAccountAuthFailure,
  IDENTITY_STATE_EVENT,
  type AccountRequest,
  type IdentityProvider,
  type IdentityRequest,
  type IdentityState,
  type PrivyBridgeHandle,
  type PrivyBridgeStartupOptions,
  type SessionMutationCoordinator,
  type SignInFailureDiagnostic,
  type SignInFailureKind,
} from "./auth_lazy"
import {
  activeEthereumWallet,
  forgetEthereumWalletSelection,
  forgetWalletDisconnected,
  pendingEthereumWalletSelection,
  rememberEthereumWalletSelection,
  replaceActiveEthereumWallet,
  replaceConnectedEthereumWallets,
  walletDisconnected,
  walletWorkEpoch,
  type EthereumProvider,
} from "./wallet_actions/connected_wallet"

type AccountRequestHandlerOptions = {
  connectWallet: () => Promise<void>
  signIn: () => Promise<void>
  providerLogout: () => Promise<void>
  synchronizeWallets: () => Promise<void>
}

function createAccountRequestHandler({
  connectWallet,
  signIn,
  providerLogout,
  synchronizeWallets,
}: AccountRequestHandlerOptions): (request: AccountRequest) => Promise<void> {
  return async request => {
    // Asking for a wallet is not getting one: both of these only open Privy's
    // own window, and they answer as soon as it is open. What ends the
    // disconnected state is the visitor coming back with a wallet, which Privy
    // reports on its own callbacks, so nothing about the Disconnect changes
    // here.
    if (request === "connect-wallet") {
      await connectWallet()
      return
    }

    if (request === "sign-in") {
      await signIn()
      return
    }

    if (request === "sync") {
      await synchronizeWallets()
      return
    }

    await providerLogout()
  }
}

// A refusal the server itself answered, told apart from a failure on the way.
class ServerReportedSessionError extends Error {
  constructor() {
    super("Sign in could not be completed.")
  }
}

class StalePrivyOperation extends Error {
  constructor() { super("Privy operation was superseded."); this.name = "AbortError" }
}

function requireCurrent(current: () => boolean): void {
  if (!current()) throw new StalePrivyOperation()
}

function refusal(response: Response): Error {
  return response.status === 401
    ? new ServerReportedSessionError()
    : new Error("Sign in could not be completed.")
}

type SignInRequestOptions = {
  isCurrent?: () => boolean
  authenticated: () => boolean
  providerLogout: () => Promise<void>
  openLogin: () => void
  loginOpen: {current: boolean}
}

// Sign in is only offered on a signed-out page, and it always goes through
// Privy's window, so the wallet the visitor proves is the one their wallet app
// is on now. A Privy session this browser still remembers belongs to whoever
// signed in before; it is logged out first, never reused.
function createSignInRequest({
  authenticated,
  providerLogout,
  openLogin,
  loginOpen,
  isCurrent = () => true,
}: SignInRequestOptions): () => Promise<void> {
  return async () => {
    const epoch = walletWorkEpoch()
    const current = () => isCurrent() && walletWorkEpoch() === epoch
    requireCurrent(current)
    if (loginOpen.current) return

    if (authenticated()) {
      try {
        await providerLogout()
      } catch {
        throw new AccountAuthFailure("provider", "provider_error")
      }
      requireCurrent(current)
    }
    if (loginOpen.current) return
    loginOpen.current = true
    openLogin()
  }
}

type IdentityOutcome = Pick<IdentityState, "action" | "provider">

type IdentityRequestHandlerOptions = {
  linkX: () => void
  linkGithub: () => void
  linkFarcaster: () => void
  unlinkOAuth: (provider: "twitter" | "github", subject: string) => Promise<void>
  unlinkFarcaster: (fid: number) => Promise<void>
  refreshSession: (outcome: IdentityOutcome) => Promise<void>
}

// Privy names the account kind it linked; only the three the page offers are
// ours to report on.
function identityProviderFor(linkMethod: string): IdentityProvider | null {
  if (linkMethod === "twitter") return "x"
  if (linkMethod === "github" || linkMethod === "farcaster") return linkMethod
  return null
}

function createIdentityRequestHandler({
  linkX,
  linkGithub,
  linkFarcaster,
  unlinkOAuth,
  unlinkFarcaster,
  refreshSession,
}: IdentityRequestHandlerOptions): (request: IdentityRequest) => Promise<void> {
  return async request => {
    if (request.action === "link") {
      if (request.provider === "x") linkX()
      if (request.provider === "github") linkGithub()
      if (request.provider === "farcaster") linkFarcaster()
      return
    }

    if (!request.subject) throw new Error("The connected account is unavailable.")

    if (request.provider === "farcaster") {
      const fid = Number(request.subject)
      if (!Number.isSafeInteger(fid) || fid <= 0) {
        throw new Error("The connected account is unavailable.")
      }
      await unlinkFarcaster(fid)
    } else {
      await unlinkOAuth(request.provider === "x" ? "twitter" : "github", request.subject)
    }

    await refreshSession({action: "unlink", provider: request.provider})
  }
}

type SignOutOnlyBridgeOptions = {
  ordinaryRequest: (request: AccountRequest) => Promise<void>
  ordinaryIdentity: (request: IdentityRequest) => Promise<void>
  onTerminal?: () => void
}

function createSignOutOnlyBridgeState({
  ordinaryRequest,
  ordinaryIdentity,
  onTerminal = () => undefined,
}: SignOutOnlyBridgeOptions) {
  let state: "preterminal" | "terminal" = "preterminal"
  let providerSignOutAttempt: Promise<void> | null = null
  let explicitRequestTail = Promise.resolve()

  const finish = () => {
    if (state === "terminal") return
    state = "terminal"
    onTerminal()
  }

  const afterProviderSignOut = <T,>(request: () => Promise<T>): Promise<T> => {
    const providerSettled = providerSignOutAttempt?.then(
      () => undefined,
      () => undefined,
    ) ?? Promise.resolve()
    const attempt = explicitRequestTail.then(() => providerSettled).then(request)
    explicitRequestTail = attempt.then(
      () => undefined,
      () => undefined,
    )
    return attempt
  }

  return {
    request(request: AccountRequest): Promise<void> {
      if (state === "terminal") {
        if (request === "sign-out") return Promise.resolve()
        if (request === "sync") {
          return Promise.reject(new Error("Automatic reconciliation is disabled."))
        }
        return afterProviderSignOut(() => ordinaryRequest(request))
      }
      if (request !== "sign-out") {
        return Promise.reject(new Error("Provider sign out is still in progress."))
      }
      if (providerSignOutAttempt) return providerSignOutAttempt

      const attempt = ordinaryRequest("sign-out")
      providerSignOutAttempt = attempt
      void attempt.then(finish, finish)
      return attempt
    },
    identity(request: IdentityRequest): Promise<void> {
      return state === "terminal"
        ? afterProviderSignOut(() => ordinaryIdentity(request))
        : Promise.reject(new Error("Provider sign out is still in progress."))
    },
    finish,
  }
}

export {clearLocalSession, csrfToken}

// Privy's two tokens have two different jobs: the access token proves this
// browser's Privy session and the identity token carries the signed accounts
// that session is entitled to. Regent needs both, so they travel together.
type PrivyTokenPair = {accessToken: string; identityToken: string}

type PrivyTokenSources = {
  getIdentityToken: () => Promise<string | null>
  getAccessToken: () => Promise<string | null>
  capture?: () => () => boolean
}

// The evidence is asked for first and the session proof second, so the proof is
// never older than the evidence it is offered with. A half pair is never sent:
// if either read fails or comes back empty, nothing is requested at all and any
// local session this browser already holds is left exactly as it is.
function createPrivyTokenPairSource({
  getIdentityToken: identity,
  getAccessToken: access,
  capture = () => () => true,
}: PrivyTokenSources): () => Promise<PrivyTokenPair> {
  return async () => {
    const current = capture()
    requireCurrent(current)
    const identityToken = await identity()
    requireCurrent(current)
    const accessToken = await access()
    requireCurrent(current)

    if (!identityToken?.trim() || !accessToken?.trim()) {
      throw new Error("Sign in could not be completed.")
    }

    return {accessToken, identityToken}
  }
}

async function createLocalSession(
  tokens: PrivyTokenPair,
  fetcher: typeof fetch = fetch,
  sessionMutations: SessionMutationCoordinator = browserSessionMutations,
  current: () => boolean = () => true,
): Promise<{
  sessionChanged: boolean
  identityError?: "already-connected"
}> {
  // The barrier spans the whole establishment, including the recovery attempt
  // that follows a dropped lineage. Only the outcomes that actually write a
  // session leave this tab holding a token it has not confirmed, so an attempt
  // refused before one of those lands renews nothing and leaves reconnects
  // available.
  return sessionMutations.establish((signal, commit) =>
    acrossCookieRotation(renewed =>
      recoverOnce(() => {
        requireCurrent(current)
        return establishLocalSession(tokens, fetcher, signal, commit, renewed, current)
      }),
    ),
  )
}

async function establishLocalSession(
  {accessToken, identityToken}: PrivyTokenPair,
  fetcher: typeof fetch,
  signal: AbortSignal,
  commit: () => void,
  renewed: () => void,
  current: () => boolean,
): Promise<{sessionChanged: boolean; identityError?: "already-connected"}> {
  const csrf = await csrfToken(fetcher, signal, renewed)
  if (signal.aborted) throw signal.reason
  requireCurrent(current)
  // From here the response may renew the cookie, so it is never abandoned: an
  // abandoned renewal would leave this tab holding a retired token.
  commit()
  // Each token travels in its own header and never in the URL or the body.
  const response = await fetcher("/auth/privy/session", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      authorization: `Bearer ${accessToken}`,
      "privy-id-token": identityToken,
      "x-csrf-token": csrf,
    },
  })
  const lifecycle = await sessionLifecycleError(response).catch(unreadable => {
    // An account switch and a revoked lineage both drop the cookie at header
    // time and both answer 409, so a conflict this tab cannot read counts as
    // the drop it has not adopted.
    renewed()
    throw unreadable
  })
  // The exact sign-in outcomes that leave a different cookie in this browser: a
  // bind or refresh rotates it, and a refused bearer, an account switch or a
  // revoked lineage drop it. Only a superseded claim writes no session, and only
  // its own parsed body proves that.
  const wroteSession =
    response.status === 409
      ? lifecycle?.lifecycle !== "session_superseded"
      : response.ok || response.status === 401
  if (wroteSession) renewed()
  if (!current() && !response.ok) {
    // Adopt cookie-changing responses, but never recover an obsolete operation
    // into another POST after its owner or provider identity has changed.
    if (wroteSession) {
      await csrfToken(fetcher)
      announceCsrfRotation()
    }
    throw new StalePrivyOperation()
  }
  if (lifecycle) throw lifecycle
  if (!response.ok) throw refusal(response)
  const sessionChanged = response.headers.get("x-ash-session-changed")
  if (sessionChanged !== "true" && sessionChanged !== "false") {
    throw new Error("Sign in could not be completed.")
  }
  const identityError = response.headers.get("x-ash-identity-error")
  if (identityError && identityError !== "already-connected") {
    throw new Error("Sign in could not be completed.")
  }
  const verifiedIdentityError = identityError === "already-connected" ? identityError : undefined
  // The renewed session rotated its CSRF state: this tab adopts the new token
  // and tells the other tabs sharing the cookie to adopt it too.
  await csrfToken(fetcher)
  announceCsrfRotation()
  return {
    sessionChanged: sessionChanged === "true",
    ...(verifiedIdentityError ? {identityError: verifiedIdentityError} : {}),
  }
}

// Privy allocates a new ConnectedWallet object for the same wallet whenever its
// chain, link state or connection is refreshed, and finds its selection by
// address inside that fresh array, so object identity says nothing about whether
// the customer changed wallets. Address and wallet app do: two apps holding one
// address are still two wallets, and Privy names an injected app it does not
// recognise "unknown", so a new object from such an app, or one with no app
// identity at all, cannot be told from another app's and is treated as a change.
// Whether the same provider stands behind a recognised object is only known once
// it resolves, and is decided at publication.
function sameConnectedWallet(
  previous: ConnectedWallet | null,
  next: ConnectedWallet | null,
): boolean {
  if (!previous || !next) return previous === next
  if (previous === next) return true
  const app = previous.walletClientType
  if (!app || app === "unknown" || !previous.connectorType) return false
  return (
    previous.address.toLowerCase() === next.address.toLowerCase() &&
    app === next.walletClientType &&
    previous.connectorType === next.connectorType
  )
}

// The one account the same wallet app now reports in place of the account the
// customer had selected there. Anything else is not a switch: the selected
// account still listed, that app gone entirely, several of its accounts to
// choose between, or an account from a different app.
function switchedAccountOf(
  previous: ConnectedWallet | null,
  wallets: readonly ConnectedWallet[],
): ConnectedWallet | null {
  // Privy names an injected provider it does not recognise "unknown", so two
  // such apps are indistinguishable and neither may stand in for the other.
  if (!previous || previous.walletClientType === "unknown") return null
  const sameApp = wallets.filter(
    wallet =>
      wallet.type === "ethereum" &&
      wallet.walletClientType === previous.walletClientType &&
      wallet.connectorType === previous.connectorType,
  )
  const [candidate] = sameApp
  return sameApp.length === 1 && candidate.address.toLowerCase() !== previous.address.toLowerCase()
    ? candidate
    : null
}

type ProviderSessionReconcilerOptions = {
  clearSession: () => Promise<void>
  disconnectWallets?: () => Promise<void>
  providerAuthenticated: () => boolean
  reload: () => void
  signedIn: () => boolean
}

// Startup reconciliation only reads the provider. Remaining signed in is not a
// session event: this can end a local session the provider no longer supports,
// but it can never establish or refresh one, so an ordinary signed-in load
// advances no generation, renews no cookie and rotates no CSRF state.
function createProviderSessionReconciler({
  clearSession,
  disconnectWallets = async () => undefined,
  providerAuthenticated,
  reload,
  signedIn,
}: ProviderSessionReconcilerOptions): () => Promise<boolean> {
  return async () => {
    if (providerAuthenticated()) return true
    // Only a page that still shows its signed-in account control has a session
    // to end, and only this reading of it counts: the page may have been
    // replaced while the provider was being sampled, and an anonymous page waiting
    // for its first sign in must be left exactly as it is.
    if (!signedIn()) return true

    await clearSession()
    await disconnectWallets()
    reload()
    return false
  }
}

const showsSignedInAccount = () =>
  document.querySelector("#account-control [data-account-target='profile']") !== null

// The wallet the server signed the account in with, as the page was drawn.
const accountWallet = () =>
  document.querySelector<HTMLElement>("#account-control")?.dataset.accountWallet?.toLowerCase() ?? null

type PrivySessionCompletionOptions = {
  acquireTokens: () => Promise<PrivyTokenPair>
  fetcher?: typeof fetch
  localSessionNeeded: () => boolean
  reload: () => void
  capture?: () => {current: () => boolean; identity: unknown}
}

// The pair is acquired inside the attempt, so every entry point — a granted
// token, an explicit sign in, a same-account refresh — asks Privy for one
// complete, current pair and sends nothing when it cannot get one.
function createPrivySessionCompletion({
  acquireTokens,
  fetcher = fetch,
  localSessionNeeded,
  reload,
  capture = () => ({current: () => true, identity: undefined}),
}: PrivySessionCompletionOptions): () => Promise<void> {
  let inFlight: {promise: Promise<void>; current: () => boolean} | null = null
  let adopted: {identity: unknown; transitioned: boolean} | null = null

  return () => {
    if (!localSessionNeeded()) { adopted = null; return Promise.resolve() }
    const operation = capture()
    if (!operation.current()) return Promise.resolve()
    if (adopted && adopted.identity === operation.identity) {
      if (!adopted.transitioned) { adopted.transitioned = true; reload() }
      return Promise.resolve()
    }
    if (inFlight?.current()) return inFlight.promise
    adopted = null

    const attempt = (async () => {
      const tokens = await acquireTokens()
      requireCurrent(operation.current)
      await createLocalSession(tokens, fetcher, browserSessionMutations, operation.current)
      if (capture().identity !== operation.identity) return
      adopted = {identity: operation.identity, transitioned: false}
      if (operation.current()) { adopted.transitioned = true; reload() }
    })()

    inFlight = {promise: attempt, current: operation.current}
    const settled = () => { if (inFlight?.promise === attempt) inFlight = null }
    void attempt.then(settled, settled)

    return attempt
  }
}

function createPrivyTokenCallbacks(completeLogin: () => Promise<void>) {
  return {
    onAccessTokenGranted: () => completeLogin().catch(() => undefined),
    onAccessTokenRemoved: () => undefined,
  } satisfies PrivyEvents["accessToken"]
}

type PrivyLoginCallbackOptions = {
  completeLogin: () => Promise<void>
  isCurrent?: () => boolean
  acceptsSubject?: (subject: string | undefined) => boolean
  loginOpen: {current: boolean}
  showFailure: (failure: SignInFailureKind) => void
  reportFailure?: (failure: SignInFailureDiagnostic) => void
}

const privyLoginFailureDiagnostics: Partial<Record<string, SignInFailureDiagnostic>> = {
  exited_auth_flow: "flow_closed",
  client_request_timeout: "request_timeout",
  invalid_message: "invalid_message",
  unable_to_sign: "unable_to_sign",
}

function privyLoginFailureDiagnostic(error: unknown): SignInFailureDiagnostic {
  return privyLoginFailureDiagnostics[typeof error === "string" ? error : ""] ?? "provider_error"
}

// Privy runs this for its own provider bootstrap too, for a modal this page
// never opened, and that entry shares the one in-flight completion with a
// deliberate click. Only a modal this page opened may speak for it, so a
// bootstrap refusal stays silent, and a completion this page asked for says so
// rather than rejecting into nothing. Both outcomes close the modal, so both
// release the guard for the next click.
export function createPrivyLoginCallbacks({
  completeLogin,
  loginOpen,
  showFailure,
  reportFailure = reportSignInFailure,
  isCurrent = () => true,
  acceptsSubject = () => true,
}: PrivyLoginCallbackOptions): PrivyEvents["login"] {
  return {
    onComplete: ({loginAccount, user, wasAlreadyAuthenticated}) => {
      if (!isCurrent() || !acceptsSubject(user?.id)) return
      const opened = loginOpen.current
      loginOpen.current = false
      // A Privy session the browser already held is never the visitor's own
      // sign-in: a page's sign-in logs Privy out first, and a real redirect
      // return arrives signed out. So after a Disconnect it stays signed out.
      if ((!opened || wasAlreadyAuthenticated) && walletDisconnected()) return
      forgetEthereumWalletSelection()
      if (loginAccount?.type === "wallet" && loginAccount.chainType === "ethereum") {
        rememberEthereumWalletSelection(loginAccount)
      }
      // The visitor signed in, which is one of the two ways they come back with
      // a wallet. This runs before the session completion reloads the document,
      // so the page that replaces this one reads a cleared note on its first
      // wallet sync.
      forgetWalletDisconnected()
      void completeLogin().catch(error => {
        if (!opened || !isCurrent() || error instanceof StalePrivyOperation) return
        if (!(error instanceof ServerReportedSessionError)) {
          reportFailure("session_exchange")
        }
        showFailure("session")
      })
    },
    onError: error => {
      if (!isCurrent()) return
      const opened = loginOpen.current
      loginOpen.current = false
      if (!opened) return
      const diagnostic = privyLoginFailureDiagnostic(error)
      reportFailure(diagnostic)
      // A person who closes the sign-in window chose to; nothing is said.
      if (diagnostic !== "flow_closed") showFailure("provider")
    },
  } satisfies PrivyEvents["login"]
}

type AccountBridgeProps = {
  // The page is Privy's return from a Google or other redirect sign-in, which
  // the person started from the sign-in window on the page before.
  oauthReturn: boolean
  mode: "ordinary" | "sign-out-only"
  lifetime: AbortSignal
  providerState?: PrivyBridgeProviderState
  publishRequestHandler: (
    requestHandler: PrivyBridgeHandle["request"],
    identityHandler: NonNullable<PrivyBridgeHandle["identity"]>,
    finishSignOutOnly: () => void,
    ready: boolean,
  ) => void
}

type PrivyBridgeProviderState = {
  userId?: string
  appId: string
  authenticated: boolean
  getAccessToken: () => Promise<string | null>
  getIdentityToken?: () => Promise<string | null>
  logout: () => Promise<void>
  ready: boolean
  walletsReady: ReturnType<typeof useWallets>["ready"]
  wallets: ReturnType<typeof useWallets>["wallets"]
  activeWallet?: ReturnType<typeof useActiveWallet>["wallet"]
  linkedWallets?: string[]
  setActiveWallet?: ReturnType<typeof useActiveWallet>["setActiveWallet"]
  connectWallet?: ReturnType<typeof useConnectWallet>["connectWallet"]
}

function AccountBridge({oauthReturn, mode, providerState, publishRequestHandler, lifetime}: AccountBridgeProps) {
  const privy = usePrivy()
  const providerWallets = useWallets()
  const providerActiveWallet = useActiveWallet()
  const synchronizeWalletsRef = React.useRef<() => Promise<void>>(async () => undefined)
  const loginEpoch = React.useRef(walletWorkEpoch())
  const connectEpoch = React.useRef(walletWorkEpoch())
  const finishWalletConnection = React.useCallback(() => {
    if (lifetime.aborted) return
    forgetWalletDisconnected()
    void synchronizeWalletsRef.current().catch(() => undefined)
  }, [lifetime])
  // The other way a visitor comes back with a wallet: they finished Privy's
  // connect flow. Abandoning that window never reaches here, so the Disconnect
  // stands until a wallet is actually connected again.
  const providerWalletConnector = useConnectWallet({
    onSuccess: ({wallet}) => {
      if (lifetime.aborted || connectEpoch.current !== walletWorkEpoch()) return
      forgetEthereumWalletSelection()
      if (wallet.type === "ethereum") rememberEthereumWalletSelection(wallet)
      finishWalletConnection()
    },
    onError: error => {
      if (lifetime.aborted || connectEpoch.current !== walletWorkEpoch() || error === "exited_auth_flow") return
      showAccountAuthFailure("connect-wallet")
      window.dispatchEvent(new Event("ash:wallet-connect-failed"))
    },
  })
  const authenticated = providerState?.authenticated ?? privy.authenticated
  const logout = providerState?.logout ?? privy.logout
  const ready = providerState?.ready ?? privy.ready
  const walletsReady = providerState?.walletsReady ?? providerWallets.ready
  const wallets = providerState?.wallets ?? providerWallets.wallets
  const activeWallet = providerState?.activeWallet ?? providerActiveWallet.wallet
  const setActiveWallet = providerState?.setActiveWallet ?? providerActiveWallet.setActiveWallet
  const connectWallet = providerState?.connectWallet ?? providerWalletConnector.connectWallet
  // The Ethereum wallets the signed-in account is linked to, joined so a render
  // with the same accounts leaves the wallet sync below alone.
  const linkedWallets = (
    providerState?.linkedWallets ??
    (privy.user?.linkedAccounts ?? []).flatMap(account =>
      account.type === "wallet" && account.chainType === "ethereum" ? [account.address] : [],
    )
  ).map(address => address.toLowerCase()).join(",")
  const signOutOnly = mode === "sign-out-only"
  const signOutOnlyState = React.useRef<"preterminal" | "terminal">(
    signOutOnly ? "preterminal" : "terminal",
  )
  // Acquisition depends on the provider hooks below, while the one in-flight
  // attempt these callbacks share must survive every rerender, so the stable
  // completion reads the latest pair source rather than closing over one.
  const acquireTokensRef = React.useRef<() => Promise<PrivyTokenPair>>(() =>
    Promise.reject(new Error("Sign in could not be completed.")),
  )
  const completeExplicitLogin = React.useMemo(
    () =>
      createPrivySessionCompletion({
        acquireTokens: () => acquireTokensRef.current(),
        capture: () => {
          const generation = identityGeneration.current
          const subject = provider.current.subject
          const epoch = walletWorkEpoch()
          return {
            identity: JSON.stringify([subject, epoch, generation]),
            current: () => !lifetime.aborted && provider.current.ready && provider.current.authenticated &&
              identityGeneration.current === generation && provider.current.subject === subject && walletWorkEpoch() === epoch,
          }
        },
        localSessionNeeded: () =>
          (!signOutOnly || signOutOnlyState.current === "terminal") &&
          document.querySelector("#account-control [data-account-target='sign-in']") !== null,
        reload: () => window.location.reload(),
      }),
    [signOutOnly, lifetime],
  )
  const completeWalletLogin = React.useCallback(async () => {
    requireCurrent(() => !lifetime.aborted && loginEpoch.current === walletWorkEpoch())
    await completeExplicitLogin()
    if (!lifetime.aborted && provider.current.ready && provider.current.authenticated && loginEpoch.current === walletWorkEpoch()) {
      finishWalletConnection()
    }
  }, [completeExplicitLogin, finishWalletConnection, lifetime])
  // A redirect return finishes the sign-in window the person opened, so it
  // speaks for the page and its own sign-in clears an earlier Disconnect.
  const loginOpen = React.useRef(oauthReturn)
  const loginCallbacks = React.useMemo(
    () =>
      createPrivyLoginCallbacks({
        completeLogin: completeWalletLogin,
        isCurrent: () => !lifetime.aborted && loginEpoch.current === walletWorkEpoch(),
        acceptsSubject: subject => !subject || !provider.current.authenticated || !provider.current.subject || provider.current.subject === subject,
        loginOpen,
        showFailure: failure => showAccountAuthFailure("sign-in", document, failure),
      }),
    [completeWalletLogin, lifetime],
  )
  const {login} = useLogin(loginCallbacks)
  // The published handler outlives every render, so the click it answers reads
  // the provider of the latest committed render — never one React started and
  // discarded — which is why this is written after the commit and before the
  // effect that publishes the handler.
  const subject = providerState?.userId ?? privy.user?.id ?? null
  // A person who signs in with email or Google gets their Privy wallet just
  // after Privy signs them in, and the site's sign-in needs a wallet.
  const hasWallet = linkedWallets !== ""
  const provider = React.useRef({authenticated, hasWallet, login, logout, ready, subject})
  // Counts the times the signed-in person changed, so work started for one
  // never finishes on behalf of the next.
  const identityGeneration = React.useRef(0)
  React.useEffect(() => {
    const changed = provider.current.authenticated !== authenticated || provider.current.subject !== subject
    provider.current = {authenticated, hasWallet, login, logout, ready, subject}
    if (changed) identityGeneration.current += 1
  }, [authenticated, hasWallet, login, logout, ready, subject])
  const signIn = React.useMemo(
    () =>
      createSignInRequest({
        isCurrent: () => !lifetime.aborted,
        authenticated: () => provider.current.authenticated,
        providerLogout: () => provider.current.logout(),
        openLogin: () => provider.current.login(),
        loginOpen,
      }),
    [lifetime],
  )
  // Adoption only ever asks the server, and only once the person has a wallet:
  // the run that follows their new wallet asks then.
  const completeAutomaticLogin = React.useCallback(
    () =>
      lifetime.aborted || !provider.current.ready || !provider.current.authenticated ||
        !provider.current.hasWallet || walletDisconnected() || signOutOnly
        ? Promise.resolve() : completeExplicitLogin(),
    [completeExplicitLogin, signOutOnly, lifetime],
  )
  const tokenCallbacks = React.useMemo(
    () => createPrivyTokenCallbacks(completeAutomaticLogin),
    [completeAutomaticLogin],
  )
  const providerToken = useToken(tokenCallbacks)
  const getAccessToken = providerState?.getAccessToken ?? providerToken.getAccessToken
  const acquireTokens = React.useMemo(
    () =>
      createPrivyTokenPairSource({
        getIdentityToken: providerState?.getIdentityToken ?? getIdentityToken,
        getAccessToken,
        capture: () => {
          const generation = identityGeneration.current
          const epoch = walletWorkEpoch()
          return () => !lifetime.aborted && provider.current.ready && provider.current.authenticated &&
            identityGeneration.current === generation && walletWorkEpoch() === epoch
        },
      }),
    [getAccessToken, providerState?.getIdentityToken, lifetime],
  )
  React.useEffect(() => { acquireTokensRef.current = acquireTokens }, [acquireTokens])
  const notifyIdentityState = React.useCallback((state: IdentityState) => {
    if (lifetime.aborted) return
    window.dispatchEvent(new CustomEvent(IDENTITY_STATE_EVENT, {detail: state}))
  }, [lifetime])
  const refreshIdentitySession = React.useCallback(async (outcome: IdentityOutcome) => {
    const generation = identityGeneration.current
    const epoch = walletWorkEpoch()
    const current = () => !lifetime.aborted && provider.current.ready && provider.current.authenticated &&
      identityGeneration.current === generation && walletWorkEpoch() === epoch
    requireCurrent(current)
    const tokens = await acquireTokensRef.current()
    requireCurrent(current)
    const result = await createLocalSession(tokens, fetch, browserSessionMutations, current)
    if (current()) notifyIdentityState({...outcome, error: result.identityError ?? null})
  }, [lifetime, notifyIdentityState])
  // Privy answers a link on these after its own flow, including after X and
  // GitHub bring the tab back, so the outcome names the account kind it was for.
  const linkCallbacks = React.useMemo<PrivyEvents["linkAccount"]>(
    () => ({
      onSuccess: ({linkMethod}) => {
        const provider = identityProviderFor(linkMethod)
        if (!provider) return
        void refreshIdentitySession({action: "link", provider}).catch(error => {
          if (!(error instanceof StalePrivyOperation)) {
            notifyIdentityState({error: "failed", action: "link", provider})
          }
        })
      },
      onError: (_error, {linkMethod}) => {
        const provider = identityProviderFor(linkMethod)
        if (provider) notifyIdentityState({error: "failed", action: "link", provider})
      },
    }),
    [notifyIdentityState, refreshIdentitySession],
  )
  const {linkTwitter, linkGithub, linkFarcaster} = useLinkAccount(linkCallbacks)
  const {unlink: unlinkOAuth} = useUnlinkOAuth()
  const {unlink: unlinkFarcasterAccount} = useUnlinkFarcaster()
  const walletSyncGeneration = React.useRef(0)
  const selectedWalletRef = React.useRef<ConnectedWallet | null>(null)
  const reconcileProviderSession = React.useMemo(
    () =>
      createProviderSessionReconciler({
        clearSession: () => browserSessionMutations.signOut(clearLocalSession),
        disconnectWallets: () => finishWalletSignOut(document, window),
        providerAuthenticated: () => authenticated,
        reload: () => reloadDocumentOnce(document, () => window.location.reload()),
        signedIn: showsSignedInAccount,
      }),
    [authenticated],
  )

  React.useEffect(() => {
    if (signOutOnly || !ready || !authenticated || !hasWallet) return

    void completeAutomaticLogin().catch(() => undefined)
  }, [authenticated, completeAutomaticLogin, hasWallet, ready, signOutOnly])

  // The active selection is published alongside the connected set and depends on
  // it, so a selection change with an unchanged wallets array still runs this and
  // still announces `ash:wallet-state`.
  const synchronizeWallets = React.useCallback(async () => {
    if (lifetime.aborted) return
    const epoch = walletWorkEpoch()
    const generation = ++walletSyncGeneration.current
    // Provider logout is authoritative independently of wallet hydration or a
    // remembered wallet-only disconnect. Never let that early return mask it.
    if (ready && !authenticated && !signOutOnly && showsSignedInAccount()) {
      await reconcileProviderSession()
      return
    }

    // Disconnect is the visitor's own choice and outlives the document it was
    // made in. Until they connect a wallet or sign in again, nothing the wallet
    // app still reports to Privy is this page's wallet.
    if (walletDisconnected()) {
      selectedWalletRef.current = null
      replaceConnectedEthereumWallets([])
      replaceActiveEthereumWallet(null)
      window.dispatchEvent(new CustomEvent("ash:wallet-state"))
      return
    }

    let selectedWallet =
      activeWallet?.type === "ethereum" &&
      wallets.some(wallet => wallet.address.toLowerCase() === activeWallet.address.toLowerCase())
        ? activeWallet
        : null
    const pendingSelection = pendingEthereumWalletSelection()
    if (pendingSelection) {
      const matches = ready && walletsReady ? wallets.filter(wallet =>
        wallet.type === "ethereum" && wallet.address.toLowerCase() === pendingSelection.address &&
        wallet.walletClientType === pendingSelection.walletClientType,
      ) : []
      // An unhydrated or ambiguous selection is no wallet, never the first item
      // in the connected list or the wallet left selected by another login.
      selectedWallet = matches.length === 1 ? matches[0] : null
      if (selectedWallet) {
        if (!sameConnectedWallet(activeWallet?.type === "ethereum" ? activeWallet : null, selectedWallet)) {
          setActiveWallet(selectedWallet)
        }
        forgetEthereumWalletSelection()
      }
    }
    // Privy names no wallet after a sign-in that skipped its window, or in a new
    // tab. The signed-in wallet then sends as this tab has it connected: the one
    // connected wallet the account is linked to, or, when this tab has several,
    // the account's own wallet the page was drawn for. Several and none of them
    // the account's own is no wallet; the press opens Privy's connect window.
    if (!selectedWallet && !pendingSelection && ready && walletsReady && linkedWallets) {
      const linked = linkedWallets.split(",")
      const signedIn = wallets.filter(wallet =>
        wallet.type === "ethereum" && linked.includes(wallet.address.toLowerCase()),
      )
      const own = accountWallet()
      const chosen = signedIn.length === 1
        ? signedIn
        : signedIn.filter(wallet => wallet.address.toLowerCase() === own)
      if (chosen.length === 1) {
        selectedWallet = chosen[0]
        setActiveWallet(selectedWallet)
      }
    }
    const switchedAccount = selectedWallet || pendingSelection ? null : switchedAccountOf(selectedWalletRef.current, wallets)

    // The wallet the customer just left stops being the active wallet here, before
    // any of the work below can await, so nothing can be prepared or sent for it
    // while the newly selected provider is still resolving.
    if (activeEthereumWallet() && !sameConnectedWallet(selectedWalletRef.current, selectedWallet)) {
      replaceActiveEthereumWallet(null)
      window.dispatchEvent(new CustomEvent("ash:wallet-state"))
    }
    selectedWalletRef.current = selectedWallet

    // An account switched inside the wallet app the customer was already using
    // is their own choice, so Privy's selection follows it. This run ends with
    // no wallet; the run Privy's new selection starts publishes the account.
    if (switchedAccount) {
      setActiveWallet(switchedAccount)
      return
    }

    // A sign-out-only bridge has just ended the session on purpose, so there is
    // nothing to reconcile; reconciling would end it a second time and reload.
    const reconciled = ready && (signOutOnly || (await reconcileProviderSession()))
    if (!reconciled || !walletsReady) {
      if (walletSyncGeneration.current !== generation) return
      replaceConnectedEthereumWallets([])
      replaceActiveEthereumWallet(null)
      window.dispatchEvent(new CustomEvent("ash:wallet-state"))
      return
    }

    // Each connected wallet's provider is resolved once, and the selection is
    // taken from those resolved entries. A wallet whose provider does not
    // resolve is not a wallet here, so a failed selection leaves the page with no
    // active wallet rather than with the previous one.
    const resolved = await Promise.allSettled(
      wallets.map(async wallet => ({
        address: wallet.address.toLowerCase(),
        provider: (await wallet.getEthereumProvider()) as EthereumProvider,
        // Privy's own way of letting go of this wallet, carried beside the
        // provider so Disconnect can release both without the bridge.
        disconnect: () => wallet.disconnect(),
      })),
    )
    if (walletSyncGeneration.current !== generation || lifetime.aborted || walletWorkEpoch() !== epoch) return

    const entries = resolved.flatMap(result => (result.status === "fulfilled" ? [result.value] : []))
    const selectedIndex = selectedWallet ? wallets.indexOf(selectedWallet) : -1
    const selectedResult = selectedIndex >= 0 ? resolved[selectedIndex] : null
    let selectedProvider =
      selectedResult?.status === "fulfilled" ? selectedResult.value.provider : null
    if (selectedWallet && selectedIndex < 0) {
      try {
        selectedProvider = (await selectedWallet.getEthereumProvider()) as EthereumProvider
      } catch {
        selectedProvider = null
      }
      if (walletSyncGeneration.current !== generation) return
    }
    // Everything above was awaited, so Disconnect may have landed while this
    // sync was in flight. The generation counter only knows about newer syncs,
    // which is why the visitor's own choice is read again here, last.
    if (walletDisconnected() || lifetime.aborted || walletWorkEpoch() !== epoch) return

    replaceConnectedEthereumWallets(
      entries.map(entry => [entry.address, {provider: entry.provider, disconnect: entry.disconnect}]),
    )
    replaceActiveEthereumWallet(
      selectedWallet && selectedProvider
        ? {address: selectedWallet.address, provider: selectedProvider}
        : null,
    )
    window.dispatchEvent(new CustomEvent("ash:wallet-state"))
  }, [
    activeWallet,
    linkedWallets,
    ready,
    reconcileProviderSession,
    setActiveWallet,
    signOutOnly,
    wallets,
    walletsReady,
    lifetime,
  ])

  // A sign-out-only bridge publishes nothing while the provider sign out is
  // still settling. From the moment it settles it publishes exactly as an
  // ordinary bridge does: the wallets Privy still holds, and every wallet the
  // customer connects afterwards on this page.
  React.useEffect(() => { synchronizeWalletsRef.current = synchronizeWallets }, [synchronizeWallets])

  React.useEffect(() => {
    if (signOutOnly && signOutOnlyState.current !== "terminal") return
    void synchronizeWallets().catch(() => undefined)
    return () => {
      walletSyncGeneration.current += 1
    }
  }, [signOutOnly, synchronizeWallets])

  // Privy's connect window, for a wallet this tab does not have yet or for a
  // choice between wallets. Its own success callback above says the visitor
  // came back with one, so there is nothing to read from this answer.
  const connectSelectedWallet = React.useCallback(async () => {
    requireCurrent(() => !lifetime.aborted)
    connectEpoch.current = walletWorkEpoch()
    await Promise.resolve(
      connectWallet({walletChainType: "ethereum-only", description: "Connect the wallet you want to use here."}),
    )
  }, [connectWallet, lifetime])

  const markSignOutTerminal = React.useCallback(() => {
    signOutOnlyState.current = "terminal"
    walletSyncGeneration.current += 1
    void synchronizeWalletsRef.current().catch(() => undefined)
  }, [])

  const ordinaryRequestHandler = React.useMemo(
    () =>
      createAccountRequestHandler({
        connectWallet: connectSelectedWallet,
        signIn: () => {
          requireCurrent(() => !lifetime.aborted)
          loginEpoch.current = walletWorkEpoch()
          return signIn()
        },
        providerLogout: () => provider.current.logout(),
        synchronizeWallets,
      }),
    [connectSelectedWallet, signIn, synchronizeWallets, lifetime],
  )

  const ordinaryIdentityHandler = React.useMemo(
    () =>
      createIdentityRequestHandler({
        linkX: linkTwitter,
        linkGithub,
        linkFarcaster,
        unlinkOAuth: async (provider, subject) => {
          await unlinkOAuth({provider, subject})
        },
        unlinkFarcaster: async fid => {
          await unlinkFarcasterAccount({fid})
        },
        refreshSession: refreshIdentitySession,
      }),
    [
      linkFarcaster,
      linkGithub,
      linkTwitter,
      refreshIdentitySession,
      unlinkFarcasterAccount,
      unlinkOAuth,
    ],
  )

  const ordinaryRequestHandlerRef = React.useRef(ordinaryRequestHandler)
  const ordinaryIdentityHandlerRef = React.useRef(ordinaryIdentityHandler)
  React.useEffect(() => {
    ordinaryRequestHandlerRef.current = ordinaryRequestHandler
    ordinaryIdentityHandlerRef.current = ordinaryIdentityHandler
  }, [ordinaryRequestHandler, ordinaryIdentityHandler])

  const signOutOnlyBridge = React.useMemo(
    () =>
      createSignOutOnlyBridgeState({
        ordinaryRequest: request => ordinaryRequestHandlerRef.current(request),
        ordinaryIdentity: request => ordinaryIdentityHandlerRef.current(request),
        onTerminal: markSignOutTerminal,
      }),
    [markSignOutTerminal],
  )
  const requestHandler = signOutOnly
    ? signOutOnlyBridge.request
    : ordinaryRequestHandler
  const identityHandler = signOutOnly
    ? signOutOnlyBridge.identity
    : ordinaryIdentityHandler
  const finishSignOutOnly = signOutOnlyBridge.finish

  React.useEffect(
    () => publishRequestHandler(requestHandler, identityHandler, finishSignOutOnly, ready),
    [finishSignOutOnly, identityHandler, publishRequestHandler, ready, requestHandler],
  )

  return null
}

export function startPrivyBridge(
  {mode = "ordinary", signal, readyTimeoutMs = 15_000}: PrivyBridgeStartupOptions = {},
  providerState?: PrivyBridgeProviderState,
): Promise<PrivyBridgeHandle> {
  if (signal?.aborted) return Promise.reject(new StalePrivyOperation())
  const appId =
    providerState?.appId ??
    document.querySelector<HTMLMetaElement>("meta[name='privy-app-id']")?.content
  if (!appId) return Promise.reject(new Error("Privy app is unavailable"))
  // Read before Privy finishes the return and clears these from the address.
  const oauthReturn = returnedFromOAuth(window.location.search)
  const host = document.createElement("div")
  host.hidden = true
  document.body.append(host)

  return new Promise((resolve, reject) => {
    let currentRequestHandler: PrivyBridgeHandle["request"] | null = null
    let currentIdentityHandler: PrivyBridgeHandle["identity"] | null = null
    let currentFinishSignOutOnly: (() => void) | null = null
    let resolved = false
    let currentReady = false
    const controller = new AbortController()
    const root = createRoot(host)
    let timeout: ReturnType<typeof setTimeout> | undefined
    const onAbort = () => dispose()
    const dispose = (reason: Error = new StalePrivyOperation()) => {
      if (controller.signal.aborted) return
      controller.abort(reason)
      clearTimeout(timeout)
      signal?.removeEventListener("abort", onAbort)
      currentRequestHandler = null
      currentIdentityHandler = null
      root.unmount()
      host.remove()
      if (!resolved) reject(reason)
    }
    signal?.addEventListener("abort", onAbort, {once: true})
    timeout = setTimeout(() => dispose(new AccountAuthFailure("startup", "request_timeout")), readyTimeoutMs)
    const handle: PrivyBridgeHandle = {
      dispose,
      request(request) {
        if (controller.signal.aborted) return Promise.reject(new StalePrivyOperation())
        if (!currentReady && request !== "sync" && request !== "sign-out") {
          return Promise.reject(new AccountAuthFailure("startup", "request_timeout"))
        }
        return currentRequestHandler
          ? currentRequestHandler(request)
          : Promise.reject(new Error("Privy bridge is not ready"))
      },
      identity(request) {
        return currentIdentityHandler
          ? currentIdentityHandler(request)
          : Promise.reject(new Error("Privy bridge is not ready"))
      },
      finishSignOutOnly() {
        currentFinishSignOutOnly?.()
      },
    }
    const publishRequestHandler: AccountBridgeProps["publishRequestHandler"] = (
      requestHandler,
      identityHandler,
      finishSignOutOnly,
      ready,
    ) => {
      if (controller.signal.aborted) return
      currentReady = ready
      currentRequestHandler = requestHandler
      currentIdentityHandler = identityHandler
      currentFinishSignOutOnly = finishSignOutOnly
      if (!ready || resolved) return
      clearTimeout(timeout)
      resolved = true
      resolve(handle)
    }

    root.render(
      // The sign-in choices (a wallet, Google and the others) come from the Privy
      // dashboard. Someone who signs in without a wallet gets a Privy Ethereum
      // wallet of their own at once, linked to their account, so every account
      // can act. It is an ordinary wallet, never a smart wallet: SIWA checks its
      // signatures without asking the chain. Privy's own list of networks covers
      // every network a step goes to, through Privy's own nodes, and a person
      // always sees Privy's confirm window before their Privy wallet signs.
      <PrivyProvider
        appId={appId}
        config={{
          appearance: {logo: "/mark.png"},
          embeddedWallets: {showWalletUIs: true, ethereum: {createOnLogin: "users-without-wallets"}},
        }}
      >
        <AccountBridge
          oauthReturn={oauthReturn}
          mode={mode}
          lifetime={controller.signal}
          providerState={providerState}
          publishRequestHandler={publishRequestHandler}
        />
      </PrivyProvider>,
    )
  })
}
