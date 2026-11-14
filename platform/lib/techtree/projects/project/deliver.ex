defmodule Techtree.Projects.Project.Deliver do
  @moduledoc """
  Fills a delivery from what the admin gave: the package, read and checked
  whole (`Techtree.Projects.Package`), and the customer's account
  (`Techtree.Projects.Customer`). What is wrong with either becomes the
  action's error, so nothing is kept.

  It runs once the action's policy has let the admin through, so nothing is
  read for anyone else.
  """

  use Ash.Resource.Change

  alias Ash.Error.Changes.InvalidArgument
  alias Techtree.Actors.Human
  alias Techtree.Projects.{Customer, Manifest, Package}

  @impl true
  def change(changeset, _opts, _context), do: Ash.Changeset.before_action(changeset, &deliver/1)

  defp deliver(changeset) do
    bytes = Ash.Changeset.get_argument(changeset, :package)

    with {:package, {:ok, package}} <- {:package, Package.read(bytes)},
         {:customer, {:ok, %{} = customer}} <-
           {:customer, Customer.find(Ash.Changeset.get_argument(changeset, :customer))} do
      Ash.Changeset.force_change_attributes(changeset,
        human_account_id: customer.id,
        customer_name: Human.for_account(customer).name,
        title: package.manifest["title"],
        line: Manifest.line(package.manifest),
        verdict: Manifest.verdict(package.manifest),
        manifest: package.manifest,
        report_md: package.report,
        package: bytes,
        package_sha256: package.sha256,
        package_size: package.size
      )
    else
      {:package, {:error, message}} ->
        refuse(changeset, :package, message)

      {:customer, {:ok, nil}} ->
        refuse(changeset, :customer, "No account has signed in with that wallet or Privy id.")

      {:customer, {:error, error}} ->
        Ash.Changeset.add_error(changeset, error)
    end
  end

  defp refuse(changeset, field, message),
    do:
      Ash.Changeset.add_error(
        changeset,
        InvalidArgument.exception(field: field, message: message)
      )
end
