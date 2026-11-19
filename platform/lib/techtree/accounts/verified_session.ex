defmodule Techtree.Accounts.VerifiedSession do
  @moduledoc "Exchanges verified Privy evidence for the canonical human account."

  alias Ash.Error.Changes.InvalidAttribute
  alias Techtree.Accounts
  alias Techtree.Accounts.EnsIdentity
  alias Techtree.Actors.System

  @actor %System{}

  @doc """
  Registers or refreshes the account the verified session names, gives the
  person their shared profile when they have none, reconciles its linked
  socials and asks
  Ethereum for its wallet's ENS name again, returning the providers whose social
  account another account already holds where it cannot be shared.
  Without a linked wallet the account's wallet evidence is withdrawn instead.
  """
  def establish(%RegentPrivy.Session{privy_user_id: did} = verified) do
    # `RegentPrivy.Session` already lowercases the list, keeps each wallet once
    # and puts the person's main wallet (their own, or else the Regents wallet)
    # inside it.
    case verified do
      %{wallet_address: primary, wallet_addresses: [_ | _] = addresses} when is_binary(primary) ->
        with {:ok, account} <- Accounts.register_verified(did, primary, addresses, actor: @actor),
             {:ok, account} <-
               Accounts.refresh_verified(account, primary, addresses, actor: @actor),
             {:ok, _profile} <- RegentIdentity.ensure(verified),
             {:ok, conflicts} <- reconcile(account.id, verified.linked_socials),
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
         {:ok, conflicts} <- upsert_socials(linked_socials, existing, account_id) do
      kept = linked_socials |> Enum.map(& &1.provider) |> MapSet.new()
      remove_missing(existing, kept, conflicts)
    end
  end

  # The first social per provider wins; a provider whose subject another account
  # holds, where that provider's accounts are not shared, is reported as a
  # conflict rather than stopping the sign-in.
  defp upsert_socials(linked_socials, existing, account_id) do
    linked_socials
    |> Enum.uniq_by(& &1.provider)
    |> Enum.reduce_while({:ok, []}, fn social, {:ok, conflicts} ->
      case upsert_social(social, existing, account_id) do
        :ok -> {:cont, {:ok, conflicts}}
        :conflict -> {:cont, {:ok, [social.provider | conflicts]}}
        {:error, error} -> {:halt, {:error, error}}
      end
    end)
  end

  # `existing` is the account's own links, so whether another account holds the
  # subject is never read here: the database answers that when it is linked.
  defp upsert_social(%{provider: provider, subject: subject} = social, existing, account_id) do
    identity =
      social
      |> Map.take([:provider, :subject, :username, :display_name])
      |> Map.merge(%{
        verified_at: DateTime.utc_now(),
        metadata: %{},
        human_account_id: account_id
      })

    current = Enum.find(existing, &(&1.provider == provider and &1.subject == subject))

    case save_social(current, identity) do
      {:ok, _identity} -> :ok
      {:error, error} -> conflict_or_error(error)
    end
  end

  # A subject new to the account links it: a first link for the provider, or one
  # that replaces the account's earlier subject. A subject other accounts hold is
  # linked here as well when its provider's accounts are shared; otherwise the
  # database refuses it. The same subject again refreshes it.
  defp save_social(nil, identity), do: Accounts.upsert_linked_identity(identity, actor: @actor)

  defp save_social(current, identity) do
    Accounts.refresh_linked_identity(
      current,
      Map.take(identity, [:username, :display_name, :verified_at, :metadata]),
      actor: @actor
    )
  end

  # `LinkedIdentity` `:unique_subject_per_provider` refuses a subject another
  # account holds, one a concurrent sign-in just took included, with an error on
  # the subject alone that names the unique rule: that is the conflict.
  defp conflict_or_error(%Ash.Error.Invalid{errors: errors} = error) do
    if Enum.any?(errors, &subject_taken?/1), do: :conflict, else: {:error, error}
  end

  defp conflict_or_error(error), do: {:error, error}

  defp subject_taken?(%InvalidAttribute{field: :subject, private_vars: vars}),
    do: vars[:constraint_type] == :unique

  defp subject_taken?(_error), do: false

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
