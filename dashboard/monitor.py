from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from datetime import datetime


console = Console()


def render_dashboard(bot) -> str:
    risk_status = bot.risk.get_status()
    total_assets = bot.get_total_assets()

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="trades", size=12),
    )

    # 헤더
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode = "[red]실거래[/red]" if not bot.dry_run else "[yellow]모의투자[/yellow]"
    layout["header"].update(
        Panel(f"[bold cyan]FundManager Trading Bot[/bold cyan] | {mode} | {now}", style="cyan")
    )

    # 자산 & 포지션
    asset_table = Table(show_header=True, header_style="bold magenta")
    asset_table.add_column("항목", style="cyan")
    asset_table.add_column("값", justify="right")
    asset_table.add_row("KRW 잔고", f"{total_assets:,.0f}원")
    asset_table.add_row("오픈 포지션", str(risk_status["open_positions"]))
    asset_table.add_row("일일 손익", f"{risk_status['daily_pnl_pct']:+.2f}%")
    daily_pnl = risk_status["daily_pnl_pct"]
    pnl_color = "green" if daily_pnl >= 0 else "red"
    asset_table.add_row("상태", f"[{pnl_color}]{'수익 중' if daily_pnl >= 0 else '손실 중'}[/{pnl_color}]")

    # 최근 거래 내역
    trade_table = Table(show_header=True, header_style="bold blue", title="최근 거래 내역")
    trade_table.add_column("시간", style="dim")
    trade_table.add_column("시장")
    trade_table.add_column("종목")
    trade_table.add_column("액션")
    trade_table.add_column("가격", justify="right")
    trade_table.add_column("사유")

    recent_trades = bot.trade_log[-10:][::-1]
    for t in recent_trades:
        action_color = "green" if t["action"] == "buy" else "red"
        trade_table.add_row(
            t["time"][11:19],
            t["market"],
            t["symbol"],
            f"[{action_color}]{t['action'].upper()}[/{action_color}]",
            f"{t.get('price', 0):,}",
            t.get("reason", "")[:30],
        )

    layout["body"].update(Panel(asset_table, title="포트폴리오"))
    layout["trades"].update(Panel(trade_table))

    console.clear()
    console.print(layout)


def print_startup_banner(dry_run: bool):
    mode = "모의투자" if dry_run else "실거래"
    console.print(Panel(
        f"[bold green]FundManager 트레이딩 봇 시작[/bold green]\n"
        f"모드: [yellow]{mode}[/yellow]\n"
        f"코인: 업비트 | 주식: 한국투자증권\n"
        f"[dim]Ctrl+C로 종료[/dim]",
        title="🚀 FundManager",
        border_style="green",
    ))
