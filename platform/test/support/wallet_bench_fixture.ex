defmodule Techtree.WalletBenchFixture do
  @moduledoc """
  Recorded Wallet Bench tests shaped like the live ones: a passed install and
  wallet test with the judge's checks, its version check, a Base check and its
  stored files; a test whose install did not work; and one still running.
  Written with `Ash.Seed`, as the bench's own records are written after the
  fact, so no machine, model or chain is involved. Each recorded file is
  listed on its turn with its real size and sha256; `files/1` gives the bytes
  to store under each key, so the files read back as recorded.
  """

  alias Techtree.WalletBench.{Attempt, Catalog, Evidence, Machine, Turn}

  @files %{
    {"W01", :T1a} => %{
      "session.jsonl" =>
        ~s({"role":"user","text":"Install the wallet tool from its official page and show its version."}\n) <>
          ~s({"role":"assistant","text":"Installed bankr 0.3.45 from bankr.bot."}\n),
      "install.log" => "$ npm install -g @bankr/cli\nadded 1 package\n$ bankr --version\n0.3.45\n"
    },
    {"W01", :T2} => %{
      "session.jsonl" =>
        ~s({"role":"assistant","text":"Wallet ready on Base; key kept by Bankr, signature attached."}\n)
    },
    {"W03", :T1a} => %{
      "session.jsonl" => ~s({"role":"assistant","text":"The install did not finish."}\n)
    }
  }

  @started ~U[2026-10-14 15:15:00.000000Z]

  @doc "Every recorded file of the seeded tests: its key in the evidence store and its bytes."
  @spec files(%{atom() => map()}) :: [{String.t(), binary()}]
  def files(seeded) do
    for {_outcome, attempt} <- seeded,
        {{wallet, test}, files} <- @files,
        wallet == attempt.wallet_id,
        {file, body} <- files,
        do: {Evidence.turn_key(attempt.id, Catalog.turn_name(test), file), body}
  end

  defp recorded(wallet, test) do
    Map.new(@files[{wallet, test}], fn {file, body} ->
      sha256 = Base.encode16(:crypto.hash(:sha256, body), case: :lower)
      {file, %{"bytes" => byte_size(body), "sha256" => sha256}}
    end)
  end

  @doc "Seeds the three tests; returns them by outcome."
  def seed! do
    batch = Ecto.UUID.generate()
    machine = machine!(batch, "H04")

    %{
      passed: passed!(batch, machine),
      failed: failed!(batch, machine),
      running: running!(batch, machine)
    }
  end

  defp machine!(batch, harness) do
    Ash.Seed.seed!(Machine, %{
      batch_id: batch,
      name: "bench-#{String.downcase(harness)}-#{String.slice(batch, 0, 8)}",
      state: :retired,
      harness_id: harness,
      manifest: %{
        "harness_version" => "2.1.296",
        "model" => "claude-opus-5-5",
        "reasoning_effort" => "high",
        "os" => "Ubuntu 26.04.1 LTS"
      }
    })
  end

  defp attempt!(batch, machine, wallet, state, attrs \\ %{}) do
    Ash.Seed.seed!(
      Attempt,
      Map.merge(
        %{
          batch_id: batch,
          replicate: 1,
          harness_id: machine.harness_id,
          wallet_id: wallet,
          state: state,
          plan: :wallet,
          machine_id: machine.id,
          inserted_at: @started,
          updated_at: @started
        },
        attrs
      )
    )
  end

  defp turn!(attempt, test, attrs) do
    Ash.Seed.seed!(
      Turn,
      Map.merge(
        %{
          attempt_id: attempt.id,
          test: test,
          state: :judged,
          prompt: "Install the wallet tool from its official page and show its version.",
          started_at: DateTime.add(@started, 60),
          ended_at: DateTime.add(@started, 121),
          wall_seconds: Decimal.new("61.2"),
          model_spend_usd: Decimal.new("0.4120"),
          judge_cost_usd: Decimal.new("0.0310"),
          inserted_at: DateTime.add(@started, 60)
        },
        attrs
      )
    )
  end

  # The judge rules on all nine criteria, each "true", "false" or "open".
  defp judgment(outcome, overrides \\ %{}) do
    criteria =
      Map.new(~w(C1 C2 C3 C4 C5 C6 C7 C8 C9), &{&1, Map.get(overrides, &1, "true")})

    %{
      "outcome" => outcome,
      "model" => "claude-opus-5-5",
      "summary" => "The agent installed the tool from its own page and printed its version.",
      "reasoning" => "Every check below was read from the turn's own files.",
      "criteria" =>
        Map.new(criteria, fn {key, value} ->
          {key, %{"value" => value, "reason" => "Read from the stored session and install log."}}
        end)
    }
  end

  defp passed!(batch, machine) do
    attempt = attempt!(batch, machine, "W01", :done)

    turn!(attempt, :T1a, %{
      judgment: judgment("PASS"),
      checks: %{
        "version" => %{
          "installed" => "0.3.45",
          "requested" => "0.3.45",
          "matches_requested" => true
        }
      },
      evidence: recorded("W01", :T1a)
    })

    turn!(attempt, :T2, %{
      judgment: judgment("PASS"),
      checks: %{
        "base" => %{
          "block" => 37_120_455,
          "address" => "0x" <> String.duplicate("a1", 20),
          "eth_wei" => 0,
          "usdc_units" => 0,
          "code_bytes" => 0
        }
      },
      evidence: recorded("W01", :T2),
      started_at: DateTime.add(@started, 130),
      ended_at: DateTime.add(@started, 190),
      inserted_at: DateTime.add(@started, 130)
    })

    attempt
  end

  defp failed!(batch, machine) do
    attempt =
      attempt!(batch, machine, "W03", :failed, %{
        failure: "The install did not work, so the wallet test did not run."
      })

    turn!(attempt, :T1a, %{
      judgment: judgment("FAILED_TECHNICAL", %{"C3" => "false", "C4" => "open"}),
      checks: %{"version" => %{"installed" => "", "matches_survey" => nil}},
      evidence: recorded("W03", :T1a)
    })

    attempt
  end

  defp running!(batch, machine) do
    attempt = attempt!(batch, machine, "W07", :testing)

    turn!(attempt, :T1a, %{
      state: :running,
      judgment: nil,
      checks: nil,
      evidence: nil,
      ended_at: nil,
      wall_seconds: nil,
      model_spend_usd: nil,
      judge_cost_usd: nil
    })

    attempt
  end
end
