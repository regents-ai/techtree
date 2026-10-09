defmodule Techtree.MixProject do
  use Mix.Project

  # Shared Regent libraries, each pinned to one published commit. To move a pin,
  # change its ref and run `mix deps.update <name>`.
  @elixir_utils "https://github.com/regents-ai/elixir-utils.git"
  @elixir_utils_ref "f8a93857d4ae914e752d7d838a76d4c19c995872"
  @design_system "https://github.com/regents-ai/design-system.git"
  @design_system_ref "4da6db2bfe3559a8f8a761018dc099a28ab5f6a3"
  @regents "https://github.com/regents-ai/regents.git"
  @regents_ref "ba23ceee534c34ff9f773a8c1b38bfca49d7b790"

  def project do
    [
      app: :techtree,
      version: "0.2.0",
      elixir: "~> 1.15",
      elixirc_paths: elixirc_paths(Mix.env()),
      start_permanent: Mix.env() == :prod,
      aliases: aliases(),
      deps: deps(),
      usage_rules: usage_rules(),
      releases: releases(),
      compilers: [:phoenix_live_view] ++ Mix.compilers(),
      listeners: [Phoenix.CodeReloader],
      consolidate_protocols: Mix.env() != :dev
    ]
  end

  # The deployed artifact. `rel/overlays/bin` ships the two entry points a host
  # needs — `server` to run the site, `migrate` to migrate before it starts —
  # so neither has to be spelled as a quoted `eval` inside a host's own
  # configuration file, where the quoting is what breaks.
  defp releases do
    [
      techtree: [
        include_executables_for: [:unix]
      ]
    ]
  end

  # Configuration for the OTP application.
  #
  # Type `mix help compile.app` for more information.
  def application do
    [
      mod: {Techtree.Application, []},
      extra_applications: [:logger, :runtime_tools]
    ]
  end

  def cli do
    [
      preferred_envs: [precommit: :test]
    ]
  end

  # Specifies which paths to compile per environment.
  defp elixirc_paths(:test), do: ["lib", "test/support"]
  defp elixirc_paths(_), do: ["lib"]

  # Specifies your project dependencies.
  #
  # Type `mix help deps` for examples and options.
  defp deps do
    [
      {:regent_ui, git: @design_system, ref: @design_system_ref, sparse: "regent_ui"},
      {:regent_blog, git: @elixir_utils, ref: @elixir_utils_ref, sparse: "blog"},
      # regent_identity names regent_privy by a sibling path; this pin replaces it.
      {:regent_privy,
       git: @elixir_utils, ref: @elixir_utils_ref, sparse: "privy", override: true},
      {:regent_agent_access, git: @elixir_utils, ref: @elixir_utils_ref, sparse: "agent_access"},
      {:regent_sprites, git: @elixir_utils, ref: @elixir_utils_ref, sparse: "sprites"},
      {:regent_openai, git: @elixir_utils, ref: @elixir_utils_ref, sparse: "openai"},
      # The wallet bench signs its funding sends with it.
      {:regent_chain, git: @elixir_utils, ref: @elixir_utils_ref, sparse: "chain"},
      # regent_openai names regent_http by a sibling path; this pin replaces it.
      {:regent_http, git: @elixir_utils, ref: @elixir_utils_ref, sparse: "http", override: true},
      # The ref regent_agents already brings; the bench recovers signatures with it.
      {:siwa, git: @elixir_utils, ref: @elixir_utils_ref, sparse: "siwa/siwa-elixir/apps/siwa"},
      {:regent_identity, git: @regents, ref: @regents_ref, sparse: "identity"},
      {:regent_agents, git: @regents, ref: @regents_ref, sparse: "agents"},
      {:sourceror, "~> 1.8", only: [:dev, :test]},
      {:credo, "~> 1.7", only: [:dev, :test], runtime: false},
      {:ex_slop, "~> 0.4", only: [:dev, :test], runtime: false},
      {:credo_ash,
       git: @elixir_utils,
       ref: @elixir_utils_ref,
       sparse: "credo_ash",
       only: [:dev, :test],
       runtime: false},
      {:sobelow, "~> 0.14", only: [:dev, :test], runtime: false},
      # Test too: precommit runs in the test environment and checks the AGENTS.md block.
      {:usage_rules, "~> 1.2.8", only: [:dev, :test], runtime: false},
      {:ash_phoenix, "~> 2.0"},
      # 2.13.1 and later write upserts without the Repo's schema, into public.
      {:ash_postgres, "== 2.13.0"},
      {:ash, "~> 3.34 and >= 3.34.6"},
      {:ash_oban, "~> 0.9.0"},
      {:oban, "~> 2.24"},
      {:req, "~> 0.7"},
      {:picosat_elixir, "~> 0.2"},
      {:igniter, "~> 0.6", only: [:dev, :test]},
      {:phoenix, "~> 1.8.4"},
      {:phoenix_ecto, "~> 4.5"},
      {:ecto_sql, "~> 3.13"},
      {:postgrex, ">= 0.0.0"},
      {:phoenix_html, "~> 4.1"},
      {:phoenix_live_reload, "~> 1.2", only: :dev},
      {:phoenix_live_view, "~> 1.2.11"},
      {:lazy_html, ">= 0.1.0", only: :test},
      {:esbuild, "~> 0.10", runtime: Mix.env() == :dev},
      {:telemetry_metrics, "~> 1.0"},
      {:telemetry_metrics_prometheus_core, "~> 1.2"},
      {:telemetry_poller, "~> 1.0"},
      {:jason, "~> 1.2"},
      {:decimal, "~> 3.1"},
      {:dns_cluster, "~> 0.3.0"},
      {:bandit, "~> 1.5"}
    ]
  end

  # Aliases are shortcuts or tasks specific to the current project.
  # For example, to install project dependencies and perform other setup tasks, run:
  #
  #     $ mix setup
  #
  # See the documentation for `Mix` for more info on aliases.
  # `mix usage_rules.sync` writes the marked block at the end of AGENTS.md: how to
  # read the installed version's docs, and links to each package's own rules in deps/.
  defp usage_rules do
    [
      file: "AGENTS.md",
      usage_rules: [
        {:usage_rules, sub_rules: []},
        {:usage_rules, sub_rules: :all, main: false, link: :markdown},
        {:ash, link: :markdown},
        {~r/^ash_/, link: :markdown},
        {:phoenix, sub_rules: ["phoenix", "liveview", "html"], link: :markdown}
      ]
    ]
  end

  defp aliases do
    [
      setup: ["deps.get", "ash.setup", "assets.setup", "assets.build"],
      test: ["ash.setup --quiet", "test"],
      "catalog.verify": ["techtree.catalog.verify"],
      "catalog.import": ["techtree.catalog.import"],
      precommit: [
        "compile --warnings-as-errors",
        "deps.unlock --check-unused",
        "cmd mix hex.audit",
        "format --check-formatted",
        "credo --strict",
        "cmd env SOBELOW_HOME=_build/sobelow mix sobelow --exit",
        # Ash resources and their domains compile against each other; this is the floor.
        "xref graph --label compile-connected --fail-above 16",
        "ash.codegen --check",
        "usage_rules.sync --check",
        "cmd --cd assets npm run typecheck",
        "test"
      ],
      "assets.setup": ["cmd --cd assets npm ci --ignore-scripts", "esbuild.install --if-missing"],
      "assets.build": [
        "compile",
        "regent_ui.assets",
        "regent_blog.assets",
        "esbuild techtree"
      ],
      "assets.deploy": [
        "regent_ui.assets",
        "regent_blog.assets",
        "esbuild techtree --minify",
        "phx.digest"
      ]
    ]
  end
end
