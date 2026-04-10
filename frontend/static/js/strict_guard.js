/**
 * Strict Guard - Ultra-strict gibberish detection for critical fields
 * Used for Job Title Analysis and Manual Profile Builder in the dashboard.
 */
(function() {
  const strictGuard = {
    isGibberish: (text) => {
      if (!text) return false;
      const s = text.trim();
      const total = s.length;
      if (total < 3) return false;
      
      // Allow short common abbreviations
      const commonAbbrev = [
        "hr", "vp", "it", "ai", "ceo", "cto", "cfo", "coo", "qa", "ux", "ui", "pm", "po",
        "ba", "ma", "md", "jd", "phd", "bsc", "msc", "mba", "gpa", "sr", "jr", "ii", "iii",
        "dev", "eng", "ops", "sys", "aws", "gcp", "sql", "js", "ts", "cs", "se"
      ];
      if (commonAbbrev.includes(s.toLowerCase())) return false;

      // 1. Check for repeating characters (e.g., "aaaa")
      if (/(.)\1{3,}/.test(s)) return true;

      // 2. Check for repeating patterns (e.g., "asdasd", "abcabc")
      const repeatingPattern = /(.{2,5})\1{2,}/i;
      if (repeatingPattern.test(s)) return true;

      const alphaCount = (s.match(/[a-zA-Z]/g) || []).length;
      const digitCount = (s.match(/[0-9]/g) || []).length;
      const spaceCount = (s.match(/\s/g) || []).length;
      const symCount = total - (alphaCount + digitCount + spaceCount);
      
      // 3. High density of non-alphanumeric characters
      if (symCount / total > 0.25) return true;
      
      // 4. High density of digits mixed with alphabets
      if (alphaCount > 0 && digitCount > 0) {
        if (digitCount / (alphaCount + digitCount) > 0.35) return true;
      }

      const vowels = "aeiouy";
      const hasVowel = [...s.toLowerCase()].some(c => vowels.includes(c));
      
      // 5. No vowels in a long-ish string
      if (total > 4 && !hasVowel && alphaCount > 0) return true;
      
      const tokens = s.split(/\s+/);
      for (const tok of tokens) {
        if (tok.length > 3) {
          const tokVowels = [...tok.toLowerCase()].filter(c => vowels.includes(c)).length;
          // Very low vowel ratio (tightened to 0.18 for words like Nginx/Rhythm)
          if (tokVowels / tok.length < 0.18) return true;
          
          // High digit ratio in a single word
          const tokDigits = (tok.match(/[0-9]/g) || []).length;
          if (tokDigits / tok.length > 0.35) return true;
          
          // 5+ consonants in a row (adjusted from 4+ to allow "Strength", "Lengths")
          if (/[bcdfghjklmnpqrstvwxyz]{5,}/i.test(tok)) return true;
          if (repeatingPattern.test(tok)) return true;

          // 10. Random uppercase in the middle (e.g., "asDqe")
          // Exclude acronyms (all caps) and known CamelCase job/tech terms
          const isAllCaps = tok === tok.toUpperCase();
          const isCommonCamel = /^(DevOps|JavaScript|TypeScript|WordPress|GitHub|GitLab|DirectX|OpenGL|macOS|iOS|iPhone|iPad|AutoCAD|PostgreSQL|MongoDB|VMware|BSc|MSc|PhD|BA|MA|MBA|QA|HR|VP|IT|AI|CEO|CTO|CFO|COO|UX|UI|PM|PO|Nginx|MySQL|SaaS|PaaS|IaaS|Kafka|Docker|Kubernetes|PyTorch|TensorFlow|GraphQL|Redis|ElasticSearch|ReactJS|NextJS|NuxtJS|VueJS)$/i.test(tok);
          const hasUpperInMiddle = /[a-z][A-Z][a-z]/.test(tok);
          if (hasUpperInMiddle && !isAllCaps && !isCommonCamel) return true;
        }
      }

      // 6. Keyboard mashing patterns
      const mashingPatterns = [
        /asdf/i, /qwerty/i, /zxcv/i, /12345/, /!@#\$/, /dfgh/i, /ghjk/i, /hjkl/i, /fghj/i, /jkl;/i, /vbnm/i,
        /asdq/i, /qwer/i, /xcvb/i, /sdfg/i, /wert/i, /erty/i, /rtyu/i, /tyui/i, /uiop/i
      ];
      if (mashingPatterns.some(p => p.test(s))) return true;

      // 7. Large entropy check for no-space strings
      if (total > 10 && spaceCount === 0) {
        const uniqueChars = new Set(s.toLowerCase()).size;
        if (uniqueChars / total > 0.45) return true;
      }

      // 8. Basic alpha/space density
      const alphaSpace = alphaCount + spaceCount;
      if (alphaSpace / total < 0.55 && digitCount < (total * 0.35)) return true;

      // 9. At least one alpha character
      const hasWord = tokens.some(tok => /[a-zA-Z]/.test(tok));
      if (!hasWord && digitCount < total) return true;

      return false;
    }
  };

  // Global exposure
  window.strictGuard = strictGuard;
})();
