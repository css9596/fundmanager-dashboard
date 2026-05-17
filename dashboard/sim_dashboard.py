from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from datetime import datetime

console = Console()


def render_sim_dashboard(bot):
    total = bot.get_total_assets()
    ret_pct = bot.get_total_return_pct()
    portfolio = bot.get_portfolio()
    risk_status = bot.risk.get_status()

    ret_color = "green" if ret_pct >= 0 else "red"
    ret_arrow = "▲" if ret_pct >= 0 else "▼"

    # 헤더
    console.clear()
    console.print(Panel(
        f"[bold cyan]FundManager[/bold cyan]  [yellow]모의투자[/yellow]  |  "
        f"{datetime.now().strftime('%H:%M:%S')}  |  "
        f"총자산 [bold]{total:,.0f}원[/bold]  [{ret_color}]{ret_arrow} {ret_pct:+.2f}%[/{ret_color}]  |  "
        f"KRW {bot.krw_balance:,.0f}원",
        border_style="cyan",
    ))

    # 보유 종목
    if portfolio:
        hold_table = Table(show_header=True, header_style="bold magenta", title="보유 종목")
        hold_table.add_column("종목", style="cyan")
        hold_table.add_column("수량", justify="right")
        hold_table.add_column("매수가", justify="right")
        hold_table.add_column("현재가", justify="right")
        hold_table.add_column("평가금액", justify="right")
        hold_table.add_column("수익률", justify="right")
        for p in portfolio:
            pnl_color = "green" if p["pnl_pct"] >= 0 else "red"
            hold_table.add_row(
                p["symbol"],
                f"{p['volume']:.6f}",
                f"{p['avg_price']:,}",
                f"{p['current_price']:,}",
                f"{p['value']:,.0f}원",
                f"[{pnl_color}]{p['pnl_pct']:+.2f}%[/{pnl_color}]",
            )
        console.print(hold_table)
    else:
        console.print("[dim]보유 종목 없음[/dim]")

    # 거래 내역
    trade_table = Table(show_header=True, header_style="bold blue", title="거래 내역 (최근 15건)")
    trade_table.add_column("시간", style="dim", width=8)
    trade_table.add_column("액션", width=6)
    trade_table.add_column("종목", style="cyan")
    trade_table.add_column("가격", justify="right")
    trade_table.add_column("금액", justify="right")
    trade_table.add_column("수익률", justify="right")
    trade_table.add_column("사유")

    for t in reversed(bot.trade_log[-15:]):
        action_color = "green" if t["action"] == "buy" else "red"
        pnl_str = f"{t.get('pnl_pct', 0):+.2f}%" if t["action"] == "sell" else "-"
        pnl_color = "green" if t.get("pnl_pct", 0) >= 0 else "red"
        trade_table.add_row(
            t["time"],
            f"[{action_color}]{'매수' if t['action']=='buy' else '매도'}[/{action_color}]",
            t["symbol"],
            f"{t['price']:,}",
            f"{t['amount']:,.0f}원",
            f"[{pnl_color}]{pnl_str}[/{pnl_color}]",
            t.get("reason", "")[:28],
        )
    console.print(trade_table)

    # 요약
    wins = [t for t in bot.trade_log if t["action"] == "sell" and t.get("pnl_pct", 0) > 0]
    losses = [t for t in bot.trade_log if t["action"] == "sell" and t.get("pnl_pct", 0) <= 0]
    total_trades = len(wins) + len(losses)
    win_rate = len(wins) / total_trades * 100 if total_trades else 0

    elapsed = (datetime.now() - bot.started_at)
    h, m = divmod(int(elapsed.total_seconds()), 3600)
    m, s = divmod(m, 60)

    console.print(
        f"[dim]실행시간: {h:02d}:{m:02d}:{s:02d}  |  "
        f"총 거래: {total_trades}건  |  승률: {win_rate:.0f}%  |  "
        f"일일손익: {risk_status['daily_pnl_pct']:+.2f}%  |  "
        f"Ctrl+C 종료[/dim]"
    )
