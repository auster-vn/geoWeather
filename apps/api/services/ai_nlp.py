import re
import logging
from underthesea import ner
from typing import Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
import unicodedata

def remove_accents(input_str):
    if not input_str:
        return ""
    input_str = input_str.replace('Đ', 'D').replace('đ', 'd')
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

logger = logging.getLogger(__name__)

# Trigger download/init on import (caches in memory)
try:
    _ = ner("Hà Nội")
except Exception as e:
    logger.error(f"Failed to init NLP model: {e}")

class LocalNLPModel:
    def __init__(self):
        # Intents keyword mapping
        self.intent_keywords = {
            "rain": ["mưa", "bão", "ngập", "lũ", "dù", "áo mưa"],
            "sun": ["nắng", "nóng", "bình minh", "hoàng hôn", "uv", "mặt trời", "đen da"],
            "forecast": ["dự báo", "ngày mai", "tuần tới", "khi nào", "sắp tới", "tương lai"],
        }
        
    def classify_intent(self, text_input: str) -> str:
        text_input = text_input.lower()
        for intent, keywords in self.intent_keywords.items():
            for kw in keywords:
                if kw in text_input:
                    return intent
        return "current_weather" # Default intent
        
    def extract_location(self, text_input: str) -> str:
        try:
            tokens = ner(text_input)
            loc_parts = []
            
            # tokens is a list of tuples: (word, pos_tag, chunk_tag, ner_label)
            for token in tokens:
                if len(token) >= 4:
                    word, pos, chunk, label = token[0], token[1], token[2], token[3]
                    if "LOC" in label or pos == "Np":
                        loc_parts.append(word)
            
            if loc_parts:
                return " ".join(loc_parts).replace("_", " ")
        except Exception as e:
            logger.warning(f"NER extraction failed: {e}")
            
        # Fallback regex for cities if NER fails
        match = re.search(r'(tại|ở|thời tiết) ([\w\s]+)', text_input, re.IGNORECASE)
        if match:
            loc = match.group(2).strip()
            # remove some stop words from end
            for sw in ["hôm nay", "lúc", "bao nhiêu", "thế nào", "có", "không", "?"]:
                loc = loc.replace(sw, "")
            return loc.strip()
            
        return None

    async def get_city_coords(self, city_name: str, db: AsyncSession) -> Tuple[float, float, str]:
        if not city_name:
            return None, None, None
            
        ascii_city = remove_accents(city_name).lower()
            
        query = text("""
            SELECT city_name, ST_Y(geom::geometry) as lat, ST_X(geom::geometry) as lon 
            FROM cities 
            WHERE city_name ILIKE :name OR ascii_name ILIKE :ascii_name 
            LIMIT 1
        """)
        result = await db.execute(query, {"name": f"%{city_name}%", "ascii_name": f"%{ascii_city}%"})
        row = result.mappings().first()
        if row:
            return row['lat'], row['lon'], row['city_name']
        return None, None, None

nlp_service = LocalNLPModel()
