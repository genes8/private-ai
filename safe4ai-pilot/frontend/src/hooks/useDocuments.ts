import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteDocument, getDocumentStatus, listDocuments, reindexDocument, uploadDocument } from "../api/documents";
import { useCallback, useEffect, useRef, useState } from "react";

export function useDocuments() {
  const qc = useQueryClient();
  const [polling, setPolling] = useState<Record<string, boolean>>({});
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
    refetchInterval: 10_000,
    refetchIntervalInBackground: false,
    staleTime: 5_000,
  });

  const pollStatus = useCallback(async (id: string) => {
    if (!mountedRef.current) return;
    setPolling((p) => ({ ...p, [id]: true }));
    for (let i = 0; i < 60; i++) {
      await new Promise<void>((resolve) => {
        const timeoutId = window.setTimeout(() => {
          timeoutIdsRef.current = timeoutIdsRef.current.filter((entry) => entry !== timeoutId);
          resolve();
        }, 2000);
        timeoutIdsRef.current.push(timeoutId);
      });
      if (!mountedRef.current) return;
      const s = await getDocumentStatus(id).catch(() => null);
      if (!s || ["indexed", "failed", "skipped"].includes(s.ingestion_status)) break;
    }
    if (!mountedRef.current) return;
    setPolling((p) => ({ ...p, [id]: false }));
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
    onSuccess: (_, id) => pollStatus(id),
  });

  return {
    docs: docs.map((d) => ({
      ...d,
      status: polling[d.id] ? ("embedding" as const) : d.status,
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
