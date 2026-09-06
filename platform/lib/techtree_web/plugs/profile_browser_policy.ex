defmodule TechtreeWeb.Plugs.ProfileBrowserPolicy do
  @moduledoc """
  Privy permissions scoped to the personal profile page. Public catalog and
  publication pages retain their stricter existing policy.

  Sets `Permissions-Policy: tools=(self)` so the WebMCP tool surface stays
  same-origin, and a Content Security Policy without `unsafe-eval`, matching the
  rule that generated content is never executed.

  A per-request nonce is published as the `:csp_nonce` assign. `connect-src`
  names this page's own origin over `ws`/`wss` so the LiveView socket connects,
  plus the Privy and WalletConnect hosts the sign-in bridge has to reach.
  """

  @behaviour Plug

  import Plug.Conn

  @impl Plug
  def init(opts), do: opts

  @impl Plug
  def call(conn, _opts) do
    nonce = Base.url_encode64(:crypto.strong_rand_bytes(18), padding: false)

    conn
    |> assign(:csp_nonce, nonce)
    |> put_resp_header("permissions-policy", "tools=(self)")
    |> put_resp_header("content-security-policy", content_security_policy(conn, nonce))
  end

  defp content_security_policy(conn, nonce) do
    authority = authority(conn)

    Enum.join(
      [
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "img-src 'self' data: blob: https://explorer-api.walletconnect.com https://www.google.com https://*.gstatic.com",
        "font-src 'self' data:",
        # The Privy dialog writes inline styles.
        "style-src 'self' 'unsafe-inline'",
        "script-src 'self' 'nonce-#{nonce}'",
        # Privy's documented hosts for @privy-io/react-auth. The page still
        # never loads remote scripts; these are fetches, sockets, and iframes.
        "connect-src 'self' ws://#{authority} wss://#{authority} https://auth.privy.io wss://relay.walletconnect.com wss://relay.walletconnect.org wss://www.walletlink.org https://*.rpc.privy.systems https://explorer-api.walletconnect.com",
        "child-src https://auth.privy.io https://verify.walletconnect.com https://verify.walletconnect.org",
        "frame-src https://auth.privy.io https://verify.walletconnect.com https://verify.walletconnect.org",
        "form-action 'self'"
      ],
      "; "
    )
  end

  defp authority(%Plug.Conn{host: host, port: port, scheme: scheme}) do
    if {scheme, port} in [{:http, 80}, {:https, 443}] do
      host
    else
      "#{host}:#{port}"
    end
  end
end
