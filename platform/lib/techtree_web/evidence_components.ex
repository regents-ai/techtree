defmodule TechtreeWeb.EvidenceComponents do
  @moduledoc """
  The one evidence graph, shown wherever campaign evidence is shown.

  There is a single drawing of this on the whole site, so that the picture on
  the front page and the picture on a campaign page cannot say different things
  about the same release. Opening a node is the point of it: the summary is a
  claim, and what sits underneath is the document that claim came from.
  """

  use TechtreeWeb, :html

  @doc """
  Draw one campaign's evidence, with every node openable.
  """
  attr :nodes, :list, required: true
  attr :compact, :boolean, default: false
  attr :id, :string, required: true

  def graph(assigns) do
    ~H"""
    <section
      id={@id}
      class={["evidence-graph", @compact && "evidence-graph--compact"]}
      aria-label="Campaign evidence graph"
    >
      <p class="evidence-graph__eyebrow">Evidence graph</p>
      <div class="evidence-graph__canvas">
        <details
          :for={node <- @nodes}
          class={[
            "evidence-node",
            "evidence-node--#{node.position}",
            "evidence-node--#{node.status}"
          ]}
        >
          <summary>
            <span class="evidence-node__joint" aria-hidden="true"></span>
            <span>
              <span class="evidence-node__label">{node.label}</span>
              <span class="evidence-node__status">{status_words(node.status)}</span>
            </span>
            <span class="evidence-node__toggle" aria-hidden="true">+</span>
          </summary>
          <div class="evidence-node__details">
            <p class="evidence-node__artifact">{node.artifact}</p>
            <dl>
              <%= for {term, value} <- node.facts do %>
                <dt>{term}</dt>
                <dd>{value}</dd>
              <% end %>
            </dl>
            <a class="digest evidence-node__digest" href={node.href}>{node.digest}</a>
          </div>
        </details>
      </div>
      <p class="evidence-graph__hint">Open a node to read the document behind it.</p>
    </section>
    """
  end

  defp status_words(:published), do: "published"
  defp status_words(:declared), do: "declared"
  defp status_words(:complete), do: "complete"
  defp status_words(:running), do: "running"
  defp status_words(:failed), do: "failed"
  defp status_words(_status), do: "unavailable"
end
