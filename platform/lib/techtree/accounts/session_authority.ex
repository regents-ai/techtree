defmodule Techtree.Accounts.SessionAuthority do
  @moduledoc """
  The durable authority behind one browser session lineage.

  The signed cookie carries a random 32-byte lineage, its generation and the
  socket topic the lineage determines, never an account: identity comes from the
  row, keyed by the lineage's SHA-256 digest so a database reader cannot rebuild
  a cookie. `/auth/csrf` commits an unbound generation-zero row; first bind and
  every same-account refresh advance the generation once, so the previous cookie
  is stale everywhere. Revocation is terminal, and a bound row older than the
  cookie's `max_age` reads as reset. Every transition inserts the row when
  absent, locks it `FOR UPDATE` and applies at most one change in one
  transaction, so the absent-row and present-row races serialize identically.
  """

  use Ash.Resource,
    domain: Techtree.Accounts,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  alias Techtree.Accounts
  alias Techtree.Accounts.VerifiedSession
  alias Techtree.Actors.{Human, System}
  alias Techtree.Repo

  @actor %System{}
  @lineage_bytes 32
  @maximum_generation 9_223_372_036_854_775_807
  @canonical_keys ["session_lineage", "session_generation", "live_socket_id"]
  @sign_in_lifetime_seconds Application.compile_env!(:techtree, [:session_options, :max_age])

  @typedoc "Everything a browser carries. There is no account here by design."
  @type claim :: %{lineage: String.t(), generation: non_neg_integer()}

  postgres do
    table "session_authorities"
    repo Techtree.Repo

    check_constraints do
      check_constraint :generation, "session_authorities_generation_nonnegative",
        check: "generation >= 0",
        message: "generation must be nonnegative"
    end

    references do
      reference :human_account, on_delete: :restrict
    end
  end

  actions do
    # The primary read is what an atomic update re-reads the locked row through.
    defaults [:read]

    read :by_lineage_digest do
      get? true
      argument :lineage_digest, :binary, allow_nil?: false
      filter expr(lineage_digest == ^arg(:lineage_digest))
    end

    create :mint do
      accept [:lineage_digest]
    end

    update :bind do
      accept []
      argument :account_id, :integer, allow_nil?: false
      validate absent([:revoked_at, :human_account_id])
      change set_attribute(:human_account_id, arg(:account_id))
      change atomic_update(:generation, expr(generation + 1))
    end

    # Refresh cannot name an account, so a bound lineage can never change one.
    update :advance do
      accept []
      validate absent(:revoked_at)
      validate present(:human_account_id)
      change atomic_update(:generation, expr(generation + 1))
    end

    update :revoke do
      accept []
      validate absent(:revoked_at)
      change set_attribute(:revoked_at, &DateTime.utc_now/0)
    end
  end

  policies do
    policy always() do
      authorize_if actor_attribute_equals(:role, :system)
    end
  end

  attributes do
    uuid_primary_key :id
    attribute :lineage_digest, :binary, allow_nil?: false, sensitive?: true
    attribute :generation, :integer, allow_nil?: false, default: 0, constraints: [min: 0]
    attribute :revoked_at, :utc_datetime_usec
    timestamps()
  end

  relationships do
    belongs_to :human_account, Techtree.Accounts.HumanAccount do
      attribute_type :integer
    end
  end

  identities do
    identity :unique_lineage_digest, [:lineage_digest]
  end

  @doc """
  The claim `session` carries, or `nil` when it carries none the server minted:
  the exact unpadded base64url encoding of 32 bytes, a generation inside the
  column's range and the socket topic this lineage determines. Anything else is
  malformed, never a weaker claim.
  """
  @spec claim(map() | nil) :: claim() | nil
  def claim(%{"session_lineage" => lineage, "session_generation" => generation} = session)
      when is_binary(lineage) and is_integer(generation) and
             generation in 0..@maximum_generation//1 do
    with {:ok, <<raw::binary-size(@lineage_bytes)>>} <- Base.url_decode64(lineage, padding: false),
         ^lineage <- Base.url_encode64(raw, padding: false),
         true <- Map.get(session, "live_socket_id") == topic(lineage) do
      %{lineage: lineage, generation: generation}
    else
      _malformed -> nil
    end
  end

  def claim(_session), do: nil

  @doc "Whether `session` states a claim at all; a malformed one is refused, not read as none."
  @spec claim_shaped?(map() | nil) :: boolean()
  def claim_shaped?(session) when is_map(session),
    do: Enum.any?(@canonical_keys, &Map.has_key?(session, &1))

  def claim_shaped?(_session), do: false

  @doc "The canonical claim fields, and only those, that a response restores."
  @spec session(claim()) :: %{String.t() => term()}
  def session(%{lineage: lineage, generation: generation}),
    do: %{
      "session_lineage" => lineage,
      "session_generation" => generation,
      "live_socket_id" => topic(lineage)
    }

  @doc """
  The `/auth/csrf` state matrix. A claim above generation zero whose row is
  absent fails closed and reports the breach without the identifying lineage.
  """
  @spec renew(claim() | nil) :: {:bootstrap | :current, claim()} | {:error, :superseded | :reset}
  def renew(nil) do
    lineage = @lineage_bytes |> :crypto.strong_rand_bytes() |> Base.url_encode64(padding: false)
    Ash.create!(__MODULE__, %{lineage_digest: digest(lineage)}, action: :mint, actor: @actor)
    {:bootstrap, %{lineage: lineage, generation: 0}}
  end

  def renew(%{lineage: lineage, generation: generation} = claim) do
    case locked(claim, &{state(&1, claim), &1}) do
      {:exact, row} -> {:current, claim_at(lineage, row)}
      {:superseded, _row} -> {:error, :superseded}
      {:reset, nil} -> absent_row(generation)
      {:reset, _row} -> {:error, :reset}
    end
  end

  @doc """
  The one serialized transition a verified sign-in performs: an exact unbound
  claim binds, an exact same-account claim refreshes, and a different account
  revokes the old lineage so a later request binds a fresh one.
  """
  @spec sign_in(claim() | nil, integer()) ::
          {:ok, :bind | :refresh, claim()}
          | {:switch, String.t()}
          | {:error, :superseded | :reset}
  def sign_in(%{lineage: lineage} = claim, account_id) do
    locked(claim, fn row ->
      case state(row, claim) do
        :exact -> transition(row, lineage, account_id)
        other -> {:error, other}
      end
    end)
  end

  def sign_in(nil, _account_id), do: {:error, :reset}

  @doc "Revokes a lineage terminally, ensuring an unseen one first; returns its socket topic."
  @spec revoke(claim() | nil) :: String.t() | nil
  def revoke(%{lineage: lineage}) do
    {:ok, _row} =
      Repo.transaction(fn ->
        ensure(lineage, DateTime.utc_now())
        lineage |> lock() |> revoke!()
      end)

    topic(lineage)
  end

  def revoke(nil), do: nil

  @doc """
  The lineage and verified account an exactly current claim resolves to, and
  the instant that sign-in lapses: `{nil, nil, nil}` when the claim is not
  current, `{lineage, nil, nil}` when it is but no one has signed in on it.
  """
  @spec resolve(claim() | nil) ::
          {String.t() | nil, Ash.Resource.record() | nil, DateTime.t() | nil}
  def resolve(%{lineage: lineage} = claim) do
    row = row(lineage)

    case state(row, claim) do
      :exact -> {lineage, verified(row.human_account_id), lapses_at(row)}
      :ensurable -> {lineage, nil, nil}
      _lifecycle -> {nil, nil, nil}
    end
  end

  def resolve(nil), do: {nil, nil, nil}

  @doc """
  The verified account a mounted lease still resolves to, or `nil`. A refresh
  advances the generation beneath a mounted socket, so a lease revalidates the
  lineage, account, revocation, sign-in age and provider evidence instead.
  """
  @spec leased_account(String.t(), integer()) :: Ash.Resource.record() | nil
  def leased_account(lineage, account_id) do
    row = row(lineage)

    if match?(%{revoked_at: nil, human_account_id: ^account_id}, row) and not lapsed?(row),
      do: verified(account_id)
  end

  @doc "The deterministic, lineage-stable topic every socket for a lineage mounts on."
  @spec topic(String.t()) :: String.t()
  def topic(lineage),
    do: "session_authority:" <> Base.url_encode64(digest(lineage), padding: false)

  # The four states an integrity-valid claim can hold against its row. A claim
  # ahead of its row, or above generation zero without one, is unrecoverable
  # rather than merely superseded, and so is a sign-in past its lifetime.
  defp state(nil, %{generation: 0}), do: :ensurable
  defp state(nil, _claim), do: :reset
  defp state(%{revoked_at: revoked_at}, _claim) when not is_nil(revoked_at), do: :reset

  defp state(%{generation: generation} = row, %{generation: claimed}) do
    cond do
      lapsed?(row) -> :reset
      claimed == generation -> :exact
      claimed < generation -> :superseded
      true -> :reset
    end
  end

  # Bind and refresh are the only updates a live row takes, and each is a
  # sign-in, so a bound row's `updated_at` is when the person last signed in.
  # An unbound row confers nothing, so it has no lifetime to outlive.
  defp lapsed?(%{human_account_id: nil}), do: false
  defp lapsed?(row), do: not DateTime.before?(DateTime.utc_now(), lapses_at(row))

  defp lapses_at(%{human_account_id: nil}), do: nil

  defp lapses_at(%{updated_at: signed_in_at}),
    do: DateTime.add(signed_in_at, @sign_in_lifetime_seconds)

  # Exhaustion is terminal rather than wrapping: the lineage is revoked and the
  # browser bootstraps a fresh one.
  defp transition(%{generation: @maximum_generation} = row, _lineage, _account_id) do
    revoke!(row)
    {:error, :reset}
  end

  defp transition(%{human_account_id: nil} = row, lineage, account_id),
    do: {:ok, :bind, updated_claim(row, lineage, :bind, %{account_id: account_id})}

  defp transition(%{human_account_id: account_id} = row, lineage, account_id),
    do: {:ok, :refresh, updated_claim(row, lineage, :advance, %{})}

  defp transition(row, lineage, _other_account_id) do
    revoke!(row)
    {:switch, topic(lineage)}
  end

  defp updated_claim(row, lineage, action, input),
    do: claim_at(lineage, Ash.update!(row, input, action: action, actor: @actor))

  defp revoke!(%{revoked_at: nil} = row),
    do: Ash.update!(row, %{}, action: :revoke, actor: @actor)

  defp revoke!(terminal), do: terminal

  # Bind and refresh may ensure the unbound generation-zero row the claim names,
  # so the absent-row order of a race takes the same lock as the present-row one.
  # `Repo.transaction`, not `Ash.transact`: an exhausted lineage is revoked and
  # then answers `{:error, :reset}`, and that revocation must commit, while
  # `Ash.transact` rolls back whenever the function returns an error.
  defp locked(%{lineage: lineage, generation: generation}, callback) do
    {:ok, result} =
      Repo.transaction(fn ->
        if generation == 0, do: ensure(lineage, nil)
        lineage |> lock() |> callback.()
      end)

    result
  end

  # Ash is bypassed on purpose: the seed confers nothing until a locked
  # transition binds it, and the loser of a concurrent seed must fall through to
  # that lock silently, which `on_conflict: :nothing` is.
  defp ensure(lineage, revoked_at) do
    now = DateTime.utc_now()

    row = %{
      id: Ash.UUID.generate(),
      lineage_digest: digest(lineage),
      generation: 0,
      revoked_at: revoked_at,
      inserted_at: now,
      updated_at: now
    }

    Repo.insert_all(__MODULE__, [row], on_conflict: :nothing, conflict_target: :lineage_digest)
  end

  defp absent_row(generation) do
    :telemetry.execute([:techtree, :session_authority, :absent_row], %{count: 1}, %{
      generation: generation
    })

    {:error, :reset}
  end

  defp lock(lineage),
    do: lineage |> lookup() |> Ash.Query.lock(:for_update) |> Ash.read_one!()

  defp row(lineage), do: lineage |> lookup() |> Ash.read_one!()

  defp lookup(lineage) do
    Ash.Query.for_read(__MODULE__, :by_lineage_digest, %{lineage_digest: digest(lineage)},
      actor: @actor
    )
  end

  defp verified(nil), do: nil

  defp verified(account_id) do
    case Accounts.get_human_account(account_id, actor: %Human{human_account_id: account_id}) do
      {:ok, account} -> if VerifiedSession.current?(account), do: account
      {:error, _unreadable} -> nil
    end
  end

  defp claim_at(lineage, %{generation: generation}),
    do: %{lineage: lineage, generation: generation}

  defp digest(lineage), do: :crypto.hash(:sha256, lineage)
end
