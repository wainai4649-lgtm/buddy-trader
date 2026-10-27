import csv
from datetime import datetime
import os
import smtplib
from email.message import EmailMessage

import pandas as pd
import yfinance as yf

# 初期テスト用。後から対象銘柄を増やせます。
TICKERS = ["7203.T", "6758.T", "8035.T", "8306.T", "8058.T", "6501.T", "6861.T", "7974.T", "4063.T", "6098.T"]


def number(value):
    try:
        result = float(value)
        return result if pd.notna(result) else None
    except (TypeError, ValueError):
        return None


def analyze(ticker):
    stock = yf.Ticker(ticker)
    history = stock.history(period="1y", auto_adjust=True)
    if len(history) < 65:
        return None
    close = history["Close"]
    volume = history["Volume"]
    if close.iloc[-1] <= 0:
        return None

    info = stock.info or {}
    growth = number(info.get("revenueGrowth"))
    margin = number(info.get("operatingMargins"))
    pe = number(info.get("trailingPE"))
    forward_pe = number(info.get("forwardPE"))
    price = float(close.iloc[-1])
    ma20 = float(close.tail(20).mean())
    ma60 = float(close.tail(60).mean())
    previous_volume = float(volume.iloc[-21:-1].mean())
    volume_ratio = float(volume.iloc[-1]) / previous_volume if previous_volume > 0 else 0
    change20 = (price / float(close.iloc[-21]) - 1) * 100

    value_score = 0
    if growth is not None:
        value_score += 25 if growth >= 0.15 else 15 if growth >= 0.05 else 0
    if margin is not None:
        value_score += 25 if margin >= 0.15 else 15 if margin >= 0.08 else 0
    if pe is not None and pe > 0:
        value_score += 25 if pe <= 15 else 15 if pe <= 25 else 0
    if forward_pe is not None and forward_pe > 0:
        value_score += 25 if forward_pe <= 15 else 15 if forward_pe <= 25 else 0

    momentum_score = 0
    momentum_score += 25 if price > ma20 else 0
    momentum_score += 25 if ma20 > ma60 else 0
    momentum_score += 25 if volume_ratio >= 2 else 15 if volume_ratio >= 1.5 else 0
    momentum_score += 25 if 5 <= change20 <= 25 else 15 if 0 < change20 < 5 else 0

    return {
        "ticker": ticker,
        "name": info.get("shortName", ticker),
        "price_jpy": round(price, 2),
        "revenue_growth_pct": round(growth * 100, 1) if growth is not None else "",
        "operating_margin_pct": round(margin * 100, 1) if margin is not None else "",
        "pe": round(pe, 1) if pe is not None else "",
        "volume_ratio": round(volume_ratio, 2),
        "change20_pct": round(change20, 1),
        "long_term_score": value_score,
        "short_term_score": momentum_score,
    }


def main():
    results = []
    for ticker in TICKERS:
        try:
            result = analyze(ticker)
            if result:
                results.append(result)
                print(f"OK: {ticker}")
            else:
                print(f"SKIP: {ticker} (insufficient price history)")
        except Exception as error:
            print(f"ERROR: {ticker}: {error}")

    if not results:
        print("No data collected. Check network access and try again.")
            filename = "buddy_trader_report.csv"
    with open(filename, "w", newline="", encoding="utf-8-sig") as file:
        # 日本語のヘッダー名（項目名）を定義します
        japanese_headers = [
            "ティッカー", "銘柄名", "株価(円)", "売上高成長率(%)", 
            "営業利益率(%)", "PER", "出来高比率", "20日変化率(%)", 
            "長期スコア", "短期スコア"
        ]
        
        writer = csv.writer(file)
        writer.writerow(japanese_headers)
        
        # データの並び順を定義
        keys = ["ticker", "name", "price_jpy", "revenue_growth_pct", 
                "operating_margin_pct", "pe", "volume_ratio", "change20_pct", 
                "long_term_score", "short_term_score"]
        
        # 長期スコア順に並び替えて書き込み
        for item in sorted(results, key=lambda x: x["long_term_score"], reverse=True):
            writer.writerow([item[key] for key in keys])


    print(f"\nBUDDY TRADER | {datetime.now():%Y-%m-%d %H:%M}")
    print("\nLONG TERM TOP 5")
    for item in sorted(results, key=lambda x: x["long_term_score"], reverse=True)[:5]:
        print(item["ticker"], item["long_term_score"], item["name"])
    print("\nSHORT TERM TOP 5")
    for item in sorted(results, key=lambda x: x["short_term_score"], reverse=True)[:5]:
        print(item["ticker"], item["short_term_score"], item["name"])
    print(f"\nSaved: {filename}")
    print("Scores are screening indicators, not forecasts or buy recommendations.")


def send_email():
    sender = os.environ.get("EMAIL_ADDRESS", "wainai4649@gmail.com")
    password = "dqyv mtsq nhkg gzoj"
    
    if not password:
        print("ERROR: EMAIL_PASSWORD environment variable is not set.")
        return
        
    recipient = "wainai4649@gmail.com"

    msg = EmailMessage()
    msg["Subject"] = "BUDDY TRADER 株式分析結果"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content("株式分析結果をCSVファイルで送ります。")

    try:
        with open("buddy_trader_report.csv", "rb") as file:
            msg.add_attachment(
                file.read(),
                maintype="text",
                subtype="csv",
                filename="buddy_trader_report.csv"
            )
    except FileNotFoundError:
        print("ERROR: buddy_trader_report.csv not found.")
        return

    print("Sending email...")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")


if __name__ == "__main__":
    main()
    send_email()
 