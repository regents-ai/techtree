defmodule Techtree.Messages.EnquiryTest do
  # Sending an enquiry, through the action the contact form calls:
  # - anyone sends one, and it is kept with every field and when it was sent;
  # - each field is required and bounded, the email has to be one, nothing
  #   hidden gets in, and a refusal keeps nothing;
  # - each address sends 5 an hour, then is refused until the hour passes;
  # - only the site's admins read enquiries.
  use ExUnit.Case, async: false

  alias Techtree.{Accounts, Messages, Repo}
  alias Techtree.Actors.{Human, System}
  alias Techtree.Messages.Enquiry

  @enquiry %{
    name: "Ada Lovelace",
    email: "ada@example.com",
    company: "Analytical Engines",
    service: :evals,
    goal: "Our support agent sends refund requests to the wrong team.\nWe want to measure it."
  }

  setup do
    :ok = Ecto.Adapters.SQL.Sandbox.checkout(Repo)
    %{key: Ecto.UUID.generate()}
  end

  test "an enquiry is kept with every field and when it was sent", %{key: key} do
    assert {:ok, %Enquiry{id: id}} = send_enquiry(@enquiry, key)

    stored = Ash.get!(Enquiry, id, authorize?: false)
    assert Map.take(stored, Map.keys(@enquiry)) == @enquiry
    assert DateTime.diff(DateTime.utc_now(), stored.inserted_at) in 0..60
  end

  test "each field is required and bounded, and a refusal keeps nothing", %{key: key} do
    for {field, value} <- [
          name: nil,
          name: "  ",
          name: String.duplicate("a", 101),
          name: "Ada\u202Egnp.exe",
          email: nil,
          email: "ada",
          email: "ada@example",
          email: "ada lovelace@example.com",
          email: "ada@exa\u200Bmple.com",
          email: String.duplicate("a", 243) <> "@example.com",
          company: nil,
          company: String.duplicate("a", 101),
          company: "Line\nbreak",
          service: nil,
          service: "watchdog",
          goal: nil,
          goal: String.duplicate("a", 2001),
          goal: "carriage\rreturn"
        ] do
      assert {:error, %Ash.Error.Invalid{errors: errors}} =
               send_enquiry(Map.put(@enquiry, field, value), key)

      assert Enum.map(errors, & &1.field) |> Enum.uniq() == [field],
             "#{field} = #{inspect(value)} was refused for #{inspect(errors)}"
    end

    assert count() == 0

    longest = %{
      @enquiry
      | name: String.duplicate("a", 100),
        email: String.duplicate("a", 242) <> "@example.com",
        company: String.duplicate("a", 100),
        goal: String.duplicate("a", 2000)
    }

    assert {:ok, _enquiry} = send_enquiry(longest, key)
    assert count() == 1
  end

  test "each address sends 5 an hour, then is refused until it passes", %{key: key} do
    for n <- 1..5 do
      assert {:ok, _enquiry} = send_enquiry(%{@enquiry | goal: "Enquiry #{n}"}, key)
    end

    assert {:error, %Ash.Error.Invalid{errors: [%Ash.Error.Changes.InvalidChanges{fields: []}]}} =
             send_enquiry(@enquiry, key)

    assert count() == 5
    assert {:ok, _enquiry} = send_enquiry(@enquiry, Ecto.UUID.generate())
  end

  test "only the site's admins read enquiries", %{key: key} do
    {:ok, _enquiry} = send_enquiry(@enquiry, key)
    did = "did:privy:admin-" <> Ecto.UUID.generate()
    put_admins([did])

    admin = %RegentAgents.Person{privy_user_id: did, role: :admin}
    assert %{results: [%Enquiry{name: "Ada Lovelace"}]} = Messages.list_enquiries!(actor: admin)

    for reader <- [
          person(),
          %System{},
          %RegentAgents.Person{privy_user_id: did},
          %RegentAgents.Person{privy_user_id: "did:privy:not-listed", role: :admin},
          nil
        ] do
      assert {:error, %Ash.Error.Forbidden{}} = Messages.list_enquiries(actor: reader)
    end
  end

  defp send_enquiry(input, key), do: Messages.send_enquiry(input, context: %{client_key: key})

  defp count, do: Enquiry |> Ash.read!(authorize?: false) |> length()

  defp person do
    wallet = "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)
    did = "did:privy:enquiry-" <> Ecto.UUID.generate()
    Human.for_account(Accounts.register_verified!(did, wallet, [wallet], actor: %System{}))
  end

  defp put_admins(admins) do
    old = Application.fetch_env(:regent_agents, :admins)
    Application.put_env(:regent_agents, :admins, admins)

    on_exit(fn ->
      case old do
        {:ok, admins} -> Application.put_env(:regent_agents, :admins, admins)
        :error -> Application.delete_env(:regent_agents, :admins)
      end
    end)
  end
end
