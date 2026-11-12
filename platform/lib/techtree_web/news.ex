defmodule TechtreeWeb.News do
  @moduledoc """
  The newest things to read about Techtree, for the home page: each release
  day that added something, named by the first addition the changelog gives a
  name of its own ("- **Train.** A new Train page …"), and each blog post.
  """

  use TechtreeWeb, :verified_routes

  @changelog Application.app_dir(:techtree, "priv/changelog.md")
  @external_resource @changelog

  # Each day's notes are a "## Website (date)" section; what it added is its
  # "### Added" part, and the first bullet there that starts with a bold name.
  @additions (for section <- String.split(File.read!(@changelog), "\n## "),
                  [_, day] <- [Regex.run(~r/\AWebsite \((\d{4}-\d{2}-\d{2})\)/, section)],
                  [_, added] <- [Regex.run(~r/^### Added\n(.*?)(?:^### |\z)/ms, section)],
                  [_, name] <- [Regex.run(~r/^- \*\*([^*]+?)\.\*\*/m, added)] do
                %{date: Date.from_iso8601!(day), name: name}
              end)

  @type item :: %{
          date: Date.t(),
          kind: String.t(),
          title: String.t(),
          line: String.t() | nil,
          href: String.t()
        }

  @doc "The `count` newest items, newest first."
  @spec latest(pos_integer()) :: [item()]
  def latest(count) do
    additions =
      for %{date: date, name: name} <- @additions do
        %{
          date: date,
          kind: "Changelog",
          title: name,
          line: nil,
          href: ~p"/changelog" <> "#blog-section-website-#{Date.to_iso8601(date)}"
        }
      end

    posts =
      for post <- TechtreeWeb.Blog.all() do
        %{
          date: post.date,
          kind: "Blog",
          title: post.title,
          line: post.description,
          href: ~p"/blog/#{post.slug}"
        }
      end

    (additions ++ posts)
    |> Enum.sort_by(& &1.date, {:desc, Date})
    |> Enum.take(count)
  end
end
