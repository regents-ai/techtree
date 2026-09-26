defmodule TechtreeWeb.Motion do
  @moduledoc """
  The Regent standard motion, as Patchbay picked it: the version of each kind
  of movement. Presses and headlines move the same way on every page from
  `assets/js/motion.js`; a live part of a page names its version from here.

  Techtree has a place today for the press, the menu, the list and the
  headline. The other parts are kept so a page that grows one uses the same
  version as every other Regent site.
  """

  @standard %{
    "drawer" => "spring",
    "sheet" => "spring",
    "menu" => "pop",
    "note" => "peel",
    "toast" => "pop",
    "list" => "bounce",
    "count" => "roll",
    "stamp" => "thunk",
    "tabs" => "glide",
    "headline" => "rise",
    "grid" => "cascade"
  }

  @doc "Every part's standard version."
  def standard, do: @standard

  @doc "The standard version of one part, such as `\"list\"`."
  def standard(part), do: Map.fetch!(@standard, part)
end
