defmodule TechtreeWeb.SharedProfileHTML do
  use TechtreeWeb, :html

  def show(assigns) do
    ~H"""
    <main id="main-content" class="shared-profile-page">
      <Regent.Profile.panel />
      <Regent.Primitives.button variant="quiet" data-profile-sign-out>
        Sign out
      </Regent.Primitives.button>
    </main>
    """
  end
end
