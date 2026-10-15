defmodule Techtree do
  @moduledoc """
  Techtree's public catalog, benchmark results and shared Regent account.

  Publication retains its independent proof requirements. Signing in to an
  account does not authorize publication, paid benchmark runs or money tests.
  """

  @site Application.compile_env!(:techtree, :site)

  @doc """
  The name this site goes by in the shared Regent libraries: the site Credits
  holds are placed under, and the app a Points event comes from.
  """
  def site, do: @site
end
