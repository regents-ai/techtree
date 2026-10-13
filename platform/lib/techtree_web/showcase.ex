defmodule TechtreeWeb.Showcase do
  @moduledoc """
  The showcase setting and the gate on the page it covers, as the template's
  `ASH_TEMPLATE_SHOWCASE` gates its own.

  The setting (`:showcase`, from `TECHTREE_SHOWCASE` in `config/runtime.exs`) is
  one of:

    * `:public` — the motion lab at `/animations` is a public page, listed in the
      sitemap.
    * `:off` — it does not exist.

  A request the gate refuses answers the site's own 404. A connected mount it
  refuses goes to the home page.
  """
  @behaviour Plug

  @doc "The showcase setting."
  def mode, do: Application.fetch_env!(:techtree, :showcase)

  @doc "True when the showcase pages are public and listed."
  def public?, do: mode() == :public

  @impl Plug
  def init(:motion_lab), do: :motion_lab

  @impl Plug
  def call(conn, :motion_lab) do
    public?() or raise TechtreeWeb.NotFoundError
    conn
  end

  def on_mount(:motion_lab, _params, _session, socket) do
    if public?(),
      do: {:cont, socket},
      else: {:halt, Phoenix.LiveView.redirect(socket, to: "/")}
  end
end
