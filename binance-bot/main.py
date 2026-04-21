"""
Binance Futures Testnet Trading Bot
====================================
الاستخدام:
  python main.py BTCUSDT BUY MARKET 0.01
  python main.py BTCUSDT SELL LIMIT 0.01 --price 30000
  python main.py --help
"""

import logging
import os
import sys
from datetime import datetime
from enum import Enum
from typing import Optional

import typer
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

# ─────────────────────────────────────────────
# الإعداد الأساسي
# ─────────────────────────────────────────────

load_dotenv()

console = Console()
app = typer.Typer(
    name="trading-bot",
    help="🤖 بوت تداول بسيط على Binance Futures Testnet",
    add_completion=False,
)

# ─────────────────────────────────────────────
# نظام السجلات (Logging)
# ─────────────────────────────────────────────

def setup_logger() -> logging.Logger:
    """إعداد نظام تسجيل العمليات في ملف trading_bot.log"""
    logger = logging.getLogger("trading_bot")
    logger.setLevel(logging.DEBUG)

    # تنسيق رسالة السجل مع التاريخ والوقت
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # معالج الملف
    file_handler = logging.FileHandler("trading_bot.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # معالج الطرفية (للأخطاء فقط في السجل)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(logging.ERROR)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


logger = setup_logger()

# ─────────────────────────────────────────────
# تعريف الأنواع المسموحة
# ─────────────────────────────────────────────

class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


# ─────────────────────────────────────────────
# الاتصال بـ Binance Testnet
# ─────────────────────────────────────────────

def get_client() -> Client:
    """
    إنشاء كلاينت Binance Futures Testnet.
    يقرأ API_KEY و API_SECRET من ملف .env
    """
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")

    if not api_key or not api_secret:
        console.print(
            Panel(
                "[bold red]❌ خطأ:[/bold red] لم يتم العثور على API_KEY أو API_SECRET في ملف .env\n"
                "تأكد من وجود ملف [bold].env[/bold] يحتوي على:\n"
                "  [green]API_KEY=your_key_here[/green]\n"
                "  [green]API_SECRET=your_secret_here[/green]",
                title="خطأ في الإعداد",
                border_style="red",
            )
        )
        logger.error("API_KEY أو API_SECRET غير موجود في ملف .env")
        raise typer.Exit(code=1)

    client = Client(api_key, api_secret, testnet=True)
    return client


# ─────────────────────────────────────────────
# دوال المساعدة للعرض
# ─────────────────────────────────────────────

def print_header():
    """طباعة رأس البوت"""
    header = Text()
    header.append("⚡ Binance Futures Testnet Bot\n", style="bold yellow")
    header.append(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
    console.print(Panel(header, border_style="yellow", box=box.DOUBLE_EDGE))


def print_order_result(order: dict, side: str, symbol: str):
    """عرض نتيجة الأمر بشكل جميل باستخدام rich"""
    side_color = "green" if side == "BUY" else "red"
    side_emoji = "📈" if side == "BUY" else "📉"

    table = Table(
        title=f"{side_emoji} تفاصيل الأمر المنفّذ",
        box=box.ROUNDED,
        border_style=side_color,
        show_header=True,
        header_style=f"bold {side_color}",
    )

    table.add_column("الحقل", style="bold white", width=20)
    table.add_column("القيمة", style="cyan", width=30)

    fields = {
        "رقم الأمر": str(order.get("orderId", "—")),
        "الرمز": order.get("symbol", symbol),
        "الجانب": order.get("side", side),
        "النوع": order.get("type", "—"),
        "الكمية": order.get("origQty", "—"),
        "السعر": order.get("price", "سعر السوق") or "سعر السوق",
        "الحالة": order.get("status", "—"),
        "وقت التنفيذ": datetime.fromtimestamp(
            order.get("updateTime", 0) / 1000
        ).strftime("%H:%M:%S") if order.get("updateTime") else "—",
    }

    for field, value in fields.items():
        table.add_row(field, str(value))

    console.print(table)


def print_error(message: str, details: str = ""):
    """عرض رسالة خطأ منسقة"""
    content = f"[bold red]❌ {message}[/bold red]"
    if details:
        content += f"\n[dim]{details}[/dim]"
    console.print(Panel(content, title="فشل الأمر", border_style="red"))


def print_success(message: str):
    """عرض رسالة نجاح منسقة"""
    console.print(Panel(f"[bold green]✅ {message}[/bold green]", border_style="green"))


# ─────────────────────────────────────────────
# الأمر الرئيسي
# ─────────────────────────────────────────────

@app.command()
def trade(
    symbol: str = typer.Argument(
        ...,
        help="رمز الزوج مثل BTCUSDT أو ETHUSDT",
        metavar="SYMBOL",
    ),
    side: Side = typer.Argument(
        ...,
        help="جانب الأمر: BUY للشراء أو SELL للبيع",
        metavar="SIDE",
    ),
    order_type: OrderType = typer.Argument(
        ...,
        help="نوع الأمر: MARKET (سعر السوق) أو LIMIT (سعر محدد)",
        metavar="ORDER_TYPE",
    ),
    quantity: float = typer.Argument(
        ...,
        help="الكمية المراد تداولها",
        metavar="QUANTITY",
    ),
    price: Optional[float] = typer.Option(
        None,
        "--price", "-p",
        help="السعر المحدد (مطلوب فقط لأوامر LIMIT)",
    ),
):
    """
    تنفيذ أمر تداول على Binance Futures Testnet.

    \b
    أمثلة:
      python main.py BTCUSDT BUY MARKET 0.01
      python main.py ETHUSDT SELL LIMIT 0.1 --price 2000
    """
    print_header()

    # التحقق من السعر لأوامر LIMIT
    if order_type == OrderType.LIMIT and price is None:
        print_error(
            "السعر مطلوب لأوامر LIMIT",
            "استخدم الخيار --price لتحديد السعر.\n"
            "مثال: python main.py BTCUSDT BUY LIMIT 0.01 --price 30000",
        )
        logger.error(
            f"فشل الأمر | {symbol} | {side.value} | {order_type.value} | "
            f"الكمية: {quantity} | السبب: السعر مطلوب لأوامر LIMIT"
        )
        raise typer.Exit(code=1)

    # عرض ملخص الأمر قبل التنفيذ
    summary = Table(box=box.SIMPLE, show_header=False)
    summary.add_column("", style="dim")
    summary.add_column("", style="bold")
    summary.add_row("الرمز:", symbol.upper())
    summary.add_row("الجانب:", f"[{'green' if side == Side.BUY else 'red'}]{side.value}[/]")
    summary.add_row("النوع:", order_type.value)
    summary.add_row("الكمية:", str(quantity))
    if price:
        summary.add_row("السعر:", f"{price:,.2f} USDT")
    console.print(Panel(summary, title="📋 ملخص الأمر", border_style="blue"))

    # الاتصال بـ Binance
    console.print("[dim]🔗 جاري الاتصال بـ Binance Testnet...[/dim]")
    try:
        client = get_client()
    except typer.Exit:
        raise

    # تنفيذ الأمر
    try:
        order = None
        symbol_upper = symbol.upper()

        if order_type == OrderType.MARKET:
            # أمر بسعر السوق
            console.print("[dim]⚙️  جاري تنفيذ أمر Market Order...[/dim]")
            order = client.futures_create_order(
                symbol=symbol_upper,
                side=side.value,
                type="MARKET",
                quantity=quantity,
            )
            log_msg = (
                f"نجح | {symbol_upper} | {side.value} | MARKET | "
                f"الكمية: {quantity} | orderId: {order.get('orderId')}"
            )

        elif order_type == OrderType.LIMIT:
            # أمر بسعر محدد
            console.print("[dim]⚙️  جاري تنفيذ أمر Limit Order...[/dim]")
            order = client.futures_create_order(
                symbol=symbol_upper,
                side=side.value,
                type="LIMIT",
                quantity=quantity,
                price=str(price),
                timeInForce="GTC",  # Good Till Cancelled
            )
            log_msg = (
                f"نجح | {symbol_upper} | {side.value} | LIMIT | "
                f"الكمية: {quantity} | السعر: {price} | orderId: {order.get('orderId')}"
            )

        # عرض النتيجة وتسجيلها
        logger.info(log_msg)
        print_order_result(order, side.value, symbol_upper)
        print_success(f"تم تنفيذ الأمر بنجاح! رقم الأمر: {order.get('orderId')}")

    except BinanceAPIException as e:
        error_msg = f"خطأ من Binance API: {e.message} (الكود: {e.code})"
        print_error("فشل تنفيذ الأمر", error_msg)
        logger.error(
            f"فشل | {symbol.upper()} | {side.value} | {order_type.value} | "
            f"الكمية: {quantity} | BinanceAPIException: {e.message} (code={e.code})"
        )
        raise typer.Exit(code=1)

    except BinanceOrderException as e:
        error_msg = f"خطأ في الأمر: {e.message} (الكود: {e.code})"
        print_error("فشل تنفيذ الأمر", error_msg)
        logger.error(
            f"فشل | {symbol.upper()} | {side.value} | {order_type.value} | "
            f"الكمية: {quantity} | BinanceOrderException: {e.message} (code={e.code})"
        )
        raise typer.Exit(code=1)

    except Exception as e:
        error_msg = f"خطأ غير متوقع: {str(e)}"
        print_error("فشل تنفيذ الأمر", error_msg)
        logger.exception(
            f"فشل | {symbol.upper()} | {side.value} | {order_type.value} | "
            f"الكمية: {quantity} | خطأ غير متوقع: {str(e)}"
        )
        raise typer.Exit(code=1)


# ─────────────────────────────────────────────
# نقطة الانطلاق
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app()
