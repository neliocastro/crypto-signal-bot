"""
Busca o Fear & Greed Index (Crypto) — gratuito, sem chave.
"""
import requests

def fear_and_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        data = r.json()["data"][0]
        score = int(data["value"])
        label = data["value_classification"]
        emoji = (
            "😱" if score <= 24 else
            "😟" if score <= 44 else
            "😐" if score <= 55 else
            "😊" if score <= 74 else
            "🤑"
        )
        return {"score": score, "label": label, "emoji": emoji}
    except Exception:
        return None