defmodule TechtreeWeb.Components.AgentMessage.Form do
  @moduledoc """
  The form inside the Agent Message window (`TechtreeWeb.Components.AgentMessage`):
  a signed-in person leaves a private message for Techtree's team under the
  window's topic, through the same `leave` action an agent's message takes, and
  sees its receipt. A signed-out visitor sees nothing here. Each field is
  checked when the person leaves it, never while they type.

  The page passes the signed-in `account` (or nil), its `session_lease` as
  `lease`, and its `client_key`. Every press re-reads the sign-in
  (`TechtreeWeb.Live.Session.check_component_lease/2`), and the message is left
  as the account it names at that moment.
  """

  use TechtreeWeb, :live_component

  alias Regent.Primitives
  alias Techtree.Actors.Human
  alias Techtree.Messages
  alias TechtreeWeb.FormErrors
  alias TechtreeWeb.Live.Session

  @impl true
  def mount(socket),
    do:
      {:ok,
       socket |> Session.check_component_lease(&assign(&1, :account, &2)) |> assign(receipt: nil)}

  @impl true
  def update(assigns, socket) do
    socket = assign(socket, Map.take(assigns, [:id, :topic, :account, :lease, :client_key]))

    # A new sign-in, or none, gets a fresh form; a re-render keeps what is typed.
    if changed?(socket, :account),
      do: {:ok, assign(socket, :form, new_form(socket))},
      else: {:ok, socket}
  end

  @impl true
  def handle_event("validate", %{"message" => params}, socket),
    do: {:noreply, assign(socket, :form, AshPhoenix.Form.validate(socket.assigns.form, params))}

  # Left as the account the sign-in names now, which the press has just re-read.
  def handle_event("leave", %{"message" => params}, socket) do
    case socket |> new_form() |> submit(params) do
      {:ok, message} ->
        {:noreply,
         assign(socket, receipt: Messages.Message.receipt(message), form: new_form(socket))}

      {:error, form} ->
        {:noreply, assign(socket, receipt: nil, form: form)}
    end
  end

  # No one is signed in, so there is no form to send.
  defp submit(nil, _params), do: {:error, nil}
  defp submit(form, params), do: AshPhoenix.Form.submit(form, params: params)

  defp new_form(%{assigns: %{account: nil}}), do: nil

  defp new_form(%{assigns: assigns}) do
    Messages.form_to_leave_message(
      actor: Human.for_account(assigns.account),
      as: "message",
      context: %{client_key: assigns.client_key},
      prepare_params: fn params, _phase -> Map.put(params, "topic", assigns.topic) end
    )
    |> to_form()
  end

  @impl true
  def render(assigns) do
    ~H"""
    <div id={@id}>
      <section :if={@form} class="agent-message__form" aria-labelledby={"#{@id}-title"}>
        <h3 id={"#{@id}-title"}>Your message</h3>
        <p class="agent-message__note">Or leave one yourself. Only Techtree's team reads it.</p>
        <Primitives.notice :if={@receipt} tone="success" id={"#{@id}-receipt"}>
          Sent {time(@receipt.inserted_at)}. Receipt <code>{@receipt.id}</code>
        </Primitives.notice>
        <.form
          for={@form}
          id={"#{@id}-form"}
          class="agent-message__fields"
          phx-change="validate"
          phx-submit="leave"
          phx-target={@myself}
        >
          <Primitives.field
            :let={field}
            id={"#{@id}-body"}
            label="Message"
            errors={FormErrors.messages(@form[:body])}
          >
            <textarea
              id={field.id}
              name={@form[:body].name}
              rows="4"
              maxlength="2000"
              phx-debounce="blur"
              aria-invalid={field.aria_invalid}
              aria-describedby={field.described_by}
            >{@form[:body].value}</textarea>
          </Primitives.field>
          <Primitives.field
            :let={field}
            id={"#{@id}-reply-to"}
            label="Reply to"
            errors={FormErrors.messages(@form[:reply_to])}
          >
            <input
              id={field.id}
              name={@form[:reply_to].name}
              value={@form[:reply_to].value}
              maxlength="200"
              autocomplete="email"
              phx-debounce="blur"
              aria-invalid={field.aria_invalid}
              aria-describedby={field.described_by}
            />
            <:hint>Optional. An email or a profile where the team can answer you.</:hint>
          </Primitives.field>
          <Primitives.button type="submit" phx-disable-with="Sending…">Send</Primitives.button>
        </.form>
      </section>
    </div>
    """
  end

  defp time(at), do: Calendar.strftime(at, "%-d %b %Y, %H:%M UTC")
end
