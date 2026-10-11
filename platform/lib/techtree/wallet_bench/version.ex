defmodule Techtree.WalletBench.Version do
  @moduledoc "Exact-version admission to a release comparison; historical rulings stay unchanged."

  def enforce(judgment, version, nil, _verification), do: {judgment, version}

  def enforce(judgment, version, spec, verification) do
    version = evidence(spec, verification) |> Map.merge(version)
    matches = normalize(version.installed) == normalize(version.requested) && version.verified
    version = Map.put(version, :matches_requested, matches)
    judgment = refuse_pass(judgment, version)

    judgment =
      if matches do
        judgment
      else
        put_in(judgment, ["criteria", "C3"], %{"value" => "false", "reason" => reason(version)})
      end

    {judgment, version}
  end

  def enforce_wallet(judgment, nil, _verifications), do: {judgment, nil}

  def enforce_wallet(judgment, spec, verifications) do
    observations = Enum.map(verifications, &evidence(spec, &1))
    verified = observations != [] && Enum.all?(observations, & &1.verified)

    version = %{
      requested: spec["wallet_version"],
      installed: if(verified, do: spec["wallet_version"]),
      verified: verified,
      matches_requested: verified
    }

    {refuse_pass(judgment, version), version}
  end

  defp evidence(spec, verification) do
    expected = spec["wallet_version"]

    pattern =
      Regex.compile!(
        "(?<![0-9A-Za-z.+_-])v?" <> Regex.escape(normalize(expected)) <> "(?![0-9A-Za-z.+_-])"
      )

    verified = Enum.any?(successful_outputs(verification), &Regex.match?(pattern, &1))
    %{requested: expected, installed: if(verified, do: expected), verified: verified}
  end

  # The install check ends with one line per version command: its exit status
  # and its output in base64, which printed output cannot imitate. Only the
  # last marker starts that section; earlier copies are part of what was printed.
  defp successful_outputs(verification) do
    case String.split(verification || "", "--- version proof (exit, base64 output)\n") do
      [_ | [_ | _] = sections] ->
        sections
        |> List.last()
        |> String.split("\n", trim: true)
        |> Enum.flat_map(&successful_output/1)

      _ ->
        []
    end
  end

  defp successful_output(line) do
    with ["0", encoded] <- String.split(line, " ", parts: 2),
         {:ok, output} <- Base.decode64(encoded) do
      [output]
    else
      _ -> []
    end
  end

  defp refuse_pass(judgment, %{matches_requested: true}), do: judgment

  defp refuse_pass(judgment, version) do
    if judgment["outcome"] in ["PASS", "PASS*"] do
      judgment
      |> Map.put("outcome", "FAILED_TECHNICAL")
      |> Map.put("summary", reason(version))
      |> Map.put("retry_error", reason(version))
    else
      judgment
    end
  end

  defp reason(version),
    do:
      "Requested wallet #{version.requested}; the captured successful version command did not verify that release (installed #{version.installed || "unknown"})."

  defp normalize(value) when is_binary(value), do: String.trim_leading(value, "v")
  defp normalize(_), do: nil
end
