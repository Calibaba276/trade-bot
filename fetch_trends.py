import requests
import re
import time

from pydantic import BaseModel
from typing import List
from google import genai
from google.genai import types
from google.api_core.exceptions import ResourceExhausted, TooManyRequests

class TradeSignal(BaseModel):
    ticker: str
    sentiment_score: float
    reason: str

class TradeBatch(BaseModel):
    signals: List[TradeSignal]


class FetchTrends:
    def __init__(self, news_key, gemini_key):

        self.NEWS_API_KEY = news_key
        self.GEMINI_API_KEY = gemini_key
        self.client = genai.Client(api_key=self.GEMINI_API_KEY)
        self.url = "https://newsapi.org/v2/top-headlines"
        self.params = {
            "category": "business",
            "country": "us",
            "pageSize": 100,
            "apiKey": self.NEWS_API_KEY
        } 

        self.prompt = f"""SYSTEM INSTRUCTIONS:
        You are a financial data extractor. I will provide a list of news headlines

        TASK:
        1. Scan the news headlines.
        2. If a headline is about a company is in the S&P 500 LIST
        3. Just give the response as the ticker and sentiment score no extra response is needed JUST THE TICKER and THE SENTIMENT SCORE
        4. If a headline is NOT about a company in the S&P 500, ignore it.
        5. Be conservative. If the news is just a routine announcement, give it a score of 0.0. Only give scores above 0.7 for major breakthroughs, earnings beats, or massive contracts.

        NEWS TO SCAN:
        {self.get_market_news()} # This is the blob of text from NewsAPI
        """

    def _generate_trade_signals(self):
        return self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=self.prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TradeBatch,
                temperature=0.0
            )
        )
    
    def _extract_retry_delay_seconds(self, error_message):
        retry_in_match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_message, re.IGNORECASE)
        if retry_in_match:
            return max(1, int(float(retry_in_match.group(1))))

        retry_delay_match = re.search(r"retryDelay['\"]?\s*:\s*['\"](\d+)s['\"]", error_message, re.IGNORECASE)
        if retry_delay_match:
            return max(1, int(retry_delay_match.group(1)))

        return None

    def _resolve_rate_limit_wait(self, error_message):
        error_upper = error_message.upper()

        # Daily quotas usually do not include a reliable reset timestamp in the exception.
        # Retry hourly until the quota window resets.
        if "PERDAY" in error_upper or "REQUESTSPERDAY" in error_upper:
            return 3600, "daily"

        retry_seconds = self._extract_retry_delay_seconds(error_message)
        if retry_seconds is not None:
            return retry_seconds, "retry_delay"

        return 60, "default"

    def _format_duration(self, total_seconds):
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds or not parts:
            parts.append(f"{seconds}s")
        return " ".join(parts)

    def get_market_news(self):
        response = requests.get(url=self.url, params=self.params)
        response = response.json()
        articles_list = response.get("articles", [])

        article = '\n'.join([f"{index}. {article['title']}" for (index, article) in enumerate(articles_list)])

        return article

    def get_ai_response(self):
        while True:
            try:
                response = self._generate_trade_signals()
                return response.text
            except (ResourceExhausted, TooManyRequests) as e:
                wait_seconds, wait_type = self._resolve_rate_limit_wait(str(e))
                if wait_type == "daily":
                    print("[RATE LIMIT] Daily Gemini quota reached. It may take up to 24h to clear. Retrying in 1h...")
                else:
                    print(f"[RATE LIMIT] Please wait {self._format_duration(wait_seconds)}. Retrying automatically...")
                time.sleep(wait_seconds)
            except Exception as e:
                error_message = str(e).upper()
                if "429" in error_message or "RESOURCE_EXHAUSTED" in error_message or "QUOTA" in error_message:
                    wait_seconds, wait_type = self._resolve_rate_limit_wait(error_message)
                    if wait_type == "daily":
                        print("[RATE LIMIT] Daily Gemini quota reached. It may take up to 24h to clear. Retrying in 1h...")
                    else:
                        print(f"[RATE LIMIT] Please wait {self._format_duration(wait_seconds)}. Retrying automatically...")
                else:
                    wait_seconds = 60
                    print("[ERROR] Gemini request failed. Retrying in 1m...")
                time.sleep(wait_seconds)

