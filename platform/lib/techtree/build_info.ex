defmodule Techtree.BuildInfo do
  @moduledoc """
  Identifies the source revision used to build the running application.
  """

  @spec source_revision() :: String.t()
  def source_revision do
    Application.get_env(:techtree, :deployed_source_revision, "development")
  end
end
