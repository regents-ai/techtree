defmodule TechtreeWeb.CoreComponents do
  @moduledoc """
  The small set of pieces every page is built from.

  Each one is presentation only: it decides how something reads, never what is
  true. Values arrive already resolved from the imported catalog, and every one
  of them is escaped as text — nothing on this site renders markup that came
  from a document.

  Commands are the one place that needs care. An installation or run
  instruction is always held as a list of arguments, because that is the only
  form a machine should ever be handed. Turning it into a single line is a
  courtesy for a human reader, done here, at the last moment, and never used as
  the thing that runs.
  """

  use Phoenix.Component

  @doc """
  Name a protocol document, in the spelling the protocol uses.
  """
  attr :name, :string, required: true
  attr :rest, :global

  def protocol_badge(assigns) do
    ~H"""
    <span class="badge badge--exact" {@rest}>{@name}</span>
    """
  end

  @doc """
  Say where a Climb is in its life, in words rather than a code.
  """
  attr :status, :string, required: true

  def status_badge(assigns) do
    ~H"""
    <span class={["badge", @status == "development" && "badge--attention"]}>
      {status_words(@status)}
    </span>
    """
  end

  @doc """
  Show the fingerprint a document is filed under, optionally linking to it.

  The value wraps rather than overflowing: on a phone a fingerprint is four
  lines of characters, and a reader comparing one against another needs to see
  all of it.
  """
  attr :value, :string, required: true
  attr :href, :string, default: nil

  def digest(assigns) do
    ~H"""
    <span class="digest">
      <%= if @href do %>
        <a href={@href}>{@value}</a>
      <% else %>
        {@value}
      <% end %>
    </span>
    """
  end

  @doc """
  The word "verifiers", with what it is one hover away.

  Founder ruling 2026-08-26: wherever the library is named, a reader can hover
  (or focus, on a keyboard or a phone) to learn that verifiers is Prime
  Intellect's library for building evaluation environments, with one link to
  its repository. The card is plain markup — no script, nothing submitted.
  """
  attr :label, :string, default: "verifiers"
  attr :code, :boolean, default: false

  def verifiers_term(assigns) do
    ~H"""
    <span class="hoverdef">
      <%= if @code do %>
        <code class="hoverdef__term" tabindex="0">{@label}</code>
      <% else %>
        <span class="hoverdef__term" tabindex="0">{@label}</span>
      <% end %>
      <span class="hoverdef__card" role="note">
        <span>
          verifiers is a library by Prime Intellect for creating environments to
          train and evaluate LLMs.
        </span>
        <a
          class="hoverdef__button"
          href="https://github.com/PrimeIntellect-ai/verifiers"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub
        </a>
      </span>
    </span>
    """
  end

  @doc """
  What this release is, written once and shown wherever a page says so.

  Decision 0035: v0.1 is a proof of concept for a stack of three independent
  parts, and two of the three are other people's work. A page that says what
  this release is has to name all three with the projects that made them, and
  has to say where the seams are — the engine, the host and the container are
  pinned, and the release is only as reproducible as those pins. Written in one
  place so that two pages cannot drift into two different claims.
  """
  attr :class, :string, default: "section"
  attr :eyebrow, :string, default: nil

  def proof_of_concept(assigns) do
    ~H"""
    <section class={@class} aria-labelledby="what-this-release-is">
      <div class="section-heading">
        <p :if={@eyebrow} class="eyebrow">{@eyebrow}</p>
        <h2 id="what-this-release-is">What v0.1 is</h2>
      </div>
      <div class="what-this-is">
        <p>
          Techtree Climb v0.1 is a proof of concept for a stack of three independent parts:
          Prime Intellect’s Verifiers as the evaluation engine, Nous Research’s Hermes as the
          agent host, and Techtree as the campaign kernel and evidence layer. What it
          demonstrates is that the three pin together tightly enough for a controlled
          comparison to run end to end and leave a receipt that verifies offline. It is a
          development release, and nothing it produces is a measurement anyone should cite.
        </p>
        <p class="small quiet">
          The evaluation engine, the agent host, and the container the agent under test runs
          in are each pinned to an exact version, and the release is only as reproducible as
          those pins. Those are the seams of the stack, and this site names them rather than
          leaving a reader to find them.
        </p>
      </div>
    </section>
    """
  end

  @doc """
  Show one command, built from the arguments that make it up.

  The copy control hands over exactly the characters shown, and nothing on this
  site ever runs them: what a reader copies is what the release published, and
  where it is run is their business.
  """
  attr :argv, :list, required: true
  attr :label, :string, default: nil
  attr :copy, :boolean, default: true
  attr :id, :string, default: nil

  def command_block(assigns) do
    command = display_command(assigns.argv)

    assigns =
      assigns
      |> assign(:command, command)
      |> assign(:copy_id, assigns.id || command_id(command, assigns.label))

    ~H"""
    <div class="command">
      <div class="command__head">
        <p class="command__label">{@label || "Command"}</p>
        <button
          :if={@copy}
          id={@copy_id}
          class="command__copy"
          type="button"
          phx-hook="CopyCommand"
          phx-update="ignore"
          data-copy-value={@command}
        >
          <span data-copy-label>Copy</span>
        </button>
      </div>
      <pre class="command__block"><code>{@command}</code></pre>
    </div>
    """
  end

  @doc """
  Show one line of instruction meant for an agent rather than a shell.

  It carries the same copy control a command does, because a reader hands it
  over the same way. It is drawn differently on purpose: no prompt character in
  front of it, prose rather than mono, and it wraps instead of running off the
  side, because it is a sentence and a reader has to be able to read all of it.
  """
  attr :text, :string, required: true
  attr :label, :string, required: true
  attr :id, :string, required: true

  def prompt_block(assigns) do
    ~H"""
    <div class="command command--prose">
      <div class="command__head">
        <p class="command__label">{@label}</p>
        <button
          id={@id}
          class="command__copy"
          type="button"
          phx-hook="CopyCommand"
          phx-update="ignore"
          data-copy-value={@text}
        >
          <span data-copy-label>Copy</span>
        </button>
      </div>
      <p class="command__block">{@text}</p>
    </div>
    """
  end

  @doc """
  A list of short facts, one per row.
  """
  slot :fact do
    attr :term, :string, required: true
  end

  def definition_list(assigns) do
    ~H"""
    <dl class="facts">
      <%= for fact <- @fact do %>
        <dt class="facts__term">{fact.term}</dt>
        <dd class="facts__value">{render_slot(fact)}</dd>
      <% end %>
    </dl>
    """
  end

  @doc """
  Set two things side by side that are easy to confuse.
  """
  slot :side do
    attr :title, :string, required: true
  end

  def comparison_boundary(assigns) do
    ~H"""
    <div class="boundary">
      <section :for={side <- @side} class="boundary__side">
        <h3 class="boundary__title">{side.title}</h3>
        {render_slot(side)}
      </section>
    </div>
    """
  end

  @doc """
  Say something the reader would be worse off for missing.
  """
  attr :title, :string, required: true
  attr :attention, :boolean, default: false
  slot :inner_block, required: true

  def warning_callout(assigns) do
    ~H"""
    <aside class={["callout", @attention && "callout--attention"]}>
      <p class="callout__title">{@title}</p>
      {render_slot(@inner_block)}
    </aside>
    """
  end

  @doc """
  One step of something the reader is being asked to do.
  """
  attr :title, :string, required: true
  slot :inner_block

  def next_step(assigns) do
    ~H"""
    <li>
      <p class="plain"><strong>{@title}</strong></p>
      {render_slot(@inner_block)}
    </li>
    """
  end

  @doc """
  What a Climb is measuring, said as a question a reader can answer.
  """
  @spec purpose_words(String.t()) :: String.t()
  def purpose_words("component_uplift"), do: "Does one added component make the agent better?"
  def purpose_words("harness_comparison"), do: "Does one harness do better than another?"
  def purpose_words(other), do: plain_words(other)

  @doc """
  What is allowed to differ between the two runs.
  """
  @spec mutation_words(String.t()) :: String.t()
  def mutation_words("skill_insertion"), do: "One skill is added. Nothing else may differ."

  def mutation_words("skill_replacement"),
    do: "One skill is replaced by another. Nothing else may differ."

  def mutation_words(other), do: plain_words(other)

  @doc """
  What a result from this Climb may be presented as.
  """
  @spec proof_grade_words(String.t()) :: String.t()
  def proof_grade_words("development_only"),
    do: "Development only. Results exercise the machinery and are not evidence of anything."

  def proof_grade_words("P1"),
    do: "Signed on the machine that produced it, and checkable there. Not independently repeated."

  def proof_grade_words(other), do: plain_words(other)

  # A Climb's terms describe a published result, and this build publishes
  # nothing. Read alone, "is published as part of entering" tells someone
  # their Skill will be taken; two agents refused to start a run over
  # exactly that. Decision 0013 also forbids an unqualified "it stays here",
  # because model calls do leave — so the sentence says both halves in the
  # same breath. Written once, shown wherever the terms are.
  @publication_note "Nothing you produce is published. " <>
                      "Your Skill, the recordings of each attempt and the result summary " <>
                      "stay on your machine, and there is nowhere on this site to send them. " <>
                      "The agent still makes calls to the model provider you selected, under " <>
                      "that provider's policies."

  @doc """
  The rights a participant would be agreeing to, one sentence each.
  """
  @spec data_policy_lines(map()) :: [{String.t(), String.t()}]
  def data_policy_lines(data_policy) do
    [
      {"Your recordings", recordings_words(data_policy["raw_episode_server_upload"])},
      {"Training", training_words(data_policy["raw_episode_training_use"])},
      {"The work you submit", submission_words(data_policy["candidate_skill_public_release"])},
      {"The result summary", report_words(data_policy["uplift_report_visibility"])},
      {"In this release", publication_note()}
    ]
  end

  # -- Internals ------------------------------------------------------------

  @doc """
  What this release does with everything a Climb's terms govern.
  """
  @spec publication_note() :: String.t()
  def publication_note, do: @publication_note

  defp recordings_words("prohibited"), do: "Stay on your machine. They are never uploaded."
  defp recordings_words("consent_required"), do: "Are uploaded only if you agree, each time."
  defp recordings_words("allowed"), do: "May be uploaded."
  defp recordings_words(other), do: plain_words(other)

  defp training_words("prohibited"), do: "Your recordings are never used to train a model."
  defp training_words("consent_required"), do: "Used for training only if you agree."
  defp training_words("allowed"), do: "May be used for training."
  defp training_words(other), do: plain_words(other)

  defp submission_words("required_for_climb"),
    do:
      "Would be published as part of entering. " <>
        "Under these terms nothing you submit is treated as private."

  defp submission_words("consent_required"), do: "Is published only if you agree."
  defp submission_words("prohibited"), do: "Is never published."
  defp submission_words("allowed"), do: "May be published under these terms."
  defp submission_words(other), do: plain_words(other)

  defp report_words("public"), do: "May be published under these terms. It carries no recordings."
  defp report_words("private"), do: "Stays private."
  defp report_words("prohibited"), do: "Is not published."
  defp report_words(other), do: plain_words(other)

  defp plain_words(value) when is_binary(value) do
    value |> String.replace("_", " ") |> String.capitalize()
  end

  defp plain_words(value), do: to_string(value)

  defp status_words("open"), do: "Open"
  defp status_words("closed"), do: "Closed"
  defp status_words("development"), do: "In development"
  defp status_words(other), do: plain_words(other)

  # Display only. An argument that would need quoting in a shell is shown
  # quoted, so that what a reader copies is what the argument list means.
  defp display_command(argv), do: Enum.map_join(argv, " ", &quote_argument/1)

  # A stable name for the copy control, derived from what it copies, so that a
  # page holding several commands does not have to name each one by hand.
  defp command_id(command, label) do
    digest = :crypto.hash(:sha256, [label || "", command]) |> Base.encode16(case: :lower)
    "copy-command-" <> String.slice(digest, 0, 12)
  end

  defp quote_argument(argument) do
    if String.match?(argument, ~r|\A[A-Za-z0-9_@%+=:,./-]+\z|) do
      argument
    else
      "'" <> String.replace(argument, "'", "'\\''") <> "'"
    end
  end
end
