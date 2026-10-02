"""Secret Manager의 설정으로 GCP VM에서 Discord 봇을 실행한다.

bot.py는 bot/ 폴더 옆의 config.json을 읽고, 이 런처가 그 파일을 RAM 설정에 연결한다.
Compute Engine에서 다음 순서로 동작한다.
1. bot/bot.py가 있는지 확인하고 이전 실행이 남긴 링크와 RAM 파일을 지운다.
2. Secret Manager에서 설정 secret을 읽는다(기본값 DISCORD_BOT_CONFIG).
3. secret이 JSON인지 검증한다.
4. JSON을 /dev/shm의 RAM 파일(권한 0600)에 저장한다.
5. bot/ 폴더 옆에 그 RAM 파일을 가리키는 config.json symlink를 만든다.
6. 같은 Python 인터프리터로 bot/bot.py를 실행한다.
7. 봇이 멈추면 symlink와 RAM 파일을 지운다.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from google.cloud import secretmanager

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
BOT_PATH = HERE / "bot.py"
CONFIG_LINK = PROJECT_ROOT / "config.json"

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "discord-party-parrots")
CONFIG_SECRET_ID = os.environ.get("CONFIG_SECRET_ID", "DISCORD_BOT_CONFIG")

RAM_DIR = Path("/dev/shm")
RAM_CONFIG = RAM_DIR / f"discord-bot-config-{os.getuid()}.json"


# Secret Manager에서 봇 설정 JSON을 읽는다.
def read_secret() -> bytes:
    client = secretmanager.SecretManagerServiceClient()
    name = (
        f"projects/{GCP_PROJECT_ID}"
        f"/secrets/{CONFIG_SECRET_ID}"
        f"/versions/latest"
    )
    response = client.access_secret_version(request={"name": name})
    payload = response.payload.data

    # secret이 올바른 JSON이 아니면 bot.py 실행 전에 실패시킨다.
    json.loads(payload.decode("utf-8"))
    return payload


# 이전 실행이 남긴 설정 링크와 RAM 파일을 지운다.
def remove_runtime_config() -> None:
    if CONFIG_LINK.is_symlink():
        try:
            target = os.readlink(CONFIG_LINK)
        except OSError:
            target = ""

        if target == str(RAM_CONFIG):
            CONFIG_LINK.unlink(missing_ok=True)

    RAM_CONFIG.unlink(missing_ok=True)


# 설정을 RAM 파일에 쓰고 config.json 링크로 연결한다.
def prepare_runtime_config(payload: bytes) -> None:
    if not RAM_DIR.is_dir():
        raise RuntimeError("/dev/shm이 없습니다. 이 런처는 Linux VM의 /dev/shm을 사용합니다.")

    # VM에 실제 config.json 파일이 있으면 Secret Manager를 쓰는 의미가 없다.
    if CONFIG_LINK.exists() and not CONFIG_LINK.is_symlink():
        raise RuntimeError(
            f"{CONFIG_LINK}가 일반 파일로 존재합니다. "
            f"VM의 {CONFIG_LINK}를 삭제한 뒤 다시 실행하세요."
        )

    if CONFIG_LINK.is_symlink():
        CONFIG_LINK.unlink()

    RAM_CONFIG.unlink(missing_ok=True)

    fd = os.open(
        RAM_CONFIG,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    try:
        with os.fdopen(fd, "wb") as fp:
            fp.write(payload)
            fp.flush()
            os.fsync(fp.fileno())
    except Exception:
        RAM_CONFIG.unlink(missing_ok=True)
        raise

    CONFIG_LINK.symlink_to(RAM_CONFIG)


# 같은 Python으로 봇을 실행하고 종료 코드를 반환한다.
def run_bot() -> int:
    child = subprocess.Popen(
        [sys.executable, str(BOT_PATH)],
        cwd=str(PROJECT_ROOT),
        start_new_session=True,
    )

    # 받은 종료 신호를 봇 프로세스 그룹에 전달한다.
    def forward_signal(signum: int, _frame: object) -> None:
        if child.poll() is None:
            try:
                os.killpg(child.pid, signum)
            except ProcessLookupError:
                pass

    signal.signal(signal.SIGTERM, forward_signal)
    signal.signal(signal.SIGINT, forward_signal)

    return child.wait()


# 설정 준비, 봇 실행, 정리를 차례로 수행한다.
def main() -> int:
    if not BOT_PATH.is_file():
        raise RuntimeError(f"bot.py를 찾을 수 없습니다: {BOT_PATH}")

    remove_runtime_config()
    payload = read_secret()
    prepare_runtime_config(payload)

    try:
        return run_bot()
    finally:
        remove_runtime_config()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"[run_gcp] {exc}", file=sys.stderr)
        raise SystemExit(1)
