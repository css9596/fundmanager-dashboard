import logging
import argparse
import time
from bot.trader import TradingBot
from dashboard.monitor import print_startup_banner, render_dashboard
from config import TRADING

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/trading.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="FundManager 트레이딩 봇")
    parser.add_argument("--live", action="store_true", help="실거래 모드 (기본: 모의투자)")
    parser.add_argument("--once", action="store_true", help="1회만 실행")
    args = parser.parse_args()

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
