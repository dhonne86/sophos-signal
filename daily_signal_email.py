from __future__ import annotations

import argparse
import math
import os
import smtplib
from dataclasses import replace
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv
import yfinance as yf

from signal_engine import Signal, gerar_sinal
from Util import baixar_dados_b3

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "daily_signal_page.html"
DEFAULT_RECIPIENT = "dhonne137@gmail.com"
DEFAULT_TICKER = "PETR4.SA"
DEFAULT_EMPRESA = "PETROBRAS"
DEFAULT_WINDOW_DAYS = 90

load_dotenv(BASE_DIR / ".env")

YFINANCE_CACHE_DIR = BASE_DIR / ".cache" / "yfinance"
YFINANCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
try:
    yf.set_tz_cache_location(str(YFINANCE_CACHE_DIR))
except Exception:
    pass


def format_brl(value: float | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def carregar_sinal(ticker: str, empresa: str, janela_dias: int) -> Signal:
    fim = date.today()
    inicio = fim - timedelta(days=janela_dias)
    df = baixar_dados_b3(ticker=ticker, inicio=str(inicio), fim=str(fim))
    if df.is_empty():
        raise ValueError(f"Nao foi possivel baixar dados para {ticker}.")
    return replace(gerar_sinal(df, empresa, ticker, perfil_risco="Moderado"), janela_dias=janela_dias)


def render_html(signal: Signal) -> str:
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    rr = f"{signal.rr:.2f}" if signal.rr else "-"
    gatilhos = "".join(f"<li>{item}</li>" for item in signal.gatilhos)
    accent = "#0f766e" if signal.direcao == "COMPRA" else "#dc2626" if signal.direcao == "VENDA" else "#b45309"
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sophos Signal - Sinal diario</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #17231f; background: #f4f8f6; }}
    main {{ max-width: 820px; margin: 0 auto; padding: 28px 18px; }}
    .panel {{ background: #fff; border: 1px solid #dbe5e1; border-radius: 8px; padding: 22px; }}
    .brand {{ color: #0f766e; font-size: 13px; font-weight: 700; text-transform: uppercase; }}
    h1 {{ margin: 8px 0 6px; font-size: 28px; }}
    .muted {{ color: #5b6b66; }}
    .signal {{ border-left: 6px solid {accent}; margin-top: 18px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }}
    .metric {{ border: 1px solid #dbe5e1; border-radius: 8px; padding: 12px; }}
    .label {{ color: #5b6b66; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .value {{ font-size: 20px; font-weight: 700; margin-top: 4px; }}
    ul {{ margin-bottom: 0; }}
    @media (max-width: 640px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <section class="panel signal">
      <div class="brand">Sophos Signal</div>
      <h1>{signal.direcao} - {signal.empresa}</h1>
      <p class="muted">{signal.ticker} | Gerado em {generated_at} | Janela tecnica: ultimos {signal.janela_dias} dias</p>
      <div class="grid">
        <div class="metric"><div class="label">Entrada</div><div class="value">{format_brl(signal.entrada)}</div></div>
        <div class="metric"><div class="label">Stop</div><div class="value">{format_brl(signal.stop)}</div></div>
        <div class="metric"><div class="label">Alvo</div><div class="value">{format_brl(signal.alvo)}</div></div>
        <div class="metric"><div class="label">Risco/Retorno</div><div class="value">{rr}</div></div>
        <div class="metric"><div class="label">Confianca</div><div class="value">{signal.confianca}%</div></div>
        <div class="metric"><div class="label">RSI / ADX</div><div class="value">{signal.rsi:.1f} / {signal.adx:.1f}</div></div>
        <div class="metric"><div class="label">Estocastico / Volume rel.</div><div class="value">{signal.stoch_k:.1f} / {signal.volume_relativo:.2f}x</div></div>
      </div>
      <h2>Gatilhos</h2>
      <ul>{gatilhos}</ul>
      <p class="muted">Uso educacional. Valide liquidez, spread, contexto de mercado e gerenciamento de risco antes de qualquer operacao.</p>
    </section>
  </main>
</body>
</html>"""


def send_email(recipient: str, subject: str, html: str) -> None:
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    sender = os.getenv("SMTP_FROM", smtp_user).strip()

    missing = [
        name
        for name, value in {
            "SMTP_HOST": smtp_host,
            "SMTP_USER": smtp_user,
            "SMTP_PASSWORD": smtp_password,
            "SMTP_FROM ou SMTP_USER": sender,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError("Configure as variaveis de e-mail: " + ", ".join(missing))

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content("Seu relatorio Sophos Signal esta em HTML. Abra em um cliente compativel.")
    message.add_alternative(html, subtype="html")
    message.add_attachment(
        html.encode("utf-8"),
        maintype="text",
        subtype="html",
        filename="sophos-signal.html",
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera e envia o relatorio diario Sophos Signal.")
    parser.add_argument("--recipient", default=os.getenv("SIGNAL_EMAIL_TO", DEFAULT_RECIPIENT))
    parser.add_argument("--ticker", default=os.getenv("SIGNAL_TICKER", DEFAULT_TICKER))
    parser.add_argument("--empresa", default=os.getenv("SIGNAL_EMPRESA", DEFAULT_EMPRESA))
    parser.add_argument("--window-days", type=int, default=int(os.getenv("SIGNAL_WINDOW_DAYS", DEFAULT_WINDOW_DAYS)))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    signal = carregar_sinal(args.ticker, args.empresa, args.window_days)
    html = render_html(signal)
    OUTPUT_PATH.write_text(html, encoding="utf-8")

    subject = f"Sophos Signal diario: {signal.direcao} {signal.ticker}"
    if args.dry_run:
        print(f"Pagina gerada em {OUTPUT_PATH}")
        print(f"Assunto: {subject}")
        return

    send_email(args.recipient, subject, html)
    print(f"E-mail enviado para {args.recipient}. Pagina gerada em {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
