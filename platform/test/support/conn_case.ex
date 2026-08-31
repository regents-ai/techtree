defmodule TechtreeWeb.ConnCase do
  @moduledoc """
  This module defines the test case to be used by
  tests that require setting up a connection.

  Such tests rely on `Phoenix.ConnTest` and also
  import other functionality to make it easier
  to build common data structures and query the data layer.

  Finally, if the test case interacts with the database,
  we enable the SQL sandbox, so changes done to the database
  are reverted at the end of every test. If you are using
  PostgreSQL, you can even run database tests asynchronously
  by setting `use TechtreeWeb.ConnCase, async: true`, although
  this option is not recommended for other databases.
  """

  use ExUnit.CaseTemplate

  using do
    quote do
      # The default endpoint for testing
      @endpoint TechtreeWeb.Endpoint

      use TechtreeWeb, :verified_routes

      # Import conveniences for testing with connections
      import Plug.Conn
      import Phoenix.ConnTest
      import TechtreeWeb.ConnCase
    end
  end

  setup tags do
    Techtree.DataCase.setup_sandbox(tags)
    {:ok, conn: Phoenix.ConnTest.build_conn()}
  end

  @doc """
  The words a reader would see, with the markup and the line wrapping removed.

  Copy is asserted against this rather than against the raw markup: a sentence
  that the template happened to wrap across two lines is the same sentence, and
  a word that only appears inside a class name is not on the page at all.
  """
  def visible_text(html) do
    html
    |> String.replace(~r/<script.*?<\/script>/s, " ")
    |> String.replace(~r/<[^>]*>/, " ")
    |> String.replace(~r/\s+/, " ")
  end
end
