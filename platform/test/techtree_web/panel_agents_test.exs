defmodule TechtreeWeb.PanelAgentsTest do
  # Invariant: the side panel shows at most three of a person's agents, none left
  # out more recently active than one shown, every active one before the rest
  # (never active, or not yet read), and the rest in the order given (newest
  # paired first).
  use ExUnit.Case, async: true
  use ExUnitProperties

  alias TechtreeWeb.PanelAgents

  property "the panel shows the three most recently active agents" do
    check all(
            seconds <-
              list_of(one_of([constant(nil), constant(:none), integer(0..50)]), max_length: 8)
          ) do
      agents = Enum.with_index(seconds, fn _second, index -> %{id: index} end)

      last_actions =
        for {second, id} <- Enum.with_index(seconds), second, into: %{} do
          {id,
           if(second == :none,
             do: :none,
             else: %{site: "Keyfleet", at: DateTime.from_unix!(second)}
           )}
        end

      shown = PanelAgents.shown(agents, last_actions)

      at = fn agent ->
        with %{at: at} <- last_actions[agent.id], do: DateTime.to_unix(at), else: (_never -> nil)
      end

      assert length(shown) == min(3, length(agents))
      assert Enum.uniq(shown) == shown

      for left_out <- agents -- shown,
          at.(left_out) != nil,
          shown_agent <- shown,
          do: assert(at.(shown_agent) != nil and at.(shown_agent) >= at.(left_out))

      {active, never} = Enum.split_while(shown, at)
      assert Enum.all?(never, &(at.(&1) == nil))
      assert Enum.map(active, at) == Enum.sort(Enum.map(active, at), :desc)
      assert never == agents |> Enum.filter(&(at.(&1) == nil)) |> Enum.take(length(never))
    end
  end
end
