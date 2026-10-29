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
    history = stock.history(period="2y", auto_adjust=True)
    if len(history) < 120:
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
    
    previous_volume_short = float(volume.iloc[-21:-1].mean())
    volume_ratio_short = float(volume.iloc[-1]) / previous_volume_short if previous_volume_short > 0 else 0
    
    change20 = (price / float(close.iloc[-21]) - 1) * 100
    change60 = (price / float(close.iloc[-61]) - 1) * 100

    short_term_score = 0
    short_reason = "特になし"
    if price > ma20 and volume_ratio_short >= 1.5 and 0 < change20 <= 25:
        short_reason = "急激な買いを伴う短期上昇トレンド"
    elif price > ma20 and volume_ratio_short >= 1.5:
        short_reason = "出来高急増、短期的な資金流入"
    elif price > ma20:
        short_reason = "20日移動平均線上をキープ（堅調）"
        
    short_term_score += 30 if price > ma20 else 0
    short_term_score += 30 if volume_ratio_short >= 2.0 else 15 if volume_ratio_short >= 1.5 else 0
    short_term_score += 40 if 5 <= change20 <= 25 else 20 if 0 < change20 < 5 else 0

    medium_term_score = 0
    medium_reason = "特になし"
    if ma20 > ma60 and price > ma60 and change60 > 0:
        medium_reason = "ゴールデンクロス維持。中期上昇トレンドが継続"
    elif ma20 > ma60:
        medium_reason = "20日線が60日線を上回り、買い優勢ゾーン"
        
    medium_term_score += 40 if ma20 > ma60 else 0
    medium_term_score += 30 if price > ma60 else 0
    medium_term_score += 30 if change60 > 0 else 0

    long_term_score = 0
    long_reasons = []
    if growth is not None and growth >= 0.05:
        long_reasons.append("売上高成長")
    if margin is not None and margin >= 0.08:
        long_reasons.append("高利益率")
    if ((pe is not None and 0 < pe <= 25) or (forward_pe is not None and 0 < forward_pe <= 25)):
        long_reasons.append("指標面で割安感あり")
    long_reason = "・".join(long_reasons) if long_reasons else "ファンダメンタルズ平均的"

    if growth is not None:
        long_term_score += 25 if growth >= 0.15 else 15 if growth >= 0.05 else 0
    if margin is not None:
        long_term_score += 25 if margin >= 0.15 else 15 if margin >= 0.08 else 0
    if pe is not None and pe > 0:
        long_term_score += 25 if pe <= 15 else 15 if pe <= 25 else 0
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
        "short_reason": short_reason,
        "medium_reason": medium_reason,
        "long_reason": long_reason,
    }
def generate_email_body(results):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = f"BUDDY TRADER 株式分析・売買シグナル通知（{now_str}時点）\n"
    body += "--------------------------------------------------\n"
    body += "SBI証券の公式アプリ（SBI株アプリ）を開き、注目銘柄を検索してご活用ください。\n\n"
    
    body += "■ 短期売買ランキング（推奨期間：数日〜半月）\n"
    body += "短期の資金流入と値動きの勢い（トレンド）を捉える売買手法です。\n"
    for i, item in enumerate(sorted(results, key=lambda x: x["short_term_score"], reverse=True)[:5], 1):
        body += f" 【第{i}位】 {item['ticker']} - {item['name']} \n"
        body += f"   株価: {item['price_jpy']}円 | スコア: {item['short_term_score']}点\n"
        body += f"   選定理由: {item['short_reason']}\n\n"
        
    body += "--------------------------------------------------\n"
    
    body += "■ 中期投資ランキング（推奨期間：〜3ヶ月）\n"
    body += "移動平均線のゴールデンクロスなどを元に、中期のトレンド転換を捉える手法です。\n"
    for i, item in enumerate(sorted(results, key=lambda x: x["medium_term_score"], reverse=True)[:5], 1):
        body += f" 【第{i}位】 {item['ticker']} - {item['name']} \n"
        body += f"   株価: {item['price_jpy']}円 | スコア: {item['medium_term_score']}点\n"
        body += f"   選定理由: {item['medium_reason']}\n\n"
        
    body += "--------------------------------------------------\n"
    
    body += "■ 長期投資ランキング（推奨期間：〜3年程度）\n"
    body += "企業の成長率や利益率（稼ぐ力）と、割安性を重視した王道の長期投資手法です。\n"
    for i, item in enumerate(sorted(results, key=lambda x: x["long_term_score"], reverse=True)[:5], 1):
        body += f" 【第{i}位】 {item['ticker']} - {item['name']} \n"
        body += f"   株価: {item['price_jpy']}円 | スコア: {item['long_term_score']}点\n"
        body += f"   選定理由: {item['long_reason']}\n\n"
        
    body += "--------------------------------------------------\n"
    body += "※当ツールで計算されたスコアはスクリーニング用の指標であり、投資の成果を保証するものではありません。売買の最終判断はご自身の責任にてお願いいたします。"
    return body


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
        japanese_headers = [
            "ティッカー", "銘柄名", "株価(円)", "売上高成長率(%)", 
            "営業利益率(%)", "PER", "出来高比率", "20日変化率(%)", 
            "短期スコア", "中期スコア", "長期スコア"
        ]
        writer = csv.writer(file)
        writer.writerow(japanese_headers)
        
        keys = ["ticker", "name", "price_jpy", "revenue_growth_pct", 
                "operating_margin_pct", "pe", "volume_ratio", "change20_pct", 
                "short_term_score", "medium_term_score", "long_term_score"]
        
        for item in sorted(results, key=lambda x: x["long_term_score"], reverse=True):
            writer.writerow([item[key] for key in keys])

    email_text = generate_email_body(results)
    send_email(email_text)


def send_email(email_text):
    sender = os.environ.get("EMAIL_ADDRESS", "wainai4649@gmail.com")
    password = "dqyv mtsq nhkg gzoj"
    
    if not password:
        print("ERROR: EMAIL_PASSWORD environment variable is not set.")
        return
        
    recipient = "wainai4649@gmail.com"

    msg = EmailMessage()
    msg["Subject"] = f"【BUDDY TRADER】株式売買ランキング案内 - {datetime.now():%Y/%m/%d}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(email_text)

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
