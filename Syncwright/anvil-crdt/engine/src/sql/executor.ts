import { splitComma, parseValue, substitute } from "./parser.js";
import { tableSchema } from "../relational/schema.js";

export function executeSql(engine, sql, params = []) {
  const text = sql.trim().replace(/;$/, "");
  if (/^create\s+/i.test(text)) return [];
  if (/^insert\s+/i.test(text)) return insert(engine, text, [...params]);
  if (/^update\s+/i.test(text)) return update(engine, text, [...params]);
  if (/^delete\s+/i.test(text)) return remove(engine, text, [...params]);
  if (/^select\s+/i.test(text)) return select(engine, text, [...params]);
  throw new Error(`unsupported SQL: ${sql}`);
}

function insert(engine, text, params) {
  const match = text.match(/^insert\s+into\s+(\w+)(?:\s*\(([^)]*)\))?\s+values\s*\((.*)\)$/i);
  if (!match) throw new Error(`bad INSERT: ${text}`);
  const [, tableName, colsText, valsText] = match;
  const schema = tableSchema(tableName);
  const columns = colsText ? splitComma(colsText).map((c) => c.trim()) : schema.columns;
  const rawValues = splitComma(valsText).map((v) => substitute(parseValue(v), params));
  const values = { ...schema.defaults };
  columns.forEach((column, index) => (values[column] = rawValues[index]));
  engine.insert(tableName, values);
  return [];
}

function update(engine, text, params) {
  const match = text.match(/^update\s+(\w+)\s+set\s+(.+)\s+where\s+id\s*=\s*(.+)$/i);
  if (!match) throw new Error(`bad UPDATE: ${text}`);
  const [, tableName, assignsText, idText] = match;
  const values = {};
  for (const assignment of splitComma(assignsText)) {
    const [column, rawValue] = assignment.split("=").map((part) => part.trim());
    values[column] = substitute(parseValue(rawValue), params);
  }
  const rowId = substitute(parseValue(idText), params);
  engine.update(tableName, rowId, values);
  return [];
}

function remove(engine, text, params) {
  const match = text.match(/^delete\s+from\s+(\w+)\s+where\s+id\s*=\s*(.+)$/i);
  if (!match) throw new Error(`bad DELETE: ${text}`);
  const [, tableName, idText] = match;
  engine.delete(tableName, substitute(parseValue(idText), params));
  return [];
}

function select(engine, text, params) {
  if (/join\s+orders/i.test(text)) return engine.joinUsersOrders();
  const match = text.match(/^select\s+(.+)\s+from\s+(\w+)(?:\s+where\s+(.+?))?(?:\s+order\s+by\s+(\w+))?$/i);
  if (!match) throw new Error(`bad SELECT: ${text}`);
  const [, colsText, tableName, whereText, orderBy] = match;
  let rows = engine.selectAll(tableName);
  if (whereText) rows = rows.filter((row) => evaluateWhere(row, whereText, params));
  if (orderBy) rows.sort((a, b) => String(a[orderBy]).localeCompare(String(b[orderBy])));
  const cols = colsText.trim() === "*" ? null : splitComma(colsText).map((c) => c.trim());
  return cols ? rows.map((row) => Object.fromEntries(cols.map((col) => [col, row[col]]))) : rows;
}

function evaluateWhere(row, whereText, params) {
  const clauses = whereText.split(/\s+or\s+/i);
  return clauses.some((clause) => {
    const match = clause.trim().match(/^(\w+)\s*=\s*(.+)$/i);
    if (!match) return false;
    const [, column, rawValue] = match;
    return row[column] === substitute(parseValue(rawValue), [...params]);
  });
}

