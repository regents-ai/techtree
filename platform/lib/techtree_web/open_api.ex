defmodule TechtreeWeb.OpenAPI do
  @moduledoc """
  The OpenAPI 3.1 description of every machine address this site answers:
  the public read API, the one public write, the owner-only profile, and the
  health check.

  Each operation says what its controller actually sends. Documents this site
  serves byte for byte (the catalog, the bootstrap contract, catalog objects)
  are described by what they are rather than restated field by field, because
  their fields belong to the release that generated them.
  """

  alias Techtree.Network
  alias TechtreeWeb.Endpoint

  @digest_pattern "^sha256:[0-9a-f]{64}$"
  @request_rate_limit Application.compile_env!(:techtree, :request_rate_limit)
  @climb_objects ~w(climb campaign execution_plan data_policy taskset_validation)

  @doc "The OpenAPI document, addressed at this deployment."
  @spec document() :: map()
  def document do
    %{
      "openapi" => "3.1.0",
      "info" => %{
        "title" => "Techtree",
        "version" => "3",
        "summary" =>
          "Controlled Skill comparisons with signed results anyone can verify offline.",
        "description" =>
          "The public catalog of Climbs, the log of published Results, the one address " <>
            "that accepts a signed Result bundle or its withdrawal, an agent's pairing " <>
            "with its person's Regent account, and the owner-only shared profile. Reads need no account. Every error is an `error` object " <>
            "with a stable code: a refusal from an address says whether retrying could " <>
            "help, and an unknown address, an unreadable body, a request over the rate " <>
            "limit or an unexpected failure says what to do next. A breaking change " <>
            "ships with a new major `info.version` and is listed in the documentation's " <>
            "versioning and deprecation section the same day.",
        "license" => %{"name" => "MIT", "identifier" => "MIT"},
        "contact" => %{"name" => "Regents Labs", "email" => "build@regents.sh"}
      },
      "servers" => [%{"url" => Endpoint.url()}],
      "security" => [],
      "externalDocs" => %{"url" => Endpoint.url() <> "/docs"},
      "paths" => paths() |> Map.new(fn {path, item} -> {path, with_rate_limits(item)} end),
      "components" => components()
    }
  end

  defp paths do
    %{
      "/healthz" => %{
        "get" => %{
          "operationId" => "getHealth",
          "summary" => "Whether a catalog release is being served",
          "description" =>
            "Healthy means an active, completed catalog release is served. Without one " <>
              "the answer is 503 with `status` set to `unavailable`.",
          "responses" => %{
            "200" => json("A catalog release is being served.", ref("Health")),
            "503" => json("No catalog release is being served.", ref("Health"))
          }
        }
      },
      "/api/v1/bootstrap" => %{
        "get" => %{
          "operationId" => "getBootstrap",
          "summary" => "The installation contract for this release channel",
          "description" =>
            "The exact bootstrap document of the active release, byte for byte. Every " <>
              "instruction in it is an array of arguments; it carries no credential. " <>
              "The `ETag` is the digest of the bytes.",
          "parameters" => [ref_parameter("IfNoneMatch")],
          "responses" => %{
            "200" => exact("The bootstrap document.", generated("bootstrap document")),
            "304" => not_modified(),
            "503" => error("No release is active, or its bytes no longer match their digest.")
          }
        }
      },
      "/api/v1/catalog" => %{
        "get" => %{
          "operationId" => "getCatalog",
          "summary" => "The catalog index of the active release",
          "description" =>
            "The generated catalog index exactly as it was generated, with its digest " <>
              "as the `ETag`.",
          "parameters" => [ref_parameter("IfNoneMatch")],
          "responses" => %{
            "200" => exact("The catalog index.", generated("catalog index")),
            "304" => not_modified(),
            "503" => error("No release is active, or its bytes no longer match their digest.")
          }
        }
      },
      "/api/v1/climbs/{slug}" => %{
        "get" => %{
          "operationId" => "getClimb",
          "summary" => "A summary of one public Climb",
          "description" =>
            "A convenience summary for choosing between Climbs, addressed by slug. The " <>
              "Climb's own documents are linked under `objects`, not restated.",
          "parameters" => [
            %{
              "name" => "slug",
              "in" => "path",
              "required" => true,
              "description" => "The Climb's slug, such as `hello-world-climb`.",
              "schema" => %{"type" => "string"}
            }
          ],
          "responses" => %{
            "200" => json("The Climb summary.", ref("ClimbSummary")),
            "404" => error("No Climb in the active release has that slug.")
          }
        }
      },
      "/api/v1/objects/{digest}" => %{
        "get" => %{
          "operationId" => "getObject",
          "summary" => "One content-addressed object, byte for byte",
          "description" =>
            "The exact bytes filed under a digest: a catalog object of the active " <>
              "release, or the starter Skill this release ships. The bytes are hashed " <>
              "again before they are sent. A content address never changes meaning, so " <>
              "the response may be cached forever.",
          "parameters" => [
            digest_parameter("digest", "The object's digest."),
            ref_parameter("IfNoneMatch")
          ],
          "responses" => %{
            "200" => %{
              "description" =>
                "The object's exact bytes, in the media type it was published with.",
              "headers" => exact_headers(),
              "content" => %{
                "application/json" => %{"schema" => generated("protocol object")},
                "text/markdown" => %{"schema" => %{"type" => "string"}}
              }
            },
            "304" => not_modified(),
            "400" =>
              error("The digest is not `sha256:` followed by 64 lowercase hex characters."),
            "404" => error("Nothing is published under that digest."),
            "503" => error("The stored bytes no longer match their digest.")
          }
        }
      },
      "/api/v1/publications" => %{
        "get" => %{
          "operationId" => "listPublications",
          "summary" => "One page of the Result log, newest arrival first",
          "description" =>
            "Published Results in arrival order and no other. A log sequence is handed " <>
              "out in arrival order and may have gaps; it is not a rank. Withdrawn " <>
              "entries stay on the log with `withdrawn_at` set.",
          "parameters" => [
            %{
              "name" => "before_sequence",
              "in" => "query",
              "description" =>
                "Return entries before this log sequence, taken from an entry you already hold.",
              "schema" => %{"type" => "integer", "minimum" => 1}
            },
            %{
              "name" => "limit",
              "in" => "query",
              "description" => "How many entries to return.",
              "schema" => %{
                "type" => "integer",
                "minimum" => 1,
                "maximum" => Network.maximum_page_size(),
                "default" => Network.default_page_size()
              }
            },
            %{
              "name" => "agent",
              "in" => "query",
              "description" => "Only Results from this agent harness. Sent with `agent_version`.",
              "schema" => %{"type" => "string", "minLength" => 1, "maxLength" => 128}
            },
            %{
              "name" => "agent_version",
              "in" => "query",
              "description" => "Only Results from this harness version. Sent with `agent`.",
              "schema" => %{"type" => "string", "minLength" => 1, "maxLength" => 128}
            },
            %{
              "name" => "model",
              "in" => "query",
              "description" => "Only Results from this model.",
              "schema" => %{"type" => "string", "minLength" => 1, "maxLength" => 512}
            },
            %{
              "name" => "challenge",
              "in" => "query",
              "description" => "Only Results for this Campaign, by its digest.",
              "schema" => %{"type" => "string", "minLength" => 1, "maxLength" => 512}
            }
          ],
          "responses" => %{
            "200" => json("One page of the log.", ref("PublicationLog")),
            "400" => error("A query parameter is not in the documented form.")
          }
        },
        "post" => %{
          "operationId" => "createPublication",
          "summary" => "Publish a finished Result, or withdraw one already published",
          "description" =>
            "The one public write. The body is either a publication submission (a " <>
              "finished run's proof bundle) or a signed withdrawal request; each declares " <>
              "what it is in its own `schema_version`. Every check runs before anything " <>
              "is stored, and a refusal names the check that failed. The body must be " <>
              "`application/json` and at most #{Network.maximum_body_bytes()} bytes. " <>
              "Publishing is rate limited per caller.",
          "parameters" => [
            header_parameter(
              "x-techtree-contributor-address",
              "An Ethereum address to be recognised by later. Kept apart from the Result and never published."
            ),
            header_parameter(
              "x-techtree-skill-name",
              "A name for the Skill, sent beside the signed bundle. It is shown with the " <>
                "published Result as given by the publisher, and Techtree does not check it."
            ),
            header_parameter(
              "x-techtree-skill-github-url",
              "A GitHub address for the Skill, sent beside the signed bundle. It is shown with " <>
                "the published Result as given by the publisher. Techtree does not check it, and " <>
                "it says nothing about who owns the repository or what it holds."
            )
          ],
          "requestBody" => %{
            "required" => true,
            "content" => %{
              "application/json" => %{
                "schema" => %{
                  "oneOf" => [ref("PublicationSubmission"), ref("WithdrawalRequest")]
                }
              }
            }
          },
          "responses" => %{
            "200" =>
              json(
                "The same submission was already published, and its original receipt is " <>
                  "returned; or a withdrawal was recorded, or was already recorded and its " <>
                  "original receipt is returned.",
                %{"oneOf" => [ref("SignedReceipt"), ref("SignedWithdrawalReceipt")]}
              ),
            "201" =>
              "The Result was published."
              |> json(ref("SignedReceipt"))
              |> Map.put("headers", %{
                "Location" => %{
                  "description" => "Where the new log entry is read.",
                  "schema" => %{"type" => "string"}
                }
              }),
            "400" =>
              json(
                "The body is not one of the two documents, or not JSON.",
                ref("Error")
              ),
            "404" => error("The withdrawal names no published Result."),
            "409" => error("A different document was already published for this run."),
            "413" => json("The body is larger than the limit.", ref("Error")),
            "422" => error("A check on the bundle or the withdrawal failed; the code names it."),
            "429" =>
              "Too many publications from this caller; retry after the stated seconds."
              |> error()
              |> Map.put("headers", %{"Retry-After" => header_ref("RetryAfter")}),
            "503" =>
              error(
                "The site cannot sign a new receipt right now, so nothing was recorded; " <>
                  "the same body can be sent again."
              )
          }
        }
      },
      "/api/v1/publications/{bundle_digest}" => %{
        "get" => %{
          "operationId" => "getPublication",
          "summary" => "One published Result",
          "description" =>
            "Everything this site says about one published Result, recomputed from bytes " <>
              "that verified. It is not the submitted bundle; that is at `/bundle`.",
          "parameters" => [digest_parameter("bundle_digest", "The Result bundle's digest.")],
          "responses" => %{
            "200" => json("The log entry.", ref("PublicationEntry")),
            "400" => error("The digest is not in the documented form."),
            "404" => error("No Result is published under that digest.")
          }
        }
      },
      "/api/v1/publications/{bundle_digest}/bundle" => %{
        "get" => %{
          "operationId" => "getPublicationBundle",
          "summary" => "The exact bytes a Result was submitted as",
          "description" =>
            "The submitted document byte for byte, never re-encoded, so its signatures " <>
              "can be checked offline against what the participant signed.",
          "parameters" => [
            digest_parameter("bundle_digest", "The Result bundle's digest."),
            ref_parameter("IfNoneMatch")
          ],
          "responses" => %{
            "200" => exact("The submitted bundle.", ref("PublicationSubmission")),
            "304" => not_modified(),
            "400" => error("The digest is not in the documented form."),
            "404" => error("No Result is published under that digest."),
            "410" => error("The participant withdrew this Result; its log entry remains.")
          }
        }
      },
      "/api/v1/publication-keys/{key_id}" => %{
        "get" => %{
          "operationId" => "getPublicationKey",
          "summary" => "The public key this site countersigns receipts with",
          "description" =>
            "Served at its own fingerprint, so a receipt's `key_id` is the address of the " <>
              "key that checks it.",
          "parameters" => [
            digest_parameter("key_id", "The key's fingerprint."),
            ref_parameter("IfNoneMatch")
          ],
          "responses" => %{
            "200" => exact("The public key.", ref("PublicKey")),
            "304" => not_modified(),
            "404" => error("This site countersigns with no key under that fingerprint."),
            "503" => error("This site holds no signing key.")
          }
        }
      },
      "/api/agents/v1/pair" => %{
        "post" => %{
          "operationId" => "pairAgent",
          "summary" => "Pair an agent with its person's Regent account",
          "description" =>
            "The agent sends the pairing code its person made on regents.sh, a name and " <>
              "what it runs on, signed with its own key. One pairing works on every Regent " <>
              "site. A code works once and expires ten minutes after it was made.",
          "security" => [%{"AgentSignature" => []}],
          "requestBody" => %{
            "required" => true,
            "content" => %{"application/json" => %{"schema" => ref("AgentPairing")}}
          },
          "responses" => %{
            "201" => json("The agent is paired.", agent_data(ref("PairedAgent"))),
            "400" =>
              error(
                "`pairing_failed`: the code is used, expired or mistyped. `harness_unknown`: " <>
                  "`harness` is not on the list."
              ),
            "401" => error("`verification_failed`: the signature could not be verified."),
            "503" =>
              error("`verification_unavailable`: the sign-in service could not be reached.")
          }
        }
      },
      "/api/agents/v1/me" => %{
        "get" => %{
          "operationId" => "getAgentCheckIn",
          "summary" => "An agent checks in with the pairing it holds",
          "description" =>
            "Signed with the agent's own key, with no body. Techtree keeps no account " <>
              "for a person, so `account` is always empty here.",
          "security" => [%{"AgentSignature" => []}],
          "responses" => %{
            "200" => json("The agent's pairing.", agent_data(ref("AgentCheckIn"))),
            "401" => error("`verification_failed`: the signature could not be verified."),
            "404" => error("`not_paired`: this agent is not paired with an account."),
            "503" =>
              error("`verification_unavailable`: the sign-in service could not be reached.")
          }
        }
      },
      "/api/v1/profile" => %{
        "get" => %{
          "operationId" => "getProfile",
          "summary" => "The signed-in owner's shared profile",
          "security" => [%{"PrivyAccess" => [], "PrivyIdentity" => []}],
          "responses" =>
            profile_responses(%{
              "200" => json("The owner's profile.", ref("ProfileResponse")),
              "404" => error("No profile exists yet; sync first.")
            })
        },
        "patch" => %{
          "operationId" => "updateProfile",
          "summary" => "Change the owner's display name or selected wallet",
          "security" => [%{"PrivyAccess" => [], "PrivyIdentity" => []}],
          "parameters" => [
            header_parameter(
              "x-regent-profile-id",
              "When sent, the update applies only if it names the owner's profile."
            )
          ],
          "requestBody" => %{
            "required" => true,
            "content" => %{"application/json" => %{"schema" => ref("ProfileUpdate")}}
          },
          "responses" =>
            profile_responses(%{
              "200" => json("The updated profile.", ref("ProfileResponse")),
              "400" => json("The body is not valid JSON.", ref("Error")),
              "413" => json("The body is larger than 8 KiB.", ref("Error")),
              "415" => error("The body is not `application/json`."),
              "422" => error("The update is not valid.")
            })
        }
      },
      "/api/v1/profile/sync" => %{
        "post" => %{
          "operationId" => "syncProfile",
          "summary" => "Create or refresh the owner's profile from their sign-in",
          "description" =>
            "Reads the linked wallets and X account from the owner's verified sign-in " <>
              "and records them. Takes no request body.",
          "security" => [%{"PrivyAccess" => [], "PrivyIdentity" => []}],
          "responses" =>
            profile_responses(%{
              "200" => json("The created or refreshed profile.", ref("ProfileResponse")),
              "409" => error("The sign-in is older than, or conflicts with, the one on record.")
            })
        }
      }
    }
  end

  defp components do
    %{
      "securitySchemes" => %{
        "AgentSignature" => %{
          "type" => "apiKey",
          "in" => "header",
          "name" => "signature",
          "description" =>
            "A signature over the request made with the agent's own key, as " <>
              "https://siwa.regents.sh/skill.md describes."
        },
        "PrivyAccess" => %{
          "type" => "http",
          "scheme" => "bearer",
          "description" => "The Privy access token of the signed-in owner."
        },
        "PrivyIdentity" => %{
          "type" => "apiKey",
          "in" => "header",
          "name" => "privy-id-token",
          "description" => "The Privy identity token paired with the access token."
        }
      },
      "headers" => %{
        "RateLimitPolicy" => %{
          "description" =>
            "The budget this request counted against, as \"policy\";q=requests;w=window seconds. " <>
              "Each client address has #{@request_rate_limit[:limit]} requests per " <>
              "#{@request_rate_limit[:window_seconds]} seconds, `default`, shared by the health " <>
              "check and the API. Publishing and withdrawing count against their own budget, " <>
              "`publication`, instead.",
          "schema" => %{"type" => "string"},
          "example" =>
            ~s("default";q=#{@request_rate_limit[:limit]};w=#{@request_rate_limit[:window_seconds]})
        },
        "RateLimit" => %{
          "description" =>
            "What is left of that budget, as \"policy\";r=remaining;t=seconds until the window resets.",
          "schema" => %{"type" => "string"},
          "example" => ~s("default";r=#{@request_rate_limit[:limit] - 1};t=42)
        },
        "RetryAfter" => %{
          "description" => "Seconds to wait before the window resets.",
          "schema" => %{"type" => "integer", "minimum" => 1}
        }
      },
      "parameters" => %{
        "IfNoneMatch" => %{
          "name" => "If-None-Match",
          "in" => "header",
          "description" => "A digest you already hold, quoted; a match answers 304.",
          "schema" => %{"type" => "string"}
        }
      },
      "schemas" => schemas()
    }
  end

  defp schemas do
    %{
      "Error" => %{
        "type" => "object",
        "required" => ["error"],
        "properties" => %{
          "error" => %{
            "type" => "object",
            "required" => ["code", "message", "hint"],
            "properties" => %{
              "code" => %{
                "type" => "string",
                "description" =>
                  "A stable code, such as `publication_missing`, `not_found` or `too_many_requests`."
              },
              "message" => %{"type" => "string"},
              "hint" => %{"type" => "string", "description" => "What to do next."}
            }
          }
        }
      },
      "Digest" => %{"type" => "string", "pattern" => @digest_pattern},
      "Health" => %{
        "type" => "object",
        "required" => ["status", "channel", "catalog_import_status", "deployed_source_revision"],
        "properties" => %{
          "status" => %{"type" => "string", "enum" => ["ok", "unavailable"]},
          "channel" => %{"type" => "string"},
          "catalog_import_status" => %{"type" => "string"},
          "catalog_digest" => ref("Digest"),
          "source_revision" => %{"type" => "string"},
          "imported_at" => %{"type" => "string", "format" => "date-time"},
          "climb_count" => %{"type" => "integer", "minimum" => 0},
          "reason" => %{"type" => "string", "description" => "Why no release is served."},
          "deployed_source_revision" => %{"type" => "string"}
        }
      },
      "LinkedObject" => %{
        "type" => "object",
        "required" => ["digest", "media_type", "url"],
        "properties" => %{
          "digest" => ref("Digest"),
          "media_type" => %{"type" => "string"},
          "url" => %{"type" => "string", "description" => "Relative address of the exact bytes."}
        }
      },
      "ClimbSummary" => %{
        "type" => "object",
        "required" => ["kind", "reference", "slug", "objects"],
        "additionalProperties" => true,
        "properties" => %{
          "kind" => %{"const" => "climb_summary_projection"},
          "reference" => %{"type" => "string"},
          "slug" => %{"type" => "string"},
          "version" => %{"type" => ["string", "integer", "null"]},
          "title" => %{"type" => ["string", "null"]},
          "summary" => %{"type" => ["string", "null"]},
          "status" => %{"type" => ["string", "null"]},
          "climb_digest" => ref("Digest"),
          "campaign_spec_digest" => ref("Digest"),
          "execution_plan_digest" => ref("Digest"),
          "data_policy_digest" => ref("Digest"),
          "validation_receipt_digest" => ref("Digest"),
          "task_count" => %{"type" => ["integer", "null"]},
          "subject_harness" => %{"type" => ["string", "null"]},
          "subject_harness_version" => %{"type" => ["string", "null"]},
          "objects" => %{
            "type" => "object",
            "required" => @climb_objects,
            "properties" => Map.new(@climb_objects, &{&1, ref("LinkedObject")}),
            "additionalProperties" => ref("LinkedObject")
          }
        }
      },
      "PublicationSummary" => %{
        "type" => "object",
        "required" => [
          "log_sequence",
          "bundle_digest",
          "run_id",
          "accepted_at",
          "withdrawn_at",
          "entry_url",
          "participant",
          "climb",
          "campaign_spec_digest",
          "data_policy_digest",
          "skill_digest",
          "subject",
          "result",
          "statuses",
          "decision",
          "proof_grade",
          "checks"
        ],
        "properties" => %{
          "log_sequence" => %{"type" => "integer", "minimum" => 1},
          "bundle_digest" => ref("Digest"),
          "run_id" => %{"type" => "string"},
          "accepted_at" => %{"type" => "string", "format" => "date-time"},
          "withdrawn_at" => %{"type" => ["string", "null"], "format" => "date-time"},
          "entry_url" => %{"type" => "string", "format" => "uri"},
          "participant" => %{
            "type" => "object",
            "required" => ["kind", "key_id", "public_key"],
            "properties" => %{
              "kind" => %{"type" => "string", "enum" => ["local_ed25519"]},
              "key_id" => ref("Digest"),
              "public_key" => %{"type" => "string"}
            }
          },
          "climb" => %{"type" => "string", "description" => "The Climb reference."},
          "campaign_spec_digest" => ref("Digest"),
          "campaign_name" => %{"type" => ["string", "null"]},
          "data_policy_digest" => ref("Digest"),
          "skill_digest" => ref("Digest"),
          "skill_name" => %{
            "type" => ["string", "null"],
            "description" =>
              "A label the publisher sent beside the signed bundle. It is not signed and not checked."
          },
          "skill_github_url" => %{
            "type" => ["string", "null"],
            "description" =>
              "A GitHub address the publisher sent beside the signed bundle. It is not signed and " <>
                "not checked, and says nothing about who owns the repository or what it holds."
          },
          "subject" => %{
            "type" => "object",
            "required" => ["harness", "harness_version", "provider", "model"],
            "properties" => %{
              "harness" => %{"type" => "string"},
              "harness_version" => %{"type" => "string"},
              "provider" => %{"type" => "string"},
              "model" => %{"type" => "string"}
            }
          },
          "result" => %{
            "type" => "object",
            "required" => [
              "baseline_mean",
              "candidate_mean",
              "absolute_delta",
              "wins",
              "losses",
              "ties",
              "task_count"
            ],
            "properties" => %{
              "baseline_mean" => %{"type" => "number"},
              "candidate_mean" => %{"type" => "number"},
              "absolute_delta" => %{"type" => "number"},
              "wins" => %{"type" => "integer", "minimum" => 0},
              "losses" => %{"type" => "integer", "minimum" => 0},
              "ties" => %{"type" => "integer", "minimum" => 0},
              "task_count" => %{"type" => "integer", "minimum" => 0}
            }
          },
          "statuses" => %{"type" => "object"},
          "decision" => %{"type" => "string"},
          "proof_grade" => %{"type" => "string"},
          "checks" => %{
            "type" => "object",
            "required" => ["run", "passed"],
            "properties" => %{
              "run" => %{"type" => "integer", "minimum" => 1},
              "passed" => %{"type" => "integer", "minimum" => 1}
            }
          }
        }
      },
      "PublicationLog" => %{
        "type" => "object",
        "required" => ["schema_version", "entries", "next_before_sequence"],
        "properties" => %{
          "schema_version" => %{"const" => "techtree.publication-log.v1alpha1"},
          "entries" => %{"type" => "array", "items" => ref("PublicationSummary")},
          "next_before_sequence" => %{
            "type" => ["integer", "null"],
            "description" => "Pass as `before_sequence` for the next page; null on the last page."
          }
        }
      },
      "PublicationEntry" => %{
        "allOf" => [
          ref("PublicationSummary"),
          %{
            "type" => "object",
            "required" => ["schema_version", "task_deltas", "receipt"],
            "properties" => %{
              "schema_version" => %{"const" => "techtree.publication-entry.v1alpha1"},
              "task_deltas" => %{"type" => "array", "items" => %{"type" => "object"}},
              "receipt" => %{
                "type" => "object",
                "required" => ["payload_digest", "key_id"],
                "properties" => %{
                  "payload_digest" => ref("Digest"),
                  "key_id" => ref("Digest")
                }
              }
            }
          }
        ]
      },
      "PublicationSubmission" => %{
        "type" => "object",
        "description" =>
          "A finished run's proof bundle. Exactly these four members; `files` maps each " <>
            "relative path in the bundle to its bytes in canonical base64.",
        "required" => ["schema_version", "run_id", "bundle_digest", "files"],
        "additionalProperties" => false,
        "properties" => %{
          "schema_version" => %{"const" => "techtree.publication-submission.v1alpha1"},
          "run_id" => %{"type" => "string"},
          "bundle_digest" => ref("Digest"),
          "files" => %{
            "type" => "object",
            "additionalProperties" => %{"type" => "string", "contentEncoding" => "base64"}
          }
        }
      },
      "Signature" => %{
        "type" => "object",
        "required" => ["algorithm", "key_id", "signature"],
        "properties" => %{
          "algorithm" => %{"const" => "ed25519"},
          "key_id" => ref("Digest"),
          "signature" => %{"type" => "string", "contentEncoding" => "base64"}
        }
      },
      "PublicKey" => %{
        "type" => "object",
        "required" => ["algorithm", "key_id", "public_key"],
        "additionalProperties" => false,
        "properties" => %{
          "algorithm" => %{"const" => "ed25519"},
          "key_id" => ref("Digest"),
          "public_key" => %{"type" => "string", "contentEncoding" => "base64"}
        }
      },
      "WithdrawalRequest" => %{
        "type" => "object",
        "description" => "A participant's signed request to withdraw a Result they published.",
        "required" => ["payload", "payload_digest", "signature"],
        "properties" => %{
          "payload" => %{
            "type" => "object",
            "required" => ["schema_version", "bundle_digest", "requested_at"],
            "properties" => %{
              "schema_version" => %{"const" => "techtree.publication-withdrawal.v1alpha1"},
              "bundle_digest" => ref("Digest"),
              "requested_at" => %{"type" => "string", "format" => "date-time"}
            }
          },
          "payload_digest" => ref("Digest"),
          "signature" => ref("Signature")
        }
      },
      "SignedReceipt" => %{
        "type" => "object",
        "description" => "This site's countersigned receipt for a published Result.",
        "required" => ["payload", "payload_digest", "signature"],
        "properties" => %{
          "payload" => %{
            "type" => "object",
            "required" => [
              "schema_version",
              "id",
              "run_id",
              "log_sequence",
              "bundle_digest",
              "accepted_at",
              "checks",
              "entry_url",
              "public_key"
            ],
            "properties" => %{
              "schema_version" => %{"const" => "techtree.publication-receipt.v1alpha1"},
              "id" => %{"type" => "string"},
              "run_id" => %{"type" => "string"},
              "log_sequence" => %{"type" => "integer"},
              "bundle_digest" => ref("Digest"),
              "accepted_at" => %{"type" => "string", "format" => "date-time"},
              "checks" => %{
                "type" => "array",
                "items" => %{
                  "type" => "object",
                  "required" => ["id", "passed", "detail"],
                  "properties" => %{
                    "id" => %{"type" => "string"},
                    "passed" => %{"type" => "boolean"},
                    "detail" => %{"type" => "string"}
                  }
                }
              },
              "entry_url" => %{"type" => "string", "format" => "uri"},
              "public_key" => ref("PublicKey")
            }
          },
          "payload_digest" => ref("Digest"),
          "signature" => ref("Signature")
        }
      },
      "SignedWithdrawalReceipt" => %{
        "type" => "object",
        "description" => "This site's countersigned record that a Result is withdrawn.",
        "required" => ["payload", "payload_digest", "signature"],
        "properties" => %{
          "payload" => %{
            "type" => "object",
            "required" => [
              "schema_version",
              "bundle_digest",
              "withdrawn_at",
              "entry_url",
              "public_key"
            ],
            "properties" => %{
              "schema_version" => %{
                "const" => "techtree.publication-withdrawal-receipt.v1alpha1"
              },
              "bundle_digest" => ref("Digest"),
              "withdrawn_at" => %{"type" => "string", "format" => "date-time"},
              "entry_url" => %{"type" => "string", "format" => "uri"},
              "public_key" => ref("PublicKey")
            }
          },
          "payload_digest" => ref("Digest"),
          "signature" => ref("Signature")
        }
      },
      "Profile" => %{
        "type" => "object",
        "required" => [
          "profile_id",
          "verification_basis",
          "evidence_issued_at",
          "display_name",
          "linked_wallets",
          "wallet",
          "x"
        ],
        "properties" => %{
          "profile_id" => %{"type" => "string", "format" => "uuid"},
          "verification_basis" => %{"const" => "last_synchronized_privy_proof"},
          "evidence_issued_at" => %{
            "type" => "integer",
            "description" => "When the sign-in proof on record was issued, in Unix seconds."
          },
          "display_name" => %{"type" => ["string", "null"], "maxLength" => 80},
          "linked_wallets" => %{"type" => "array", "items" => %{"type" => "string"}},
          "wallet" => %{
            "type" => "object",
            "required" => ["address", "verified"],
            "properties" => %{
              "address" => %{"type" => ["string", "null"]},
              "verified" => %{
                "type" => "boolean",
                "description" => "Whether the selected wallet is one of the linked wallets."
              }
            }
          },
          "x" => %{
            "type" => ["object", "null"],
            "required" => ["username", "display_name", "verified", "source"],
            "properties" => %{
              "username" => %{"type" => ["string", "null"]},
              "display_name" => %{"type" => ["string", "null"]},
              "verified" => %{"const" => true},
              "source" => %{"const" => "privy"}
            }
          }
        }
      },
      "AgentPairing" => %{
        "type" => "object",
        "required" => ["code", "name", "harness"],
        "additionalProperties" => false,
        "properties" => %{
          "code" => %{"type" => "string", "description" => "The pairing code from the person."},
          "name" => %{"type" => "string", "description" => "What the person calls this agent."},
          "harness" => %{
            "type" => "string",
            "enum" => Enum.map(RegentAgents.Harness.values(), &Atom.to_string/1),
            "description" => "What the agent runs on; `other` for anything not listed."
          }
        }
      },
      "PairedAgent" => %{
        "type" => "object",
        "required" => ["name", "harness", "wallet", "paired_at", "last_contact_at"],
        "properties" => %{
          "name" => %{"type" => "string"},
          "harness" => %{"type" => "string"},
          "wallet" => %{"type" => "string", "description" => "The address of the agent's key."},
          "paired_at" => %{"type" => "string", "format" => "date-time"},
          "last_contact_at" => %{"type" => "string", "format" => "date-time"}
        }
      },
      "AgentCheckIn" => %{
        "allOf" => [
          ref("PairedAgent"),
          %{
            "type" => "object",
            "required" => ["account"],
            "properties" => %{
              "account" => %{"type" => "object", "additionalProperties" => false}
            }
          }
        ]
      },
      "ProfileResponse" => %{
        "type" => "object",
        "required" => ["profile"],
        "properties" => %{"profile" => ref("Profile")}
      },
      "ProfileUpdate" => %{
        "type" => "object",
        "minProperties" => 1,
        "additionalProperties" => false,
        "properties" => %{
          "display_name" => %{"type" => ["string", "null"], "maxLength" => 80},
          "wallet_address" => %{
            "type" => ["string", "null"],
            "description" => "One of the wallets linked to the owner's sign-in."
          }
        }
      }
    }
  end

  defp profile_responses(responses) do
    Map.merge(
      %{
        "401" => error("The paired Privy proof is missing or does not verify."),
        "403" => error("The proof does not grant access to this profile."),
        "503" => error("Profiles are not available right now.")
      },
      responses
    )
  end

  # Every answer from the health check and the API says where the caller stands
  # in its budget; past it the answer is 429. `default` covers what is not
  # listed: an unknown address or method, or an unexpected failure.
  defp with_rate_limits(item) do
    Map.new(item, fn {method, operation} ->
      {method, Map.update!(operation, "responses", &rate_limited/1)}
    end)
  end

  defp rate_limited(responses) do
    responses
    |> Map.put_new(
      "429",
      json(
        "Too many requests from this client address in the current window.",
        ref("Error")
      )
      |> Map.put("headers", %{"Retry-After" => header_ref("RetryAfter")})
    )
    |> Map.new(fn {status, response} ->
      {status,
       Map.update(response, "headers", rate_limit_headers(), &Map.merge(&1, rate_limit_headers()))}
    end)
    |> Map.put(
      "default",
      json(
        "Any other error, such as an unknown address or method.",
        ref("Error")
      )
    )
  end

  defp rate_limit_headers,
    do: %{
      "RateLimit-Policy" => header_ref("RateLimitPolicy"),
      "RateLimit" => header_ref("RateLimit")
    }

  defp header_ref(name), do: %{"$ref" => "#/components/headers/" <> name}

  defp ref(name), do: %{"$ref" => "#/components/schemas/" <> name}
  defp ref_parameter(name), do: %{"$ref" => "#/components/parameters/" <> name}

  defp json(description, schema),
    do: %{
      "description" => description,
      "content" => %{"application/json" => %{"schema" => schema}}
    }

  defp exact(description, schema),
    do: description |> json(schema) |> Map.put("headers", exact_headers())

  defp error(description), do: json(description, ref("Error"))

  defp agent_data(schema),
    do: %{"type" => "object", "required" => ["data"], "properties" => %{"data" => schema}}

  defp not_modified, do: %{"description" => "The caller already holds these exact bytes."}

  defp exact_headers do
    %{
      "ETag" => %{
        "description" => "The quoted digest of the bytes sent.",
        "schema" => %{"type" => "string"}
      }
    }
  end

  defp generated(what) do
    %{
      "type" => "object",
      "description" =>
        "The #{what} exactly as the release generated it; its `schema_version` names its format.",
      "additionalProperties" => true
    }
  end

  defp digest_parameter(name, description) do
    %{
      "name" => name,
      "in" => "path",
      "required" => true,
      "description" => description <> " `sha256:` followed by 64 lowercase hex characters.",
      "schema" => ref("Digest")
    }
  end

  defp header_parameter(name, description) do
    %{
      "name" => name,
      "in" => "header",
      "required" => false,
      "description" => description,
      "schema" => %{"type" => "string"}
    }
  end
end
