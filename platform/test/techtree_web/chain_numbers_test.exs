defmodule TechtreeWeb.ChainNumbersTest do
  # Sentinel reads the age of the oldest unconfirmed send from the site's own
  # wallet off the metrics listener (fly-sentinel docs/metrics-contract.md). The
  # test configuration names no query, so the poller never reads the database
  # outside a test's sandbox; these tests call the query themselves.
  use ExUnit.Case, async: false

  import ExUnit.CaptureLog

  alias TechtreeWeb.Telemetry

  test "a site's query of its own sends sets each flow's oldest age, 0 when none waits" do
    signed_at = DateTime.add(DateTime.utc_now(), -90, :second)

    assert :ok = Telemetry.oldest_unconfirmed_sends({__MODULE__, :sends, [signed_at]})

    assert value("health_wallet_unconfirmed_oldest_seconds", [~s(flow="test_waiting")]) >= 90
    assert value("health_wallet_unconfirmed_oldest_seconds", [~s(flow="test_none")]) == 0
  end

  test "a query that fails is logged and the tick skipped" do
    log =
      capture_log(fn ->
        assert :ok = Telemetry.oldest_unconfirmed_sends({__MODULE__, :unanswered, []})
      end)

    assert log =~ "unconfirmed send age not measured: no answer"
  end

  test "the poller reads the query the site names, and nothing when none is named" do
    query = {Techtree.WalletBench.Funding, :unconfirmed_sends, []}
    config = Application.get_env(:techtree, Telemetry)
    on_exit(fn -> Application.put_env(:techtree, Telemetry, config) end)

    refute Enum.any?(measurements(), &match?({Telemetry, :oldest_unconfirmed_sends, _}, &1))

    Application.put_env(:techtree, Telemetry, unconfirmed_sends: query)
    assert {Telemetry, :oldest_unconfirmed_sends, [query]} in measurements()
  end

  def sends(signed_at), do: [{"test_waiting", signed_at}, {"test_none", nil}]

  def unanswered, do: raise("no answer")

  defp measurements do
    {:telemetry_poller, opts} = Telemetry.site_poller()
    opts[:measurements]
  end

  defp value(name, labels) do
    Telemetry.scrape()
    |> String.split("\n")
    |> Enum.find_value(fn line ->
      with [series, number] <- String.split(line, " "),
           true <- String.starts_with?(series, name <> "{"),
           true <- Enum.all?(labels, &String.contains?(series, &1)) do
        {number, ""} = Float.parse(number)
        number
      else
        _ -> nil
      end
    end)
  end
end
