defmodule TechtreeWeb.ProjectPackageController do
  @moduledoc """
  A delivered project's package, the exact bytes the team uploaded
  (`Techtree.Projects.Project`), as a file to save.

  It goes to the project's owner, signed in, or to one of the site's admins; a
  signed-out visitor is sent to the project's page, which asks them to sign
  in. A project that is someone else's, was withdrawn or never was is not
  found. A paired agent downloads its person's through
  `TechtreeWeb.AgentAccountController`, sent the same way (`send_package/2`).
  """

  use TechtreeWeb, :controller

  alias Techtree.Actors.Human
  alias Techtree.Projects
  alias TechtreeWeb.TeamGate

  def show(%{assigns: %{current_human_account: nil}} = conn, %{"id" => id}),
    do: redirect(conn, to: ~p"/account/projects/#{id}")

  def show(conn, %{"id" => id}) do
    account = conn.assigns.current_human_account

    read =
      case {Ecto.UUID.cast(id), TeamGate.admin(account)} do
        {:error, _admin} -> {:ok, nil}
        {{:ok, id}, nil} -> Projects.get_my_package(id, actor: Human.for_account(account))
        {{:ok, id}, admin} -> Projects.get_team_package(id, actor: admin)
      end

    case read do
      {:ok, %{} = project} -> send_package(conn, project)
      {:ok, nil} -> raise TechtreeWeb.NotFoundError, "no project of yours has that id"
      {:error, error} -> raise error
    end
  end

  @doc """
  Sends a project's package as a gzip file to save, never shown and never
  kept on the way (`no-store`, nosniff), under a name made of the title's
  plain letters and digits and the project's id (`file_name/1`).
  """
  # sobelow_skip ["XSS.SendResp"]
  @spec send_package(Plug.Conn.t(), Ash.Resource.record()) :: Plug.Conn.t()
  def send_package(conn, project) do
    conn
    |> put_resp_content_type("application/gzip", nil)
    |> put_resp_header("content-disposition", ~s(attachment; filename="#{file_name(project)}"))
    |> put_resp_header("cache-control", "private, no-store")
    |> put_resp_header("x-content-type-options", "nosniff")
    |> send_resp(200, project.package)
  end

  @doc "The name a project's package is saved under, such as `skill-uplift-1a2b3c4d.tar.gz`."
  @spec file_name(%{title: String.t(), id: String.t()}) :: String.t()
  def file_name(%{title: title, id: id}) do
    words =
      title
      |> String.downcase()
      |> String.replace(~r/[^a-z0-9]+/, "-")
      |> String.slice(0, 60)
      |> String.trim("-")

    [words, binary_part(id, 0, 8)]
    |> Enum.reject(&(&1 == ""))
    |> Enum.join("-")
    |> Kernel.<>(".tar.gz")
  end
end
