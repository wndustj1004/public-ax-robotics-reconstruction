"""설정 파일 로더.

configs/classes.yaml 을 읽어 검증한 뒤 dict 로 돌려준다.
설정을 코드에 박지 않는 이유는, 클래스 문자열과 임계값이
'확인되지 않은 값'이기 때문이다 (RECONSTRUCTION_NOTICE.md 참조).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "classes.yaml"

REQUIRED_TOP_LEVEL = ("class_names", "action_table", "fallback", "detection")
REQUIRED_ACTION_KEYS = ("action", "destination", "requires_human")


class ConfigError(ValueError):
    """설정 파일이 규약을 만족하지 않을 때."""


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """classes.yaml 을 읽어 검증한 dict 를 반환한다.

    Raises:
        ConfigError: 파일이 없거나, 필수 항목이 빠졌거나,
            class_names 와 action_table 의 키가 어긋난 경우.
    """
    cfg_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH

    if not cfg_path.exists():
        raise ConfigError(
            f"설정 파일을 찾을 수 없습니다: {cfg_path}\n"
            "저장소 루트에서 실행했는지 확인하거나 --config 로 경로를 지정하십시오."
        )

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise ConfigError(
            "PyYAML 이 필요합니다.  pip install -r requirements.txt"
        ) from exc

    with cfg_path.open(encoding="utf-8") as fp:
        cfg = yaml.safe_load(fp)

    if not isinstance(cfg, dict):
        raise ConfigError(f"설정 파일의 최상위가 매핑이 아닙니다: {cfg_path}")

    missing = [k for k in REQUIRED_TOP_LEVEL if k not in cfg]
    if missing:
        raise ConfigError(f"설정에 다음 항목이 없습니다: {', '.join(missing)}")

    _validate_action_table(cfg)
    _validate_fallback(cfg)
    return cfg


def _validate_action_table(cfg: dict[str, Any]) -> None:
    names = cfg["class_names"]
    table = cfg["action_table"]

    if not isinstance(names, list) or not names:
        raise ConfigError("class_names 는 비어 있지 않은 목록이어야 합니다.")
    if not isinstance(table, dict):
        raise ConfigError("action_table 은 매핑이어야 합니다.")

    undefined = [n for n in names if n not in table]
    if undefined:
        raise ConfigError(
            "class_names 에는 있으나 action_table 에 항목이 없는 클래스: "
            + ", ".join(undefined)
        )

    orphan = [k for k in table if k not in names]
    if orphan:
        raise ConfigError(
            "action_table 에만 있고 class_names 에 없는 클래스: " + ", ".join(orphan)
        )

    for name, entry in table.items():
        if not isinstance(entry, dict):
            raise ConfigError(f"action_table['{name}'] 이 매핑이 아닙니다.")
        lacking = [k for k in REQUIRED_ACTION_KEYS if k not in entry]
        if lacking:
            raise ConfigError(
                f"action_table['{name}'] 에 다음 키가 없습니다: {', '.join(lacking)}"
            )


def _validate_fallback(cfg: dict[str, Any]) -> None:
    fb = cfg["fallback"]
    if not isinstance(fb, dict):
        raise ConfigError("fallback 은 매핑이어야 합니다.")
    lacking = [k for k in REQUIRED_ACTION_KEYS if k not in fb]
    if lacking:
        raise ConfigError(f"fallback 에 다음 키가 없습니다: {', '.join(lacking)}")
    if fb.get("requires_human") is not True:
        raise ConfigError(
            "fallback.requires_human 은 반드시 true 여야 합니다. "
            "판정할 수 없는 대상을 자동으로 처분하지 않기 위한 안전 조건입니다."
        )
