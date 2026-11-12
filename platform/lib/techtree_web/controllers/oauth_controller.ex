defmodule TechtreeWeb.OAuthController do
  @moduledoc "Boruta protocol routes and consent under the verified browser session and CSRF."
  use TechtreeWeb, :controller

  plug :rate_limit when action in [:register, :token, :revoke, :authorize, :approve]

  for action <- [:resource_metadata, :server_metadata, :register, :token, :revoke] do
    def unquote(action)(conn, _params), do: RegentOAuth.Protocol.call(conn, unquote(action))
  end

  for action <- [:authorize, :approve, :connections, :revoke_connection] do
    def unquote(action)(conn, _params), do: apply(RegentOAuth.Consent, unquote(action), [conn])
  end

  defp rate_limit(conn, _opts) do
    {address, _source} = TechtreeWeb.ClientAddress.key(conn)
    action = action_name(conn)
    # Opening consent may record a new app from its published identity, as
    # registering does, so the two share the lower limit.
    limit = if action in [:register, :authorize], do: 30, else: 120

    case Techtree.Accounts.RequestRateLimiter.admit({:oauth, action, address}, limit, 60) do
      {:ok, _} ->
        conn

      {:error, :rate_limited, _} ->
        conn
        |> put_resp_header("retry-after", "60")
        |> RegentOAuth.Protocol.json(429, %{error: "rate_limited"})
        |> halt()
    end
  end
end
