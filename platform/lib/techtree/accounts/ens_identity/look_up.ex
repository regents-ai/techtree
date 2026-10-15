defmodule Techtree.Accounts.EnsIdentity.LookUp do
  @moduledoc """
  Reads the wallet's verified ENS name and picture before the row is written.

  The chain is read before the update and outside any transaction. A name is
  kept only when it resolves back to the same wallet, and a picture only when
  the ENS avatar service answers with one (`AgentEns.PrimaryName`). A failed
  read fails the action as a server fault, so the job retries with backoff and
  the reason reaches saved errors (`Techtree.ErrorIgnorer` leaves out invalid
  input); a server with no Ethereum endpoint cancels it. The avatar service not answering in time is a
  failed read too, never "no picture": it is slow for a name it has not been
  asked about lately, and the picture already stored must outlast that.

  The answer is written only while the row still names the wallet it was read
  for. A sign-in with another wallet while the read runs can't queue a second
  job for the row, so the write fails as stale instead, and the retry reads the
  row's new wallet.
  """

  use Ash.Resource.Change

  require Ash.Expr

  alias AgentEns.PrimaryName
  alias Ash.Error.Unknown.UnknownError
  alias AshOban.Errors.CancelJob
  alias Techtree.Accounts.EnsIdentity

  @impl true
  def change(changeset, _opts, _context) do
    wallet = changeset.data.wallet_address

    changeset
    |> Ash.Changeset.filter(Ash.Expr.expr(wallet_address == ^wallet))
    |> Ash.Changeset.before_action(fn changeset ->
      case look_up(wallet) do
        {:ok, identity} ->
          changeset
          |> Ash.Changeset.force_change_attribute(:ens_name, identity[:name])
          |> Ash.Changeset.force_change_attribute(:ens_avatar_url, identity[:avatar_url])
          |> Ash.Changeset.force_change_attribute(:lookup_state, :done)

        {:cancel, reason} ->
          Ash.Changeset.add_error(changeset, CancelJob.exception(reason: reason))

        {:error, reason} ->
          Ash.Changeset.add_error(
            changeset,
            UnknownError.exception(error: "ENS lookup failed: #{inspect(reason)}")
          )
      end
    end)
  end

  defp look_up(wallet) do
    case EnsIdentity.rpc_url() do
      nil ->
        {:cancel, :no_ethereum_endpoint}

      rpc_url ->
        with {:ok, identity} <- PrimaryName.verified_primary_identity(wallet, rpc_url: rpc_url),
             do: {:ok, identity || %{}}
    end
  end
end
