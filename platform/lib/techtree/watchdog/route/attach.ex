defmodule Techtree.Watchdog.Route.Attach do
  @moduledoc """
  Attaches a route to one of the person's own hosts. The host is read as the
  acting person, so a route can never be hung off someone else's host, and the
  route's owner and host are taken from that host, not from the request. The
  address must be a web address on that same host. A route under a host that
  isn't proven yet starts paused, so it can only become active once the host is
  proven.
  """

  use Ash.Resource.Change

  alias Techtree.Watchdog.Host

  @impl true
  def change(changeset, _opts, context) do
    Ash.Changeset.before_action(changeset, fn changeset ->
      host_id = Ash.Changeset.get_argument(changeset, :host_id)
      url = changeset |> Ash.Changeset.get_attribute(:url) |> normalize_url()

      with {:ok, host} <- own_host(host_id, context),
           {:ok, url} <- url,
           :ok <- on_host?(url, host) do
        Ash.Changeset.force_change_attributes(changeset, %{
          url: url,
          host_id: host.id,
          human_account_id: host.human_account_id,
          kind: :public,
          state: initial_state(host)
        })
      else
        {:error, :bad_host} ->
          Ash.Changeset.add_error(changeset, field: :host_id, message: "isn't one of your sites")

        {:error, :bad_url} ->
          Ash.Changeset.add_error(changeset, field: :url, message: "isn't a web address")

        {:error, :off_host} ->
          Ash.Changeset.add_error(changeset,
            field: :url,
            message: "has to be an address on that site"
          )
      end
    end)
  end

  defp own_host(host_id, context) when is_binary(host_id) do
    case Ash.get(Host, host_id, actor: context.actor, authorize?: true) do
      {:ok, host} -> {:ok, host}
      {:error, _not_found} -> {:error, :bad_host}
    end
  end

  defp own_host(_host_id, _context), do: {:error, :bad_host}

  defp normalize_url(url) when is_binary(url) do
    trimmed = String.trim(url)

    case URI.parse(trimmed) do
      %URI{scheme: scheme, host: host} when scheme in ["http", "https"] and is_binary(host) ->
        {:ok, trimmed}

      _not_a_web_address ->
        {:error, :bad_url}
    end
  end

  defp normalize_url(_url), do: {:error, :bad_url}

  defp on_host?(url, host) do
    case URI.parse(url) do
      %URI{host: h} when is_binary(h) ->
        if String.downcase(h) == host.origin, do: :ok, else: {:error, :off_host}

      _unparsed ->
        {:error, :off_host}
    end
  end

  defp initial_state(%{ownership_state: :verified}), do: :active
  defp initial_state(_unverified), do: :paused
end
