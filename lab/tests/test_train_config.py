"""The hosted training config, checked offline with prime CLI 0.20.3's own code: the
same steps `prime train <config>` takes before it would call Prime. Nothing here
reaches Prime; its schema check of the inner prime-rl tables runs on submission."""

import io
from importlib.metadata import version
from pathlib import Path

from prime_cli.api.training import build_payload_from_toml
from prime_cli.commands import rl
from rich.console import Console

from techtree_lab import train_config
from techtree_lab.cli import TRAIN_CONFIG, main


def _quiet() -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    return Console(file=buffer), buffer


def test_prime_cli_is_the_pinned_version() -> None:
    assert version("prime") == "0.20.3"


def test_committed_config_is_what_the_cli_writes(tmp_path: Path) -> None:
    written = tmp_path / "config.toml"
    main(["train-config", "--out", str(written)])
    assert written.read_bytes() == TRAIN_CONFIG.read_bytes()


def test_prime_accepts_the_shape(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    train_config.write(path)
    raw = rl._load_toml(str(path))
    assert raw == train_config.config()

    assert not rl._looks_like_lora(raw)

    console, said = _quiet()
    assert rl._training_mode(raw, path, console) == "rl"
    hosted = rl._hosted_config(raw, console)
    assert said.getvalue() == ""
    assert "type" not in raw

    assert rl._config_string(raw, "gpu_type", path) == train_config.GPU_TYPE
    for key in ("image_tag", "volume", "volume_size"):
        assert rl._config_string(raw, key, path) is None
    assert rl._selected_source_ref(None, raw.get("source_ref"), path) is None

    assert "mode" not in hosted
    schema_input = rl._schema_input(hosted)
    assert "name" not in schema_input
    assert schema_input["model"] == {"name": train_config.MODEL}

    payload = build_payload_from_toml(hosted, name=raw.get("name"))
    assert payload == {"config": hosted, "name": train_config.NAME}


def test_config_trains_lora_on_the_train_split() -> None:
    config = train_config.config()
    assert config["mode"] == "rl"
    assert config["max_steps"] == 50
    assert config["model"]["name"] == "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16"
    assert config["trainer"]["model"]["lora"]["rank"] > 0
    train = config["orchestrator"]["train"]
    [source] = train["source"]
    assert source["env"]["taskset"] == {"id": "regents/payment-terms", "split": "train", "seed": 0}
    assert source["env"]["agent"]["harness"] == {"id": "null"}
    assert config["orchestrator"]["batch_size"] % train["group_size"] == 0
    assert config["deployment"]["num_infer_gpus"] > 0 and "inference" in config


def test_held_out_is_measured_before_the_first_step_and_after_the_last() -> None:
    config = train_config.config()
    evaluation = config["orchestrator"]["eval"]
    [source] = evaluation["source"]
    assert source["env"]["taskset"] == {
        "id": "regents/payment-terms",
        "split": "held_out",
        "seed": 0,
    }
    assert evaluation["interval"] == config["max_steps"] and "skip_first_step" not in evaluation
    assert evaluation["sampling"] == {"temperature": 0.0}
    sampling = source["env"]["agent"]["sampling"]
    assert sampling == {"max_tokens": 512, "chat_template_kwargs": {"enable_thinking": False}}
    assert config["orchestrator"]["train"]["source"][0]["env"]["agent"] == source["env"]["agent"]
