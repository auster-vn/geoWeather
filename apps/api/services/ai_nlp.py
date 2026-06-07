import re
import logging
from underthesea import ner
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
import unicodedata
from flashtext import KeywordProcessor

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
        self.vn_provinces = [
            "hà nội", "hồ chí minh", "sài gòn", "đà nẵng", "hải phòng", "cần thơ", 
            "an giang", "bà rịa", "vũng tàu", "bạc liêu", "bắc giang", "bắc kạn", "bắc ninh",
            "bến tre", "bình dương", "bình định", "bình phước", "bình thuận", "cà mau",
            "cao bằng", "đắk lắk", "đắk nông", "điện biên", "đồng nai", "đồng tháp",
            "gia lai", "hà giang", "hà nam", "hà tĩnh", "hải dương", "hậu giang",
            "hoà bình", "hưng yên", "khánh hòa", "kiên giang", "kon tum", "lai châu",
            "lâm đồng", "lạng sơn", "lào cai", "long an", "nam định", "nghệ an",
            "ninh bình", "ninh thuận", "phú thọ", "phú yên", "quảng bình", "quảng nam",
            "quảng ngãi", "quảng ninh", "quảng trị", "sóc trăng", "sơn la", "tây ninh",
            "thái bình", "thái nguyên", "thanh hóa", "thừa thiên huế", "huế",
            "tiền giang", "trà vinh", "tuyên quang", "vĩnh long", "vĩnh phúc", "yên bái"
        ]
        self.keyword_processor = KeywordProcessor(case_sensitive=False)
        self._is_initialized = False

    async def _initialize_keywords(self, db: AsyncSession):
        if self._is_initialized:
            return
            
        logger.info("Initializing FlashText KeywordProcessor with VN locations...")
        query = text("SELECT city_name, ascii_name FROM cities WHERE country_code = 'VN'")
        result = await db.execute(query)
        
        # Load all 53k cities into memory for O(1) text extraction
        for row in result:
            city_name = row[0]
            ascii_name = row[1]
            if city_name:
                self.keyword_processor.add_keyword(city_name.lower(), city_name)
            if ascii_name:
                self.keyword_processor.add_keyword(ascii_name.lower(), city_name)
                
        # Add all VN provinces as keywords to prevent partial matches 
        # (e.g. extracting "Hồ" instead of "Hồ Chí Minh")
        for province in self.vn_provinces:
            # handle special cases for title capitalization
            title_province = province.title()
            if title_province == "Hồ Chí Minh":
                title_province = "Ho Chi Minh City"
            self.keyword_processor.add_keyword(province.lower(), title_province)
                
        # Also add common aliases
        self.keyword_processor.add_keyword("sài gòn", "Ho Chi Minh City")
        self.keyword_processor.add_keyword("sg", "Ho Chi Minh City")
        self.keyword_processor.add_keyword("hn", "Hà Nội")
        self.keyword_processor.add_keyword("đn", "Đà Nẵng")
        self.keyword_processor.add_keyword("hcm", "Ho Chi Minh City")
        self.keyword_processor.add_keyword("hcmc", "Ho Chi Minh City")
        
        self._is_initialized = True
        logger.info("FlashText initialization complete.")
        
    def classify_intent(self, text_input: str) -> str:
        text_input = text_input.lower()
        for intent, keywords in self.intent_keywords.items():
            for kw in keywords:
                if kw in text_input:
                    return intent
        return "current_weather" # Default intent
        
    def extract_time(self, text_input: str) -> str:
        # Match pattern: <number> [giờ|h|g] [sáng|trưa|chiều|tối|đêm]
        match = re.search(r'(\d{1,2})\s*(?:giờ|h|g)\b(?:\s*(sáng|trưa|chiều|tối|đêm))?', text_input, re.IGNORECASE)
        if match:
            hour = int(match.group(1))
            meridiem = match.group(2)
            
            if meridiem:
                meridiem = meridiem.lower()
                if meridiem in ["chiều", "tối", "đêm"] and hour < 12:
                    hour += 12
            
            if 0 <= hour <= 23:
                return f"{hour:02d}:00"
        return None
        
    async def extract_location(self, text_input: str, db: AsyncSession) -> str:
        # Lazy initialization of flashtext with DB
        if not self._is_initialized:
            await self._initialize_keywords(db)
            
        # 1. First try FlashText (handles all 53k+ communes, districts, provinces instantly)
        extracted = self.keyword_processor.extract_keywords(text_input.lower())
        if extracted:
            return extracted[-1]
            
        # 2. Try Underthesea NER as fallback
        try:
            tokens = ner(text_input)
            for word, pos, chunk, label in tokens:
                if label == 'B-LOC' or label == 'I-LOC':
                    return word
        except Exception as e:
            logger.warning(f"NER extraction failed: {e}")
            
        # 3. Fallback regex for cities
        match = re.search(r'(tại|ở|thời tiết|cho) ([\w\s]+)', text_input, re.IGNORECASE)
        if match:
            loc = match.group(2).strip()
            # remove some stop words from end
            for sw in ["hôm nay", "lúc", "bao nhiêu", "thế nào", "có", "không", "?", "mấy giờ", "giờ"]:
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
            WHERE city_name ILIKE :exact_name 
               OR ascii_name ILIKE :exact_ascii
               OR city_name ILIKE :like_name 
               OR ascii_name ILIKE :like_ascii
            ORDER BY 
               (city_name ILIKE :exact_name OR ascii_name ILIKE :exact_ascii) DESC,
               (country_code = 'VN') DESC,
               population DESC NULLS LAST
            LIMIT 1
        """)
        result = await db.execute(query, {
            "exact_name": city_name,
            "exact_ascii": ascii_city,
            "like_name": f"%{city_name}%", 
            "like_ascii": f"%{ascii_city}%"
        })
        row = result.mappings().first()
        if row:
            return row['lat'], row['lon'], row['city_name']
        return None, None, None

nlp_service = LocalNLPModel()
