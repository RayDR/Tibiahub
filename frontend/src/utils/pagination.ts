export function boundedWindow<T>(rows: T[], limit: number): { items: T[]; hasMore: boolean } {
  return { items: rows.slice(0, limit), hasMore: rows.length > limit };
}

export function clampPageSkip(skip: number, limit: number, total: number): number {
  if (total <= 0) return 0;
  const lastSkip = Math.floor((total - 1) / limit) * limit;
  return Math.min(Math.max(0, skip), lastSkip);
}
