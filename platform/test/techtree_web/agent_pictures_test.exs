defmodule TechtreeWeb.AgentPicturesTest do
  # Regression: pairings are shared across sites, so an agent paired on one site
  # shows on every site. Claude joined the harness list before the design system
  # had its picture, and Regent.Account.agent_mark raised wherever that person's
  # agents were drawn. Every agent kind the library knows has a picture.
  use ExUnit.Case, async: true

  import Phoenix.LiveViewTest

  test "every agent kind draws its picture" do
    for kind <- RegentAgents.Harness.values() do
      html = render_component(&Regent.Account.agent_mark/1, kind: to_string(kind))

      assert html =~ ~r{<img src="/images/regent-ui/agents/[a-z-]+\.(png|svg)"},
             "no picture for #{kind}"
    end
  end
end
