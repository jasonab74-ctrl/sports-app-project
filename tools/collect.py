import os
import re
import json
import yaml
import feedparser
import requests
import tempfile
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urlunparse
from rapidfuzz import fuzz

# =====================================================
# CONFIG
# =====================================================

MAX_RESULTS = 20            # we only ship top 20
MAX_AGE_DAYS = 14           # rolling window
DEDUP_TITLE_SIM = 85        # fuzzy title dedupe threshold
HTTP_TIMEOUT = 6            # seconds for thumbnail scrape

FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (PurdueMBBHub/1.0)"
}

# Canonical source names we want to show in UI
SOURCE_CANON = {
    "hammer & rails": "Hammer & Rails",
    "hammerandrials": "Hammer & Rails",
    "hammerandrails": "Hammer & Rails",

    "journal & courier": "Journal & Courier",
    "journal and courier": "Journal & Courier",
    "jconline": "Journal & Courier",

    "goldandblack": "GoldandBlack (Rivals)",
    "gold and black": "GoldandBlack (Rivals)",
    "rivals": "GoldandBlack (Rivals)",
    "goldandblack.com": "GoldandBlack (Rivals)",

    "on3 purdue": "On3 Purdue",
    "on3.com": "On3 Purdue",
    "on3": "On3 Purdue",

    "espn": "ESPN",
    "espn.com": "ESPN",

    "yahoo sports": "Yahoo Sports",
    "sports.yahoo.com": "Yahoo Sports",
    "yahoo!": "Yahoo Sports",

    "cbs sports": "CBS Sports",
    "cbssports.com": "CBS Sports",

    "field of 68": "Field of 68",
    "the field of 68": "Field of 68",

    "the athletic": "The Athletic",
    "theathletic.com": "The Athletic",

    "stadium / jeff goodman": "Stadium / Jeff Goodman",
    "stadium": "Stadium / Jeff Goodman",
    "watchstadium.com": "Stadium / Jeff Goodman",

    "associated press (ap)": "Associated Press (AP)",
    "ap news": "Associated Press (AP)",
    "apnews.com": "Associated Press (AP)",
    "associated press": "Associated Press (AP)",

    "big ten network": "Big Ten Network",
    "btn.com": "Big Ten Network",
    "btn": "Big Ten Network",

    "p