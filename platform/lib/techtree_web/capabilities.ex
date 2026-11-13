defmodule TechtreeWeb.Capabilities do
  @moduledoc """
  What a paired agent may do on its person's behalf, as the pairing pages list
  it (`TechtreeWeb.Components.AgentsPanel`).
  """

  @doc "The actions a paired agent may take on its person's behalf."
  def may do
    [
      "Read your Points",
      "Publish benchmark results with an independent publication proof",
      "Submit and read your Model Climb proofs"
    ]
  end
end
