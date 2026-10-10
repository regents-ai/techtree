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

  @fields ~w(format batch axis target operator harnesses wallets repeats recipe protocol access model effort judge)
  @pin_fields ~w(version source_ref archive_sha256)
  @version ~r/\Av?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\z/
  @sha ~r/\A[0-9a-f]{64}\z/
  @ref ~r/\A[0-9a-f]{40}\z/

  @doc "Resolve one upgraded harness against all wallets, or one wallet against all harnesses."
  def plan(options) do
    axis = Keyword.fetch!(options, :axis)
    target = Keyword.fetch!(options, :id)
    version = Keyword.fetch!(options, :version)

    harnesses =
      for id <- Enum.sort(Catalog.harness_ids()), into: %{}, do: {id, Catalog.harness_pin!(id)}

    wallets =
      for id <- Enum.sort(Catalog.tested_wallet_ids()),
          into: %{},
          do: {id, Catalog.wallet!(id).survey_version}

    {harnesses, wallets} =
      case axis do
        "harness" ->
          pin = upgraded_pin(Map.fetch!(harnesses, target), version, options)

          {%{target => pin}, wallets}

        "wallet" ->
          _ = Map.fetch!(wallets, target)
          {harnesses, %{target => version}}

        _ ->
          raise ArgumentError, "axis must be harness or wallet"
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
      "model" => "gpt-6-luna",
      "effort" => "high",
      "judge" => Judge.model()
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

    Enum.each(wallets, fn {id, version} ->
      check(id in Catalog.tested_wallet_ids(), "supported wallet")
      version!(version)
    end)

    manifest
  end

  @doc "Count and model stop threshold for review; judge and Sprite costs are additional."
  def summary(manifest) do
    count = map_size(manifest["harnesses"]) * map_size(manifest["wallets"]) * manifest["repeats"]

    %{
      batch: manifest["batch"],
      attempts: count,
      model_stop_threshold_usd: count * 5,
      access: "unassisted",
      money_tests: false
    }
  end

  @doc "Operator-only admission. Call only after the batch's provider spending is approved."
  def start(manifest) do
    manifest = validate!(manifest)

    Ash.transact([Machine, Attempt], fn ->
      # Concurrent submissions are constrained by machine name and batch/pair/replicate identities.
      existing = attempts(manifest["batch"])

      if existing == [] do
        admit(manifest)
      else
        validate_existing!(existing, manifest)

        existing
      end
    end)
  end

  @doc "Do not continue a frozen batch through changed scripts or review guides."
  def require_current!(nil), do: :ok

  def require_current!(spec) do
    check(spec["recipe"] == Catalog.recipe_digest(), "execution recipe changed")
    check(spec["protocol"] == Catalog.protocol_digest(), "test protocol changed")
    check(spec["judge"] == Judge.model(), "judge model changed")
  end

  @doc "One read of progress; this function never polls or starts provider work."
  def status(batch) do
    {:ok, batch} = Ecto.UUID.cast(batch)
    rows = attempts(batch)
    machines = Machine |> Ash.Query.filter(batch_id == ^batch) |> Ash.read!()

    %{
      batch: batch,
      attempts:
        Enum.map(
          rows,
          &Map.take(&1, [:id, :harness_id, :wallet_id, :replicate, :state, :failure])
        ),
      machines:
        Enum.map(
          machines,
          &Map.take(&1, [:name, :harness_id, :state, :baseline_checkpoint_id, :failure])
        )
    }
  end

  defp attempts(batch), do: Attempt |> Ash.Query.filter(batch_id == ^batch) |> Ash.read!()

  defp admit(manifest) do
    Enum.each(manifest["harnesses"], fn {id, pin} ->
      name = "wb-" <> String.downcase(id) <> "-" <> manifest["batch"]

      # Operator-only batch admission; public policies deliberately deny these writes.
      WalletBench.request_machine!(name, id, %{batch_id: manifest["batch"], configuration: pin},
        authorize?: false
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
        authorize?: false
      )
    end
  end

  defp spec(manifest, harness, wallet) do
    manifest
    |> Map.drop(~w(harnesses wallets))
    |> Map.put("harness", manifest["harnesses"][harness])
    |> Map.put("wallet_version", manifest["wallets"][wallet])
  end

  defp upgraded_pin(pin, version, options) do
    pin = if pin["version"] == version, do: pin, else: %{"version" => version}

    Enum.reduce([:source_ref, :archive_sha256], pin, fn key, acc ->
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
      manifest["model"] == "gpt-6-luna" && manifest["effort"] == "high",
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

      _ ->
        check(false, "axis must be harness or wallet")
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

  defp validate_source!(id, pin) when id in ["H09", "H16"] do
    check(
      is_binary(pin["archive_sha256"]) && Regex.match?(@sha, pin["archive_sha256"]),
      "release archive requires SHA-256"
    )

    check(Map.keys(pin) -- ~w(version archive_sha256) == [], "archive pin fields")
  end

  defp validate_source!(_id, pin), do: check(Map.keys(pin) == ["version"], "package pin fields")

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
