export function rebuildSecondaryIndexes(engine) {
  const byUser = new Map();
  const orders = engine.tables.get("orders");
  if (!orders) return { orders_by_user: byUser };
  for (const { data } of orders.allRows()) {
    const key = `${data.user_id ?? ""}\u0000${data.status ?? ""}`;
    if (!byUser.has(key)) byUser.set(key, []);
    byUser.get(key).push(data.id);
  }
  return { orders_by_user: byUser };
}

