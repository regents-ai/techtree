defmodule Techtree.Actors.System do
  @moduledoc """
  The actor the site's own machinery acts as: importing the catalog, moving the
  published bootstrap release and looking up accounts. Policies admit it by its role.
  """

  defstruct role: :system
end
