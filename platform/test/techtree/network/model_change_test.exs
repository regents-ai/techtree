defmodule Techtree.Network.ModelChangeTest do
  @moduledoc """
  The model change a `model_substitution` Result measured: only the model's
  weights, and the candidate's record of how they were made, may differ
  between its two runs (`docs/spec/model-substitution-v1.md`).

  The fixture Campaign and the two runs' settings are the hello-world proof's,
  with the subject's model written as open weights and the Campaign letting
  only those weights differ. Each test changes the one thing it is about.
  """

  use ExUnit.Case, async: true

  alias Techtree.Network.Result

  @fixtures "test/support/fixtures/proof-v4"
  @weights "/agents/subject/model/weights"

  @original %{
    "weights" => %{
      "repo" => "Qwen/Qwen3-8B",
      "revision" => "b968826d9c46dd6066d109eabc6255188de91218",
      "weights_root" => "sha256:" <> String.duplicate("1", 64)
    },
    "tokenizer_digest" => "sha256:" <> String.duplicate("2", 64),
    "chat_template_digest" => "sha256:" <> String.duplicate("3", 64),
    "serving" => %{
      "engine" => "vllm",
      "version" => "0.11.0",
      "dtype" => "bfloat16",
      "quantization" => nil,
      "max_model_len" => 32_768
    },
    "derivation" => nil
  }

  @changed_root "sha256:" <> String.duplicate("4", 64)

  @derivation %{
    "tool" => "obliteratus",
    "tool_commit" => "43b5d6d1b3327655596a0612cb8a7f9d6565da01",
    "source" => %{
      "repo" => "Qwen/Qwen3-8B",
      "revision" => "b968826d9c46dd6066d109eabc6255188de91218"
    },
    "method" => "advanced",
    "method_config_digest" => "sha256:" <> String.duplicate("5", 64),
    "seed" => 42,
    "weights_root" => "sha256:" <> String.duplicate("4", 64)
  }

  @abliterated %{
    @original
    | "weights" => %{"repo" => nil, "revision" => nil, "weights_root" => @changed_root},
      "derivation" => @derivation
  }

  test "a change of weights alone, with the record of how they were made, is the model change" do
    assert {:ok, change} = check()

    assert change.baseline == %{
             repo: "Qwen/Qwen3-8B",
             revision: "b968826d9c46dd6066d109eabc6255188de91218",
             weights_root: "sha256:" <> String.duplicate("1", 64)
           }

    assert change.candidate == %{repo: nil, revision: nil, weights_root: @changed_root}
    assert change.derivation == @derivation
  end

  test "weights without a derivation record are a model change too" do
    candidate = model(%{@abliterated | "derivation" => nil})

    assert {:ok, %{derivation: nil}} = check(candidate: candidate)
  end

  test "a second difference the report leaves out is caught from the runs' own settings" do
    candidate =
      put_in(
        model(@abliterated),
        ["agents", "subject", "model", "serving", "max_model_len"],
        8192
      )

    # The report lists only the weights, as if nothing else had changed.
    assert {:error, %{code: :submission_model_change_invalid, details: details}} =
             check(candidate: candidate, report: report(model(@abliterated)))

    assert details == %{"pointer" => "/agents/subject/model/serving/max_model_len"}
  end

  test "a second difference the report owns up to is still not a model change" do
    for {path, value} <- [
          {["agents", "subject", "model", "tokenizer_digest"],
           "sha256:" <> String.duplicate("6", 64)},
          {["agents", "subject", "model", "chat_template_digest"],
           "sha256:" <> String.duplicate("7", 64)},
          {["agents", "subject", "model", "serving", "quantization"], "awq"},
          {["agents", "subject", "sampling", "reasoning_effort"], "low"},
          {["budgets", "maximum_model_calls"], 45}
        ] do
      candidate = put_in(model(@abliterated), path, value)
      pointer = "/" <> Enum.join(path, "/")

      honest = report(candidate)

      owned_up =
        update_in(
          honest["manifest_comparison"]["differences"],
          &Enum.sort_by(
            [
              %{
                "pointer" => pointer,
                "baseline" => get_in(model(@original), path),
                "candidate" => value
              }
              | &1
            ],
            fn difference -> difference["pointer"] end
          )
        )

      assert {:error,
              %{code: :submission_model_change_invalid, details: %{"pointer" => ^pointer}}} =
               check(candidate: candidate, report: owned_up)
    end
  end

  test "a Skill added beside the new weights is a second difference" do
    skill = %{
      "digest" => "sha256:" <> String.duplicate("8", 64),
      "media_type" => "application/vnd.techtree.instruction-skill.v1",
      "relative_path" => nil,
      "size" => 10
    }

    candidate = put_in(model(@abliterated), ["agents", "subject", "harness", "skills"], [skill])

    assert {:error, %{details: %{"pointer" => "/agents/subject/harness/skills/0"}}} =
             check(candidate: candidate)
  end

  test "a report whose differences are not the runs' own is refused" do
    honest = report(model(@abliterated))
    differences = honest["manifest_comparison"]["differences"]

    invented = %{
      "pointer" => @weights <> "/repo",
      "baseline" => "Qwen/Qwen3-8B",
      "candidate" => "someone/else"
    }

    for listed <- [
          Enum.reject(differences, &(&1["pointer"] == "/agents/subject/model/derivation")),
          [invented | Enum.reject(differences, &(&1["pointer"] == @weights <> "/repo"))]
        ] do
      report = put_in(honest, ["manifest_comparison", "differences"], listed)

      assert {:error, %{code: :submission_model_change_invalid, details: %{"reported" => _}}} =
               check(report: report)
    end
  end

  test "a report the CLI would not call controlled is refused" do
    report = put_in(report(model(@abliterated)), ["manifest_comparison", "violations"], ["x"])

    assert {:error, %{code: :submission_model_change_invalid}} = check(report: report)
  end

  test "the same weights under another name measure no change" do
    renamed = %{
      @original
      | "weights" => %{@original["weights"] | "repo" => "someone/Qwen3-8B-copy"}
    }

    assert {:error, %{details: %{"pointer" => "/agents/subject/model/weights/weights_root"}}} =
             check(candidate: model(renamed))
  end

  test "a derivation record must name the candidate's weights and the baseline's model" do
    for derivation <- [
          %{@derivation | "weights_root" => "sha256:" <> String.duplicate("9", 64)},
          %{@derivation | "source" => %{@derivation["source"] | "repo" => "Qwen/Qwen3-14B"}},
          %{
            @derivation
            | "source" => %{
                @derivation["source"]
                | "revision" => "0000000000000000000000000000000000000000"
              }
          }
        ] do
      candidate = model(%{@abliterated | "derivation" => derivation})

      assert {:error, %{details: %{"pointer" => "/agents/subject/model/derivation"}}} =
               check(candidate: candidate)
    end
  end

  test "the run without the change is the model its Campaign names, exactly" do
    derived = %{@original | "derivation" => @derivation}

    assert {:error, %{details: %{"pointer" => "/agents/subject/model"}}} =
             check(baseline: model(derived))

    # Even when its Campaign names it that way, the model without the change
    # is the source, never something derived.
    assert {:error, %{details: %{"pointer" => "/agents/subject/model/derivation"}}} =
             check(campaign: campaign(derived), baseline: model(derived))

    unpinned = %{@original | "weights" => %{@original["weights"] | "revision" => nil}}

    assert {:error, %{details: %{"pointer" => "/agents/subject/model"}}} =
             check(
               campaign: campaign(unpinned),
               baseline: model(unpinned),
               report: report(model(@abliterated), model(unpinned))
             )
  end

  test "a model block written any other way is refused" do
    for broken <- [
          Map.put(@abliterated, "access", ["prime_key"]),
          Map.delete(@abliterated, "derivation"),
          put_in(@abliterated, ["serving", "engine"], "sglang"),
          put_in(@abliterated, ["serving", "max_model_len"], 0),
          put_in(
            @abliterated,
            ["weights", "revision"],
            "b968826d9c46dd6066d109eabc6255188de91218"
          ),
          put_in(@abliterated, ["weights", "weights_root"], "sha256:ABC"),
          put_in(@abliterated, ["derivation", "tool_commit"], "main"),
          put_in(@abliterated, ["derivation", "seed"], "42")
        ] do
      assert {:error, %{details: %{"pointer" => "/agents/subject/model"}}} =
               check(candidate: model(broken))
    end
  end

  test "a Campaign that lets a Skill differ is not a model comparison" do
    skill_campaign = fixture("campaign.json")

    assert {:error, %{code: :submission_model_change_invalid, details: details}} =
             check(campaign: skill_campaign)

    assert details["mutation_contract"]["kind"] == "skill_insertion"
  end

  # -- The fixture, rewritten as a model comparison ---------------------------

  defp check(options \\ []) do
    baseline = Keyword.get(options, :baseline, model(@original))
    candidate = Keyword.get(options, :candidate, model(@abliterated))
    report = Keyword.get_lazy(options, :report, fn -> report(candidate, baseline) end)
    campaign = Keyword.get(options, :campaign, campaign(@original))

    Result.model_change(report, campaign, baseline, candidate)
  end

  # The baseline run's settings with the subject's model replaced; the
  # candidate's Skill list is the baseline's, so the model is the one change.
  defp model(block) do
    fixture("baseline-experiment.json")["configuration"]
    |> put_in(["agents", "subject", "model"], block)
    |> put_in(["mutation_contract"], contract())
  end

  defp campaign(block) do
    fixture("campaign.json")
    |> put_in(["agents", "subject", "model"], block)
    |> put_in(["mutation_contract"], contract())
  end

  defp contract do
    %{
      "kind" => "model_substitution",
      "target_agent" => "subject",
      "allowed_differences" => [@weights]
    }
  end

  # The report the CLI writes: its comparison lists every leaf at which the two
  # runs' settings differ, by pointer, in pointer order.
  defp report(candidate, baseline \\ model(@original)) do
    differences =
      Enum.flat_map(
        [
          {"/agents/subject/model/derivation", ["derivation"]},
          {@weights <> "/repo", ["weights", "repo"]},
          {@weights <> "/revision", ["weights", "revision"]},
          {@weights <> "/weights_root", ["weights", "weights_root"]}
        ],
        fn {pointer, path} ->
          before = get_in(baseline, ["agents", "subject", "model" | path])
          now = get_in(candidate, ["agents", "subject", "model" | path])

          if before == now,
            do: [],
            else: [%{"pointer" => pointer, "baseline" => before, "candidate" => now}]
        end
      )

    %{
      "manifest_comparison" => %{
        "allowed_differences" => [@weights],
        "controlled" => true,
        "violations" => [],
        "differences" => differences
      }
    }
  end

  defp fixture(name), do: Path.join(@fixtures, name) |> File.read!() |> Jason.decode!()
end
