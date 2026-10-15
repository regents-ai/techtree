defmodule Techtree.Accounts.LinkedIdentity.Providers do
  @moduledoc false

  @labels [x: "X", github: "GitHub", farcaster: "Farcaster"]
  @by_name Map.new(@labels, fn {provider, _label} -> {Atom.to_string(provider), provider} end)
  @profile_roots %{
    x: "https://x.com/",
    github: "https://github.com/",
    farcaster: "https://farcaster.xyz/"
  }

  def all, do: for({provider, label} <- @labels, do: %{provider: provider, label: label})

  def label(provider), do: @labels[provider]

  @doc "The provider a browser names by its string form, or `:error` for any other string."
  def parse(name), do: Map.fetch(@by_name, name)

  def profile_url(provider, username) do
    case {@profile_roots[provider], present(username)} do
      {root, name} when is_binary(root) and is_binary(name) -> root <> URI.encode_www_form(name)
      _unlinked -> nil
    end
  end

  def handle(%{provider: :github, username: username}), do: present(username)

  def handle(%{username: username}) do
    case present(username) do
      nil -> nil
      name -> "@" <> name
    end
  end

  defp present(value) when is_binary(value) do
    case String.trim(value) do
      "" -> nil
      value -> value
    end
  end

  defp present(_value), do: nil
end
