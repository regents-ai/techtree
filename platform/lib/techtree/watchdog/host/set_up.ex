defmodule Techtree.Watchdog.Host.SetUp do
  @moduledoc """
  Prepares a host a person adds: reads the host out of what they typed (a bare
  name, or a name inside a URL), lowercased and without a port or path, gives it
  a fresh proof token, and starts it unproven. The owner is the acting person,
  taken from the actor, never from the request.
  """

  use Ash.Resource.Change

  alias Techtree.Watchdog.Ownership

  @impl true
  def change(changeset, _opts, context) do
    changeset
    |> set_origin()
    |> Ash.Changeset.force_change_attributes(%{
      verification_token: Ownership.new_token(),
      ownership_state: :unverified,
      human_account_id: actor_account_id(context)
    })
  end

  defp set_origin(changeset) do
    case changeset |> Ash.Changeset.get_argument(:origin) |> normalize() do
      {:ok, origin} -> Ash.Changeset.force_change_attribute(changeset, :origin, origin)
      :error -> Ash.Changeset.add_error(changeset, field: :origin, message: "isn't a web address")
    end
  end

  @doc "Reads a bare host out of a typed address, lowercased, without a port or path."
  @spec normalize(String.t() | nil) :: {:ok, String.t()} | :error
  def normalize(input) when is_binary(input) do
    trimmed = String.trim(input)

    host =
      case URI.parse(with_scheme(trimmed)) do
        %URI{host: host} when is_binary(host) -> host
        _unparsed -> nil
      end

    cond do
      is_nil(host) -> :error
      host == "" -> :error
      not valid_host?(host) -> :error
      true -> {:ok, String.downcase(host)}
    end
  end

  def normalize(_input), do: :error

  defp with_scheme(input) do
    if String.contains?(input, "://"), do: input, else: "https://" <> input
  end

  # A host is letters, digits, dots and hyphens (a name), or an address literal.
  defp valid_host?(host) do
    Regex.match?(~r/\A[a-zA-Z0-9.\-:\[\]]+\z/, host) and String.length(host) <= 253
  end

  defp actor_account_id(%{actor: %{human_account_id: id}}), do: id
  defp actor_account_id(_context), do: nil
end
