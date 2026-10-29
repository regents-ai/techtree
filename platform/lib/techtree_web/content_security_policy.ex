defmodule TechtreeWeb.ContentSecurityPolicy do
  @moduledoc """
  The content security policy the site's pages are served under.

  `reading/0` is the strict baseline every response starts with: scripts,
  styles, images and fonts come from this site, requests and the live connection
  go back to it, and nothing frames another site or is framed itself. Pages use
  `sign_in/0`, which admits Privy and the template account components, because
  every page's account control can sign in.

  Stricter than the template's baseline, because nothing here needs more: no
  style attributes in markup (the headline reveal clips each word with a class),
  and no form submits anywhere.
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
    {"connect-src", ["'self'"]},
    {"frame-src", @own_frames},
    {"base-uri", ["'none'"]},
    {"form-action", ["'none'"]},
    {"frame-ancestors", ["'none'"]}
  ]

  @sign_in %{
    "script-src" => ["https://challenges.cloudflare.com"],
    "style-src" => ["'unsafe-inline'"],
    "img-src" => ["blob:", "https://explorer-api.walletconnect.com"],
    "frame-src" => [
      "https://auth.privy.io",
      "https://verify.walletconnect.com",
      "https://verify.walletconnect.org",
      "https://challenges.cloudflare.com"
    ],
    "connect-src" => [
      "https://auth.privy.io",
      "https://*.rpc.privy.systems",
      "wss://relay.walletconnect.com",
      "wss://relay.walletconnect.org",
      "https://verify.walletconnect.org",
      "https://explorer-api.walletconnect.com",
      "https://rpc.walletconnect.org",
      "https://pulse.walletconnect.org",
      "wss://www.walletlink.org"
    ]
  }

  @doc "The strict baseline every page is served under."
  def reading, do: render(@baseline)

  @doc "The template policy for pages, each of which can start sign-in."
  def sign_in do
    @baseline
    |> List.keyreplace("form-action", 0, {"form-action", ["'self'"]})
    |> List.keyreplace(
      "img-src",
      0,
      {"img-src", ["'self'", "data:", "https://metadata.ens.domains"]}
    )
    |> Kernel.++([{"style-src-attr", ["'unsafe-inline'"]}])
    |> Enum.map(fn {directive, sources} ->
      {directive, Enum.uniq(sources ++ Map.get(@sign_in, directive, []))}
    end)
    |> render()
  end

  defp render(directives) do
    directives
    |> Enum.reject(fn {_directive, sources} -> sources == [] end)
    |> Enum.map_join("; ", fn {directive, sources} -> Enum.join([directive | sources], " ") end)
  end
end
