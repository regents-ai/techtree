defmodule TechtreeWeb.ContentSecurityPolicy do
  @moduledoc """
  The content security policy the site's pages are served under.

  `reading/0` is the strict baseline: scripts, styles, images and fonts come
  from this site, requests and the live connection go back to it, and no page
  frames another site or is framed itself. No page signs anyone in, so there is
  no sign-in profile.

  Stricter than the template's baseline, because nothing here needs more: no
  style attributes in markup (the headline reveal clips each word with a class),
  and no form submits anywhere. The one origin added is GitHub's API, which the
  masthead reads for the repository's star count.
  """

  # The development code reloader runs in a frame from this site.
  @own_frames if Application.compile_env(:techtree, [TechtreeWeb.Endpoint, :code_reloader]),
                do: ["'self'"],
                else: []

  @baseline [
    {"default-src", ["'none'"]},
    {"script-src", ["'self'"]},
    {"style-src", ["'self'"]},
    {"img-src", ["'self'", "data:"]},
    {"font-src", ["'self'"]},
    {"connect-src", ["'self'", "https://api.github.com"]},
    {"frame-src", @own_frames},
    {"base-uri", ["'none'"]},
    {"form-action", ["'none'"]},
    {"frame-ancestors", ["'none'"]}
  ]

  @doc "The strict baseline every page is served under."
  def reading, do: render(@baseline)

  defp render(directives) do
    directives
    |> Enum.reject(fn {_directive, sources} -> sources == [] end)
    |> Enum.map_join("; ", fn {directive, sources} -> Enum.join([directive | sources], " ") end)
  end
end
