defmodule TechtreeWeb.PageReadTest do
  @moduledoc """
  One client address's allowance of public page reads (`TechtreeWeb.Plugs.PageRead`):
  under it pages answer, past it the next read is refused with a time to wait,
  another address is unaffected, and the health check is never counted. Each
  test reads from its own address under a small allowance, so it spends its own
  budget and not the rest of the suite's.
  """

  use TechtreeWeb.ConnCase, async: false

  @limit 3

  setup do
    limits = Application.fetch_env!(:techtree, :limits)
    on_exit(fn -> Application.put_env(:techtree, :limits, limits) end)

    Application.put_env(
      :techtree,
      :limits,
      Keyword.put(limits, :page_read, limit: @limit, window_seconds: 1_000_000_000)
    )

    :ok
  end

  test "reads under the allowance answer, and the next is refused with Retry-After" do
    from = address()

    for path <- ["/about", "/results", "/llms.txt"] do
      assert read(path, from).status == 200, path
    end

    refused = read("/about", from)
    assert refused.status == 429
    assert [seconds] = get_resp_header(refused, "retry-after")
    assert String.to_integer(seconds) > 0
  end

  test "an address over the allowance leaves another address's reads alone" do
    spent = address()
    for _ <- 1..@limit, do: read("/about", spent)
    assert read("/about", spent).status == 429

    assert read("/about", address()).status == 200
  end

  test "the health check is never counted" do
    from = address()

    for _ <- 1..(@limit * 3) do
      refute read("/healthz", from).status == 429
    end

    assert read("/about", from).status == 200
  end

  test "each refusal is counted once" do
    from = address()
    ref = :telemetry_test.attach_event_handlers(self(), [[:techtree, :page_read, :rate_limited]])
    on_exit(fn -> :telemetry.detach(ref) end)

    for _ <- 1..(@limit + 2), do: read("/about", from)

    for _ <- 1..2 do
      assert_received {[:techtree, :page_read, :rate_limited], ^ref, %{count: 1},
                       %{source: :peer}}
    end

    refute_received {[:techtree, :page_read, :rate_limited], ^ref, _, _}
  end

  defp read(path, from) do
    build_conn()
    |> Map.put(:remote_ip, from)
    |> get(path)
  end

  defp address do
    <<_::8, b, c, d>> = <<System.unique_integer([:positive])::32>>
    {10, b, c, d}
  end
end
