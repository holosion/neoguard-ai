// Readings that reached the server more than 2 minutes after they were measured were recorded offline and synced later.
// The server cannot know how many readings never arrived, so lost_count stays null.
export function recoveredSync(readings) {
  const late = readings.filter((r) => r.received_at && new Date(r.received_at) - new Date(r.recorded_at) > 120000);
  if (!late.length) return null;
  const ts = late.map((r) => new Date(r.recorded_at).getTime());
  return {
    recovered_count: late.length,
    lost_count: null,
    period_start: new Date(Math.min(...ts)).toISOString(),
    period_end: new Date(Math.max(...ts)).toISOString(),
  };
}
