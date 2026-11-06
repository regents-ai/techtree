defmodule TechtreeWeb.AccountSite do
  @moduledoc """
  This site's own part of pairing and the Agents page: something beside each paired
  agent in the list (`TechtreeWeb.AgentsPanel`), and a line under the pairing box,
  in the pairing window, once an agent has paired (`TechtreeWeb.PairingBox`). The
  template has none, so it reads nothing and both parts draw nothing. A site with
  its own, such as the Keys Keyfleet's agents hold a shard of, keeps it in its copy
  of this module, and the Agents page, its list and the pairing window stay the
  template's.

  A site whose part changes while the page is open sends the agents list
  `site_changed: true` (`Phoenix.LiveView.send_update/3`), and it reads again.
  """
  use TechtreeWeb, :html

  @doc """
  What this site shows for each of the account's agents, by the agent's wallet.
  A wallet with nothing to show is left out, and one whose part couldn't be read
  is `:unavailable`, so its agent says so.
  """
  def read(_account, _wallets), do: %{}

  attr :id, :string, required: true
  attr :part, :any, required: true, doc: "the agent's entry from `read/2`, or nil"

  @doc "Beside an agent in the list, before its own actions."
  def agent(assigns), do: ~H""

  attr :id, :string, required: true
  attr :agent, :map, required: true, doc: "the agent that has just paired"
  attr :part, :any, required: true, doc: "its entry from `read/2`, or nil"

  @doc "Under the pairing box once the agent has paired."
  def paired(assigns), do: ~H""
end
