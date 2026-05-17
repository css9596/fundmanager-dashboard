import logging
import argparse
import atexit
import os
import sys
import time
from bot.trader import TradingBot
from dashboard.monitor import print_startup_banner, render_dashboard
from config import TRADING

LOCK_PATH = "/tmp/fundmanager.lock"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/trading.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _acquire_lock():
    """PID 파일 락 — 중복 실행 방지. 다른 봇이 이미 돌고 있으면 종료."""
    if os.path.exists(LOCK_PATH):
        try:
            with open(LOCK_PATH) as f:
                old_pid = int(f.read().strip())
            # 해당 PID 프로세스가 실제 살아있는지 확인
            try:
                os.kill(old_pid, 0)  # signal 0 = 존재 확인만
                print(f"❌ 이미 봇이 동작 중입니다 (PID={old_pid}). "
                      f"중복 실행 방지를 위해 종료합니다.")
                print(f"   기존 봇을 끄려면: kill {old_pid}")
                sys.exit(1)
            except ProcessLookupError:
                # 죽은 PID — 락 파일만 남음. 정리하고 진행
                os.remove(LOCK_PATH)
        except (ValueError, FileNotFoundError):
            try:
                os.remove(LOCK_PATH)
            except FileNotFoundError:
                pass

    with open(LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(_release_lock)


def _release_lock():
    try:
        if os.path.exists(LOCK_PATH):
            with open(LOCK_PATH) as f:
                if int(f.read().strip()) == os.getpid():
                    os.remove(LOCK_PATH)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="FundManager 트레이딩 봇")
    parser.add_argument("--live", action="store_true", help="실거래 모드 (기본: 모의투자)")
    parser.add_argument("--once", action="store_true", help="1회만 실행")
    args = parser.parse_args()

    _acquire_lock()

    dry_run = not args.live
    bot = TradingBot(dry_run=dry_run)

    print_startup_banner(dry_run)

    if args.once:
        bot.run_once()
        render_dashboard(bot)
        return

    while True:
        try:
            bot.run_once()
            render_dashboard(bot)
        except KeyboardInterrupt:
            logger.info("사용자 종료 요청")
            break
        except Exception as e:
            logger.error(f"오류 발생: {e}")
        time.sleep(TRADING["analysis_interval"])


if __name__ == "__main__":
    main()
