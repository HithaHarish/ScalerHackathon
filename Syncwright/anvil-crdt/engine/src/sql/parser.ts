export function parseValue(raw) {
  const text = String(raw).trim();
  if (text === "?") return { param: true };
  if (/^null$/i.test(text)) return null;
  if (/^-?\d+$/.test(text)) return Number(text);
  const quoted = text.match(/^'(.*)'$/s);
  if (quoted) return quoted[1].replace(/''/g, "'");
  return text;
}

export function splitComma(text) {
  const parts = [];
  let current = "";
  let quoted = false;
  for (const ch of text) {
    if (ch === "'") quoted = !quoted;
    if (ch === "," && !quoted) {
      parts.push(current.trim());
      current = "";
    } else {
      current += ch;
    }
  }
  if (current.trim()) parts.push(current.trim());
  return parts;
}

export function substitute(value, params) {
  if (value && value.param) return params.shift();
  return value;
}

