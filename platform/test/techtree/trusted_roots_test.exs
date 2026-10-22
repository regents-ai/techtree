defmodule Techtree.TrustedRootsTest do
  # Regression: outbound TLS trusted the image's Debian roots, which still held the
  # eMudhra roots Mozilla dropped after their compromise (20 Oct 2026). Every
  # connection now trusts castore's list, loaded as the application starts.
  use ExUnit.Case, async: true

  test "outbound TLS trusts exactly castore's list, without the dropped eMudhra roots" do
    trusted = MapSet.new(:public_key.cacerts_get(), fn {:cert, der, _decoded} -> der end)

    castore =
      CAStore.file_path()
      |> File.read!()
      |> :public_key.pem_decode()
      |> MapSet.new(fn {:Certificate, der, _} -> der end)

    assert trusted == castore

    for name <- ["emSign Root CA - C1", "emSign ECC Root CA - C3", "emSign ECC Root CA - G3"] do
      refute Enum.any?(trusted, &String.contains?(&1, name)), name
    end
  end
end
