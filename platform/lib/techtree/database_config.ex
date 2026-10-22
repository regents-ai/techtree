defmodule Techtree.DatabaseConfig do
  @moduledoc """
  The released site's database connections, in ash-template's shape: production reaches
  only the shared cluster's direct host, and staging only the staging database.
  """

  @cluster_id "dzx6qo6xqzvojpv5"
  @cluster_name "regents-platform-prod"
  @production_database_host "direct.dzx6qo6xqzvojpv5.flympg.net"
  # Superseded identities refused in production configuration: the legacy
  # platform application and the retired rehearsal cluster.
  @production_identities ["platform-phx", "regents-pg-test", "nvwq9ozp9ye03kl1"]
  @staging_hosts ["regents-staging-db.flycast", "regents-staging-db.internal"]
  # Staging can never reach production, so it refuses production's cluster, database
  # host and web application anywhere in a URL (host, database or credentials). These
  # terms are staging's alone: production runs as the Fly application techtree-sh,
  # so refusing that name on the production role would refuse its own release commands.
  @staging_refusals [
    @cluster_id,
    @production_database_host,
    "techtree-sh" | @production_identities
  ]
  @deployment_role_error ~s(TECHTREE_DEPLOYMENT_ROLE must be set to "production" or "staging")

  def runtime_config!(getenv \\ &System.get_env/1) do
    role = deployment_role!(getenv)
    getenv |> database_url!("DATABASE_POOLED_URL", role) |> serving()
  end

  def release_config!(getenv \\ &System.get_env/1) do
    role = deployment_role!(getenv)
    if role == :production, do: require_production_target!(getenv)
    database_url!(getenv, "DATABASE_DIRECT_URL", role)
  end

  # The serving connection shares one database with every other site, so it holds
  # five connections, names itself in pg_stat_activity, keeps connection details out
  # of its errors, and gives up on a statement, a lock wait or an idle open transaction
  # before it can stall anyone else. Release commands connect with their own login
  # and none of these limits.
  defp serving(options) do
    Keyword.merge(options,
      pool_size: 5,
      show_sensitive_data_on_connection_error: false,
      parameters: [
        application_name: "techtree-web",
        statement_timeout: "15000",
        lock_timeout: "5000",
        idle_in_transaction_session_timeout: "15000"
      ]
    )
  end

  # No default and no fallback between roles: an unset or unrecognized role stops
  # the boot before any database URL is read.
  defp deployment_role!(getenv) do
    case getenv.("TECHTREE_DEPLOYMENT_ROLE") do
      "production" -> :production
      "staging" -> :staging
      _unset_or_unknown -> raise @deployment_role_error
    end
  end

  # The hosts a role admits and the terms its URL may not name anywhere.
  defp venue(:production), do: {[@production_database_host], @production_identities}
  defp venue(:staging), do: {@staging_hosts, @staging_refusals}

  defp database_url!(getenv, variable, role) do
    {admitted_hosts, refused_terms} = venue(role)

    with value when is_binary(value) and value != "" <- getenv.(variable),
         {:ok, %URI{scheme: scheme, host: host, path: "/" <> database, userinfo: userinfo} = uri}
         when scheme in ["postgres", "postgresql"] <- URI.new(value),
         true <- present?(host) and present?(database) and valid_userinfo?(userinfo),
         false <- refused_identity?(uri, refused_terms),
         admitted_host = String.downcase(host),
         true <- admitted_host in admitted_hosts,
         true <- uri.port in [nil, 5432] and uri.query in [nil, ""] and valid_ecto_url?(value) do
      connection_options(URI.to_string(%{uri | host: admitted_host}), admitted_host)
    else
      value when value in [nil, ""] -> raise "#{variable} is required"
      _ -> raise "#{variable} must be a valid PostgreSQL URL for the approved target"
    end
  end

  defp valid_ecto_url?(value) do
    Ecto.Repo.Supervisor.parse_url(value)
    true
  rescue
    _error -> false
  end

  # Every admitted host is fixed by its hostname alone, so the URL may carry no port
  # other than PostgreSQL's and no query option: Ecto turns every URL query key into
  # an atom and merges parsed URL options after the explicit Repo configuration, so a
  # query could otherwise weaken TLS or replace the endpoint after these checks.
  defp connection_options(url, host) do
    options = [url: url, port: 5432, socket_options: [:inet6]]
    if host == @production_database_host, do: [ssl: ssl(host)] ++ options, else: options
  end

  defp ssl(host) do
    [
      verify: :verify_peer,
      # Read before the application loads castore into `cacerts_get/0`.
      cacertfile: CAStore.file_path(),
      server_name_indication: String.to_charlist(host),
      customize_hostname_check: [match_fun: :public_key.pkix_verify_hostname_match_fun(:https)]
    ]
  end

  defp require_production_target!(getenv) do
    if getenv.("TECHTREE_DATABASE_TARGET_MODE") == "production" and
         getenv.("TECHTREE_DATABASE_CLUSTER_ID") == @cluster_id and
         getenv.("TECHTREE_DATABASE_CLUSTER_NAME") == @cluster_name and
         not names_any?(getenv.("FLY_APP_NAME"), @production_identities) do
      :ok
    else
      raise "database migration requires production mode for cluster dzx6qo6xqzvojpv5 named regents-platform-prod"
    end
  end

  defp valid_userinfo?(userinfo) when is_binary(userinfo),
    do: userinfo |> String.split(":", parts: 2) |> Enum.map(&present?/1) == [true, true]

  defp valid_userinfo?(_userinfo), do: false

  defp refused_identity?(%URI{} = uri, refused_terms) do
    Enum.any?([uri.host, uri.path, uri.userinfo], &names_any?(&1, refused_terms))
  end

  defp names_any?(value, terms) when is_binary(value) do
    decoded = value |> decode() |> String.downcase()
    Enum.any?(terms, &String.contains?(decoded, &1))
  end

  defp names_any?(_value, _terms), do: false

  defp decode(value) do
    URI.decode(value)
  rescue
    _error -> value
  end

  defp present?(value), do: is_binary(value) and String.trim(value) != ""
end
