// Minimal hook layer. No React Query — keeping deps tight. Replace with
// React Query / SWR when caching + invalidation patterns get repetitive.

import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "./client";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | Error | null;
  reload: () => void;
}

export function useApi<T>(
  path: string | null,
  opts: { orgSlug?: string; deps?: unknown[] } = {},
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api<T>(path, { orgSlug: opts.orgSlug })
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e : new Error(String(e)));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, opts.orgSlug, tick, ...(opts.deps ?? [])]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, loading, error, reload };
}

export function useMutation<TIn, TOut>(
  fn: (input: TIn) => Promise<TOut>,
): {
  call: (input: TIn) => Promise<TOut>;
  loading: boolean;
  error: ApiError | Error | null;
  data: TOut | null;
  reset: () => void;
} {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [data, setData] = useState<TOut | null>(null);

  const call = useCallback(
    async (input: TIn): Promise<TOut> => {
      setLoading(true);
      setError(null);
      try {
        const out = await fn(input);
        setData(out);
        return out;
      } catch (e) {
        const err = e instanceof Error ? e : new Error(String(e));
        setError(err);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [fn],
  );

  const reset = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  return { call, loading, error, data, reset };
}
