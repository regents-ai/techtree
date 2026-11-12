defmodule Techtree.Agents.Connection do
  @moduledoc """
  The one Regents identity an app keeps when a person connects it to their
  account here, such as Claude: the identity tools of the hosted MCP server.
  Only that app may run them (`Techtree.Agents.Connection.Caller`), with the
  token its connection holds, as itself or as its paired identity;
  `RegentMCPAgents` does the work for the account the token names. register_identity prepares the identity, get_identity reads whether it
  is paired, pair_identity pairs it with the account's own pairing code, and
  check_in tells the person it is active. A refusal carries the site's own
  code, words and `retry_after` when the site answered, such as
  `pairing_code_unknown` or `agent_not_paired`, the seconds to wait when the
  signer or the site answered 429 with them, and the library's words for where
  the connection stands when no answer came
  (`Techtree.Agents.Connection.Refused`).
  """

  use Ash.Resource,
    domain: Techtree.Agents,
    authorizers: [Ash.Policy.Authorizer]

  alias Techtree.Actors.{Agent, ConnectedApp}
  alias Techtree.Agents.Connection.{Caller, Refused}

  actions do
    action :register_identity, :map do
      description "Prepares the connection's identity for the account its token names."
      run fn _input, context -> answer(RegentMCPAgents.register(principal(context))) end
    end

    action :get_identity, :map do
      description "Reads whether the connection's identity is paired."
      run fn _input, context -> answer(RegentMCPAgents.status(principal(context))) end
    end

    action :pair_identity, :map do
      description "Pairs the connection's identity with the account's own pairing code."

      # What `RegentMCPAgents.pair/2` takes, as given: a code and a name of these
      # lengths, untrimmed, and one of the apps whose connection the site serves,
      # which config/runtime.exs sets to Claude alone with the connector's switch.
      argument :code, :string,
        allow_nil?: false,
        constraints: [min_length: 1, max_length: 128, trim?: false],
        description: "Your person's one-use pairing code, 1 to 128 characters."

      argument :name, :string,
        allow_nil?: false,
        constraints: [min_length: 1, max_length: 100, trim?: false],
        description: "The name your person will see for you, 1 to 100 characters."

      argument :harness, :atom,
        allow_nil?: false,
        constraints: [one_of: [:claude]],
        description: "The app you are."

      run fn %{arguments: %{code: code, name: name, harness: harness}}, context ->
        args = %{"code" => code, "name" => name, "harness" => Atom.to_string(harness)}
        answer(RegentMCPAgents.pair(principal(context), args))
      end
    end

    action :check_in, :map do
      description "Checks in as the paired identity and reads the account it is paired with."
      run fn _input, context -> answer(RegentMCPAgents.check_in(principal(context))) end
    end
  end

  policies do
    policy always() do
      authorize_if Caller
    end
  end

  defp principal(%{actor: %ConnectedApp{principal: principal}}), do: principal
  defp principal(%{actor: %Agent{connection: %{} = principal}}), do: principal

  defp answer({:ok, answer}), do: {:ok, answer}

  defp answer({:answer, _status, %{"error" => %{} = error}, retry_after}),
    do: {:error, Refused.exception(error: error, retry_after: retry_after)}

  defp answer({:refused, _status, error}), do: {:error, Refused.exception(error: error)}
  defp answer({:error, {:rate_limited, seconds}}), do: {:error, Refused.exception(wait: seconds)}
  defp answer(_no_answer), do: {:error, Refused.exception([])}
end
