from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    service_name: str
    assets_dir: Path
    output_dir: Path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    repo_root = Path(__file__).resolve().parents[3]

    assets_dir = Path(os.getenv("VIDEO_EDITTED_ASSETS_DIR", repo_root / "assets"))
    output_dir = Path(os.getenv("VIDEO_EDITTED_OUTPUT_DIR", repo_root / "output"))

    return Settings(
        service_name="video-editted-backend",
        assets_dir=assets_dir,
        output_dir=output_dir,
    )

