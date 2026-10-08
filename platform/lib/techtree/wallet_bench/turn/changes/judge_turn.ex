defmodule Techtree.WalletBench.Turn.Changes.JudgeTurn do
  @moduledoc """
  Rules on a finished turn from its stored, blanked evidence.

  An install turn (T1a, T1b) goes to the judge with the prompt, the wallet's
  notes, the timing, the transcript, the install check and the storage check;
  the bench then compares the version the judge read with the version the
  survey installed. A wallet turn (T2) first has its printed address, message
  and signature read out (`Techtree.WalletBench.Judge.extract/1`), keeping only
  answers found word for word in the transcript, then checked on Base
  (`Techtree.WalletBench.BaseCheck`); the signature request is ruled on
  together with the T2 turn before it, as one T2 result.

  A money turn (T3, T4, T5) goes to the judge with the funding, the bench's
  look at the agent's wallet on Base and every USDC transfer since the funding
  (`Techtree.WalletBench.MoneyCheck`), the transcript and the storage check; T4
  also with the list of images the turn left. The turn that returns what is
  left is not scored and goes to no judge: the bench records what came back.

  With `evidence: :stored` (the `:rejudge` action) a wallet or money turn is
  ruled on again from what was read and checked when it was first judged: the
  printed address, message and signature and the Base checks at their blocks
  stay as they are, so only the ruling is new.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Attempt.Changes.RecordEvent, only: [put_detail: 2]

  alias Techtree.WalletBench.{Attempt, BaseCheck, BaseRpc, Catalog, Evidence, Judge, MoneyCheck}

  @impl true
  def change(changeset, opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      turn = changeset.data

      with {:ok, attempt} <-
             Ash.get(Attempt, turn.attempt_id, load: [:machine, :turns, :payments]),
           {:ok, judgment, checks, cost} <- judge(attempt, turn, opts[:evidence]) do
        changeset
        |> Ash.Changeset.force_change_attributes(%{
          judgment: judgment,
          checks: checks,
          judge_cost_usd: cost
        })
        |> put_detail(%{outcome: judgment["outcome"], summary: judgment["summary"]})
      else
        {:error, error} -> Ash.Changeset.add_error(changeset, error)
      end
    end)
  end

  defp judge(attempt, %{test: test} = turn, _evidence) when test in [:T1a, :T1b] do
    wallet = Catalog.wallet!(attempt.wallet_id)

    with {:ok, files} <-
           files(attempt, turn, ~w(transcript.md verify-install.txt verify-storage.txt)),
         {:ok, judgment, cost} <-
           Judge.rule(
             :install,
             Catalog.review_guide(test),
             install_evidence(attempt, turn, files)
           ) do
      installed = judgment["installed_version"]

      version = %{
        installed: installed,
        survey: wallet.survey_version,
        matches_survey: if(installed == "", do: nil, else: installed == wallet.survey_version)
      }

      {:ok, judgment, %{version: version}, cost}
    end
  end

  defp judge(attempt, %{test: test} = turn, :stored) when test in [:T2, :T2_signature] do
    first = Enum.find(attempt.turns, &(&1.test == :T2))
    turns = if test == :T2, do: [turn], else: [first, turn]
    base = turn.checks["base"]

    with {:ok, parts} <- turn_files(attempt, turns),
         {:ok, judgment, cost} <-
           Judge.rule(:wallet, Catalog.review_guide(test), wallet_evidence(attempt, parts, base)) do
      {:ok, judgment, turn.checks, cost}
    end
  end

  defp judge(attempt, %{test: :T2} = turn, :fresh) do
    with {:ok, files} <- files(attempt, turn, ~w(transcript.md stream.jsonl verify-storage.txt)),
         {:ok, printed, extract_cost} <- printed(files),
         {:ok, base} <- base_check(printed.address, printed),
         evidence = wallet_evidence(attempt, [{turn, files}], base),
         {:ok, judgment, cost} <- Judge.rule(:wallet, Catalog.review_guide(:T2), evidence) do
      {:ok, judgment, %{printed: printed, base: base}, Decimal.add(cost, extract_cost)}
    end
  end

  defp judge(attempt, %{test: :T2_signature} = turn, :fresh) do
    first = Enum.find(attempt.turns, &(&1.test == :T2))
    address = first.checks["printed"]["address"]

    with {:ok, first_files} <- files(attempt, first, ~w(transcript.md verify-storage.txt)),
         {:ok, files} <- files(attempt, turn, ~w(transcript.md stream.jsonl verify-storage.txt)),
         {:ok, printed, extract_cost} <- printed(files),
         {:ok, base} <- base_check(address, printed),
         evidence = wallet_evidence(attempt, [{first, first_files}, {turn, files}], base),
         {:ok, judgment, cost} <-
           Judge.rule(:wallet, Catalog.review_guide(:T2_signature), evidence) do
      {:ok, judgment, %{printed: Map.put(printed, :address, address), base: base},
       Decimal.add(cost, extract_cost)}
    end
  end

  defp judge(attempt, %{test: test} = turn, evidence) when test in [:T3, :T4, :T5] do
    names = ~w(transcript.md verify-storage.txt) ++ if(test == :T4, do: ["images.txt"], else: [])

    with {:ok, files} <- files(attempt, turn, names),
         {:ok, money} <- money_check(attempt, turn, evidence),
         {:ok, judgment, cost} <-
           Judge.rule(
             test,
             Catalog.review_guide(test),
             money_evidence(attempt, turn, files, money)
           ) do
      {:ok, judgment, %{money: money}, cost}
    end
  end

  defp judge(attempt, %{test: :return} = turn, evidence) do
    with {:ok, money} <- money_check(attempt, turn, evidence) do
      {:ok, returned(money), %{money: money}, Decimal.new(0)}
    end
  end

  defp money_check(_attempt, turn, :stored), do: {:ok, turn.checks["money"]}

  defp money_check(attempt, turn, :fresh) do
    since =
      attempt.turns
      |> Enum.filter(&(&1.test in [:T3, :T4, :T5] and &1.id != turn.id and &1.checks))
      |> Enum.map(& &1.checks["money"]["block"])
      |> Enum.max(fn -> MoneyCheck.funding_block(attempt) end)

    MoneyCheck.check(attempt, since)
  end

  defp returned(money) do
    units = MoneyCheck.returned_units(money)

    %{
      "outcome" => "UNSCORED",
      "model" => "none: the bench's Base check",
      "summary" =>
        "#{BaseRpc.decimal(units, 6)} USDC came back to the bench's wallet in this turn; " <>
          "the agent's wallet now holds #{BaseRpc.decimal(money["usdc_units"], 6)} USDC and " <>
          "#{BaseRpc.decimal(money["eth_wei"], 18)} ETH.",
      "returned_usdc_units" => units
    }
  end

  defp money_evidence(attempt, turn, files, money) do
    images =
      if turn.test == :T4,
        do:
          "\n# Images the turn left (stored file, sha256, bytes, where the agent saved it | file type)\n\n#{files["images.txt"]}",
        else: ""

    """
    #{pair(attempt)}

    # Wallet notes

    #{Catalog.wallet_notes(attempt.wallet_id)}

    # #{Catalog.turn_name(turn.test)}: the prompt sent

    #{turn.prompt}

    ## Turn timing

    #{timing(turn)}

    ## Transcript

    #{files["transcript.md"]}

    ## Storage check

    #{files["verify-storage.txt"]}
    #{images}
    # The bench's Base check

    #{MoneyCheck.describe(money)}
    """
  end

  defp turn_files(attempt, turns) do
    Enum.reduce_while(turns, {:ok, []}, fn turn, {:ok, parts} ->
      case files(attempt, turn, ~w(transcript.md verify-storage.txt)) do
        {:ok, files} -> {:cont, {:ok, parts ++ [{turn, files}]}}
        {:error, error} -> {:halt, {:error, error}}
      end
    end)
  end

  defp files(attempt, turn, names) do
    Enum.reduce_while(names, {:ok, %{}}, fn name, {:ok, files} ->
      case Evidence.get(Evidence.turn_key(attempt.id, Catalog.turn_name(turn.test), name)) do
        {:ok, content} -> {:cont, {:ok, Map.put(files, name, content)}}
        {:error, error} -> {:halt, {:error, error}}
      end
    end)
  end

  # What the harness printed, keeping only answers found word for word in the
  # transcript or, inside its JSON strings, in the raw stream.
  defp printed(files) do
    with {:ok, answer, cost} <- Judge.extract(files["transcript.md"]) do
      keep = &keep(files, answer, &1)
      message = keep.("message")

      {:ok,
       %{
         address: keep.("address"),
         message: message,
         encoding: if(message == "", do: "none", else: answer["encoding"]),
         signature: keep.("signature"),
         dropped:
           for(key <- ~w(address message signature), answer[key] != "", keep.(key) == "", do: key)
       }, cost}
    end
  end

  defp keep(files, answer, key) do
    if found?(files, answer[key]), do: answer[key], else: ""
  end

  defp found?(_files, ""), do: false

  defp found?(files, value) do
    escaped = value |> Jason.encode!() |> String.slice(1..-2//1)

    String.contains?(files["transcript.md"], value) or
      String.contains?(files["stream.jsonl"], escaped)
  end

  defp base_check("", _printed), do: {:ok, nil}

  defp base_check(address, %{message: message, signature: signature} = printed)
       when message != "" and signature != "" do
    BaseCheck.check(address, Map.take(printed, [:message, :encoding, :signature]))
  end

  defp base_check(address, _printed), do: BaseCheck.check(address, nil)

  defp install_evidence(attempt, turn, files) do
    """
    #{pair(attempt)}

    # The test

    #{install_test(attempt, turn)}

    # The prompt sent

    #{turn.prompt}

    # Wallet notes

    #{Catalog.wallet_notes(attempt.wallet_id)}

    # Turn timing

    #{timing(turn)}

    # Transcript

    #{files["transcript.md"]}

    # Install check (run as bench after the turn)

    #{files["verify-install.txt"]}

    # Storage check

    #{files["verify-storage.txt"]}
    """
  end

  defp install_test(_attempt, %{test: :T1a}), do: "T1a, the first turn."

  defp install_test(attempt, %{test: :T1b}) do
    first = Enum.find(attempt.turns, &(&1.test == :T1a))

    "T1b, the retry after T1a, which was ruled #{first.judgment["outcome"]}: " <>
      "#{first.judgment["summary"]} The error sent back is in the prompt below."
  end

  defp wallet_evidence(attempt, turns, base) do
    turn_parts =
      Enum.map_join(turns, "\n", fn {turn, files} ->
        """
        # #{Catalog.turn_name(turn.test)}: the prompt sent

        #{turn.prompt}

        ## Turn timing

        #{timing(turn)}

        ## Transcript

        #{files["transcript.md"]}

        ## Storage check

        #{files["verify-storage.txt"]}
        """
      end)

    """
    #{pair(attempt)}

    # Wallet notes

    #{Catalog.wallet_notes(attempt.wallet_id)}

    #{turn_parts}
    # The bench's Base check

    #{if base, do: BaseCheck.describe(base), else: "The harness gave no Base address, so nothing was checked."}
    """
  end

  defp pair(attempt) do
    harness = Catalog.harness!(attempt.harness_id)
    wallet = Catalog.wallet!(attempt.wallet_id)
    manifest = attempt.machine.manifest

    """
    # The pair

    Harness: #{harness.name} (#{harness.id}), #{manifest["harness_version"]}, in the account `bench`; every model
    call is #{manifest["model"]} at #{manifest["reasoning_effort"]} effort through the bench's translator
    (#{manifest["translator"]}). Machine: #{manifest["os"]}.
    Wallet: #{wallet.name} (#{wallet.id}); executable `#{wallet.executable}`; help `#{Enum.join([wallet.executable | wallet.help], " ")}`.
    """
  end

  defp timing(turn) do
    "Exit code #{turn.exit_code}; wall time #{turn.wall_seconds} seconds of the " <>
      "#{Catalog.wall_cap(turn.test)}-second watchdog; started #{turn.started_at}, ended #{turn.ended_at}."
  end
end
