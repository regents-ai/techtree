defmodule Techtree.WalletBench.Batch do
  @moduledoc """
  Manual, nonfinancial release batches. Planning makes no database or provider
  calls. Starting freezes the reviewed manifest in every attempt and queues
  existing AshOban steps in one transaction. Reusing a batch id cannot admit
  a second copy. Historical attempts are never changed.
  """

  require Ash.Query

  alias Techtree.WalletBench
  alias Techtree.WalletBench.{Attempt, Catalog, Judge, Machine}

  @fields ~w(format batch axis target operator harnesses wallets repeats recipe protocol access model effort judge
             model_budget_usd skill)
  @pin_fields ~w(version source_ref archive_sha256 integrity)
  @version ~r/\Av?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\z/
  @sha ~r/\A[0-9a-f]{64}\z/
  @ref ~r/\A[0-9a-f]{40}\z/
  @integrity ~r/\Asha512-[A-Za-z0-9+\/]{86}==\z/

  @doc """
  Resolve one upgraded harness against all wallets, one wallet against all
  harnesses, or one pair (`H05-W01`) at both default releases. `:skill` names
  a Skill the agent gets before its first turn, and `:model_budget_usd` the
  most each attempt's model calls may cost (`Catalog.model_budget_usd/0` unless given).
  """
  def plan(options) do
    axis = Keyword.fetch!(options, :axis)
    target = Keyword.fetch!(options, :id)

    harnesses =
      for id <- Enum.sort(Catalog.harness_ids()), into: %{}, do: {id, Catalog.harness_pin!(id)}

    wallets =
      for id <- Enum.sort(Catalog.tested_wallet_ids()),
          into: %{},
          do: {id, Catalog.wallet_version!(id)}

    {harnesses, wallets} =
      case axis do
        "harness" ->
          version = Keyword.fetch!(options, :version)
          pin = upgraded_pin(Map.fetch!(harnesses, target), version, options)

          {%{target => pin}, wallets}

        "wallet" ->
          _ = Map.fetch!(wallets, target)
          {harnesses, %{target => Keyword.fetch!(options, :version)}}

        "pair" ->
          if options[:version], do: raise(ArgumentError, "a pair runs both default releases")
          [harness, wallet] = String.split(target, "-")

          {%{harness => Map.fetch!(harnesses, harness)}, %{wallet => Map.fetch!(wallets, wallet)}}

        _ ->
          raise ArgumentError, "axis must be harness, wallet or pair"
      end

    %{
      "format" => 1,
      "batch" => Ecto.UUID.generate(),
      "axis" => axis,
      "target" => target,
      "operator" => Keyword.fetch!(options, :operator),
      "harnesses" => harnesses,
      "wallets" => wallets,
      "repeats" => Keyword.get(options, :repeats, 1),
      "recipe" => Catalog.recipe_digest(),
      "protocol" => Catalog.protocol_digest(),
      "access" => "unassisted",
      "model" => "claude-opus-5-5",
      "effort" => "high",
      "judge" => Judge.model(),
      "model_budget_usd" => Keyword.get(options, :model_budget_usd, Catalog.model_budget_usd()),
      "skill" => skill(options[:skill])
    }
    |> validate!()
  end

  @doc "Validate an edited manifest; refuse moving versions and stale execution or test recipes."
  def validate!(manifest) do
    validate_context!(manifest)
    harnesses = manifest["harnesses"]
    wallets = manifest["wallets"]
    check(is_map(harnesses) && is_map(wallets), "version maps")

    validate_axis!(manifest, harnesses, wallets)

    Enum.each(harnesses, &validate_pin!/1)

    check(
      manifest["skill"] == nil or Map.keys(harnesses) -- Catalog.skill_harness_ids() == [],
      "a Skill reaches only the agents in Catalog.skill_harness_ids/0"
    )

    Enum.each(wallets, fn {id, version} ->
      check(id in Catalog.tested_wallet_ids(), "supported wallet")
      version!(version)
    end)

    manifest
  end

  @doc "Count, Skill and model spending cap for review; judge and Sprite costs are additional."
  def summary(manifest) do
    count = map_size(manifest["harnesses"]) * map_size(manifest["wallets"]) * manifest["repeats"]

    %{
      batch: manifest["batch"],
      attempts: count,
      skill: manifest["skill"],
      model_budget_usd: manifest["model_budget_usd"],
      model_cap_usd: count * manifest["model_budget_usd"],
      access: "unassisted",
      money_tests: false
    }
  end

  @doc "Operator-only admission. Call only after the batch's provider spending is approved."
  def start(manifest) do
    manifest = validate!(manifest)

    Ash.transact([Machine, Attempt], fn ->
      # One admission per batch id at a time, so a second manifest naming the same
      # id sees the first one's attempts and is refused, even with other pairs.
      Techtree.Repo.query!("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", [
        manifest["batch"]
      ])

      existing = attempts(manifest["batch"])

      if existing == [] do
        admit(manifest)
      else
        validate_existing!(existing, manifest)

        existing
      end
    end)
  end

  @doc "Do not continue a frozen batch through a new site release, changed scripts or review guides."
  def require_current!(nil), do: :ok

  def require_current!(spec) do
    check(spec["revision"] == commit(), "site release changed")
    check(spec["recipe"] == Catalog.recipe_digest(), "execution recipe changed")
    check(spec["protocol"] == Catalog.protocol_digest(), "test protocol changed")
    check(spec["judge"] == Judge.model(), "judge model changed")
  end

  @doc """
  One read of progress, with what the batch's model and judge calls have cost so
  far; this function never polls or starts provider work.
  """
  def status(batch) do
    {:ok, batch} = Ecto.UUID.cast(batch)
    rows = batch |> attempts() |> Ash.load!([:model_spend_usd, :judge_cost_usd])
    machines = Machine |> Ash.Query.filter(batch_id == ^batch) |> Ash.read!()

    spent = fn field ->
      Enum.reduce(rows, Decimal.new(0), &Decimal.add(Map.fetch!(&1, field) || 0, &2))
    end

    %{
      batch: batch,
      model_spend_usd: spent.(:model_spend_usd),
      judge_cost_usd: spent.(:judge_cost_usd),
      attempts:
        Enum.map(
          rows,
          &Map.take(&1, [
            :id,
            :harness_id,
            :wallet_id,
            :replicate,
            :state,
            :failure,
            :model_spend_usd,
            :judge_cost_usd
          ])
        ),
      machines:
        Enum.map(
          machines,
          &Map.take(&1, [:name, :harness_id, :state, :baseline_checkpoint_id, :failure])
        )
    }
  end

  defp attempts(batch), do: Attempt |> Ash.Query.filter(batch_id == ^batch) |> Ash.read!()

  # The manifest names its operator; each admission records the name.
  defp operator(manifest), do: %Techtree.Actors.Operator{name: manifest["operator"]}

  defp admit(manifest) do
    Enum.each(manifest["harnesses"], fn {id, pin} ->
      name = "wb-" <> String.downcase(id) <> "-" <> manifest["batch"]

      # Operator-only batch admission; public policies deliberately deny these writes.
      WalletBench.request_machine!(name, id, %{batch_id: manifest["batch"], configuration: pin},
        authorize?: false,
        actor: operator(manifest)
      )
    end)

    for {harness, _} <- Enum.sort(manifest["harnesses"]),
        {wallet, _} <- Enum.sort(manifest["wallets"]),
        replicate <- 1..manifest["repeats"] do
      # Operator-only batch admission; public policies deliberately deny these writes.
      WalletBench.request_attempt!(
        harness,
        wallet,
        %{
          plan: :wallet,
          batch_id: manifest["batch"],
          replicate: replicate,
          run_spec: spec(manifest, harness, wallet)
        },
        authorize?: false,
        actor: operator(manifest)
      )
    end
  end

  defp spec(manifest, harness, wallet) do
    manifest
    |> Map.drop(~w(harnesses wallets))
    |> Map.put("harness", manifest["harnesses"][harness])
    |> Map.put("wallet_version", manifest["wallets"][wallet])
    |> Map.put("revision", commit())
  end

  # The commit this release runs, which /capabilities.json names.
  defp commit, do: Application.fetch_env!(:techtree, :build).commit

  defp skill(nil), do: nil

  defp skill(name) do
    skill = Catalog.skill!(name)
    %{"name" => skill.name, "sha256" => skill.sha256}
  end

  defp upgraded_pin(pin, version, options) do
    pin = if pin["version"] == version, do: pin, else: %{"version" => version}

    Enum.reduce([:source_ref, :archive_sha256, :integrity], pin, fn key, acc ->
      put_pin(acc, key, options[key])
    end)
  end

  defp put_pin(pin, _key, nil), do: pin
  defp put_pin(pin, key, value), do: Map.put(pin, Atom.to_string(key), value)

  defp validate_context!(manifest) do
    check(
      is_map(manifest) && Enum.sort(Map.keys(manifest)) == Enum.sort(@fields),
      "manifest fields"
    )

    check(manifest["format"] == 1, "manifest format")
    check(match?({:ok, _}, Ecto.UUID.cast(manifest["batch"])), "batch UUID")

    check(
      is_binary(manifest["operator"]) &&
        Regex.match?(~r/\A[a-zA-Z0-9_.-]{1,64}\z/, manifest["operator"]),
      "operator"
    )

    check(manifest["repeats"] in 1..3, "repeats (1 to 3)")
    check(manifest["access"] == "unassisted", "only unassisted access is supported")

    check(
      manifest["model"] == "claude-opus-5-5" && manifest["effort"] == "high",
      "frozen model and effort"
    )

    check(
      manifest["recipe"] == Catalog.recipe_digest(),
      "execution recipe changed; make a new plan"
    )

    check(
      manifest["protocol"] == Catalog.protocol_digest(),
      "test protocol changed; make a new plan"
    )

    check(manifest["judge"] == Judge.model(), "judge model changed; make a new plan")

    check(
      is_number(manifest["model_budget_usd"]) and manifest["model_budget_usd"] > 0 and
        manifest["model_budget_usd"] <= Catalog.model_budget_usd(),
      "model budget (above 0, at most #{Catalog.model_budget_usd()} dollars an attempt)"
    )

    check(
      manifest["skill"] == nil or
        (is_map(manifest["skill"]) and manifest["skill"]["name"] in Catalog.skill_names() and
           manifest["skill"] == skill(manifest["skill"]["name"])),
      "Skill unknown or changed; make a new plan"
    )
  end

  defp validate_axis!(manifest, harnesses, wallets) do
    case manifest["axis"] do
      "harness" ->
        check(Map.keys(harnesses) == [manifest["target"]], "one target harness")

        check(
          Enum.sort(Map.keys(wallets)) == Enum.sort(Catalog.tested_wallet_ids()),
          "all supported wallets"
        )

      "wallet" ->
        check(Map.keys(wallets) == [manifest["target"]], "one target wallet")

        check(
          Enum.sort(Map.keys(harnesses)) == Enum.sort(Catalog.harness_ids()),
          "all supported harnesses"
        )

      "pair" ->
        check(
          [Enum.join(Map.keys(harnesses) ++ Map.keys(wallets), "-")] == [manifest["target"]],
          "one target harness and wallet"
        )

        [harness] = Map.keys(harnesses)
        check(harness in Catalog.harness_ids(), "supported harness")
        check(:T2 in Catalog.tests(harness), "a harness that takes the wallet test")

      _ ->
        check(false, "axis must be harness, wallet or pair")
    end
  end

  defp validate_pin!({id, pin}) do
    Catalog.harness!(id)
    check(is_map(pin) && Map.keys(pin) -- @pin_fields == [], "harness pin fields")
    version!(pin["version"])
    validate_source!(id, pin)
  end

  defp validate_source!("H04", pin) do
    check(
      is_binary(pin["source_ref"]) && Regex.match?(@ref, pin["source_ref"]),
      "Hermes requires its full commit"
    )

    check(Map.keys(pin) -- ~w(version source_ref) == [], "Hermes pin fields")
  end

  defp validate_source!(id, pin) when id in ["H01", "H05", "H09", "H16"] do
    check(
      is_binary(pin["archive_sha256"]) && Regex.match?(@sha, pin["archive_sha256"]),
      "release archive requires SHA-256"
    )

    check(Map.keys(pin) -- ~w(version archive_sha256) == [], "archive pin fields")
  end

  # The agents npm installs: the registry's published fingerprint for that exact version.
  defp validate_source!(_id, pin) do
    check(
      is_binary(pin["integrity"]) && Regex.match?(@integrity, pin["integrity"]),
      "npm package requires its published integrity"
    )

    check(Map.keys(pin) -- ~w(version integrity) == [], "package pin fields")
  end

  defp validate_existing!(existing, manifest) do
    check(length(existing) == summary(manifest).attempts, "existing batch is incomplete")

    Enum.each(existing, fn attempt ->
      check(
        attempt.run_spec == spec(manifest, attempt.harness_id, attempt.wallet_id),
        "batch id already names different versions or settings"
      )
    end)
  end

  defp version!(value),
    do:
      check(
        is_binary(value) && byte_size(value) <= 80 && Regex.match?(@version, value),
        "exact major.minor.patch release version"
      )

  defp check(true, _reason), do: :ok
  defp check(false, reason), do: raise(ArgumentError, "Invalid wallet-bench plan: " <> reason)
end
