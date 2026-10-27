import csv
from datetime import datetime
import os
import smtplib
from email.message import EmailMessage

import pandas as pd
import yfinance as yf

# 対象銘柄（お好みに合わせて変更・追加してください）
TICKERS = ["7203.T", "6758.T", "8035.T", "8306.T", "8058.T", "6501.T", "6861.T", "7974.T", "4063.T", "6098.T"]


def number(value):
    try:
        result = float(value)
        return result if pd.notna(result) else None
    except (TypeError, ValueError):
        return None


def analyze(ticker):
    stock = yf.Ticker(ticker)
    # 中期・長期のトレンドを見るため、期間を「2年」に拡大してデータを取得します
    history = stock.history(period="2y", auto_adjust=True)
    if len(history) < 120:  # 必要な過去データ（最低120日分）があるかチェック
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
    
    # 各種テクニカル指標の計算
    price = float(close.iloc[-1])
    ma20 = float(close.tail(20).mean())
    ma60 = float(close.tail(60).mean())
    ma120 = float(close.tail(120).mean())
    
    # 出来高の計算
    previous_volume_short = float(volume.iloc[-21:-1].mean())
    volume_ratio_short = float(volume.iloc[-1]) / previous_volume_short if previous_volume_short > 0 else 0
    
    # 変化率の計算
    change20 = (price / float(close.iloc[-21]) - 1) * 100
    change60 = (price / float(close.iloc[-61]) - 1) * 100

    # --------------------------------------------------
    # 1. 短期スコア（数日〜半月）: 最大100点
    # --------------------------------------------------
    short_term_score = 0
    # 株価が20日線の上にあるか（上昇トレンドの勢い）
    short_term_score += 30 if price > ma20 else 0
    # 出来高が直近20日平均より急増しているか（買いのエネルギー）
    short_term_score += 30 if volume_ratio_short >= 2.0 else 15 if volume_ratio_short >= 1.5 else 0
    # 20日間の上昇率が適度か（急激すぎない健全な上昇）
    short_term_score += 40 if 5 <= change20 <= 25 else 20 if 0 < change20 < 5 else 0

    # --------------------------------------------------
    # 2. 中期スコア（〜3ヶ月）: 最大100点
    # --------------------------------------------------
    medium_term_score = 0
    # 20日線が60日線の上にあるか（ゴールデンクロス状態の維持）
    medium_term_score += 40 if ma20 > ma60 else 0
    # 株価が中期（60日）の平均線の上にあるか
    medium_term_score += 30 if price > ma60 else 0
    # 3ヶ月（60日）の変化率がプラスか
    medium_term_score += 30 if change60 > 0 else 0

    # --------------------------------------------------
    # 3. 長期スコア（〜3年程度）: 最大100点
    # --------------------------------------------------
    long_term_score = 0
    # 売上高成長率（15%以上で高評価）
    if growth is not None:
        long_term_score += 25 if growth >= 0.15 else 15 if growth >= 0.05 else 0
    # 営業利益率（15%以上で高評価）
    if margin is not None:
        long_term_score += 25 if margin >= 0.15 else 15 if margin >= 0.08 else 0
    # 過去PER（15倍以下で割安）
    if pe is not None and pe > 0:
        long_term_score += 25 if pe <= 15 else 15 if pe <= 25 else 0
    # 予想PER（15倍以下で割安）
    if forward_pe is not None and forward_pe > 0:
        long_term_score += 25 if forward_pe <= 15 else 15 if forward_pe <= 25 else 0

    return {
        "ticker": ticker,
        "name": info.get("shortName", ticker),
        "price_jpy": round(price, 2),
        "revenue_growth_pct": round(growth * 100, 1) if growth is not None else "",
        "operating_margin_pct": round(margin * 100, 1) if margin is not None else "",
        "pe": round(pe, 1) if pe is not None else "",
        "volume_ratio": round(volume_ratio_short, 2),
        "change20_pct": round(change20, 1),
        "short_term_score": short_term_score,
        "medium_term_score": medium_term_score,
        "long_term_score": long_term_score,
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
                print(f"SKIP: {ticker} (データ不足または株価異常)")
        except Exception as error:
            print(f"ERROR: {ticker}: {error}")

    if not results:
        print("No data collected. Check network access and try again.")
        return

    filename = "buddy_trader_report.csv"
    with open(filename, "w", newline="", encoding="utf-8-sig") as file:
        # 日本語のヘッダー名に「中期スコア」を追加しました
        japanese_headers = [
            "ティッカー", "銘柄名", "株価(円)", "売上高成長率(%)", 
            "営業利益率(%)", "PER", "出来高比率", "20日変化率(%)", 
            "短期スコア", "中期スコア", "長期スコア"
        ]
        
        writer = csv.writer(file)
        writer.writerow(japanese_headers)
        
        # CSVに出力するデータの英名キーの順番
        keys = ["ticker", "name", "price_jpy", "revenue_growth_pct", 
                "operating_margin_pct", "pe", "volume_ratio", "change20_pct", 
                "short_term_score", "medium_term_score", "long_term_score"]
        
        # ひとまず長期スコア順でCSVファイルに全データを書き込みます
        for item in sorted(results, key=lambda x: x["long_term_score"], reverse=True):
            writer.writerow([item[key] for key in keys])

    # 画面（ログ）へのランキング出力表示
    print(f"\nBUDDY TRADER | {datetime.now():%Y-%m-%d %H:%M}")
    
    print("\n▼ 短期ランキング TOP 5 (数日〜半月)")
    for item in sorted(results, key=lambda x: x["short_term_score"], reverse=True)[:5]:
        print(f"{item['ticker']} | スコア: {item['short_term_score']}点 | {item['name']}")
        
    print("\n▼ 中期ランキング TOP 5 (〜3ヶ月)")
    for item in sorted(results, key=lambda x: x["medium_term_score"], reverse=True)[:5]:
        print(f"{item['ticker']} | スコア: {item['medium_term_score']}点 | {item['name']}")
        
    print("\n▼ 長期ランキング TOP 5 (〜3年程度)")
    for item in sorted(results, key=lambda x: x["long_term_score"], reverse=True)[:5]:
        print(f"{item['ticker']} | スコア: {item['long_term_score']}点 | {item['name']}")
        
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
    msg["Subject"] = "BUDDY TRADER 株式分析結果（短・中・長期ランキング）"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content("短・中・長期に分けて算出された株式分析結果をCSVファイルで送ります。")

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
        with smtplib.SMTP_SSL("://gmail.com", 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")


if __name__ == "__main__":
    main()
    send_email()
