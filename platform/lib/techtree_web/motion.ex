defmodule TechtreeWeb.Motion do
  @moduledoc """
  The standard motion: the version of each kind of movement the real pages use,
  picked in the motion lab at `/animations` and shared by every Regent site. A
  live part of a page names its version from here in `data-variant`.
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
