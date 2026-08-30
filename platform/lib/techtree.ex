defmodule Techtree do
  @moduledoc """
  The read-only public surface of Techtree Climb.

  `Techtree.Catalog` holds the imported public catalog and the release state
  behind it; `TechtreeWeb` publishes it. Nothing in this application executes an
  evaluation, accepts an artifact, or signs anything — the scientific loop lives
  in `techtree-python` and keeps working when this application does not.
  """
end
