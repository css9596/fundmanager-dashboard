"""한 사이클만 실행 (GitHub Actions에서 호출).

USE_RULE_STRATEGY 환경변수를 1로 강제해서 Claude API 없이 동작.
"""
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Rule 전략 강제 (Actions에는 ANTHROPIC_API_KEY 없음)
os.environ["USE_RULE_STRATEGY"] = "1"

# logs/ 디렉토리 보장 (simulation.log 출력용)
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/simulation.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

from bot.simulator import SimulationBot

bot = SimulationBot()
print(f"전략: {bot.strategy_name}")
bot.run_once()
print("한 사이클 완료")
