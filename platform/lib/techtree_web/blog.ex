defmodule TechtreeWeb.Blog do
  @moduledoc "This product's repository-owned, release-safe blog catalog."
  use RegentBlog.Catalog, root: Path.expand("../../../blog", __DIR__)
end
