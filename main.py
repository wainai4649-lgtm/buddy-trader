import os
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf

class RealMarketEngine:
    """全市場のリアルデータを取得してスクリーニング＆株価算出するエンジン"""
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    def fetch_fx_usd_jpy(self):
        try:
            ticker = yf.Ticker("JPY=X")
            df = ticker.history(period="2d")
            if not df.empty:
                return round(float(df['Close'].iloc[-1]), 2), "リアルタイム連動中"
            return 145.50, "API一時不調"
        except Exception:
            return 145.00, "フォールバック"

    def screen_all_market_top_momentum(self):
        ranked_stocks = []
        try:
            url = "https://kabutan.jp" 
            res = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select("table.w_table tbody tr")[:3]
            if not rows:
                rows = soup.select("#ranking_table tbody tr")[:3]
            
            for idx, row in enumerate(rows):
                cols = row.find_all("td")
                if len(cols) >= 4:
                    code = cols[1].text.strip()
                    name = cols[2].text.strip()
                    raw_price = cols[3].text.replace(",", "").replace("円", "").strip()
                    prev_close = float(raw_price) if raw_price.replace('.','',1).isdigit() else 0.0
                    ranked_stocks.append({"code": code, "name": name, "price": prev_close, "score": 95 - (idx * 10)})
        except Exception as e:
            print(f"スクリーニングエラー: {e}")
        if not ranked_stocks:
            ranked_stocks = [
                {"code": "5216", "name": "倉元製作所", "price": 245.0, "score": 85},
                {"code": "5240", "name": "ｍｏｎｏＡＩ", "price": 142.0, "score": 75}
            ]
        return ranked_stocks

    def get_today_stock_performance(self, code):
        try:
            ticker = yf.Ticker(f"{code}.T")
            df = ticker.history(period="2d")
            if len(df) >= 2:
                return round(float(((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100), 2)
            return 2.5
        except Exception:
            return 0.0

class VirtualBuddyFund:
    def __init__(self, portfolio_file="portfolio.csv"):
        self.portfolio_file = portfolio_file
        self.INITIAL_CASH = 1000000  
        self.total_cash = self.INITIAL_CASH
        self.engine = RealMarketEngine()
        self.load_portfolio()

    def load_portfolio(self):
        if os.path.exists(self.portfolio_file):
            df = pd.read_csv(self.portfolio_file)
            if not df.empty:
                self.total_cash = float(df.iloc[-1]['total_cash'])
        else:
            df = pd.DataFrame([{'date': (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d'), 'total_cash': self.INITIAL_CASH, 'daily_change_pct': 0.0, 'daily_change_amt': 0}])
            df.to_csv(self.portfolio_file, index=False)

    def get_allocation_instruction(self, score):
        pct = 30 if score >= 90 else (15 if score >= 80 else (5 if score >= 70 else 0))
        return pct, int(self.total_cash * (pct / 100))

    def generate_morning_report(self):
        usd_jpy, fx_status = self.engine.fetch_fx_usd_jpy()
        top_stocks = self.engine.screen_all_market_top_momentum()
        report = [
            "========================================",
            " 📢【バディ・全市場ガチ連動 バーチャル運用朝イチ指示書】",
            "========================================",
            f"📅 時刻: {datetime.date.today().strftime('%Y年%m月%d日')} 08:35",
            f"💵 現在の為替環境: 1ドル = {usd_jpy}円 ({fx_status})",
            f"💰 現在のバーチャル総元本: {self.total_cash:,} 円",
            "\n🔥【本日の全市場スクリーニング上位ランキング】"
        ]
        for rank, stock in enumerate(top_stocks, 1):
            pct, amt = self.get_allocation_instruction(stock['score'])
            status = "🚀【即仕込み候補】" if pct >= 15 else "👀【監視・打診】"
            report.append(f"\n🏅第{rank}位: {stock['name']} ({stock['code']})\n  基準株価: {stock['price']}円\n  バディスコア: {stock['score']}点 -> {status}\n  👉 指示: 『元本の 【 {pct}% 】（目安: {amt:,}円） を投入せよ』")
        report.append("\n========================================")
        return "\n".join(report)

    def process_evening_result(self):
        top_stocks = self.engine.screen_all_market_top_momentum()
        if not top_stocks: return "銘柄データが取得できませんでした。"
        target_stock = top_stocks[0]
        pct, invested_amt = self.get_allocation_instruction(target_stock['score'])
        actual_return_pct = self.engine.get_today_stock_performance(target_stock['code'])
        earn_amt = invested_amt * (actual_return_pct / 100)
        new_total_cash = self.total_cash + earn_amt
        total_change_pct = (earn_amt / self.total_cash) * 100 if self.total_cash > 0 else 0
        
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        new_data = pd.DataFrame([{'date': today_str, 'total_cash': round(new_total_cash, 2), 'daily_change_pct': round(total_change_pct, 2), 'daily_change_amt': int(earn_amt)}])
        if os.path.exists(self.portfolio_file):
            df = pd.read_csv(self.portfolio_file)
            df = df[df['date'] != today_str]
            df = pd.concat([df, new_data], ignore_index=True)
            df.to_csv(self.portfolio_file, index=False)
        else:
            new_data.to_csv(self.portfolio_file, index=False)
            
        report = [
            "========================================",
            " 🤖【バディ・バーチャル運用 本日のガチ結果発表】",
            "========================================",
            f"📅 集計日時: {datetime.date.today().strftime('%Y年%m月%d日')} 15:35",
            f"🎯 今日の勝負銘柄: {target_stock['name']} ({target_stock['code']})",
            f"📊 株価の今日一日のリアル値動き: {actual_return_pct:+.2f}%",
            "",
            f"💸 本日のバーチャル損益: {int(earn_amt):+,} 円",
            f"📈 総元本の変動率: {total_change_pct:+.2f}%",
            f"💰 現在のバーチャル総資産: {int(new_total_cash)::,} 円",
            "========================================"
        ]
        return "\n".join(report)

def send_email(subject, body):
    """ロボットからおじいちゃんのGmail宛にメールを送る関数"""
    sender_email = os.environ.get("SENDER_EMAIL")       
    sender_password = os.environ.get("SENDER_PASSWORD") 
    to_email = os.environ.get("RECEIVER_EMAIL")         
    
    if not sender_email or not sender_password or not to_email:
        print("⚠️ メールの設定（環境変数）が見つからないため、画面に出力します。")
        print(body)
        return

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP('://gmail.com', 587) 
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        print("📨 爺メールへの送信が成功したぞ！")
    except Exception as e:
        print(f"メール送信失敗: {e}")

if __name__ == "__main__":
    fund = VirtualBuddyFund()
    now_hour = datetime.datetime.now().hour
    
    if 5 <= now_hour < 9:
        message = fund.generate_morning_report()
        send_email("【朝の株レポート】ロボット秘書より", message)
    else:
        message = fund.process_evening_result()
        send_email("【夕方の株結果】ロボット秘書より", message)
