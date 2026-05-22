import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteDocument, getDocumentStatus, listDocuments, reindexDocument, uploadDocument } from "../api/documents";
import { useCallback, useEffect, useRef, useState } from "react";

export function useDocuments() {
  const qc = useQueryClient();
  // "queued" = mutation in flight (API call), "embedding" = polling for completion
  const [reindexingIds, setReindexingIds] = useState<Set<string>>(new Set());
  const [pollingIds, setPollingIds] = useState<Set<string>>(new Set());
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadCount, setUploadCount] = useState(0);
  const mountedRef = useRef(true);
  const timeoutIdsRef = useRef<number[]>([]);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      for (const timeoutId of timeoutIdsRef.current) {
        window.clearTimeout(timeoutId);
      }
      timeoutIdsRef.current = [];
    };
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
    for (let i = 0; i < 120; i++) {
      await new Promise<void>((resolve) => {
        const tid = window.setTimeout(() => {
          timeoutIdsRef.current = timeoutIdsRef.current.filter((e) => e !== tid);
          resolve();
        }, 2000);
        timeoutIdsRef.current.push(tid);
      });
      if (!mountedRef.current) return;
      const s = await getDocumentStatus(id).catch(() => null);
      if (!s || ["indexed", "failed", "skipped"].includes(s.ingestion_status)) break;
    }
    if (!mountedRef.current) return;
    setPollingIds((s) => { const n = new Set(s); n.delete(id); return n; });
    await qc.invalidateQueries({ queryKey: ["documents"] });
  }, [qc]);

  const upload = useCallback(async (file: File) => {
    setUploadError(null);
    setUploadCount((count) => count + 1);
    try {
      const res = await uploadDocument(file);
      await qc.invalidateQueries({ queryKey: ["documents"] });
      void pollStatus(res.id);
    } catch {
      if (mountedRef.current) {
        setUploadError(`Failed to upload "${file.name}". Check file type and size, then try again.`);
      }
    } finally {
      if (mountedRef.current) {
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
    clearUploadError: () => setUploadError(null),
    remove: deleteMut.mutate,
    reindex: reindexMut.mutate,
  };
}
