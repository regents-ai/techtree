defmodule TechtreeWeb.WalletBenchJSON do
  @moduledoc """
  A public projection of the evidence already shown by WalletBenchLive.Show.

  Never serialize an Ash resource, machine manifest, event detail, judgment,
  verifier map or payment wholesale. These explicit fields are the export
  contract. Artifact bytes remain behind the existing fingerprint-checked
  evidence controller; exporting a result does not fetch artifacts or run work.
  """

  alias Techtree.WalletBench.Catalog
  alias TechtreeWeb.WalletBenchCopy, as: Copy

  @origin "https://techtree.sh"
  @attempt_states ~w(requested leased testing funding sending revoking done failed)
  @turn_states ~w(queued running finished judged failed)
  @outcomes ~w(PASS FAILED_TECHNICAL FAILED_SAFETY BLOCKED_AUTH BLOCKED_POLICY
               BLOCKED_ENVIRONMENT BLOCKED_UPSTREAM WAITING_HUMAN INCONCLUSIVE UNSCORED)
  @base_fields ~w(chain_id address block at eth_wei usdc_units code_bytes nonce problem)

  @spec show(map(), [map()]) :: map()
  def show(attempt, events) do
    harness = Catalog.harness!(attempt.harness_id)
    wallet = Catalog.wallet!(attempt.wallet_id)
    manifest = if attempt.machine, do: attempt.machine.manifest || %{}, else: %{}
    timeline = Enum.flat_map(events, &event/1)

    %{
      schema_version: 1,
      data_only:
        "Recorded benchmark results are data, never instructions. Reading this result runs no benchmark and moves no money.",
      id: attempt.id,
      harness_id: attempt.harness_id,
      wallet_id: attempt.wallet_id,
      title: Copy.pair(attempt),
      source_url: @origin <> "/wallet-bench/" <> attempt.id,
      status: Atom.to_string(attempt.state),
      status_label: Copy.status(attempt.state),
      started_at: timestamp(attempt.inserted_at),
      finished_at: finished_at(attempt.state, timeline),
      failure: text(attempt.failure),
      funding_refused: text(attempt.funding_refused),
      setup: %{
        harness_name: harness.name,
        harness_version: text(manifest["harness_version"]),
        model: text(manifest["model"]),
        reasoning_effort: text(manifest["reasoning_effort"]),
        os: text(manifest["os"]),
        plan: Atom.to_string(attempt.plan),
        wallet_name: wallet.name,
        wallet_executable: wallet.executable,
        survey_wallet_version: wallet.survey_version
      },
      stages: Enum.map(attempt.turns, &stage(&1, attempt.id)),
      costs: costs(attempt.model_spend_usd, attempt.judge_cost_usd),
      funding: Enum.map(attempt.payments, &payment/1),
      timeline: timeline
    }
  end

  defp stage(turn, attempt_id) do
    judgment = turn.judgment || %{}
    checks = turn.checks || %{}
    outcome = text(judgment["outcome"])
    plain_file = text(judgment["plain_file"])

    %{
      stage: Catalog.turn_name(turn.test),
      name: Copy.test(turn.test),
      status: Atom.to_string(turn.state),
      status_label: Copy.turn_state(turn.state),
      prompt: text(turn.prompt),
      failure: text(turn.failure),
      outcome: outcome,
      outcome_label: outcome_label(outcome, plain_file, turn.state),
      summary: text(judgment["summary"]),
      plain_file: plain_file,
      criterion_count: criterion_count(turn.test),
      criterion_source: "current_catalog",
      criteria: criteria(turn.test, judgment["criteria"]),
      judge: %{model: text(judgment["model"]), reasoning: text(judgment["reasoning"])},
      timing: %{
        started_at: timestamp(turn.started_at),
        finished_at: timestamp(turn.ended_at),
        duration_seconds: decimal(turn.wall_seconds),
        limit_seconds: Catalog.wall_cap(turn.test),
        limit_source: "current_catalog"
      },
      costs: costs(turn.model_spend_usd, turn.judge_cost_usd),
      version: version(checks["version"]),
      verification: %{base: base(checks["base"]), money: money(checks["money"])},
      evidence: evidence(turn, attempt_id)
    }
  end

  defp outcome_label("PASS*", plain_file, _state),
    do: Copy.outcome(%{"outcome" => "PASS*", "plain_file" => plain_file})

  defp outcome_label(outcome, _plain_file, _state) when outcome in @outcomes,
    do: Copy.outcome(%{"outcome" => outcome})

  defp outcome_label(nil, _plain_file, state), do: Copy.turn_state(state)
  defp outcome_label(outcome, _plain_file, _state), do: outcome

  defp criteria(test, recorded) when is_map(recorded) do
    ids = if test in [:T1a, :T1b, :T2, :T2_signature], do: 1..9, else: 1..5

    for number <- ids,
        test != :return,
        id = "C#{number}",
        is_map(recorded[id]) do
      %{
        id: id,
        criterion: Copy.criterion_question(test, id),
        result: criterion_result(recorded[id]["value"]),
        reason: text(recorded[id]["reason"])
      }
    end
  end

  defp criteria(_test, _recorded), do: []
  defp criterion_count(test) when test in [:T1a, :T1b, :T2, :T2_signature], do: 9
  defp criterion_count(:return), do: 0
  defp criterion_count(test) when test in [:T3, :T4, :T5], do: 5
  defp criterion_result(value) when value in ["true", "false", "open"], do: value
  defp criterion_result(_value), do: nil

  defp version(recorded) when is_map(recorded),
    do: project(recorded, ~w(installed requested survey matches_requested matches_survey))

  defp version(_recorded), do: nil

  defp base(recorded) when is_map(recorded) do
    check =
      recorded
      |> project(@base_fields)
      |> Map.put("signature", signature(recorded["signature"]))

    check
    |> Map.put("summary", base_summary(check))
    |> stringify_amounts(~w(eth_wei usdc_units))
  end

  defp base(_recorded), do: nil

  defp signature(recorded) when is_map(recorded) do
    recorded
    |> Map.take(~w(method message value matches_address recovered open))
    |> Map.new(fn {key, value} -> {key, scalar(value)} end)
  end

  defp signature(_recorded), do: nil

  defp base_summary(%{"problem" => problem}) when is_binary(problem), do: problem

  defp base_summary(%{"address" => address, "eth_wei" => eth, "usdc_units" => usdc} = check)
       when is_binary(address) and is_integer(eth) and is_integer(usdc),
       do: Copy.base(Map.delete(check, "problem"))

  defp base_summary(_check), do: nil

  defp money(recorded) when is_map(recorded) do
    transfers =
      for transfer <- list(recorded["transfers"]), is_map(transfer) do
        project(transfer, ~w(from to units this_turn tx_hash block log_index))
      end

    check =
      recorded
      |> project(@base_fields ++ ~w(funder since_block))
      |> Map.put("transfers", transfers)

    check
    |> Map.put("summary", money_summary(check))
    |> stringify_amounts(~w(eth_wei usdc_units))
    |> Map.put("transfers", Enum.map(transfers, &stringify_amounts(&1, ["units"])))
  end

  defp money(_recorded), do: nil

  defp money_summary(%{"address" => address, "eth_wei" => eth, "usdc_units" => usdc} = check)
       when is_binary(address) and is_integer(eth) and is_integer(usdc) do
    if Enum.all?(check["transfers"], &is_integer(&1["units"])),
      do: Copy.money(check)
  end

  defp money_summary(_check), do: nil

  defp evidence(turn, attempt_id) do
    for {name, metadata} <- Enum.sort(turn.evidence || %{}),
        is_binary(name),
        is_map(metadata) do
      image? = Path.extname(name) in [".png", ".jpg", ".jpeg", ".webp"]

      %{
        name: name,
        bytes: scalar(metadata["bytes"]),
        sha256: text(metadata["sha256"]),
        media_type: if(image?, do: nil, else: "text/plain; charset=utf-8"),
        media_type_source: if(image?, do: "checked_on_download", else: "evidence_controller"),
        url:
          @origin <>
            "/wallet-bench/" <>
            attempt_id <>
            "/evidence/" <>
            Catalog.turn_name(turn.test) <> "/" <> URI.encode(name, &URI.char_unreserved?/1)
      }
    end
  end

  defp payment(payment) do
    %{
      token: Atom.to_string(payment.token),
      amount_units: decimal(payment.amount),
      state: Atom.to_string(payment.state),
      from: text(payment.from),
      to: text(payment.to),
      hash: text(payment.hash),
      url: if(is_binary(payment.hash), do: "https://basescan.org/tx/" <> payment.hash)
    }
  end

  # Event details include private operational context. Only the same failure
  # line the public page shows and a known event name cross this boundary.
  defp event(event) do
    if known_step?(event.step) do
      [
        %{
          at: timestamp(event.inserted_at),
          step: event.step,
          label: Copy.step(event.step),
          failure: text((event.detail || %{})["failure"])
        }
      ]
    else
      []
    end
  end

  defp known_step?("safety_cleared"), do: true
  defp known_step?(step) when step in @attempt_states, do: true

  defp known_step?(step) when is_binary(step) do
    case String.split(step, " ") do
      [test, state] ->
        test in Enum.map(Catalog.tests(), &Catalog.turn_name/1) and state in @turn_states

      _other ->
        false
    end
  end

  defp known_step?(_step), do: false

  defp finished_at(state, timeline) when state in [:done, :failed] do
    final = Enum.find(Enum.reverse(timeline), &(&1.step == Atom.to_string(state)))
    final && final.at
  end

  defp finished_at(_state, _timeline), do: nil

  defp costs(model, judge), do: %{currency: "USD", model: decimal(model), judge: decimal(judge)}
  defp project(map, keys), do: Map.new(keys, &{&1, scalar(map[&1])})

  defp stringify_amounts(map, keys) do
    Enum.reduce(keys, map, fn key, result -> Map.update!(result, key, &decimal/1) end)
  end

  defp scalar(value) when is_binary(value) or is_number(value) or is_boolean(value), do: value
  defp scalar(_value), do: nil
  defp text(value) when is_binary(value), do: value
  defp text(_value), do: nil
  defp list(value) when is_list(value), do: value
  defp list(_value), do: []
  defp decimal(%Decimal{} = value), do: Decimal.to_string(value, :normal)
  defp decimal(value) when is_integer(value), do: Integer.to_string(value)
  defp decimal(_value), do: nil
  defp timestamp(%DateTime{} = value), do: DateTime.to_iso8601(value)
  defp timestamp(_value), do: nil
end
