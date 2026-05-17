"""
API 키 없이 실제 업비트 시세로 모의투자 실행
사용법: python3 simulate.py
"""
import logging
import time
from bot.simulator import SimulationBot
from dashboard.sim_dashboard import render_sim_dashboard, console
from config import TRADING

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("logs/simulation.log", encoding="utf-8")],
)

console.print("""
[bold cyan]╔══════════════════════════════════════╗[/bold cyan]
[bold cyan]║     FundManager 모의투자 시뮬레이터      ║[/bold cyan]
[bold cyan]╚══════════════════════════════════════╝[/bold cyan]

[yellow]• API 키 없이 실제 업비트 시세 사용[/yellow]
[yellow]• 가상 초기 자금: 1,000,000원[/yellow]
[yellow]• 분석 종목:[/yellow] """ + ", ".join(TRADING["crypto_symbols"]) + """
[yellow]• 분석 주기:[/yellow] """ + str(TRADING["analysis_interval"]) + """초
[dim]• Claude AI가 기술지표를 보고 매수/매도 판단[/dim]
[dim]• Ctrl+C로 종료[/dim]
""")

bot = SimulationBot()

console.print("[green]시세 불러오는 중...[/green]")
time.sleep(1)

while True:
    try:
        bot.run_once()
        render_sim_dashboard(bot)
    except KeyboardInterrupt:
        console.print("\n[yellow]시뮬레이션 종료[/yellow]")
        console.print(f"최종 수익률: [bold {'green' if bot.get_total_return_pct() >= 0 else 'red'}]{bot.get_total_return_pct():+.2f}%[/bold]")
        console.print(f"최종 자산: {bot.get_total_assets():,.0f}원")
        break
    except Exception as e:
        logging.error(f"오류: {e}")
    time.sleep(TRADING["analysis_interval"])
