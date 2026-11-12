defmodule Techtree.Agents.HostedAddress do
  @moduledoc """
  The wallet of each connected app's hosted identity: the identity an app such
  as Claude keeps for its person's account here, held by the sign-in service.
  Each app the person connects has its own. It never changes for an account
  and app on this site, so once the service has given it
  (`RegentMCPAgents.address/1`) it is kept on this machine by the account and
  the app's client together, and every later call from that app reads it here.
  An answer that failed is not kept: the next call asks again.
  """
  use Nebulex.Cache, otp_app: :techtree, adapter: Nebulex.Adapters.Local

  @doc "The wallet of the identity the connection's app keeps for its account here."
  @spec read(map()) :: {:ok, String.t()} | {:error, :unavailable}
  def read(%{subject: subject, client_id: client} = principal) do
    case get!({subject, client}) do
      nil -> ask(principal)
      address -> {:ok, address}
    end
  end

  # Two calls that miss at once both ask; the service gives both the same wallet.
  defp ask(%{subject: subject, client_id: client} = principal) do
    case RegentMCPAgents.address(principal) do
      {:ok, address} ->
        put!({subject, client}, address)
        {:ok, address}

      {:error, _reason} ->
        {:error, :unavailable}
    end
  end
end
