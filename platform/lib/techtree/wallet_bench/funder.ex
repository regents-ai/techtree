defmodule Techtree.WalletBench.Funder do
  @moduledoc """
  The bench's funder wallet on Base, used only to fund money attempts (Sean,
  8 October 2026: 1 a). Its private key is the site's `WALLETBENCH_FUNDER_KEY`
  setting, `0x` and 64 hex digits, read from the environment each time a send
  is signed and never kept: not in a job's arguments, a database row, a
  process's state or a log. Nothing here prints or inspects it.
  """

  alias RegentChain.Transaction

  @doc "The funder's address, in lowercase."
  @spec address() :: {:ok, String.t()} | {:error, String.t()}
  def address do
    with {:ok, key} <- key(),
         {:ok, address} <- Transaction.address(key) do
      {:ok, address}
    else
      _unusable -> {:error, unusable()}
    end
  end

  @doc "Signs one EIP-1559 send from the funder (`RegentChain.Transaction.sign/2`)."
  @spec sign(Transaction.fields()) ::
          {:ok, %{raw: String.t(), hash: String.t()}} | {:error, String.t()}
  def sign(fields) do
    case key() do
      {:ok, key} -> signed(Transaction.sign(fields, key))
      :error -> {:error, unusable()}
    end
  end

  defp signed({:ok, signed}), do: {:ok, signed}
  defp signed(:error), do: {:error, "The funding send's fields were refused by the signer."}

  defp key do
    with "0x" <> hex when byte_size(hex) == 64 <- System.get_env("WALLETBENCH_FUNDER_KEY", ""),
         {:ok, key} <- Base.decode16(hex, case: :mixed) do
      {:ok, key}
    else
      _unusable -> :error
    end
  end

  defp unusable,
    do: "The funder's key is not set on this site, or is not 0x and 64 hex digits."
end
