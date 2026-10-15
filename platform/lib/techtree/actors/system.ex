defmodule Techtree.Actors.System do
  @moduledoc """
  The actor release machinery writes as: importing the catalog and moving the
  published bootstrap release. Policies admit it by its role.
  """

  defstruct role: :system
end
