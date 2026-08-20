"""The only Verifiers configuration Techtree may emit. Spec section 6.7.

This module is an allow-list, and the allow-list is the control. Verifiers has
a large and growing set of knobs; a Campaign that could reach any of them could
introduce a second difference between baseline and candidate without anyone
being able to name it afterwards. Every model here forbids extra keys, so a
knob Techtree has not deliberately modelled is unrepresentable rather than
merely discouraged.

Several fields are typed as literals rather than validated at runtime, because
"the value is wrong" and "the value cannot be spelled" are different guarantees:

``push: Literal[False]``
    ``EvalConfig.push`` defaults to **true** upstream and uploads the complete
    Episode — prompts and subject replies included — to the Prime platform
    (``docs/verifiers-eval.md``, finding E1). A config that merely forgets to
    set it exfiltrates the participant's trajectories.
``rich: Literal[False]``
    The dashboard is the whole output when it is on; a captured child needs log
    lines.
``shuffle: Literal[False]`` and ``num_rollouts: Literal[1]``
    Decisions document 0001. There is no seed anywhere in the protocol, so a
    shuffled run could not be reproduced by anyone.
``use_bundled_skill: Literal[False]``
    A bundled skill catalogue is an uncontrolled second difference.

``disabled_tools`` is absent by construction. The native Hermes harness accepts
it at config time and then refuses it in the middle of a run, after Docker has
been provisioned (``docs/verifiers-eval.md``, finding E3), so the only safe
place to reject it is here.

The Docker table carries ``allow`` and ``block``, which spec section 6.7 does
not model. Upstream's default egress policy is unrestricted, so without them a
Campaign declaring ``network_policy: "restricted"`` would compile to a
container with open network access.
"""

from __future__ import annotations

import re
from typing import Any, Final, Literal, Self

import tomli_w
from pydantic import BaseModel, ConfigDict, Field, model_validator

from techtree.errors import ValidationError
from techtree.models.campaign import CREDENTIAL_ENV_PATTERN

__all__ = [
    "ALLOWED_CLIENT_HEADERS",
    "EVAL_CONFIG_INVALID",
    "IMAGE_DIGEST_PATTERN",
    "OPEN_BLOCK",
    "OPEN_NETWORK",
    "RESTRICTED_BLOCK",
    "RESTRICTED_NETWORK",
    "DockerRuntimeToml",
    "EnvToml",
    "EvalClientToml",
    "EvalToml",
    "HermesHarnessToml",
    "SamplingToml",
    "SubjectAgentToml",
    "TasksetToml",
    "TimeoutToml",
    "config_to_toml_bytes",
    "egress_for",
]

#: Stable error code. Spec section 6.7.
EVAL_CONFIG_INVALID: Final = "eval_config_invalid"

#: Headers Techtree is allowed to declare on the evaluation client. Empty: the
#: only supported profile routes through the pinned client's own resolution,
#: and a header Techtree invents is a routing decision nobody reviewed. The
#: engine may still *add* headers of its own when it resolves the config
#: (``docs/verifiers-eval.md``); that is upstream's business, not Techtree's.
ALLOWED_CLIENT_HEADERS: Final[frozenset[str]] = frozenset()

#: Framework-only egress: the interception endpoint and nothing else, which is
#: what a restricted subject runtime means. Upstream normalizes an empty
#: allow-list to exactly this pair, so Techtree declares the normalized form
#: rather than the shorthand — otherwise the configuration Techtree compiled
#: and the configuration the engine resolved would disagree at ``block`` on
#: every restricted run.
RESTRICTED_NETWORK: Final[tuple[str, ...]] = ()
RESTRICTED_BLOCK: Final[tuple[str, ...]] = ("*",)
#: Unrestricted egress, upstream's own default spelling.
OPEN_NETWORK: Final[tuple[str, ...]] = ("*",)
OPEN_BLOCK: Final[tuple[str, ...]] = ()

