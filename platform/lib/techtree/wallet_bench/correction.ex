defmodule Techtree.WalletBench.Correction do
  @moduledoc """
  A reviewer's correction to one of the judge's checks, as an operator runs it:
  `mix techtree.wallet_bench check` and `correct` locally, and on a deployed
  release these functions by release RPC, in the running site, so open pages
  see the change. A turn is named by its attempt and its test as the bench
  names it (`T2`, `T2-signature`); a check by its id (`C6`).

  `check/3` only reads. `correct/7` runs the turn's `:correct_check` action
  (`Techtree.WalletBench.Turn.Changes.CorrectCheck`) as the named operator and
  returns the check before and after; run again with the same answer, it
  changes nothing and records no second event.
  """

  alias Techtree.Actors.Operator
  alias Techtree.WalletBench
  alias Techtree.WalletBench.Catalog

  @doc "One check of a turn's ruling, as stored."
  @spec check(String.t(), String.t(), String.t()) :: {:ok, map()} | {:error, String.t()}
  def check(attempt_id, test, criterion) do
    with {:ok, turn} <- turn(attempt_id, test), do: stored(turn, test, criterion)
  end

  @doc "Sets one check of a judged turn's ruling to `value` with the reviewer's reason; returns it before and after."
  @spec correct(
          String.t(),
          String.t(),
          String.t(),
          String.t(),
          String.t(),
          String.t(),
          String.t()
        ) ::
          {:ok, %{before: map(), after: map()}} | {:error, String.t()}
  def correct(attempt_id, test, criterion, value, reason, reviewer, operator) do
    with {:ok, turn} <- turn(attempt_id, test),
         {:ok, before} <- stored(turn, test, criterion) do
      # Operator-only correction; public policies deliberately deny this write.
      case WalletBench.correct_turn_check(turn, criterion, value, reason, reviewer,
             actor: %Operator{name: operator},
             authorize?: false
           ) do
        {:ok, turn} -> {:ok, %{before: before, after: turn.judgment["criteria"][criterion]}}
        {:error, error} -> {:error, Exception.message(error)}
      end
    end
  end

  defp stored(turn, test, criterion) do
    case turn.judgment do
      %{"criteria" => %{^criterion => check}} -> {:ok, check}
      _judgment -> {:error, "The #{test} ruling has no check #{criterion}"}
    end
  end

  defp turn(attempt_id, name) do
    with {:ok, id} <- uuid(attempt_id),
         {:ok, test} <- test(name) do
      case WalletBench.get_turn(id, test, not_found_error?: false) do
        {:ok, nil} -> {:error, "Attempt #{id} has no #{name} turn"}
        {:ok, turn} -> {:ok, turn}
        {:error, error} -> {:error, Exception.message(error)}
      end
    end
  end

  defp uuid(id) do
    case Ecto.UUID.cast(id) do
      {:ok, id} -> {:ok, id}
      :error -> {:error, "#{inspect(id)} is not an attempt id"}
    end
  end

  defp test(name) do
    case Enum.find(Catalog.tests(), &(Catalog.turn_name(&1) == name)) do
      nil -> {:error, "#{inspect(name)} is not a test"}
      test -> {:ok, test}
    end
  end
end
