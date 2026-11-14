defmodule TechtreeWeb.Components.Enquiry do
  @moduledoc """
  The enquiry form in the Contact section of the home page and every service's
  page: a visitor's name, work email and company, the service (already chosen on
  a service's page) and what they want to improve, sent through
  `Techtree.Messages.Enquiry`'s `send` action, signed in or not. Each field is
  checked when the person leaves it, never while they type; after Send, the
  keyboard goes to the first field to fix (`assets/js/hooks/enquiry_form.ts`).
  Once sent, the form gives way to a short note of what happens next, and the
  keyboard moves to it.

  A field people never see or reach (`website`) catches programs that fill in
  every field: when it holds anything, the note shows and nothing is kept.

  The page passes `service` (an id from `Techtree.Messages.Enquiry.services/0`,
  or nil to let the visitor choose) and its `client_key`, which the enquiry's
  allowance counts.
  """

  use TechtreeWeb, :live_component

  alias Regent.Primitives
  alias Techtree.Messages
  alias Techtree.Messages.Enquiry
  alias TechtreeWeb.{FormErrors, Services}

  @impl true
  def mount(socket) do
    services = for id <- Enquiry.services(), do: {Services.fetch!(id).name, id}
    {:ok, assign(socket, services: services, sent?: false)}
  end

  @impl true
  def update(assigns, socket) do
    socket = assign(socket, Map.take(assigns, [:id, :service, :client_key]))

    # The first render builds the form; a later one keeps what is typed.
    if socket.assigns[:form],
      do: {:ok, socket},
      else: {:ok, assign(socket, :form, new_form(socket.assigns))}
  end

  @impl true
  def handle_event("validate", %{"enquiry" => params}, socket),
    do: {:noreply, assign(socket, :form, AshPhoenix.Form.validate(socket.assigns.form, params))}

  # Filled in by a program, not a person: it sees the note, and nothing is kept.
  def handle_event("send", %{"website" => trap}, socket) when trap != "",
    do: {:noreply, assign(socket, :sent?, true)}

  def handle_event("send", %{"enquiry" => params}, socket) do
    case AshPhoenix.Form.submit(socket.assigns.form, params: params) do
      {:ok, _enquiry} ->
        {:noreply, assign(socket, :sent?, true)}

      {:error, form} ->
        {:noreply,
         socket
         |> assign(:form, form)
         |> push_event("enquiry-refused", %{id: "#{socket.assigns.id}-form"})}
    end
  end

  defp new_form(assigns) do
    Messages.form_to_send_enquiry(
      as: "enquiry",
      params: if(assigns.service, do: %{"service" => Atom.to_string(assigns.service)}, else: %{}),
      context: %{client_key: assigns.client_key}
    )
    |> to_form()
  end

  # A refusal of the whole form, such as too many in an hour, rather than of one field.
  defp refusals(form), do: for({:_form, {message, _vars}} <- form.errors, do: message)

  @impl true
  def render(assigns) do
    ~H"""
    <section id={@id} class="mk-enquiry" aria-labelledby={"#{@id}-title"}>
      <h3 id={"#{@id}-title"} class="mk-enquiry__title">Inquiry</h3>
      <div
        :if={@sent?}
        id={"#{@id}-sent"}
        class="mk-enquiry__sent"
        tabindex="-1"
        phx-mounted={JS.focus()}
      >
        <p class="mk-enquiry__done">
          <Regent.Icons.icon name="circle-check" /> Sent
        </p>
        <p>Thank you. We reply by email, usually within two working days.</p>
        <p class="mk-enquiry__more">
          To add anything, write to <a href="mailto:build@regents.sh">build@regents.sh</a>.
        </p>
      </div>
      <.form
        :if={!@sent?}
        for={@form}
        id={"#{@id}-form"}
        class="mk-enquiry__fields"
        novalidate
        phx-change="validate"
        phx-submit="send"
        phx-target={@myself}
        phx-hook="EnquiryForm"
      >
        <Primitives.field
          :let={field}
          id={"#{@id}-name"}
          label="Name"
          errors={FormErrors.messages(@form[:name])}
        >
          <input
            id={field.id}
            name={@form[:name].name}
            value={@form[:name].value}
            maxlength="100"
            autocomplete="name"
            aria-required="true"
            phx-debounce="blur"
            aria-invalid={field.aria_invalid}
            aria-describedby={field.described_by}
          />
        </Primitives.field>
        <Primitives.field
          :let={field}
          id={"#{@id}-email"}
          label="Work email"
          errors={FormErrors.messages(@form[:email])}
        >
          <input
            id={field.id}
            type="email"
            name={@form[:email].name}
            value={@form[:email].value}
            maxlength="254"
            autocomplete="email"
            spellcheck="false"
            aria-required="true"
            phx-debounce="blur"
            aria-invalid={field.aria_invalid}
            aria-describedby={field.described_by}
          />
        </Primitives.field>
        <Primitives.field
          :let={field}
          id={"#{@id}-company"}
          label="Company"
          errors={FormErrors.messages(@form[:company])}
        >
          <input
            id={field.id}
            name={@form[:company].name}
            value={@form[:company].value}
            maxlength="100"
            autocomplete="organization"
            aria-required="true"
            phx-debounce="blur"
            aria-invalid={field.aria_invalid}
            aria-describedby={field.described_by}
          />
        </Primitives.field>
        <Primitives.field
          :let={field}
          id={"#{@id}-service"}
          label="Service"
          errors={FormErrors.messages(@form[:service])}
        >
          <select
            id={field.id}
            name={@form[:service].name}
            aria-required="true"
            phx-debounce="blur"
            aria-invalid={field.aria_invalid}
            aria-describedby={field.described_by}
          >
            <option :if={!@service} value="">Choose one</option>
            {Phoenix.HTML.Form.options_for_select(@services, @form[:service].value)}
          </select>
        </Primitives.field>
        <Primitives.field
          :let={field}
          id={"#{@id}-goal"}
          label="Goal"
          class="mk-enquiry__wide"
          errors={FormErrors.messages(@form[:goal])}
        >
          <textarea
            id={field.id}
            name={@form[:goal].name}
            rows="5"
            maxlength="2000"
            aria-required="true"
            phx-debounce="blur"
            aria-invalid={field.aria_invalid}
            aria-describedby={field.described_by}
          >{@form[:goal].value}</textarea>
          <:hint>A few sentences on the work you want to improve.</:hint>
        </Primitives.field>
        <div hidden>
          <label for={"#{@id}-website"}>Website</label>
          <input id={"#{@id}-website"} name="website" autocomplete="off" />
        </div>
        <Primitives.notice
          :for={refusal <- refusals(@form)}
          tone="error"
          class="mk-enquiry__wide"
        >
          {refusal}
        </Primitives.notice>
        <Primitives.button type="submit" class="mk-enquiry__send" phx-disable-with="Sending…">
          Send
        </Primitives.button>
      </.form>
    </section>
    """
  end
end
