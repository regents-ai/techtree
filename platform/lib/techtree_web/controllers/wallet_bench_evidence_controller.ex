defmodule TechtreeWeb.WalletBenchEvidenceController do
  @moduledoc """
  One recorded file of a wallet test: an image the agent saved as that image,
  everything else as plain text.

  Only a file the turn recorded is served: the turn and file names are looked
  up in the turn's own list, never used as a path, and the bytes read back
  must match the fingerprint recorded with them. Everything stored was blanked
  before it was stored (`Techtree.WalletBench.Blank`).
  """

  use TechtreeWeb, :controller

  alias Techtree.WalletBench
  alias Techtree.WalletBench.{Catalog, Evidence}

  def show(conn, %{"id" => id, "turn" => turn_name, "file" => file}) do
    with {:ok, id} <- Ecto.UUID.cast(id),
         {:ok, attempt} <- WalletBench.get_attempt(id, load: [:turns]),
         %{evidence: %{^file => %{"sha256" => sha256}}} <-
           Enum.find(attempt.turns, &(Catalog.turn_name(&1.test) == turn_name)) do
      {:ok, body} = Evidence.get(Evidence.turn_key(attempt.id, turn_name, file))
      ^sha256 = :crypto.hash(:sha256, body) |> Base.encode16(case: :lower)

      conn
      |> put_resp_content_type(content_type(file), nil)
      |> send_resp(200, body)
    else
      _missing -> raise TechtreeWeb.NotFoundError, "no recorded file has that name"
    end
  end

  defp content_type(file) do
    case Path.extname(file) do
      ".png" -> "image/png"
      ".jpg" -> "image/jpeg"
      ".jpeg" -> "image/jpeg"
      ".webp" -> "image/webp"
      _text -> "text/plain; charset=utf-8"
    end
  end
end
