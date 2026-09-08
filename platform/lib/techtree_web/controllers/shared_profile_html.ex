defmodule TechtreeWeb.SharedProfileHTML do
  use TechtreeWeb, :html

  def show(assigns) do
    ~H"""
    <Layouts.page>
      <Regent.Structure.panel class="shared-profile-page rg-panel__body">
        <Regent.Profile.panel />
        <Regent.Primitives.button variant="quiet" data-profile-sign-out>
          Sign out
        </Regent.Primitives.button>
      </Regent.Structure.panel>
    </Layouts.page>
    """
  end
end
