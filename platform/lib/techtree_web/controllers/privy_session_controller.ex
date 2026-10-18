defmodule TechtreeWeb.PrivySessionController do
  @moduledoc "The browser session endpoints: CSRF bootstrap, Privy sign-in, sign-out and failure reports."
  use TechtreeWeb, :controller

  alias Techtree.AccessContext
  alias Techtree.Accounts.{RequestRateLimiter, SessionAuthority, VerifiedSession}
  alias TechtreeWeb.{ClientAddress, PrivyProof}
  alias TechtreeWeb.Live.Session

  require Logger

  @browser_failure_reasons ~w(bridge_startup flow_closed invalid_message provider_error request_timeout session_exchange unable_to_sign)
  @browser_failure_limit 20
  @browser_failure_window_seconds 60

  # Every refusal answers {"error": {"code", "message", "hint"}}, the shape of the
  # site's other JSON errors. The browser reads the code; people read the words.
  @refusals %{
    "unauthorized" => {401, "This sign-in couldn't be confirmed.", "Sign in again."},
    "rate_limited" =>
      {429, "Too many new sign-ins came from this address.",
       "Wait the number of seconds in Retry-After, then try again."},
    "session_superseded" =>
      {409, "This browser was signed in again from another tab.", "Reload the page."},
    "session_reset_required" =>
      {409, "This browser's sign-in has ended.", "Reload the page, then sign in again."},
    "account_switch_required" =>
      {409, "This browser was signed in to another account.",
       "Reload the page, then sign in again."}
  }

  @doc """
  The browser-session state matrix: a browser with no claim is bootstrapped onto
  a fresh unbound lineage; an exact claim is only observed; a superseded or
  unrecoverable one is told which of the two it is instead of being silently reset.

  Observation writes no session, so this response carries no `Set-Cookie` and a
  delayed one cannot put an older generation back over a later winner's cookie.
  Only a browser carrying no claim can create a lineage, so only that request
  spends the anonymous bootstrap budget, and it spends it before `renew/1` can
  insert a row: a denial leaves behind no lineage and no CSRF session state.
  """
  def csrf(conn, _params), do: admit_bootstrap(conn, claim(conn))

  @doc """
  Records a bounded browser-side Privy failure without accepting provider text,
  identity, wallet, token, signature or exception data. The response is the same
  for valid, invalid and rate-limited reports: diagnostics never steer sign-in.
  """
  def failure(conn, %{"reason" => reason}) when reason in @browser_failure_reasons do
    report_bounded_sign_in_failure(conn, reason)
    diagnostic_accepted(conn)
  end

  def failure(conn, _untrusted_params), do: diagnostic_accepted(conn)

  def create(conn, _untrusted_params) do
    with {:ok, pair} <- PrivyProof.pair(conn),
         {:ok, verified} <-
           RegentPrivy.Session.verify(pair, Application.get_env(:techtree, :privy, [])),
         {:ok, account, identity_conflicts} <- establish(verified) do
      bind(conn, account, identity_conflicts)
    else
      {:error, {stage, reason}} -> refuse(conn, stage, reason)
    end
  end

  def show(conn, _params) do
    conn
    |> put_resp_header("cache-control", "no-store")
    |> json(session_payload(conn.assigns.current_human_account))
  end

  def delete(conn, _params),
    do: disconnect_after(conn, SessionAuthority.revoke(claim(conn)), &json(&1, %{ok: true}))

  @doc """
  The one place a request turns a cookie into an account. The cookie names no
  account, so identity comes from the locked row and only after the claim is
  exactly current; anything else leaves the request anonymous. A claim that is
  not current is also named as refused: no ordinary response may replace that
  cookie, so the page says so and the browser retires it through the session
  endpoints, which can.
  """
  def enforce_authority(conn, page) do
    session = get_session(conn)

    case session |> SessionAuthority.claim() |> Session.resolve(page) do
      {lineage, account, _lapses_at} ->
        conn
        |> assign(:current_lineage, lineage)
        |> assign(:current_human_account, account)
        |> assign(:session_refused, is_nil(lineage) and SessionAuthority.claim_shaped?(session))

      # A public page the database can't answer for draws signed out. The claim
      # isn't refused, so the browser keeps its cookie and stays signed in.
      :database_down ->
        conn
        |> assign(:current_lineage, nil)
        |> assign(:current_human_account, nil)
        |> assign(:session_refused, false)
    end
  end

  defp admit_bootstrap(conn, nil) do
    budget = Application.fetch_env!(:techtree, :session_bootstrap_rate_limit)
    window = Keyword.fetch!(budget, :window_seconds)
    {key, source} = ClientAddress.key(conn)

    case RequestRateLimiter.admit(
           {:session_bootstrap, key},
           Keyword.fetch!(budget, :limit),
           window
         ) do
      {:ok, _budget} -> renew(conn, nil)
      {:error, :rate_limited, _budget} -> rate_limited(conn, source, window)
    end
  end

  defp admit_bootstrap(conn, claim), do: renew(conn, claim)

  defp renew(conn, claim) do
    case SessionAuthority.renew(claim) do
      {:bootstrap, claim} -> conn |> rotate_session(claim) |> issue_token()
      {:current, _claim} -> issue_token(conn)
      {:error, :superseded} -> refuse(conn, "session_superseded")
      {:error, :reset} -> conn |> drop_session() |> refuse("session_reset_required")
    end
  end

  defp rate_limited(conn, source, window) do
    :telemetry.execute([:techtree, :session_bootstrap, :rate_limited], %{count: 1}, %{
      source: source
    })

    conn
    |> put_resp_header("retry-after", to_string(window))
    |> put_resp_header("cache-control", "no-store")
    |> refuse("rate_limited")
  end

  defp diagnostic_accepted(conn),
    do: conn |> put_resp_header("cache-control", "no-store") |> send_resp(:no_content, "")

  defp report_bounded_sign_in_failure(conn, reason) do
    {key, _source} = ClientAddress.key(conn)
    bucket = if reason == "flow_closed", do: :retryable, else: :actionable

    case RequestRateLimiter.admit(
           {:privy_browser_failure, bucket, key},
           @browser_failure_limit,
           @browser_failure_window_seconds
         ) do
      {:ok, _budget} -> report_sign_in_failure(reason)
      {:error, :rate_limited, _budget} -> :ok
    end
  end

  defp report_sign_in_failure(reason) do
    Logger.warning("Privy browser reported sign-in failure reason=#{reason}")
    :telemetry.execute([:techtree, :privy, :browser_failure], %{count: 1}, %{reason: reason})
  end

  # Privy is verified before the row lock, so only the transition itself is
  # serialized. A different account is a two-step cutover: this response revokes
  # and disconnects the old lineage and binds nothing.
  defp bind(conn, account, identity_conflicts) do
    case SessionAuthority.sign_in(claim(conn), account.id) do
      {:ok, transition, claim} ->
        conn
        |> rotate_session(claim)
        |> put_identity_conflict_header(identity_conflicts)
        |> put_resp_header("x-ash-session-changed", to_string(transition == :bind))
        |> json(session_payload(account))

      {:switch, topic} ->
        disconnect_after(conn, topic, &refuse(&1, "account_switch_required"))

      {:error, :superseded} ->
        refuse(conn, "session_superseded")

      {:error, :reset} ->
        conn |> drop_session() |> refuse("session_reset_required")
    end
  end

  # The account boundary's own outcomes are named; anything else it or Ash
  # returns is reduced without being inspected, so no query, changeset or record
  # detail can reach the classification.
  defp establish(verified) do
    case VerifiedSession.establish(verified) do
      {:ok, _account, _conflicts} = established -> established
      {:error, :missing_linked_wallet} -> account_evidence(:missing_linked_wallet)
      _rejected -> account_evidence(:account_rejected)
    end
  end

  defp account_evidence(reason), do: {:error, {:account_evidence, reason}}

  # Stage and reason are fixed atoms from the classification contract, so they
  # are safe as metric tags and in the message itself (the development formatter
  # drops metadata); they are never inspected or answered differently. The
  # provider attempt is over before any authority work starts, so no external
  # call sits inside the transaction: a bearer this browser cannot prove revokes
  # the lineage it was offered for instead of leaving it bound and current.
  defp refuse(conn, stage, reason) do
    Logger.info("Privy session refused stage=#{stage} reason=#{reason}")

    :telemetry.execute([:techtree, :privy, :session_refused], %{count: 1}, %{
      stage: stage,
      reason: reason
    })

    report_bounded_sign_in_failure(conn, "session_exchange")

    disconnect_after(conn, SessionAuthority.revoke(claim(conn)), &refuse(&1, "unauthorized"))
  end

  # The answer is sent before the lineage's sockets are told to disconnect, so
  # the browser reads it rather than a dropped connection.
  defp disconnect_after(conn, topic, respond) do
    %Plug.Conn{state: :sent} = conn = conn |> drop_session() |> respond.()
    if topic, do: TechtreeWeb.Endpoint.broadcast(topic, "disconnect", %{})
    conn
  end

  defp claim(conn), do: conn |> get_session() |> SessionAuthority.claim()

  defp rotate_session(conn, claim) do
    Plug.CSRFProtection.delete_csrf_token()

    conn
    |> configure_session(renew: true)
    |> clear_session()
    |> put_claim(claim)
    |> put_csrf_state()
  end

  defp put_claim(conn, claim) do
    claim
    |> SessionAuthority.session()
    |> Enum.reduce(conn, fn {key, value}, conn -> put_session(conn, key, value) end)
  end

  defp put_csrf_state(conn) do
    Plug.CSRFProtection.get_csrf_token()
    put_session(conn, "_csrf_token", Plug.CSRFProtection.dump_state())
  end

  defp issue_token(conn), do: json(conn, %{csrf_token: Plug.CSRFProtection.get_csrf_token()})

  defp refuse(conn, code) do
    {status, message, hint} = Map.fetch!(@refusals, code)
    conn |> put_status(status) |> json(%{error: %{code: code, message: message, hint: hint}})
  end

  defp drop_session(conn), do: configure_session(conn, drop: true)

  defp session_payload(account) do
    control = account |> AccessContext.for_account() |> AccessContext.account_control()
    %{authenticated: not is_nil(account), account_control: Map.from_struct(control)}
  end

  defp put_identity_conflict_header(conn, []), do: conn

  defp put_identity_conflict_header(conn, _conflicts),
    do: put_resp_header(conn, "x-ash-identity-error", "already-connected")
end
