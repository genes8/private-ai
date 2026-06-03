import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteDocument, getDocumentStatus, listDocuments, reindexDocument, uploadDocument } from "../api/documents";
import { useCallback, useEffect, useRef, useState } from "react";

const terminalIngestionStatuses = new Set(["indexed", "failed", "skipped"]);

function cleanupDocumentPolling(mountedRef: React.MutableRefObject<boolean>, timeoutIds: number[]) {
  mountedRef.current = false;
  for (const timeoutId of timeoutIds) {
    window.clearTimeout(timeoutId);
  }
  timeoutIds.length = 0;
}

export function useDocuments() {
  const qc = useQueryClient();
  // "queued" = mutation in flight (API call), "embedding" = polling for completion
  const [reindexingIds, setReindexingIds] = useState<Set<string>>(new Set());
  const [pollingIds, setPollingIds] = useState<Set<string>>(new Set());
  const [uploadError, setUploadError] = useState<string | null>(null);
  const failedUploadNamesRef = useRef<string[]>([]);
  const activeUploadCountRef = useRef(0);
  const [uploadCount, setUploadCount] = useState(0);
  const mountedRef = useRef(true);
  const timeoutIdsRef = useRef<number[]>([]);

  useEffect(() => {
    const timeoutIds = timeoutIdsRef.current;
    return () => cleanupDocumentPolling(mountedRef, timeoutIds);
  }, []);

  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    refetchInterval: 5_000,
    refetchIntervalInBackground: false,
    staleTime: 3_000,
  });

  const pollStatus = useCallback(async (id: string) => {
    if (!mountedRef.current) return;
    setPollingIds((s) => { const n = new Set(s); n.add(id); return n; });
    let attemptsRemaining = 120;
    const pollOnce = (): Promise<void> => {
      if (attemptsRemaining <= 0) return Promise.resolve();
      attemptsRemaining -= 1;
      return new Promise<void>((resolve) => {
        const tid = window.setTimeout(() => {
          timeoutIdsRef.current = timeoutIdsRef.current.filter((e) => e !== tid);
          resolve();
        }, 2000);
        timeoutIdsRef.current.push(tid);
      }).then(() => {
        if (!mountedRef.current) return;
        return getDocumentStatus(id).catch(() => null);
      }).then((s) => {
        if (!mountedRef.current || !s || terminalIngestionStatuses.has(s.ingestion_status)) return;
        return pollOnce();
      });
    };
    return pollOnce().then(() => {
      if (!mountedRef.current) return;
      setPollingIds((s) => { const n = new Set(s); n.delete(id); return n; });
      return qc.invalidateQueries({ queryKey: ["documents"] });
    });
  }, [qc]);

  const upload = useCallback(async (file: File) => {
    if (activeUploadCountRef.current === 0) {
      failedUploadNamesRef.current = [];
      setUploadError(null);
    }
    activeUploadCountRef.current += 1;
    setUploadCount((count) => count + 1);
    try {
      const res = await uploadDocument(file);
      await qc.invalidateQueries({ queryKey: ["documents"] });
      void pollStatus(res.id);
    } catch {
      if (mountedRef.current) {
        failedUploadNamesRef.current = [...failedUploadNamesRef.current, file.name];
        const names = failedUploadNamesRef.current.map((name) => `"${name}"`).join(", ");
        setUploadError(`Failed to upload ${names}. Check file type and size, then try again.`);
      }
    } finally {
      if (mountedRef.current) {
        activeUploadCountRef.current = Math.max(0, activeUploadCountRef.current - 1);
        setUploadCount((count) => Math.max(0, count - 1));
      }
    }
  }, [qc, pollStatus]);

  const deleteMut = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  const reindexMut = useMutation({
    mutationFn: reindexDocument,
    onMutate: (id: string) => {
      // Immediately show "queued" status before API responds
      setReindexingIds((s) => { const n = new Set(s); n.add(id); return n; });
    },
    onSuccess: (_, id) => {
      void qc.invalidateQueries({ queryKey: ["documents"] });
      setReindexingIds((s) => { const n = new Set(s); n.delete(id); return n; });
      void pollStatus(id);
    },
    onError: (_, id) => {
      setReindexingIds((s) => { const n = new Set(s); n.delete(id); return n; });
    },
  });

  return {
    docs: docs.map((d) => ({
      ...d,
      status: pollingIds.has(d.id)
        ? ("embedding" as const)
        : reindexingIds.has(d.id)
          ? ("queued" as const)
          : d.status,
    })),
    isLoading,
    isUploading: uploadCount > 0,
    upload,
    uploadError,
    clearUploadError: () => {
      failedUploadNamesRef.current = [];
      setUploadError(null);
    },
    remove: deleteMut.mutate,
    reindex: reindexMut.mutate,
  };
}
