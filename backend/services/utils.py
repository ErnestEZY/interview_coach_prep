from datetime import datetime, timezone, timedelta

def get_malaysia_time():
    """Returns current time in Malaysia timezone (UTC+8)"""
    return datetime.now(timezone(timedelta(hours=8)))

def is_gibberish(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return True
    
    # Allow short common abbreviations (like HR, VP, IT, AI, CEO)
    common_abbrev = {"hr", "vp", "it", "ai", "ceo", "cto", "cfo", "coo", "qa", "ux", "ui", "pm"}
    if s.lower() in common_abbrev:
        return False
        
    total = len(s)
    if total < 2:
        return True
        
    alpha_space = sum(1 for c in s if c.isalpha() or c.isspace())
    sym = sum(1 for c in s if not (c.isalnum() or c.isspace()))
    has_vowel = any(v in s.lower() for v in "aeiouy") # added 'y' as semi-vowel
    
    # Check if there's at least one word-like token
    tokens = s.split()
    has_word = any(tok.isalpha() and len(tok) >= 1 for tok in tokens)
    
    if alpha_space / total < 0.4: # slightly more relaxed
        return True
    if sym / total > 0.4: # slightly more relaxed
        return True
    
    # If it's short, we relax vowel requirement (e.g., "HR")
    if total > 4 and not has_vowel:
        return True
        
    if not has_word:
        return True
        
    return False
