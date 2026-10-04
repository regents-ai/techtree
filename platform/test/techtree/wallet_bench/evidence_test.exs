defmodule Techtree.WalletBench.EvidenceTest do
  # Evidence goes to the private bucket only as a signed request, under the
  # bucket's path, and comes back byte for byte.
  use ExUnit.Case, async: false

  alias Techtree.WalletBench.Evidence

  setup do
    previous = Application.get_env(:techtree, Evidence)

    Application.put_env(:techtree, Evidence,
      endpoint: "https://evidence.example",
      bucket: "walletbench-evidence",
      region: "auto",
      access_key_id: "test-access-key",
      secret_access_key: "test-secret-key",
      req_options: [plug: {Req.Test, __MODULE__}]
    )

    on_exit(fn -> Application.put_env(:techtree, Evidence, previous) end)
  end

  test "stores under the bucket's path with a signed request, and reads back the same bytes" do
    body = <<0, 1, 2, 255>> <> "transcript"

    Req.Test.expect(__MODULE__, 2, fn conn ->
      assert conn.request_path == "/walletbench-evidence/runs/r1/H05%20W03.jsonl"
      assert [authorization] = Plug.Conn.get_req_header(conn, "authorization")
      assert authorization =~ "AWS4-HMAC-SHA256 Credential=test-access-key/"
      assert authorization =~ "/auto/s3/aws4_request"

      case conn.method do
        "PUT" ->
          assert Plug.Conn.get_req_header(conn, "content-type") == ["application/jsonl"]
          {:ok, ^body, conn} = Plug.Conn.read_body(conn)
          Plug.Conn.send_resp(conn, 200, "")

        "GET" ->
          Plug.Conn.send_resp(conn, 200, body)
      end
    end)

    assert :ok = Evidence.put("runs/r1/H05 W03.jsonl", body, "application/jsonl")
    assert {:ok, ^body} = Evidence.get("runs/r1/H05 W03.jsonl")
  end
end
