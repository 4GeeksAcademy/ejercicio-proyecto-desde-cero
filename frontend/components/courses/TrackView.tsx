"use client";

import { useEffect } from "react";

/** Registra una visita anónima (analítica de negocio). Sin cookies, sin IP, sin usuario. */
export function TrackView({ courseId }: { courseId: string }) {
  useEffect(() => {
    fetch(`/api/v1/courses/${courseId}/view`, { method: "POST", keepalive: true }).catch(() => {});
  }, [courseId]);
  return null;
}
