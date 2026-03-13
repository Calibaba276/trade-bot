import os
import requests
import pandas as pd

from pydantic import BaseModel
from typing import List
from google import genai
from google.genai import types

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

    def get_market_news(self):
        response = requests.get(url=self.url, params=self.params)
        response = response.json()
        articles_list = response.get("articles", [])

        article = '\n'.join([f"{index}. {article['title']}" for (index, article) in enumerate(articles_list)])

        return article

    def get_ai_response(self):
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=self.prompt,
            config=types.GenerateContentConfig( 
                response_mime_type="application/json",
                response_schema=TradeBatch,
                temperature=0.0
            )
        )

        return response.text
