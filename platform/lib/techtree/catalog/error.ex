defmodule Techtree.Catalog.Error do
  @moduledoc """
  The typed failures the catalog subsystem can report.

  Spec section 15 fixes the vocabulary: a stable code, a human message that is
  safe to show a stranger, whether retrying could help, and sanitized details.
  The details of a catalog failure are deliberately limited to catalog-relative
  paths, digests, and object kinds — an absolute path on the serving host is
  internal information (spec section 8.11) and never appears here.
  """

  @typedoc """
  The catalog subset of the spec section 15 error taxonomy.
  """
  @type code ::
          :catalog_bundle_invalid
          | :catalog_object_missing
          | :catalog_object_digest_mismatch
          | :bootstrap_release_missing

  @type t :: %__MODULE__{
          code: code(),
          message: String.t(),
          retryable?: boolean(),
          details: %{optional(String.t()) => term()}
        }

  defexception [:code, :message, details: %{}, retryable?: false]

  @doc """
  A bundle that cannot be read, parsed, or believed as a whole.
  """
  @spec bundle_invalid(String.t(), map()) :: t()
  def bundle_invalid(message, details \\ %{}),
    do: new(:catalog_bundle_invalid, message, details)

  @doc """
  An object the catalog index promises that the bundle does not ship.
  """
  @spec object_missing(String.t(), map()) :: t()
  def object_missing(message, details \\ %{}),
    do: new(:catalog_object_missing, message, details)

  @doc """
  An object whose bytes do not hash to the digest they are filed under.
  """
  @spec object_digest_mismatch(String.t(), map()) :: t()
  def object_digest_mismatch(message, details \\ %{}),
    do: new(:catalog_object_digest_mismatch, message, details)

  @doc """
  A request for release/bootstrap state that no active release provides.
  """
  @spec bootstrap_missing(String.t(), map()) :: t()
  def bootstrap_missing(message, details \\ %{}),
    do: new(:bootstrap_release_missing, message, details)

  @doc """
  One line naming the code and the failure, for logs and release output.
  """
  @spec summary(t()) :: String.t()
  def summary(%__MODULE__{code: code, message: message}), do: "#{code}: #{message}"

  defp new(code, message, details) do
    %__MODULE__{code: code, message: message, details: details, retryable?: false}
  end
end
