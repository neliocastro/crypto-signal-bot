"""
Busca o Fear & Greed Index (Crypto) — gratuito, sem chave.
API: https://alternative.me/crypto/fear-and-greed-index/
"""
import requests

def get_fear_greed():
    """
    Retorna dict {'score': int, 'label': str, 'emoji': str} ou None em caso de erro.
    """
    try:
        r = requests.get(
            "https://api.alternative.me/fng/?limit=1",
            timeout=10,
        )
        r.raise_for_status()
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
    except Exception as e:
        print(f"[sentiment] erro ao buscar F&G: {e}")
        return None

# ---- aliases defensivos (compat com nomes alternativos) ----
fear_and_greed     = get_fear_greed
fetch_fear_greed   = get_fear_greed
get_sentiment      = get_fear_greed
