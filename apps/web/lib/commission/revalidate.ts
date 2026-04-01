import { getUpdates } from "./query";

export type UpdatesTransport = {
  pull: (cursor: string | null) => Promise<{ changedApplicationIds: string[]; latestCursor: string }>;
};

export const pollingTransport: UpdatesTransport = {
  pull: getUpdates,
};

export function startPollingUpdates(
  onChanged: (changedApplicationIds: string[]) => void,
  opts: {
    intervalMs?: number;
    initialCursor?: string | null;
    transport?: UpdatesTransport;
  } = {},
): () => void {
  const intervalMs = opts.intervalMs ?? 6000;
  const transport = opts.transport ?? pollingTransport;
  let cursor: string | null = opts.initialCursor ?? null;
  let active = true;
  let inFlight = false;

  const tick = async () => {
    if (!active || inFlight) return;
    inFlight = true;
    try {
      const upd = await transport.pull(cursor);
      cursor = upd.latestCursor;
      if (upd.changedApplicationIds.length) onChanged(upd.changedApplicationIds);
    } catch {
      // Soft-fail; next tick retries.
    } finally {
      inFlight = false;
    }
  };

  const id = window.setInterval(() => void tick(), intervalMs);
  void tick();
  return () => {
    active = false;
    window.clearInterval(id);
  };
}

