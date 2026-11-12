defmodule TechtreeWeb.Components.AgentMessage do
  @moduledoc """
  The Agent Message button and its window: three texts a visitor pastes into
  their agent so it leaves a private message for Techtree's team under a
  `topic` the site names, through the regents CLI, the hosted MCP server or the
  site's WebMCP tool. Each names this site's address, and the command and the
  tool are read when this module compiles from `priv/tool_manifest.json`, the
  file the browser registers its tools from, so the texts cannot name a tool
  that is not there. `texts/1` gives them to any page or document that tells an
  agent how.

  Below the texts, a signed-in person leaves a message themselves
  (`TechtreeWeb.Components.AgentMessage.Form`); a signed-out visitor sees only
  the texts. The page is a live page that reads the sign-in
  (`TechtreeWeb.Live.Session`, `:load_visitor`), and passes its signed-in
  account, its `session_lease` as `lease` and its `client_key`.
  """

  use Phoenix.Component

  alias Techtree.Capabilities
  alias TechtreeWeb.PublicDocuments

  %{"cli" => %{"namespace" => namespace}, "tools" => tools} = Capabilities.manifest()

  %{"name" => tool, "interfaces" => %{"cli" => %{"command" => command}}} =
    Enum.find(tools, &(&1["operation_id"] == "leaveMessage"))

  # `messages leave <topic>`, with the topic left for `texts/1` to fill in.
  @command "regents #{namespace} " <> String.replace(command, "<topic>", "")
  @mcp "regents mcp --site #{namespace}"
  @tool tool

  @doc """
  The three paste-ready texts for leaving a message under `topic`, each with its
  one-word title: the CLI line, the hosted MCP tool call and the WebMCP tool
  call, with this site's address and names filled in.
  """
  @spec texts(String.t()) :: [%{id: String.t(), title: String.t(), text: String.t()}]
  def texts(topic) do
    site = PublicDocuments.url("")

    message = [
      body: "<your message>",
      reply_to: "<where to answer you>",
      operation_id: "<a new UUID>"
    ]

    input = Jason.encode!(Jason.OrderedObject.new([topic: topic] ++ message), pretty: true)

    [
      %{
        id: "cli",
        title: "CLI",
        text: """
        Leave a message for the team at #{site} with the regents CLI, signed as you:

        echo '#{Jason.encode!(Jason.OrderedObject.new(message))}' | #{@command}#{topic}

        Keep the same operation_id if you retry. Only the team reads it. If your regents CLI does not have this command yet, use MCP.\
        """
      },
      %{
        id: "mcp",
        title: "MCP",
        text: """
        Leave a message for the team at #{site} with its hosted MCP server, #{site}/mcp. Call its #{@tool} tool with this input, signed by your agent (#{@mcp} signs each call for you):

        #{input}

        Keep the same operation_id if you retry. Only the team reads it.\
        """
      },
      %{
        id: "webmcp",
        title: "WebMCP",
        text: """
        Open #{site} in your browser and call the WebMCP tool #{@tool}, signed with your agent key, with this input:

        #{input}

        Keep the same operation_id if you retry. Only the team reads it.\
        """
      }
    ]
  end

  @doc "The Markdown that tells an agent how to leave a message under `topic`: the three texts."
  @spec markdown(String.t()) :: String.t()
  def markdown(topic) do
    Enum.map_join(texts(topic), "\n\n", fn %{title: title, text: text} ->
      "### #{title}\n\n```text\n#{text}\n```"
    end)
  end

  attr :id, :string, required: true
  attr :dialog, :string, required: true, doc: "The id of the `dialog/1` it opens."
  attr :class, :any, default: nil

  @doc "The Agent Message button, which opens its window."
  def button(assigns) do
    ~H"""
    <Regent.Primitives.button
      id={@id}
      type="button"
      variant="secondary"
      arrow={false}
      class={["agent-message-button", @class]}
      aria-haspopup="dialog"
      aria-controls={@dialog}
      data-agent-message-open
    >
      <Regent.Icons.icon name="bot-message-square" /> Agent Message
    </Regent.Primitives.button>
    """
  end

  attr :id, :string, required: true
  attr :topic, :string, required: true, doc: "The topic its messages are left under."
  attr :account, :map, default: nil, doc: "The signed-in account, or nil."
  attr :lease, :map, default: nil, doc: "The page's `session_lease`."
  attr :client_key, :string, required: true, doc: "The page's `client_key`."

  @doc """
  The window: the three texts, each with its copy button, and for a signed-in
  person the form that leaves a message (`AgentMessage.Form`). Closed with its X,
  Escape or a press beside it (`assets/js/agent_message.ts`).
  """
  def dialog(assigns) do
    assigns = assign(assigns, texts: texts(assigns.topic))

    ~H"""
    <Regent.Structure.dialog
      id={@id}
      class="agent-message"
      aria-labelledby={"#{@id}-title"}
      data-agent-message
      phx-mounted={Phoenix.LiveView.JS.ignore_attributes(["open"])}
    >
      <Regent.Primitives.button
        variant="quiet"
        type="button"
        class="shell-dialog-close"
        aria-label="Close"
        data-agent-message-close
      >
        <Regent.Icons.icon name="x" />
      </Regent.Primitives.button>
      <h2 id={"#{@id}-title"}>Agent Message</h2>
      <p class="agent-message__note">
        Paste one of these into your agent. It leaves a private message that only Techtree's team reads.
      </p>
      <ol class="agent-message__texts">
        <li :for={text <- @texts}>
          <div class="agent-message__head">
            <h3>{text.title}</h3>
            <Regent.Primitives.copy_button
              id={"#{@id}-copy-#{text.id}"}
              target={"#{@id}-text-#{text.id}"}
              class="agent-message__copy"
            >
              Copy
            </Regent.Primitives.copy_button>
          </div>
          <pre tabindex="0" role="region" aria-label={text.title}><code id={"#{@id}-text-#{text.id}"}>{text.text}</code></pre>
        </li>
      </ol>
      <.live_component
        module={TechtreeWeb.Components.AgentMessage.Form}
        id={"#{@id}-person"}
        topic={@topic}
        account={@account}
        lease={@lease}
        client_key={@client_key}
      />
    </Regent.Structure.dialog>
    """
  end
end
