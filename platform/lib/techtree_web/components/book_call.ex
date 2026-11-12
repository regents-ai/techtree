defmodule TechtreeWeb.Components.BookCall do
  @moduledoc """
  The Book Call button: the header, the home page and the Watchdog offer all
  show this one. It opens the booking page set in `TECHTREE_BOOK_CALL_URL`
  (`config/runtime.exs`) in a new tab. With no address set it is not shown at
  all.
  """

  use Phoenix.Component

  @doc "The booking page's address, or nil when none is set."
  @spec address() :: String.t() | nil
  def address, do: Application.get_env(:techtree, :book_call)

  attr :variant, :atom, values: [:primary, :secondary], default: :primary
  attr :class, :any, default: nil
  attr :rest, :global

  def book_call(assigns) do
    assigns = assign(assigns, :address, address())

    ~H"""
    <a
      :if={@address}
      class={["rg-button", "rg-button--#{@variant}", @class]}
      href={@address}
      target="_blank"
      rel="noopener"
      {@rest}
    >
      Book Call
    </a>
    """
  end
end
