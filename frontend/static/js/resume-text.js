/**
 * Rebuilds readable structure from extracted resume text.
 *
 * The stored text is whatever the parser could pull out of the file, so a PDF
 * arrives as one line per visual line and a DOCX as one line per paragraph.
 * Dropped straight into a <pre> element that reads as a wall of text, which
 * is why the admin surfaces render it through this module: lines are grouped
 * back into headings, bullet lists and prose paragraphs.
 *
 * The wrap width is measured from the text itself rather than assumed. A PDF
 * wraps at the width of its text column, so the tallest quarter of the lines
 * is a good estimate of where a sentence was cut in half; a line that nearly
 * fills that width is treated as continued by the next one.
 *
 * Exposed as window.icpResumeText.blocks(text) -> [{ type, text } | { type, items }]
 */
(function () {
  // Bullet glyphs, plus the "1." / "1)" numbered form, each followed by space.
  const BULLET = /^(?:[\u2022\u00b7\u25aa\u25e6\u2023\u25cf\u25cb*+\u2013\u2014-]+|\d{1,2}[.)])\s+/;
  // A line ending on one of these has finished its sentence.
  const TERMINAL = /[.!?;]$/;
  // Lines shorter than this are never treated as "wrapped".
  const MIN_WRAP_WIDTH = 40;

  function normalize(raw) {
    return String(raw == null ? '' : raw)
      .replace(/\r\n?/g, '\n')
      .replace(/\u00a0/g, ' ')
      .replace(/[ \t]+/g, ' ')
      .replace(/[ \t]*\n[ \t]*/g, '\n')
      .replace(/\n{3,}/g, '\n\n');
  }

  /**
   * Some PDFs place every glyph individually, so extraction returns
   * "S o f t w a r e" instead of "Software". The backend detects and repairs
   * such text by re-extracting the stored file, so this is the last resort for
   * records whose original file is gone: a line whose tokens are mostly a
   * single character gets glued back together, and a change of case marks
   * where the next word starts. Word boundaries between two lowercase runs are
   * not recoverable from text alone, so "Bachelorof" is the honest best this
   * can do.
   */
  function isLetterSpaced(line) {
    const tokens = line.split(' ').filter(Boolean);
    if (tokens.length < 6) return false;
    const singles = tokens.filter((token) => token.length === 1).length;
    return singles / tokens.length >= 0.6;
  }

  function despace(line) {
    if (!isLetterSpaced(line)) return line;
    let out = '';
    let previous = '';
    for (const token of line.split(' ').filter(Boolean)) {
      if (token.length === 1) {
        if (/[a-z0-9]/.test(previous) && /[A-Z]/.test(token)) out += ' ';
        out += token;
        previous = token;
      } else {
        if (out && !/\s$/.test(out)) out += ' ';
        out += token;
        previous = token.slice(-1);
      }
    }
    return out.replace(/\s+([,.;:)])/g, '$1');
  }

  /** A section title: all capitals or ending in a colon, and short. */
  function isHeading(line) {
    if (line.length > 60) return false;
    if (line.split(' ').length > 8) return false;
    if (/[.!?;]$/.test(line)) return false;
    const letters = line.replace(/[^A-Za-z]/g, '');
    if (letters.length < 3) return false;
    return letters === letters.toUpperCase() || line.endsWith(':');
  }

  /** Where the source document wrapped, estimated from its own line lengths. */
  function wrapWidth(lines) {
    const lengths = lines
      .filter((line) => line && !BULLET.test(line) && !isHeading(line))
      .map((line) => line.length)
      .sort((a, b) => a - b);
    if (!lengths.length) return 0;
    const estimate = lengths[Math.floor(lengths.length * 0.75)];
    // Narrow lines everywhere (a sparse DOCX, a two-column layout) are not
    // evidence of a wrapped sentence, so no width is reported.
    return estimate >= MIN_WRAP_WIDTH ? estimate : 0;
  }

  function blocks(raw) {
    const text = normalize(raw);
    if (!text.trim()) return [];

    const lines = text
      .split('\n')
      .map((line) => despace(line.replace(/\s+/g, ' ').trim()));
    const wrap = wrapWidth(lines);

    const out = [];
    let para = '';
    let items = null;

    const flushPara = () => {
      if (para.trim()) out.push({ type: 'p', text: para.trim() });
      para = '';
    };
    const flushList = () => {
      if (items && items.length) out.push({ type: 'ul', items: items });
      items = null;
    };

    for (const line of lines) {
      if (!line) {
        flushPara();
        flushList();
        continue;
      }

      if (BULLET.test(line)) {
        flushPara();
        if (!items) items = [];
        items.push(line.replace(BULLET, '').trim());
        continue;
      }
      flushList();

      if (isHeading(line)) {
        flushPara();
        out.push({ type: 'h', text: line.replace(/:$/, '') });
        continue;
      }

      // Continue the open paragraph when the previous line was cut off: it
      // either fills the source width, or the new line starts mid-sentence.
      const continues =
        para &&
        !TERMINAL.test(para) &&
        (para.length >= wrap * 0.7 || /^[a-z(,;]/.test(line));

      if (continues && para.length + line.length <= 320) {
        para += ' ' + line;
      } else {
        flushPara();
        para = line;
      }
    }

    flushPara();
    flushList();
    return out;
  }

  window.icpResumeText = { blocks: blocks, normalize: normalize };
})();
