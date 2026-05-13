import { useQuery } from "@tanstack/react-query";
import { listAuditLogs } from "../api/audit";
import { useState } from "react";

export function useAuditStream(start?: string) {
  const [page, setPage] = useState(0);
  const limit = 50;

  const { data: events = [], isLoading } = useQuery({
    queryKey: ["audit", page, start],
    queryFn: () => listAuditLogs(page * limit, limit, start),
    refetchInterval: 30_000,
  });

  return { events, isLoading, page, setPage, limit };
}
