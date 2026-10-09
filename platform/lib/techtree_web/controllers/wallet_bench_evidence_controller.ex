defmodule TechtreeWeb.WalletBenchEvidenceController do
  @moduledoc """
  One recorded file of a wallet test: an image the agent saved as that image,
  when its own bytes say it is one of that kind, and everything else as plain
  text.

  Only a file the turn recorded is served: the turn and file names are looked
  up in the turn's own list, never used as a path, and the bytes read back
  must match the fingerprint recorded with them (`Techtree.WalletBench.Evidence.recorded/2`).
  Everything stored was blanked before it was stored (`Techtree.WalletBench.Blank`).
  """

  use TechtreeWeb, :controller

  alias Techtree.WalletBench
  alias Techtree.WalletBench.{Catalog, Evidence}

  # The type is one of four fixed values, chosen from the stored file's own header and never from the request; an
  # image or plain text runs no script, and the site sends nosniff and its CSP with every answer.
  # sobelow_skip ["XSS.ContentType", "XSS.SendResp"]
  def show(conn, %{"id" => id, "turn" => turn_name, "file" => file}) do
    with {:ok, id} <- Ecto.UUID.cast(id),
         {:ok, attempt} <- WalletBench.get_attempt(id, load: [:turns]),
         %{evidence: %{^file => _recorded}} = turn <-
           Enum.find(attempt.turns, &(Catalog.turn_name(&1.test) == turn_name)) do
      {:ok, body} = Evidence.recorded(turn, file)

      conn
      |> put_resp_content_type(content_type(file, body), nil)
      |> send_resp(200, body)
    else
      _missing -> raise TechtreeWeb.NotFoundError, "no recorded file has that name"
    end
  end

  # The same headers the machine's image_type.py reads.
  defp content_type(file, body) do
    case {Path.extname(file), body} do
      {".png", <<0x89, "PNG\r\n", 0x1A, "\n", _rest::binary>>} -> "image/png"
      {ext, <<0xFF, 0xD8, _rest::binary>>} when ext in [".jpg", ".jpeg"] -> "image/jpeg"
      {".webp", <<"RIFF", _size::binary-size(4), "WEBP", _rest::binary>>} -> "image/webp"
      _text -> "text/plain; charset=utf-8"
    end
  end
end
