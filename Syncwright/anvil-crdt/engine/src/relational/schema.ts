export const referenceSchema = {
  users: {
    primaryKey: "id",
    columns: ["id", "email", "name"],
    unique: [{ name: "users_email_key", columns: ["email"] }],
    defaults: {}
  },
  orders: {
    primaryKey: "id",
    columns: ["id", "user_id", "status", "total_cents"],
    unique: [],
    defaults: { total_cents: 0 },
    foreignKeys: [{ column: "user_id", referencesTable: "users", referencesColumn: "id" }]
  },
  _conflict_log: {
    primaryKey: "conflict_id",
    columns: ["conflict_id", "table_name", "constraint_name", "conflicting_value", "winner_row_id", "loser_row_id", "loser_row_data", "detected_at"],
    unique: [],
    defaults: {}
  }
};

export function tableSchema(tableName) {
  const schema = referenceSchema[tableName];
  if (!schema) throw new Error(`unknown table: ${tableName}`);
  return schema;
}

