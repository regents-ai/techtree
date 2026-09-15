defmodule Techtree.Safety.Model do
  @moduledoc """
  The one call a monitor makes: a system prompt and a user message in, text
  out. Which module answers it is configuration, so the monitors and the
  runner never know whether a model provider or a scripted stand-in is behind
  them.
  """

  @doc "Whether this site can make model calls at all. Without it no comparison starts."
  @callback available?() :: boolean()

  @doc "One completion. An error is a sentence a reader can be shown."
  @callback complete(system :: String.t(), user :: String.t()) ::
              {:ok, String.t()} | {:error, String.t()}

  @doc "The module configured to answer model calls."
  @spec configured() :: module()
  def configured do
    :techtree
    |> Application.fetch_env!(Techtree.Safety)
    |> Keyword.fetch!(:model)
  end
end
