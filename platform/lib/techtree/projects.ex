defmodule Techtree.Projects do
  @moduledoc """
  The projects Techtree's team delivers to customers: each one the package a
  piece of work produced (`Techtree.Projects.Package`), with its before and
  after, kept for the customer's account (`Techtree.Projects.Project`).

  The customer reads their own, signed in or through the agent they paired.
  The site's admins find the customer's account, deliver a project to it and
  withdraw one, from the team's page.
  """

  use Ash.Domain, otp_app: :techtree

  resources do
    resource Techtree.Projects.Project do
      define :list_my_projects, action: :mine
      define :get_my_project, action: :own, get_by: [:id], not_found_error?: false
      define :get_my_package, action: :own_package, get_by: [:id], not_found_error?: false
      define :list_team_projects, action: :team
      define :get_team_package, action: :team_package, get_by: [:id], not_found_error?: false
      define :find_customer, action: :find_customer, args: [:customer]
      define :deliver_project, action: :deliver, args: [:customer, :package]
      define :withdraw_project, action: :withdraw
    end
  end
end
