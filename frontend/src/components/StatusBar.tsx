/**
 * StatusBar — shows pipeline health at the top of every page:
 * Ollama availability, article counts by stage, and a manual run button.
 */

import { useEffect, useState } from "react";
import { fetchPipelineStatus, triggerPipeline } from "../api/client";
import type { PipelineStatus } from "../types";

/**
 * Displays Ollama status, article stage counts, and a "Run Pipeline" button.
 * Polls status every 30 seconds while mounted.
 */
export default function StatusBar() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("");

  /** Fetch current pipeline status from the API. */
  const refresh = () => {
    fetchPipelineStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, []);

  /** Trigger a manual pipeline run and show a confirmation message. */
  const handleRun = async () => {
    setRunning(true);
    try {
      const res = await triggerPipeline();
      setMessage(res.message);
      setTimeout(() => setMessage(""), 5000);
    } finally {
      setRunning(false);
      setTimeout(refresh, 3000);
    }
  };

  return (
    <div className="bg-white border-b border-gray-200 px-6 py-2 flex flex-wrap items-center gap-4 text-sm text-gray-600">
      {/* Ollama availability indicator */}
      <span className="flex items-center gap-1.5">
        <span className={`w-2 h-2 rounded-full ${status?.ollama_available ? "bg-green-500" : "bg-red-500"}`} />
        Ollama {status?.ollama_available ? "online" : "offline"}
      </span>

      {/* Article stage counts */}
      {status && (
        <>
          <span>Total: {status.total_articles}</span>
          <span>Scored: {status.scored}</span>
          <span>Summarized: {status.summarized}</span>
          {status.failed > 0 && (
            <span className="text-red-500">Failed: {status.failed}</span>
          )}
        </>
      )}

      {/* Manual pipeline trigger */}
      <button
        onClick={handleRun}
        disabled={running}
        className="ml-auto bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs px-3 py-1 rounded font-medium transition-colors"
      >
        {running ? "Running…" : "Run Pipeline"}
      </button>

      {message && <span className="text-green-600 text-xs">{message}</span>}
    </div>
  );
}
