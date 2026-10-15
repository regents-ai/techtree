defmodule TechtreeWeb.Components.VerifiedConnections do
  @moduledoc false

  use Phoenix.Component

  alias Regent.Primitives, as: P
  alias Techtree.Accounts.LinkedIdentity.Providers

  attr :id, :string, required: true
  attr :identities, :list, default: [], doc: "nil until the account's connections are read"

  attr :read_state, :atom,
    default: :ready,
    values: [:idle, :loading, :ready, :empty, :stale, :error]

  attr :notice, :map, default: nil
  attr :authenticated, :boolean, default: true
  attr :title, :string, default: "Verified connections"
  attr :description, :string, default: "Connect accounts that help people recognize your work."
  attr :class, :string, default: nil

  def verified_connections(assigns) do
    assigns = assign(assigns, :rows, rows(assigns.identities))

    ~H"""
    <section
      id={@id}
      class={["verified-connections", @class]}
      aria-labelledby={"#{@id}-title"}
      phx-hook="VerifiedConnections"
    >
      <div>
        <h2 id={"#{@id}-title"}>{@title}</h2>
        <p>{@description}</p>
        <p
          :if={@notice}
          id={"#{@id}-notice"}
          class={[
            "verified-connections__notice",
            @notice.tone == :error && "verified-connections__notice--error"
          ]}
          role={if(@notice.tone == :error, do: "alert", else: "status")}
          phx-hook="MotionRefusal"
          data-refused={@notice.tone == :error}
        >
          {@notice.message}
        </p>
        <p :if={@read_state in [:idle, :loading] and is_nil(@identities)} role="status">
          Loading your connections…
        </p>
        <p :if={@read_state == :stale} class="verified-connections__notice" role="status">
          Your connections couldn’t be refreshed. This is what they were last time.
        </p>
        <p
          :if={@read_state == :error}
          class="verified-connections__notice verified-connections__notice--error"
          role="alert"
        >
          Your connections couldn’t be loaded. Refresh the page to try again.
        </p>
      </div>

      <ul :if={@rows} class="verified-connections__list">
        <li :for={{entry, identity} <- @rows} id={"#{@id}-#{entry.provider}"}>
          <div>
            <strong>{entry.label}</strong>
            <.connection identity={identity} />
          </div>

          <P.button
            :if={@authenticated}
            type="button"
            phx-click="request_verified_connection"
            phx-value-action={if identity, do: "unlink", else: "link"}
            phx-value-provider={entry.provider}
          >
            {if identity, do: "Disconnect", else: "Connect"}
          </P.button>

          <P.button :if={!@authenticated} type="button" data-account-target="sign-in">
            Sign in to connect
          </P.button>
        </li>
      </ul>
    </section>
    """
  end

  # One row per provider with the identity connected to it, or nothing at all
  # until the connections are read.
  defp rows(nil), do: nil

  defp rows(identities) do
    for entry <- Providers.all(),
        do: {entry, Enum.find(identities, &(&1.provider == entry.provider))}
  end

  attr :identity, :map, default: nil

  defp connection(%{identity: nil} = assigns) do
    ~H"""
    <span>Not connected</span>
    """
  end

  defp connection(%{identity: identity} = assigns) do
    assigns =
      assign(assigns,
        handle: Providers.handle(identity),
        profile_url: Providers.profile_url(identity.provider, identity.username)
      )

    ~H"""
    <a :if={@profile_url && @handle} href={@profile_url} target="_blank" rel="noreferrer">
      {@handle}
    </a>
    <span :if={!(@profile_url && @handle)}>
      {@identity.display_name || @handle || "Connected"}
    </span>
    """
  end
end
