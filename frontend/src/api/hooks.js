// Minimal hook layer. No React Query — keeping deps tight. Replace with
// React Query / SWR when caching + invalidation patterns get repetitive.
import { useCallback, useEffect, useState } from "react";
import { api } from "./client";
export function useApi(path, opts = {}) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [tick, setTick] = useState(0);
    useEffect(() => {
        if (path === null)
            return;
        let cancelled = false;
        setLoading(true);
        setError(null);
        api(path, { orgSlug: opts.orgSlug })
            .then((d) => {
            if (!cancelled)
                setData(d);
        })
            .catch((e) => {
            if (!cancelled)
                setError(e instanceof Error ? e : new Error(String(e)));
        })
            .finally(() => {
            if (!cancelled)
                setLoading(false);
        });
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [path, opts.orgSlug, tick, ...(opts.deps ?? [])]);
    const reload = useCallback(() => setTick((t) => t + 1), []);
    return { data, loading, error, reload };
}
export function useMutation(fn) {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);
    const call = useCallback(async (input) => {
        setLoading(true);
        setError(null);
        try {
            const out = await fn(input);
            setData(out);
            return out;
        }
        catch (e) {
            const err = e instanceof Error ? e : new Error(String(e));
            setError(err);
            throw err;
        }
        finally {
            setLoading(false);
        }
    }, [fn]);
    const reset = useCallback(() => {
        setData(null);
        setError(null);
    }, []);
    return { call, loading, error, data, reset };
}
