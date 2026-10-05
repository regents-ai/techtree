defmodule TechtreeWeb.PublishedSkillController do
  @moduledoc """
  A Skill that a published Result made public, by its fingerprint.

  Publishing a Result publishes the Skill it measured, under the Climb's own
  terms, and its proof bundle carries the Skill's files. This address hands
  those files back as data: `skill.json` as the proof carried it, each file it
  lists as base64, and the Results still standing that measured it. The site
  never runs, renders or imports a Skill, and `regents techtree skill fetch`
  checks every file against the fingerprint before it writes anything.

  The answer changes only when a Result is published or withdrawn, so a caller
  may keep it for five minutes.
  """

  use TechtreeWeb, :controller

  alias Techtree.Catalog.Digest
  alias Techtree.Network.Projection
  alias Techtree.Network.Query
  alias TechtreeWeb.ExactResponse

  @doc """
  One published Skill, with the Results that measured it.
  """
  def show(conn, %{"root_digest" => root_digest}) do
    if Digest.valid?(root_digest) do
      serve(conn, root_digest)
    else
      ExactResponse.send_error(
        conn,
        400,
        :invalid_skill_digest,
        "a Skill's fingerprint is sha256: and 64 lowercase hex characters",
        find_a_skill()
      )
    end
  end

  defp serve(conn, root_digest) do
    case Query.skill(root_digest) do
      {:ok, answer} ->
        bytes = Projection.skill(answer)

        ExactResponse.send_exact(
          conn,
          bytes,
          "application/json",
          Digest.hash_bytes(bytes),
          :revalidated
        )

      :error ->
        ExactResponse.send_error(
          conn,
          404,
          :skill_not_found,
          "no published Result still standing carried a Skill with that fingerprint",
          find_a_skill()
        )
    end
  end

  defp find_a_skill,
    do: "A Result's page and #{url(~p"/api/v1/publications")} show each Result's skill_digest."
end
