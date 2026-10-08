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

  With `evidence: :stored` (the `:rejudge` action) a wallet turn is ruled on
  again from what was read and checked when it was first judged: the printed
  address, message and signature and the Base check at that block stay as
  they are, so only the ruling is new.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Attempt.Changes.RecordEvent, only: [put_detail: 2]

  alias Techtree.WalletBench.{Attempt, BaseCheck, Catalog, Evidence, Judge}

  @impl true
  def change(changeset, opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      turn = changeset.data

      with {:ok, attempt} <-
             Ash.get(Attempt, turn.attempt_id, load: [:machine, :turns]),
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
