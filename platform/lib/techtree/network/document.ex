defmodule Techtree.Network.Document do
  @moduledoc """
  Which of the two things a participant may send this actually is.

  Decision 0038 gives this site exactly one address that accepts anything, and
  a participant sends two different documents to it: a finished run they are
  publishing, and a signed request to withdraw one they published. Telling them
  apart is a job for the documents rather than for the URL, because both of them
  already say what they are — a submission declares its schema version at the
  top, and a withdrawal declares its own inside the payload its signature
  covers. Reading that is not guessing.

  Nothing here validates either document. It reads one member and returns a name
  for what it read; `Techtree.Network.Bundle` and
  `Techtree.Network.WithdrawalRequest` do the checking, in full, before anything
  is written. A body that declares neither is refused here, and the refusal says
  what the two documents are rather than that the body was "invalid" — a
  participant whose tooling sent the wrong thing can only fix what they are told
  about.
  """

  alias Techtree.Network.Error
  alias Techtree.Network.WithdrawalRequest

  @submission_version "techtree.publication-submission.v1alpha1"

  @typedoc """
  What arrived.
  """
  @type kind :: :submission | :withdrawal

  @doc """
  The submission schema version, which is what a published run declares.
  """
  @spec submission_version() :: String.t()
  def submission_version, do: @submission_version

  @doc """
  Which document these bytes declare themselves to be.
  """
  @spec kind(binary()) :: {:ok, kind()} | {:error, Error.t()}
  def kind(raw) when is_binary(raw) do
    withdrawal = WithdrawalRequest.schema_version()

    case Jason.decode(raw) do
      {:ok, %{"schema_version" => @submission_version}} ->
        {:ok, :submission}

      {:ok, %{"payload" => %{"schema_version" => ^withdrawal}}} ->
        {:ok, :withdrawal}

      _other ->
        {:error,
         Error.new(
           :submission_malformed,
           "this address takes two documents and this is neither: a " <>
             "#{@submission_version}, which publishes a finished run, or a signed " <>
             "#{withdrawal}, which withdraws one already published"
         )}
    end
  end
end
