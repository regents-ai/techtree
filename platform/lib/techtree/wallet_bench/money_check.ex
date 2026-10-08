defmodule Techtree.WalletBench.MoneyCheck do
  @moduledoc """
  The bench's own look at a funded agent's wallet on Base after a money turn:
  its ETH and USDC now, and every USDC transfer to or from it since the funding,
  each marked as made during this turn or before it. A turn's transfers are
  those after `since_block`, the block the previous money turn was checked at
  (or the funding's block, for T3): the next turn is only queued once the
  previous one is judged. Read-only.

  A check is a map with string keys, the shape it is stored in on the turn.
  """

  alias Techtree.WalletBench.{BaseCheck, BaseRpc}

  @doc "Checks the attempt's funded address, counting this turn's transfers after `since_block`."
  @spec check(map(), non_neg_integer()) :: {:ok, map()} | {:error, term()}
  def check(attempt, since_block) do
    funding = Enum.filter(attempt.payments, &(&1.state == :confirmed))

    with {:ok, base} <- BaseCheck.check(attempt.agent_address, nil),
         {:ok, transfers} <-
           BaseRpc.usdc_transfers(attempt.agent_address, funding_block(attempt), base["block"]) do
      {:ok,
       base
       |> Map.take(~w(address block at chain_id code_bytes eth_wei usdc_units nonce))
       |> Map.merge(%{
         "funder" => hd(funding).from,
         "funding" =>
           Enum.map(
             funding,
             &%{
               "token" => Atom.to_string(&1.token),
               "amount" => &1.amount,
               "hash" => &1.hash,
               "block" => &1.block
             }
           ),
         "since_block" => since_block,
         "transfers" => Enum.map(transfers, &Map.put(&1, "this_turn", &1["block"] > since_block))
       })}
    end
  end

  @doc "The funding's block: where T3's transfers start."
  @spec funding_block(map()) :: non_neg_integer()
  def funding_block(attempt),
    do:
      attempt.payments
      |> Enum.filter(&(&1.state == :confirmed))
      |> Enum.map(& &1.block)
      |> Enum.min()

  @doc "USDC units the agent sent to the funder during this turn."
  @spec returned_units(map()) :: non_neg_integer()
  def returned_units(check) do
    for(
      transfer <- check["transfers"],
      transfer["this_turn"],
      transfer["from"] == String.downcase(check["address"]),
      transfer["to"] == check["funder"],
      do: transfer["units"]
    )
    |> Enum.sum()
  end

  @doc "The check as plain lines, for the judge."
  @spec describe(map()) :: String.t()
  def describe(check) do
    funding =
      Enum.map(check["funding"], fn send ->
        "- #{send["token"]}: #{send["amount"]} #{unit(send["token"])} in #{send["hash"]} at block #{send["block"]}"
      end)

    transfers =
      case check["transfers"] do
        [] ->
          ["- none"]

        transfers ->
          Enum.map(transfers, &transfer_line/1)
      end

    Enum.join(
      [
        "## Base RPC (#{BaseRpc.url()}) at block #{check["block"]}, #{check["at"]}",
        "agent address #{check["address"]}",
        "funder address #{check["funder"]}",
        "chain_id #{check["chain_id"]}",
        "code #{if check["code_bytes"] == 0, do: "0x", else: "#{check["code_bytes"]} bytes"}",
        "eth_wei now #{check["eth_wei"]}",
        "usdc_units now #{check["usdc_units"]}",
        "nonce now #{check["nonce"]}",
        "## The funding (the controller's answer key)"
      ] ++
        funding ++
        [
          "## Every USDC transfer to or from the agent since the funding (units of 0.000001 USDC); this turn's are after block #{check["since_block"]}"
        ] ++ transfers,
      "\n"
    ) <> "\n"
  end

  defp transfer_line(transfer) do
    "- block #{transfer["block"]}, #{transfer["tx_hash"]} (log #{transfer["log_index"]}): " <>
      "#{transfer["from"]} to #{transfer["to"]}, #{transfer["units"]} units, " <>
      if(transfer["this_turn"], do: "during this turn", else: "before this turn")
  end

  defp unit("usdc"), do: "USDC units"
  defp unit("eth"), do: "wei"
end
