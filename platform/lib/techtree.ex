defmodule Techtree do
  @moduledoc """
  Techtree's public catalog, benchmark results and shared Regent account.

  Publication retains its independent proof requirements. Signing in to an
  account does not authorize publication, paid benchmark runs or money tests.
  """
  @doc "The shared Regent site identifier."
  def site, do: Application.fetch_env!(:techtree, :site)
end
