import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteDocument, getDocumentStatus, listDocuments, reindexDocument, uploadDocument } from "../api/documents";
import { useCallback, useState } from "react";

export function useDocuments() {
  const qc = useQueryClient();
  const [polling, setPolling] = useState<Record<string, boolean>>({});
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    refetchInterval: 10_000,
    refetchIntervalInBackground: false,
    staleTime: 5_000,
  });

  const pollStatus = useCallback(async (id: string) => {
    setPolling((p) => ({ ...p, [id]: true }));
    for (let i = 0; i < 60; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      const s = await getDocumentStatus(id).catch(() => null);
      if (!s || ["indexed", "failed", "skipped"].includes(s.ingestion_status)) break;
    }
    setPolling((p) => ({ ...p, [id]: false }));
    await qc.invalidateQueries({ queryKey: ["documents"] });
  }, [qc]);

  const upload = useCallback(async (file: File) => {
    setUploadError(null);
    setIsUploading(true);
    try {
      const res = await uploadDocument(file);
      await qc.invalidateQueries({ queryKey: ["documents"] });
      pollStatus(res.id);
    } catch {
      setUploadError(`Failed to upload "${file.name}". Check file type and size, then try again.`);
    } finally {
      setIsUploading(false);
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
    isUploading,
    upload,
    uploadError,
    clearUploadError: () => setUploadError(null),
    remove: deleteMut.mutate,
    reindex: reindexMut.mutate,
  };
}
