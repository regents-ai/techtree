defmodule TechtreeWeb.TeamMessagesLive do
  @moduledoc """
  The team's page, for the site's admins only, in three tabs: the messages
  agents and people left (`Techtree.Messages.Message`), the enquiries visitors
  sent from the contact form (`Techtree.Messages.Enquiry`, `?show=enquiries`),
  and the projects delivered to customers (`Techtree.Projects.Project`,
  `?show=projects`). Each list is newest first, 50 a page. The route sits
  behind `TechtreeWeb.TeamGate`, every press asks it again, and each action's
  own policy asks once more (`RegentAgents.Checks.Admin`). `?after=` holds the
  cursor of the page before.

  On the Projects tab an admin uploads a package, which is opened and checked
  at once (`Techtree.Projects.Package`) and shown as the customer will read it,
  finds the customer's account by a wallet it signed in with or its Privy id,
  and delivers it. The uploaded bytes stay in this page until then, never
  drawn. An admin also withdraws a delivered project, which takes it from the
  customer and deletes its package and report.
  """

  use TechtreeWeb, :live_view

  alias Regent.Primitives
  alias Techtree.{Messages, Projects}
  alias Techtree.Projects.{Manifest, Package}
  alias TechtreeWeb.{ProjectsLive, Read, Services, TeamGate}

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     socket
     |> assign(
       page_title: "Messages",
       show: :messages,
       messages: %Read{},
       enquiries: %Read{},
       projects: %Read{},
       package: nil,
       package_error: nil,
       customer: nil,
       customer_search: nil,
       customer_error: nil,
       delivery: nil,
       withdrawal: nil
     )
     |> allow_upload(:package,
       accept: ~w(.gz),
       max_entries: 1,
       max_file_size: Package.max_bytes(),
       auto_upload: true,
       progress: &package_uploaded/3
     )}
  end

  @impl true
  def handle_params(params, _uri, socket) do
    case TeamGate.admin(socket.assigns.access_context) do
      nil ->
        {:noreply, redirect(socket, to: ~p"/")}

      admin ->
        show = tab(params)
        cursor = params["after"]
        page = if cursor, do: [after: cursor], else: []

        {:noreply,
         socket
         |> assign(:show, show)
         |> Read.now(show, cursor, fn -> list(show, actor: admin, page: page) end)}
    end
  end

  # Opening the file starts its upload; nothing else is asked of the form.
  @impl true
  def handle_event("package_chosen", _params, socket), do: {:noreply, socket}

  # The search stays in its box, so a miss can be corrected rather than retyped.
  def handle_event("find_customer", %{"customer" => search}, socket) do
    as_admin(socket, fn admin ->
      socket = assign(socket, :customer_search, search)

      case Projects.find_customer(search, actor: admin) do
        {:ok, %{} = account} ->
          assign(socket, customer: account, customer_error: nil, delivery: nil)

        {:ok, nil} ->
          assign(socket,
            customer: nil,
            customer_error: "No account has signed in with that wallet or Privy id."
          )

        {:error, _error} ->
          assign(socket,
            customer: nil,
            customer_error: "Accounts couldn’t be searched. Try again."
          )
      end
    end)
  end

  def handle_event("deliver", _params, socket) do
    as_admin(socket, fn admin -> deliver(socket, admin) end)
  end

  def handle_event("withdraw", %{"id" => id}, socket) do
    as_admin(socket, fn admin -> withdraw(socket, admin, id) end)
  end

  # Each press asks the team gate again, so a sign-in that ended does nothing.
  defp as_admin(socket, act) do
    case TeamGate.admin(socket.assigns.access_context) do
      nil -> {:noreply, redirect(socket, to: ~p"/")}
      admin -> {:noreply, act.(admin)}
    end
  end

  defp package_uploaded(:package, %{done?: false}, socket), do: {:noreply, socket}

  # The path is the upload's own temporary file, which LiveView names.
  # sobelow_skip ["Traversal.FileModule"]
  defp package_uploaded(:package, entry, socket) do
    bytes = consume_uploaded_entry(socket, entry, fn %{path: path} -> {:ok, File.read!(path)} end)

    case Package.read(bytes) do
      {:ok, package} ->
        {:noreply,
         assign(socket,
           package: Map.put(package, :bytes, bytes),
           package_error: nil,
           delivery: nil
         )}

      {:error, message} ->
        {:noreply, assign(socket, package: nil, package_error: message, delivery: nil)}
    end
  end

  defp deliver(%{assigns: %{package: %{bytes: bytes}, customer: %{} = customer}} = socket, admin) do
    case Projects.deliver_project(customer.privy_user_id, bytes, actor: admin) do
      {:ok, project} ->
        socket
        |> assign(
          package: nil,
          customer: nil,
          customer_search: nil,
          delivery: {:success, "Delivered “#{project.title}” to #{project.customer_name}."},
          withdrawal: nil
        )
        |> read_projects(admin)

      {:error, error} ->
        assign(socket, delivery: {:error, messages(error)})
    end
  end

  defp deliver(socket, _admin),
    do: assign(socket, delivery: {:error, "Upload a package and find its customer first."})

  defp withdraw(socket, admin, id) do
    with %Read{state: :ready, value: %{results: projects}} <- socket.assigns.projects,
         %{} = project <- Enum.find(projects, &(&1.id == id)),
         {:ok, project} <- Projects.withdraw_project(project, actor: admin) do
      socket
      |> assign(
        delivery: nil,
        withdrawal: {:success, "Withdrew “#{project.title}”. Its customer no longer sees it."}
      )
      |> read_projects(admin)
    else
      {:error, error} -> assign(socket, delivery: nil, withdrawal: {:error, messages(error)})
      _gone -> read_projects(socket, admin)
    end
  end

  defp tone({:success, _message}), do: "success"
  defp tone({:error, _message}), do: "error"

  defp read_projects(socket, admin) do
    socket
    |> Read.clear(:projects)
    |> Read.now(:projects, nil, fn -> Projects.list_team_projects(actor: admin) end)
  end

  defp messages(error) do
    error
    |> Ash.Error.to_error_class()
    |> Map.get(:errors, [error])
    |> Enum.map_join(" ", &message/1)
  end

  defp message(%{message: message}) when is_binary(message), do: message
  defp message(error), do: Exception.message(error)

  defp tab(%{"show" => "enquiries"}), do: :enquiries
  defp tab(%{"show" => "projects"}), do: :projects
  defp tab(_params), do: :messages

  defp list(:messages, opts), do: Messages.list_messages(opts)
  defp list(:enquiries, opts), do: Messages.list_enquiries(opts)
  defp list(:projects, opts), do: Projects.list_team_projects(opts)

  # The tab's own address, with the cursor of the page before when there is one.
  defp tab_path(:messages, []), do: ~p"/admin/messages"
  defp tab_path(:messages, query), do: ~p"/admin/messages?#{query}"
  defp tab_path(show, query), do: ~p"/admin/messages?#{[show: show] ++ query}"

  # A visitor's address as a link that writes to it and nothing more: anything
  # but its letters, digits and @ is escaped, so it cannot add a subject,
  # copies or text of its own.
  defp mailto(email), do: "mailto:" <> URI.encode(email, &(&1 == ?@ or URI.char_unreserved?(&1)))

  defp upload_error(:too_large), do: "The package is over 5 MB."
  defp upload_error(:not_accepted), do: "Choose a .tar.gz file."
  defp upload_error(:too_many_files), do: "Choose one package."
  defp upload_error(_error), do: "The package couldn’t be uploaded. Try again."

  defp package_errors(uploads, package_error) do
    entry_errors = Enum.flat_map(uploads.package.entries, &upload_errors(uploads.package, &1))

    (upload_errors(uploads.package) ++ entry_errors)
    |> Enum.map(&upload_error/1)
    |> Kernel.++(List.wrap(package_error))
  end

  @impl true
  def render(assigns) do
    assigns = assign(assigns, :read, Map.fetch!(assigns, assigns.show))

    ~H"""
    <Layouts.page>
      <article class="team-messages" aria-labelledby="team-messages-title">
        <header class="editorial-heading">
          <p class="eyebrow">Team</p>
          <h1 id="team-messages-title">Messages</h1>
        </header>
        <Primitives.tabs
          id="team-tabs"
          label="Team inbox"
          tabs={[
            %{label: "Messages", patch: tab_path(:messages, []), current: @show == :messages},
            %{label: "Enquiries", patch: tab_path(:enquiries, []), current: @show == :enquiries},
            %{label: "Projects", patch: tab_path(:projects, []), current: @show == :projects}
          ]}
        />
        <.deliver
          :if={@show == :projects}
          uploads={@uploads}
          package={@package}
          package_errors={package_errors(@uploads, @package_error)}
          customer={@customer}
          customer_search={@customer_search}
          customer_error={@customer_error}
          delivery={@delivery}
        />
        <Primitives.notice :if={@read.state in [:error, :stale]} tone="error">
          The {@show} couldn’t be read. Refresh the page to try again.
        </Primitives.notice>
        <Primitives.empty_state
          :if={@show == :messages and match?(%{state: :ready, value: %{results: []}}, @read)}
          title="No messages"
        >
          Messages agents and people leave for the team show here.
        </Primitives.empty_state>
        <Primitives.empty_state
          :if={@show == :enquiries and match?(%{state: :ready, value: %{results: []}}, @read)}
          title="No enquiries"
        >
          Enquiries visitors send from the contact form show here.
        </Primitives.empty_state>
        <Primitives.empty_state
          :if={@show == :projects and match?(%{state: :ready, value: %{results: []}}, @read)}
          title="No projects"
        >
          Projects you deliver show here.
        </Primitives.empty_state>
        <ol
          :if={@show == :messages and @read.state == :ready}
          id="team-messages"
          class="team-messages__list"
        >
          <li :for={message <- @read.value.results} id={"message-#{message.id}"}>
            <dl class="team-messages__meta">
              <div>
                <dt>Topic</dt>
                <dd><code>{message.topic}</code></dd>
              </div>
              <div>
                <dt>From</dt>
                <dd>
                  <bdi>{message.sender_name}</bdi>
                  <span :if={message.agent}>
                    · Agent
                    <Primitives.address
                      id={"message-#{message.id}-agent"}
                      address={message.agent.wallet_address}
                    />
                  </span>
                </dd>
              </div>
              <div>
                <dt>Sent</dt>
                <dd><.sent at={message.inserted_at} /></dd>
              </div>
              <div :if={message.reply_to}>
                <dt>Reply</dt>
                <dd><bdi>{message.reply_to}</bdi></dd>
              </div>
            </dl>
            <p class="team-messages__body">{message.body}</p>
          </li>
        </ol>
        <ol
          :if={@show == :enquiries and @read.state == :ready}
          id="team-enquiries"
          class="team-messages__list"
        >
          <li :for={enquiry <- @read.value.results} id={"enquiry-#{enquiry.id}"}>
            <dl class="team-messages__meta">
              <div>
                <dt>Service</dt>
                <dd>{Services.fetch!(enquiry.service).name}</dd>
              </div>
              <div>
                <dt>From</dt>
                <dd><bdi>{enquiry.name}</bdi>, <bdi>{enquiry.company}</bdi></dd>
              </div>
              <div>
                <dt>Email</dt>
                <dd>
                  <a href={mailto(enquiry.email)}><bdi>{enquiry.email}</bdi></a>
                </dd>
              </div>
              <div>
                <dt>Sent</dt>
                <dd><.sent at={enquiry.inserted_at} /></dd>
              </div>
            </dl>
            <p class="team-messages__body">{enquiry.goal}</p>
          </li>
        </ol>
        <section
          :if={@show == :projects and @read.state == :ready and @read.value.results != []}
          class="team-projects"
          aria-labelledby="team-projects-title"
        >
          <h2 id="team-projects-title">Delivered</h2>
          <p class="rg-muted">
            Withdrawing a project takes it away from its customer and deletes its package and report. It can’t be undone.
          </p>
          <Primitives.notice :if={@withdrawal} id="team-withdraw-outcome" tone={tone(@withdrawal)}>
            {elem(@withdrawal, 1)}
          </Primitives.notice>
          <ol id="team-projects" class="team-messages__list">
            <li :for={project <- @read.value.results} id={"team-project-#{project.id}"}>
              <div class="team-projects__head">
                <p class="team-projects__title"><bdi>{project.title}</bdi></p>
                <Primitives.status :if={project.withdrawn_at}>Withdrawn</Primitives.status>
                <ProjectsLive.verdict :if={is_nil(project.withdrawn_at)} verdict={project.verdict} />
              </div>
              <dl class="team-messages__meta">
                <div>
                  <dt>Customer</dt>
                  <dd><bdi>{project.customer_name}</bdi></dd>
                </div>
                <div>
                  <dt>Service</dt>
                  <dd>{Services.fetch!(project.line).name}</dd>
                </div>
                <div>
                  <dt>Delivered</dt>
                  <dd>
                    <.sent at={project.delivered_at} /> by <bdi>{project.delivered_by_name}</bdi>
                  </dd>
                </div>
                <div :if={project.withdrawn_at}>
                  <dt>Withdrawn</dt>
                  <dd>
                    <.sent at={project.withdrawn_at} /> by <bdi>{project.withdrawn_by_name}</bdi>
                  </dd>
                </div>
                <div>
                  <dt>Size</dt>
                  <dd>{ProjectsLive.size(project.package_size)}</dd>
                </div>
              </dl>
              <div :if={is_nil(project.withdrawn_at)} class="team-projects__actions">
                <a
                  href={~p"/account/projects/#{project.id}/package"}
                  class="rg-button rg-button--secondary"
                  download
                >
                  <span class="rg-button__label">Download</span>
                </a>
                <Primitives.button
                  type="button"
                  variant="quiet"
                  phx-click="withdraw"
                  phx-value-id={project.id}
                  data-confirm={"Withdraw “#{project.title}”? Its customer stops seeing it, and its package and report are deleted."}
                  data-confirm-action="Withdraw"
                >
                  Withdraw
                </Primitives.button>
              </div>
            </li>
          </ol>
        </section>
        <.link
          :if={@read.state == :ready and @read.value.more?}
          patch={tab_path(@show, after: List.last(@read.value.results).__metadata__.keyset)}
          class="rg-button rg-button--secondary"
        >
          Older
        </.link>
      </article>
    </Layouts.page>
    """
  end

  attr :uploads, :map, required: true
  attr :package, :map, default: nil
  attr :package_errors, :list, required: true
  attr :customer, :map, default: nil
  attr :customer_search, :string, default: nil
  attr :customer_error, :string, default: nil
  attr :delivery, :any, default: nil

  # Upload, check, find the customer, deliver.
  defp deliver(assigns) do
    ~H"""
    <section id="team-deliver" class="team-deliver" aria-labelledby="team-deliver-title">
      <h2 id="team-deliver-title">Deliver</h2>
      <Primitives.notice
        :if={@delivery}
        id="team-deliver-outcome"
        tone={tone(@delivery)}
      >
        {elem(@delivery, 1)}
      </Primitives.notice>
      <form id="team-package-form" phx-change="package_chosen" phx-submit="package_chosen">
        <Primitives.field id={@uploads.package.ref} label="Package" errors={@package_errors}>
          <.live_file_input upload={@uploads.package} />
          <:hint>The factory’s .tar.gz, up to 5 MB. It is checked as soon as it uploads.</:hint>
        </Primitives.field>
      </form>
      <dl :if={@package} id="team-package-preview" class="team-messages__meta team-deliver__preview">
        <div>
          <dt>Title</dt>
          <dd><bdi>{@package.manifest["title"]}</bdi></dd>
        </div>
        <div>
          <dt>Service</dt>
          <dd>{Services.fetch!(Manifest.line(@package.manifest)).name}</dd>
        </div>
        <div>
          <dt>Verdict</dt>
          <dd><ProjectsLive.verdict verdict={Manifest.verdict(@package.manifest)} /></dd>
        </div>
        <div>
          <dt>Before</dt>
          <dd>
            {@package.manifest["summary"]["original"]["solved"]} of {@package.manifest["summary"][
              "original"
            ]["attempts"]}
          </dd>
        </div>
        <div>
          <dt>After</dt>
          <dd>
            {@package.manifest["summary"]["selected"]["solved"]} of {@package.manifest["summary"][
              "selected"
            ]["attempts"]}
          </dd>
        </div>
        <div>
          <dt>Difference</dt>
          <dd>{ProjectsLive.difference(@package.manifest["summary"]["difference"])}</dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>{ProjectsLive.size(@package.size)}</dd>
        </div>
      </dl>
      <form id="team-customer-form" class="team-deliver__customer" phx-submit="find_customer">
        <Primitives.field
          :let={field}
          id="team-customer"
          label="Customer"
          errors={List.wrap(@customer_error)}
        >
          <input
            id={field.id}
            type="text"
            name="customer"
            value={@customer_search}
            autocomplete="off"
            spellcheck="false"
            aria-describedby={field.described_by}
            aria-invalid={field.aria_invalid}
            required
          />
          <:hint>
            A wallet their account signed in with, or its Privy id (did:privy:…). Techtree keeps no email addresses, so find the Privy id for an email in Privy’s dashboard.
          </:hint>
        </Primitives.field>
        <Primitives.button type="submit" variant="secondary">Find</Primitives.button>
      </form>
      <dl :if={@customer} id="team-customer-found" class="team-messages__meta">
        <div :if={@customer.display_name}>
          <dt>Name</dt>
          <dd><bdi>{@customer.display_name}</bdi></dd>
        </div>
        <div :if={@customer.wallet_address}>
          <dt>Wallet</dt>
          <dd>
            <Primitives.address id="team-customer-wallet" address={@customer.wallet_address} />
          </dd>
        </div>
      </dl>
      <Primitives.button
        id="team-deliver-button"
        type="button"
        phx-click="deliver"
        disabled={is_nil(@package) or is_nil(@customer)}
      >
        Deliver
      </Primitives.button>
    </section>
    """
  end

  attr :at, DateTime, required: true

  defp sent(assigns) do
    ~H"""
    <time datetime={DateTime.to_iso8601(@at)}>
      {Calendar.strftime(@at, "%-d %b %Y, %H:%M UTC")}
    </time>
    """
  end
end
