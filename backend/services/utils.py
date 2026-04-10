from datetime import datetime, timezone, timedelta

def get_malaysia_time():
    """Returns current time in Malaysia timezone (UTC+8)"""
    return datetime.now(timezone(timedelta(hours=8)))

def is_gibberish(text: str, strict: bool = True) -> bool:
    s = (text or "").strip()
    if not s:
        return True
    
    # Allow short common abbreviations
    common_abbrev = {
        "hr", "vp", "it", "ai", "ceo", "cto", "cfo", "coo", "qa", "ux", "ui", "pm", "po",
        "ba", "ma", "md", "jd", "phd", "bsc", "msc", "mba", "gpa", "sr", "jr", "ii", "iii",
        "dev", "eng", "ops", "sys", "aws", "gcp", "sql", "js", "ts", "cs", "se"
    }
    if s.lower() in common_abbrev:
        return False
        
    total = len(s)
    if total < 2:
        return True
        
    import re
    alpha_count = sum(1 for c in s if c.isalpha())
    digit_count = sum(1 for c in s if c.isdigit())
    space_count = sum(1 for c in s if c.isspace())
    sym_count = total - (alpha_count + digit_count + space_count)
    tokens = s.split()
    word_count = len(tokens)

    # --- LIGHT MODE (Interview Responses) ---
    if not strict:
        if word_count >= 2 and alpha_count > 8:
            if re.search(r'(.)\1{8,}', s): return True
            if sym_count / total > 0.5: return True
            return False
        
        if re.search(r'(.)\1{4,}', s): return True
        if sym_count / total > 0.4: return True
        if total > 6 and alpha_count > 0 and not any(v in s.lower() for v in "aeiouy"): return True
        
        mashing_patterns = [r'asdf', r'qwerty', r'zxcv', r'12345', r'!@#\$']
        if any(re.search(p, s, re.I) for p in mashing_patterns): return True
        return False

    # --- STRICT MODE (Job Titles, Profile Data) ---
    # 1. Check for long sequences of repeated characters
    if re.search(r'(.)\1{3,}', s):
        return True

    # 2. Check for repeating patterns of characters
    repeating_pattern = r'(.{2,5})\1{2,}'
    if re.search(repeating_pattern, s, re.I):
        return True

    # 3. High density of non-alphanumeric characters
    if (sym_count / total) > 0.25:
        return True
        
    # 4. High density of digits mixed with alphabets
    if alpha_count > 0 and digit_count > 0:
        if (digit_count / (alpha_count + digit_count)) > 0.35:
            return True

    # 5. Check for strings with no vowels
    vowels = "aeiouy"
    has_vowel = any(v in s.lower() for v in vowels)
    if total > 4 and not has_vowel and alpha_count > 0:
        return True
        
    for tok in tokens:
        if len(tok) > 3:
            tok_vowels = sum(1 for c in tok.lower() if c in vowels)
            # Very low vowel ratio (tightened to 0.18 for words like Nginx/Rhythm)
            if tok_vowels / len(tok) < 0.18:
                return True
            tok_digits = sum(1 for c in tok if c.isdigit())
            if tok_digits / len(tok) > 0.35:
                return True
            # 5+ consonants in a row (adjusted from 4+ to allow "Strength", "Lengths")
            if re.search(r'[bcdfghjklmnpqrstvwxyz]{5,}', tok, re.I):
                return True
            if re.search(repeating_pattern, tok, re.I):
                return True
            
            # 10. Random uppercase in the middle (e.g., "asDqe")
            # Exclude acronyms (all caps) and known CamelCase job/tech terms
            is_all_caps = tok == tok.upper()
            is_common_camel = bool(re.search(r'^(DevOps|JavaScript|TypeScript|WordPress|GitHub|GitLab|DirectX|OpenGL|macOS|iOS|iPhone|iPad|AutoCAD|PostgreSQL|MongoDB|VMware|BSc|MSc|PhD|BA|MA|MBA|QA|HR|VP|IT|AI|CEO|CTO|CFO|COO|UX|UI|PM|PO|Nginx|MySQL|SaaS|PaaS|IaaS|Kafka|Docker|Kubernetes|PyTorch|TensorFlow|GraphQL|Redis|ElasticSearch|ReactJS|NextJS|NuxtJS|VueJS)$', tok, re.I))
            has_upper_in_middle = bool(re.search(r'[a-z][A-Z][a-z]', tok))
            if has_upper_in_middle and not is_all_caps and not is_common_camel:
                return True

    # 6. Common "keyboard mashing" patterns
    mashing_patterns = [
        r'asdf', r'qwerty', r'zxcv', r'12345', r'!@#\$', r'dfgh', r'ghjk', r'hjkl', r'fghj', r'jkl;', r'vbnm',
        r'asdq', r'qwer', r'xcvb', r'sdfg', r'wert', r'erty', r'rtyu', r'tyui', r'uiop'
    ]
    if any(re.search(p, s, re.I) for p in mashing_patterns):
        return True

    # 7. Check for randomness: many unique characters in a short string
    if total > 10 and len(set(s.lower())) / total > 0.45 and space_count == 0:
        return True

    # 8. Basic alpha/space check
    alpha_space = alpha_count + space_count
    if alpha_space / total < 0.55 and digit_count < (total * 0.35):
        return True

    # 9. At least one alpha character
    has_word = any(tok.isalpha() and len(tok) >= 1 for tok in tokens)
    if not has_word and digit_count < total:
        return True
        
    return False