#: An OCI reference that names content rather than a moving tag.
IMAGE_DIGEST_PATTERN: Final = r"@sha256:[0-9a-f]{64}$"

_CREDENTIAL_ENV_RE: Final = re.compile(CREDENTIAL_ENV_PATTERN)
_IMAGE_DIGEST_RE: Final = re.compile(IMAGE_DIGEST_PATTERN)


class TomlModel(BaseModel):
    """A frozen, extra-forbidden fragment of the emitted configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)


class EvalClientToml(TomlModel):
    """The OpenAI-compatible endpoint the evaluation runs against.

    ``base_url`` is deliberately omitted for the supported profile. The pinned
    client resolves a ``PRIME_API_KEY``-keyed endpoint from the environment and
    the active Prime CLI configuration, and writing a URL here would freeze a
    deployment detail into a run's inputs.
    """

    type: Literal["eval"] = "eval"
    api_key_var: str
    base_url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_the_client_names_a_variable_and_no_headers(self) -> Self:
        """Reject a credential value, and any header Techtree may not declare."""
        if _CREDENTIAL_ENV_RE.fullmatch(self.api_key_var) is None:
            raise ValueError(
                "api_key_var must be an uppercase environment-variable name, "
                "never a credential value"
            )
        unknown = sorted(set(self.headers) - ALLOWED_CLIENT_HEADERS)
        if unknown:
            raise ValueError(f"Techtree does not declare client headers; got {unknown}")
        return self


class SamplingToml(TomlModel):
    """How the subject model is sampled."""

    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(ge=1)


class HermesHarnessToml(TomlModel):
    """The pinned Hermes Agent harness and the skills inserted into it."""

    id: Literal["hermes-agent"] = "hermes-agent"
    version: str = Field(min_length=1)
    use_bundled_skill: Literal[False] = False
    skills: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_skill_paths_are_absolute_and_distinct(self) -> Self:
        """Reject a relative or repeated skill path."""
        for path in self.skills:
            if not path.startswith("/"):
                raise ValueError(
                    f"skill paths are absolute run-owned paths; got {path!r}"
                )
        if len(set(self.skills)) != len(self.skills):
            raise ValueError("a harness mounts each skill exactly once")
        return self


class DockerRuntimeToml(TomlModel):
    """Where the subject agent executes."""

    type: Literal["docker"] = "docker"
    image: str = Field(min_length=1)
    allow: list[str] = Field(default_factory=list)
    block: list[str] = Field(default_factory=list)
    cpu: float | None = Field(default=None, gt=0.0)
    memory: float | None = Field(default=None, gt=0.0)

    @property
    def image_is_digest_pinned(self) -> bool:
        """Whether the image reference names content rather than a tag."""
        return _IMAGE_DIGEST_RE.search(self.image) is not None

    @property
    def network_is_restricted(self) -> bool:
        """Whether egress is anything narrower than unrestricted."""
        return list(self.allow) != list(OPEN_NETWORK) or bool(self.block)

    @model_validator(mode="after")
    def _check_the_egress_lists_are_not_both_concrete(self) -> Self:
        """Reject the one egress combination upstream refuses outright."""
        if self.allow and list(self.allow) != list(OPEN_NETWORK) and self.block:
            raise ValueError(
                "a concrete allow list and a block list are mutually exclusive"
            )
        return self


class TimeoutToml(TomlModel):
    """Per-rollout Verifiers lifecycle limits.

    Every one of these defaults to ``None`` upstream, and ``None`` means "no
    limit": the pinned build wraps each phase in ``asyncio.timeout(value)``, and
    ``asyncio.timeout(None)`` is a no-op. A Campaign that declares
    ``timeout_seconds`` and cannot reach this table has declared nothing, which
    is the whole reason the table exists here (decisions document 0029, layer
    A).
    """

    setup: float | None = Field(default=None, gt=0.0)
    rollout: float | None = Field(default=None, gt=0.0)
    finalize: float | None = Field(default=None, gt=0.0)
    scoring: float | None = Field(default=None, gt=0.0)


class SubjectAgentToml(TomlModel):
    """The one seat v0.1 evaluates, named for the role it plays."""

    harness: HermesHarnessToml
    runtime: DockerRuntimeToml
    max_turns: int | None = Field(default=None, ge=1)
    max_input_tokens: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    max_total_tokens: int | None = Field(default=None, ge=1)
    timeout: TimeoutToml = Field(default_factory=TimeoutToml)


class TasksetToml(TomlModel):
    """Which taskset the environment seeds from.

    Only the identifier. Every other taskset field on the pinned reference
    Taskset is a default Techtree does not vary, and a field Techtree does not
    vary should not appear in a document a reader has to check.
    """

    id: str = Field(min_length=1)


class EnvToml(TomlModel):
    """The environment block: the taskset, the subject seat, and the bound.

    The seat is spelled ``subject`` because the reference package's ``Env``
    declares a field of that name; Verifiers stamps the field name onto every
    trace as ``agent.name`` (spec section 6.5). Against an environment without
    that seat the whole configuration is rejected at parse time
    (``docs/verifiers-eval.md``, finding E0).
    """

    taskset: TasksetToml
    subject: SubjectAgentToml
    max_concurrent_agents: int = Field(default=1, ge=1)


class EvalToml(TomlModel):
    """One resolved Techtree experiment as a Verifiers evaluation."""

    model: str = Field(min_length=1)
    client: EvalClientToml
    sampling: SamplingToml
    env: EnvToml
    num_tasks: int = Field(ge=1)
    num_rollouts: Literal[1] = 1
    shuffle: Literal[False] = False
    max_concurrent: int = Field(ge=1)
    rich: Literal[False] = False
    push: Literal[False] = False
    output_dir: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_the_run_is_bounded_and_run_owned(self) -> Self:
        """Reject a relative output directory or an unbounded episode fan-out."""
        if not self.output_dir.startswith("/"):
            raise ValueError(
                "output_dir is an absolute run-owned path; a relative path "
                "lands wherever the child happened to be started"
            )
        if self.env.max_concurrent_agents > self.max_concurrent:
            raise ValueError(
                "max_concurrent_agents cannot exceed max_concurrent; the "
                "product is the number of live subject runs"
            )
        return self


def egress_for(network_policy: str) -> tuple[list[str], list[str]]:
    """Return the ``(allow, block)`` pair one Campaign network policy compiles to.

    The Campaign speaks in intent — restricted or open — and upstream speaks in
    two lists whose meaning depends on each other. This is the single place the
    two vocabularies meet, and it emits the already-normalized form so nothing
    downstream has to know that upstream would have rewritten the shorthand.
    """
    if network_policy == "restricted":
        return list(RESTRICTED_NETWORK), list(RESTRICTED_BLOCK)
    if network_policy == "open":
        return list(OPEN_NETWORK), list(OPEN_BLOCK)
    raise ValidationError(
        f"{network_policy!r} is not a network policy Techtree can compile",
        code=EVAL_CONFIG_INVALID,
        details={"network_policy": network_policy},
    )


def config_to_toml_bytes(config: EvalToml) -> bytes:
    """Serialize one configuration to deterministic TOML bytes.

    ``exclude_none`` matches what the engine itself does when it writes a
    resolved config, so an omitted optional field is absent from both documents
    rather than present as a null in one of them. Field order is declaration
    order, so the same configuration always produces the same bytes.
    """
    try:
        document: dict[str, Any] = config.model_dump(mode="json", exclude_none=True)
        return tomli_w.dumps(document).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValidationError(
            f"the compiled evaluation config is not serializable: {error}",
            code=EVAL_CONFIG_INVALID,
        ) from error
