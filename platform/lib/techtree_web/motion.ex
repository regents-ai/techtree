defmodule TechtreeWeb.Motion do
  @moduledoc """
  The Regent standard motion, as Patchbay picked it: the version of each kind
  of movement. Presses and headlines move the same way on every page from
  `assets/js/motion.js`; a live part of a page names its version from here.

  Techtree has a live place today for the menu and the list. A page that grows
  another part adds that part's standard version here.
  """

  @standard %{
    "menu" => "pop",
    "list" => "bounce"
  }

  @doc "The standard version of one part, such as `\"list\"`."
  def standard(part), do: Map.fetch!(@standard, part)
end
