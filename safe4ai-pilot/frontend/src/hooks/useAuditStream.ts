import { useQuery } from "@tanstack/react-query";
import { listAuditLogs } from "../api/audit";
import type { AuditKind } from "../api/audit";
import { useState } from "react";

export function useAuditStream(start?: string, kind?: AuditKind) {
  const [page, setPage] = useState(0);
  const limit = 50;

  const { data: events = [], isLoading } = useQuery({
    queryKey: ["audit", page, start, kind ?? "all"],
    queryFn: () => listAuditLogs(page * limit, limit, start, kind),
    refetchInterval: 30_000,
  });

  return { events, isLoading, page, setPage, limit };
}
