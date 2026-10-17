defmodule Techtree.Agents.ActivityReadingTest do
  use ExUnit.Case, async: false

  alias RegentAgents.PairedAgent
  alias Techtree.Agents.ActivityReading

  setup do
    token = Application.get_env(:regent_agents, :activity_read_token)
    Application.put_env(:regent_agents, :activity_read_token, nil)

    handler = "activity-unread-#{System.unique_integer()}"
    test = self()

    :telemetry.attach(
      handler,
      [:techtree, :agents, :activity_unread],
      fn _event, measurements, metadata, _config ->
        send(test, {:unread, measurements, metadata})
      end,
      nil
    )

    on_exit(fn ->
      :telemetry.detach(handler)
      Application.put_env(:regent_agents, :activity_read_token, token)
    end)
  end

  test "a read that gives no reading is counted once and kept, so the service is not asked again" do
    agent = %PairedAgent{
      wallet: "0x" <> String.duplicate("d", 40),
      paired_at: DateTime.utc_now()
    }

    assert ActivityReading.read(agent) == {:error, :not_configured}
    assert_receive {:unread, %{count: 1}, %{reason: :not_configured}}

    assert ActivityReading.read(agent) == {:error, :not_configured}
    refute_receive {:unread, _measurements, _metadata}
  end
end
