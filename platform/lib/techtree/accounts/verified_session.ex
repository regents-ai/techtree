defmodule Techtree.Accounts.VerifiedSession do
  @moduledoc "Exchanges verified Privy evidence for the canonical human account."

  alias Techtree.Accounts
  alias Techtree.Accounts.EnsIdentity
  alias Techtree.Actors.System

  @actor %System{}

  @doc """
  Registers or refreshes the account the verified session names, reconciles
  its linked socials, moves Credits waiting under its wallets to it and asks
  Ethereum for its wallet's ENS name again, returning the providers another
  account already holds.
  Without a linked wallet the account's wallet evidence is withdrawn instead.
  """
  def establish(%RegentPrivy.Session{privy_user_id: did} = verified) do
    # `RegentPrivy.Session` already lowercases the list, keeps each wallet once
    # and puts the wallet the person signed in with inside it.
    case verified do
      %{wallet_address: primary, wallet_addresses: [_ | _] = addresses} when is_binary(primary) ->
        with {:ok, account} <- Accounts.register_verified(did, primary, addresses, actor: @actor),
             {:ok, account} <-
               Accounts.refresh_verified(account, primary, addresses, actor: @actor),
             {:ok, conflicts} <- reconcile(account.id, verified.linked_socials),
             {:ok, _moved} <-
               RegentCredits.attach_wallets(did, addresses, actor: Techtree.Credits.site_actor()),
             :ok <- request_ens_lookup(account) do
          {:ok, account, conflicts}
        end

      _no_linked_wallet ->
        withdraw_wallet_evidence(did)
    end
  end

  @doc """
  The account a verified session names, read without changing it: an API call
  acts for the account a sign-in on the site created, while its wallet evidence
  is still current.
  """
  def account(%RegentPrivy.Session{privy_user_id: did}) do
    case Accounts.get_by_privy_did(did, actor: @actor) do
      {:ok, nil} ->
        {:error, :account_required}

      {:ok, account} ->
        if current?(account), do: {:ok, account}, else: {:error, :account_required}

      {:error, _error} = failure ->
        failure
    end
  end

  @doc "Whether the account's stored wallet evidence still names a signed-in wallet."
  def current?(%{wallet_address: primary, wallet_addresses: addresses})
      when is_binary(primary) and is_list(addresses),
      do: addresses != [] and primary in addresses

  def current?(_account), do: false

  defp request_ens_lookup(account) do
    if EnsIdentity.looking_up?() do
      with {:ok, _identity} <-
             Accounts.request_ens_lookup(account.id, account.wallet_address, actor: @actor),
           do: :ok
    else
      :ok
    end
  end

  defp reconcile(account_id, linked_socials) do
    with {:ok, existing} <- Accounts.list_linked_identities_for_account(account_id, actor: @actor),
         {:ok, conflicts} <- upsert_socials(linked_socials, account_id) do
      kept = linked_socials |> Enum.map(& &1.provider) |> MapSet.new()
      remove_missing(existing, kept, conflicts)
    end
  end

  # The first social per provider wins; a provider whose subject another
  # account holds is reported as a conflict rather than stopping the sign-in.
  defp upsert_socials(linked_socials, account_id) do
    linked_socials
    |> Enum.uniq_by(& &1.provider)
    |> Enum.reduce_while({:ok, []}, fn social, {:ok, conflicts} ->
      case upsert_social(social, account_id) do
        :ok -> {:cont, {:ok, conflicts}}
        :conflict -> {:cont, {:ok, [social.provider | conflicts]}}
        {:error, error} -> {:halt, {:error, error}}
      end
    end)
  end

  defp upsert_social(%{provider: provider, subject: subject} = social, account_id) do
    identity =
      social
      |> Map.take([:provider, :subject, :username, :display_name])
      |> Map.merge(%{
        verified_at: DateTime.utc_now(),
        metadata: %{},
        human_account_id: account_id
      })

    with {:ok, current} <-
           Accounts.get_linked_identity_by_subject(provider, subject, actor: @actor),
         :ok <- subject_available(current, account_id),
         {:ok, _identity} <- Accounts.upsert_linked_identity(identity, actor: @actor) do
      :ok
    else
      {:error, :already_linked} -> :conflict
      {:error, error} -> conflict_or_error(error, provider, subject, account_id)
    end
  end

  defp subject_available(nil, _account_id), do: :ok
  defp subject_available(%{human_account_id: id}, id), do: :ok
  defp subject_available(_identity, _account_id), do: {:error, :already_linked}

  # A concurrent sign-in may have taken the subject between the read and the
  # upsert; re-reading tells a conflict apart from a real failure.
  defp conflict_or_error(error, provider, subject, account_id) do
    case Accounts.get_linked_identity_by_subject(provider, subject, actor: @actor) do
      {:ok, %{human_account_id: id}} when id != account_id -> :conflict
      _result -> {:error, error}
    end
  end

  defp remove_missing(existing, kept, conflicts) do
    existing
    |> Enum.reject(&(&1.provider in kept))
    |> Enum.reduce_while({:ok, conflicts}, fn identity, ok ->
      case Accounts.remove_linked_identity(identity, actor: @actor) do
        :ok -> {:cont, ok}
        {:error, error} -> {:halt, {:error, error}}
      end
    end)
  end

  defp withdraw_wallet_evidence(did) do
    with {:ok, %{} = account} <- Accounts.get_by_privy_did(did, actor: @actor),
         {:ok, _account} <- Accounts.refresh_verified(account, nil, [], actor: @actor) do
      {:error, :missing_linked_wallet}
    else
      {:ok, nil} -> {:error, :missing_linked_wallet}
      error -> error
    end
  end
end
