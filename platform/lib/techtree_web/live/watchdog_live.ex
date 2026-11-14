defmodule TechtreeWeb.WatchdogLive do
  @moduledoc """
  The signed-in sites page of Security's monitoring: a person adds the sites they own and the
  addresses on them, sees each site's proof state, gets the exact record or file
  to publish, and presses Check to prove ownership. Only public addresses are
  kept in this slice. Everything is read and changed as the signed-in person, so
  the list is always their own, and the page reloads when a background check
  finishes (`Techtree.Watchdog.Host` publishes on the person's topic).
  """

  use TechtreeWeb, :live_view

  alias Techtree.Actors.Human
  alias Techtree.Watchdog
  alias Techtree.Watchdog.{Host, Limits, Ownership}

  # How long a removed site stays, hidden, before the list drops it: until the
  # list's spring (LAYOUTS.bounce in hooks/motion/moments.ts) has settled, which
  # anime.js puts at 920ms. Dropping it sooner restarts the spring mid-glide.
  @leave_ms 920

  @impl true
  def mount(_params, _session, socket) do
    if connected?(socket), do: subscribe(socket)

    {:ok,
     socket
     |> assign(
       page_title: "Your sites",
       notice: nil,
       field_errors: %{},
       signed_in?: false,
       hosts: [],
       routes: %{}
     )
     |> load_list()}
  end

  @impl true
  def handle_event("add_site", %{"origin" => origin, "ownership_method" => method}, socket) do
    with %Human{} = actor <- actor(socket),
         {:ok, method} <- parse_method(method),
         {:ok, _host} <- Watchdog.add_host(origin, %{ownership_method: method}, actor: actor) do
      {:noreply,
       socket
       |> inform(:success, "Site added. Publish its proof, then press Check.")
       |> load_list()}
    else
      {:error, error} ->
        {:noreply, refuse(socket, "watchdog-origin", error, "That site couldn't be added.")}

      nil ->
        {:noreply, socket}
    end
  end

  def handle_event("check_site", %{"id" => id}, socket) do
    update_host(
      socket,
      id,
      &Watchdog.request_host_verification/2,
      "Checking the proof now…",
      :info
    )
  end

  # The removed site stays on the page, hidden, so the list's motion (MotionList)
  # can take it out while the sites under it close the gap; then the list is read
  # again.
  def handle_event("remove_site", %{"id" => id}, socket) do
    with %Human{} = actor <- actor(socket),
         {:ok, host} <- Ash.get(Host, id, actor: actor),
         :ok <- Watchdog.remove_host(host, actor: actor) do
      Process.send_after(self(), :removed, @leave_ms)

      {:noreply,
       socket
       |> inform(:success, "Site removed.")
       |> update(:leaving, &[host.id | &1])}
    else
      {:error, error} -> {:noreply, inform_error(socket, error, "That couldn't be done.")}
      nil -> {:noreply, socket}
    end
  end

  def handle_event("add_address", %{"host_id" => host_id, "url" => url}, socket) do
    with %Human{} = actor <- actor(socket),
         {:ok, _route} <- Watchdog.add_route(host_id, %{url: url}, actor: actor) do
      {:noreply, socket |> inform(:success, "Address added.") |> load_list()}
    else
      {:error, error} ->
        {:noreply,
         refuse(socket, "watchdog-url-#{host_id}", error, "That address couldn't be added.")}

      nil ->
        {:noreply, socket}
    end
  end

  def handle_event("pause_address", %{"id" => id}, socket) do
    update_route(socket, id, &Watchdog.pause_route/2, "Address turned off.", :success)
  end

  def handle_event("resume_address", %{"id" => id}, socket) do
    update_route(socket, id, &Watchdog.resume_route/2, "Address turned on.", :success)
  end

  def handle_event("remove_address", %{"id" => id}, socket) do
    update_route(socket, id, &Watchdog.remove_route/2, "Address removed.", :success)
  end

  @impl true
  def handle_info(:removed, socket), do: {:noreply, load_list(socket)}
  def handle_info(%{__struct__: Host}, socket), do: {:noreply, load_list(socket)}
  def handle_info(_message, socket), do: {:noreply, socket}

  defp update_host(socket, id, fun, message, tone) do
    with %Human{} = actor <- actor(socket),
         {:ok, host} <- Ash.get(Host, id, actor: actor),
         {:ok, _updated} <- fun.(host, actor: actor) do
      {:noreply, socket |> inform(tone, message) |> load_list()}
    else
      {:error, error} -> {:noreply, inform_error(socket, error, "That couldn't be done.")}
      nil -> {:noreply, socket}
    end
  end

  defp update_route(socket, id, fun, message, tone) do
    with %Human{} = actor <- actor(socket),
         {:ok, route} <- Ash.get(Watchdog.Route, id, actor: actor),
         {:ok, _updated} <- fun.(route, actor: actor) do
      {:noreply, socket |> inform(tone, message) |> load_list()}
    else
      {:error, error} -> {:noreply, inform_error(socket, error, "That couldn't be done.")}
      nil -> {:noreply, socket}
    end
  end

  defp load_list(socket) do
    case actor(socket) do
      %Human{} = actor ->
        hosts = Watchdog.list_my_hosts!(actor: actor)

        routes =
          %{}
          |> Watchdog.list_my_routes!(actor: actor)
          |> Enum.reject(&(&1.state == :removed))
          |> Enum.group_by(& &1.host_id)

        assign(socket, signed_in?: true, hosts: hosts, routes: routes, leaving: [])

      nil ->
        assign(socket, signed_in?: false, hosts: [], routes: %{}, leaving: [])
    end
  end

  defp subscribe(socket) do
    case actor(socket) do
      %Human{human_account_id: id} ->
        Phoenix.PubSub.subscribe(Techtree.PubSub, Host.topic(id))

      nil ->
        :ok
    end
  end

  defp actor(%{assigns: %{access_context: %{principal: {:human, account}}}}),
    do: Human.for_account(account)

  defp actor(_socket), do: nil

  defp parse_method("dns_txt"), do: {:ok, :dns_txt}
  defp parse_method("well_known_file"), do: {:ok, :well_known_file}
  defp parse_method(_other), do: {:error, :bad_method}

  defp inform(socket, tone, message),
    do: assign(socket, notice: %{tone: tone, message: message, shown?: true}, field_errors: %{})

  # A refused site or address: what is wrong with the typed value goes under its
  # own field, and the notice fades out; anything else (a limit reached) goes in
  # the page's notice.
  defp refuse(socket, field_id, error, fallback) do
    case typed_value_message(error) do
      nil ->
        inform_error(socket, error, fallback)

      message ->
        socket
        |> update(:notice, &(&1 && %{&1 | shown?: false}))
        |> assign(field_errors: %{field_id => message})
    end
  end

  defp typed_value_message(%Ash.Error.Invalid{errors: errors}) do
    Enum.find_value(errors, fn
      %{field: field, message: message} when field in [:origin, :url] and is_binary(message) ->
        message

      _other ->
        nil
    end)
  end

  defp typed_value_message(_other), do: nil

  defp inform_error(socket, error, fallback),
    do: inform(socket, :error, first_message(error) || fallback)

  defp first_message(%Ash.Error.Invalid{errors: errors}),
    do: errors |> Enum.map(&message_of/1) |> Enum.find(& &1)

  defp first_message(%Ash.Error.Forbidden{}), do: nil
  defp first_message(_other), do: nil

  defp message_of(%{message: message}) when is_binary(message), do: message
  defp message_of(_other), do: nil

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page>
      <article class="watchdog" aria-labelledby="watchdog-title">
        <header class="editorial-heading">
          <p class="eyebrow">Security</p>
          <h1 id="watchdog-title">Your sites</h1>
          <p class="lede">
            Add the sites you own and the addresses on them. Prove each site is yours, and
            we only ever touch addresses on a proven site. Public addresses only for now.
          </p>
        </header>

        <Regent.Account.signed_out
          :if={not @signed_in?}
          id="watchdog-signed-out"
          reason={@signed_out_reason}
        >
          <:sign_in>
            <Regent.Primitives.button type="button" data-account-target="sign-in">
              Sign in
            </Regent.Primitives.button>
          </:sign_in>
        </Regent.Account.signed_out>

        <div :if={@signed_in?}>
          <Regent.Structure.panel class="watchdog-add rg-panel__body">
            <h2>New site</h2>
            <form phx-submit="add_site" class="watchdog-form">
              <Regent.Primitives.field
                :let={f}
                id="watchdog-origin"
                label="Site"
                errors={List.wrap(@field_errors["watchdog-origin"])}
              >
                <input
                  id={f.id}
                  name="origin"
                  type="text"
                  inputmode="url"
                  placeholder="example.com"
                  aria-describedby={f.described_by}
                  aria-invalid={f.aria_invalid}
                  required
                />
                <:hint>The site's address, such as example.com.</:hint>
              </Regent.Primitives.field>

              <fieldset class="watchdog-method">
                <legend>Proof</legend>
                <label>
                  <input type="radio" name="ownership_method" value="dns_txt" checked />DNS record
                </label>
                <label>
                  <input type="radio" name="ownership_method" value="well_known_file" />File
                </label>
              </fieldset>

              <Regent.Primitives.button type="submit">Add site</Regent.Primitives.button>
            </form>
            <p class="rg-muted">You can keep up to {Limits.max_hosts()} sites.</p>
            <%!-- Last, so it comes and goes without the page rebuilding the form. --%>
            <Regent.Primitives.notice
              :if={@notice}
              tone={to_string(@notice.tone)}
              hidden={!@notice.shown?}
            >
              {@notice.message}
            </Regent.Primitives.notice>
          </Regent.Structure.panel>

          <Regent.Primitives.empty_state :if={@hosts == []} title="No sites">
            Add a site above to get its proof and start.
          </Regent.Primitives.empty_state>

          <ol
            id="watchdog-sites"
            class="watchdog-sites"
            phx-hook="MotionList"
            data-layout-id="watchdog-sites"
            data-children="[data-site]"
            data-variant={TechtreeWeb.Motion.standard("list")}
          >
            <li
              :for={host <- @hosts}
              id={"watchdog-site-#{host.id}"}
              data-site
              data-layout-id={"watchdog-site-#{host.id}"}
              hidden={host.id in @leaving}
            >
              <Regent.Structure.panel class="watchdog-site rg-panel__body">
                <div class="watchdog-site__head">
                  <h2>{host.origin}</h2>
                  <Regent.Primitives.status tone={status_tone(host.ownership_state)}>
                    {status_label(host.ownership_state)}
                  </Regent.Primitives.status>
                </div>

                <div class="watchdog-proof">
                  <h3>{proof_title(host.ownership_method)}</h3>
                  <dl>
                    <div>
                      <dt>{proof_place_label(host.ownership_method)}</dt>
                      <dd>
                        <code>{proof_place(host)}</code>
                        <Regent.Primitives.copy_button
                          id={"watchdog-place-#{host.id}"}
                          text={proof_place(host)}
                        >
                          Copy
                        </Regent.Primitives.copy_button>
                      </dd>
                    </div>
                    <div>
                      <dt>Value</dt>
                      <dd>
                        <code>{Ownership.record_value(host)}</code>
                        <Regent.Primitives.copy_button
                          id={"watchdog-value-#{host.id}"}
                          text={Ownership.record_value(host)}
                        >
                          Copy
                        </Regent.Primitives.copy_button>
                      </dd>
                    </div>
                  </dl>
                </div>

                <div class="watchdog-site__actions">
                  <Regent.Primitives.button
                    type="button"
                    phx-click="check_site"
                    phx-value-id={host.id}
                    disabled={host.ownership_state == :pending}
                  >
                    {check_label(host.ownership_state)}
                  </Regent.Primitives.button>
                  <Regent.Primitives.button
                    type="button"
                    variant="quiet"
                    phx-click="remove_site"
                    phx-value-id={host.id}
                    data-confirm="Remove this site and its addresses?"
                    data-confirm-action="Remove"
                  >
                    Remove site
                  </Regent.Primitives.button>
                </div>

                <div class="watchdog-routes">
                  <h3>Addresses</h3>
                  <p :if={host.ownership_state != :verified} class="rg-muted">
                    Prove the site first; addresses stay off until it's proven.
                  </p>

                  <ul :if={routes_of(@routes, host) != []}>
                    <li :for={route <- routes_of(@routes, host)}>
                      <code>{route.url}</code>
                      <Regent.Primitives.status tone={route_tone(route.state)}>
                        {route_label(route.state)}
                      </Regent.Primitives.status>
                      <Regent.Primitives.button
                        :if={route.state == :active}
                        type="button"
                        variant="quiet"
                        phx-click="pause_address"
                        phx-value-id={route.id}
                      >
                        Turn off
                      </Regent.Primitives.button>
                      <Regent.Primitives.button
                        :if={route.state == :paused}
                        type="button"
                        variant="quiet"
                        phx-click="resume_address"
                        phx-value-id={route.id}
                      >
                        Turn on
                      </Regent.Primitives.button>
                      <Regent.Primitives.button
                        type="button"
                        variant="quiet"
                        phx-click="remove_address"
                        phx-value-id={route.id}
                      >
                        Remove
                      </Regent.Primitives.button>
                    </li>
                  </ul>

                  <form phx-submit="add_address" class="watchdog-form watchdog-form--inline">
                    <input type="hidden" name="host_id" value={host.id} />
                    <Regent.Primitives.field
                      :let={f}
                      id={"watchdog-url-#{host.id}"}
                      label="Address"
                      errors={List.wrap(@field_errors["watchdog-url-#{host.id}"])}
                    >
                      <input
                        id={f.id}
                        name="url"
                        type="url"
                        placeholder={"https://#{host.origin}/path"}
                        aria-describedby={f.described_by}
                        aria-invalid={f.aria_invalid}
                        required
                      />
                    </Regent.Primitives.field>
                    <Regent.Primitives.button type="submit" variant="secondary">
                      Add address
                    </Regent.Primitives.button>
                  </form>
                </div>
              </Regent.Structure.panel>
            </li>
          </ol>
        </div>
      </article>
    </Layouts.page>
    """
  end

  defp routes_of(routes, host), do: Map.get(routes, host.id, [])

  defp status_label(:unverified), do: "Not proven"
  defp status_label(:pending), do: "Checking"
  defp status_label(:verified), do: "Proven"
  defp status_label(:revoked), do: "Proof gone"

  defp status_tone(:verified), do: "success"
  defp status_tone(:pending), do: "info"
  defp status_tone(:revoked), do: "warning"
  defp status_tone(_unverified), do: "neutral"

  defp check_label(:verified), do: "Check again"
  defp check_label(:pending), do: "Checking…"
  defp check_label(_other), do: "Check now"

  defp proof_title(:dns_txt), do: "DNS record"
  defp proof_title(:well_known_file), do: "Hosted file"

  defp proof_place_label(:dns_txt), do: "Record name"
  defp proof_place_label(:well_known_file), do: "File address"

  defp proof_place(%{ownership_method: :dns_txt} = host), do: Ownership.txt_name(host)

  defp proof_place(%{ownership_method: :well_known_file} = host),
    do: Ownership.well_known_url(host)

  defp route_label(:active), do: "On"
  defp route_label(:paused), do: "Off"
  defp route_label(:removed), do: "Removed"

  defp route_tone(:active), do: "success"
  defp route_tone(_other), do: "neutral"
end
