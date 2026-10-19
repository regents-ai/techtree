defmodule TechtreeWeb.ResultsUnreadableError do
  @moduledoc """
  A wallet test's recorded file no longer matches what its turn recorded, found
  before its download began: the visitor gets the error page, not a broken zip.
  """
  defexception message: "a recorded file no longer matches its record", plug_status: 500
end
