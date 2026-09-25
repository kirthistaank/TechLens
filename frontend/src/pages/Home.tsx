/**
 * Home page — displays today's daily digest as a compact numbered briefing list.
 * Each item shows recommendation badge, score badge, title, "why it matters", and bullet insights.
 * Receives archivedIds from App so archiving here also hides articles on the Articles page.
 */

import { useEffect, useRef, useState } from "react";
import { fetchDailyDigest, RateLimitError } from "../api/client";
import type { Digest, DigestItem } from "../types";

const REC_STYLE: Record<string, { badge: string; border: string }> = {
  READ:   { badge: "bg-green-600 text-white",  border: "border-l-green-500" },
  SKIM:   { badge: "bg-amber-500 text-white",  border: "border-l-amber-400" },
  IGNORE: { badge: "bg-gray-400 text-white",   border: "border-l-gray-300" },
};

interface BriefItemProps {
  item: DigestItem;
  index: number;
  onArchive: (id: number) => void;
}

/** Single compact briefing row with an archive action. */
function BriefItem({ item, index, onArchive }: BriefItemProps) {
  const style = REC_STYLE[item.recommendation] ?? REC_STYLE.IGNORE;
  const insights = item.technical_insights ?? [];

  return (
    <div className={`bg-white rounded-xl border border-gray-200 border-l-4 ${style.border} p-5 shadow-sm`}>
      {/* Header row */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="text-sm font-bold text-gray-300 w-5 shrink-0">{index + 1}</span>
        <span className={`text-xs font-bold px-2.5 py-0.5 rounded ${style.badge}`}>
          {item.recommendation}
        </span>
        <span className={`text-xs font-bold px-2.5 py-0.5 rounded ${style.badge}`}>
          {item.score?.toFixed(0)}/100
        </span>
        <span className="text-xs text-gray-400">{item.source}</span>
        {item.estimated_reading_minutes && (
          <span className="text-xs text-gray-400">{item.estimated_reading_minutes} min</span>
        )}
      </div>

      {/* Title */}
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block text-base font-semibold text-gray-900 hover:text-blue-700 hover:underline leading-snug mb-2 ml-7"
      >
        {item.title}
      </a>

      {/* Why it matters */}
      {item.why_it_matters && (
        <p className="text-sm text-gray-600 ml-7 mb-2 leading-relaxed">{item.why_it_matters}</p>
      )}

      {/* Bullet insights */}
      {insights.length > 0 && (
        <ul className="ml-9 space-y-1">
          {insights.map((point, i) => (
            <li key={i} className="text-xs text-gray-500 list-disc leading-relaxed">{point}</li>
          ))}
        </ul>
      )}

      {/* Archive action */}
      <div className="mt-3 ml-7">
        <button
          onClick={() => onArchive(item.id)}
          className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
        >
          Archive
        </button>
      </div>
    </div>
  );
}

interface Props {
  archivedIds: Set<number>;
  onArchive: (id: number) => void;
}

/**
 * Fetches and renders the daily digest.
 * Shows a loading state, a pipeline-progress empty state, and the digest when ready.
 */
export default function Home({ archivedIds, onArchive }: Props) {
  const [digest, setDigest] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(true);
  const [rateLimited, setRateLimited] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = () => {
    fetchDailyDigest()
      .then((d) => {
        setRateLimited(false);
        setDigest(d);
        // Stop polling once digest has items — pipeline is done
        if (d.items.length > 0 && intervalRef.current !== null) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      })
      .catch((err) => {
        if (err instanceof RateLimitError) {
          setRateLimited(true);
        } else {
          setDigest(null);
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // Only start polling interval for the pipeline-running empty state
    intervalRef.current = setInterval(load, 30_000);
    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current);
    };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Loading…
      </div>
    );
  }

  if (rateLimited) {
    return (
      <div className="flex items-center justify-center h-64 text-center px-4">
        <div>
          <p className="text-gray-500 font-medium">Too many requests — please wait a moment and refresh.</p>
        </div>
      </div>
    );
  }

  /** Empty state — nothing collected yet or pipeline still running. */
  if (!digest || digest.items.length === 0) {
    const collected = digest?.total_collected ?? 0;
    const scored = digest?.total_scored ?? 0;

    return (
      <div className="max-w-2xl mx-auto mt-16 text-center px-4">
        <p className="text-2xl mb-3">📭</p>
        <p className="text-gray-700 font-medium text-lg mb-2">No brief ready yet for today</p>

        {collected === 0 ? (
          <p className="text-gray-400 text-sm">
            Click <strong className="text-blue-600">Run Pipeline</strong> in the toolbar to collect and score articles.
          </p>
        ) : (
          <div className="text-gray-400 text-sm space-y-1">
            <p>{collected} articles collected · {scored} scored so far</p>
            <p>Pipeline is still running — this page refreshes automatically every 30 seconds.</p>
            {scored > 0 && scored < collected && (
              <div className="mt-4 w-full bg-gray-100 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all"
                  style={{ width: `${Math.round((scored / collected) * 100)}%` }}
                />
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  const visibleItems = digest.items.filter((item) => !archivedIds.has(item.id));
  const totalMins = visibleItems.reduce(
    (sum, item) => sum + (item.estimated_reading_minutes ?? 0), 0
  );

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Digest header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Today's AI Brief
          <span className="ml-3 text-base font-normal text-gray-400">{digest.date}</span>
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          {visibleItems.length} items · {digest.total_scored} scored from {digest.total_collected} collected
          {totalMins > 0 && (
            <span className="ml-2 text-blue-500 font-medium">· ~{totalMins} min total</span>
          )}
        </p>
      </div>

      {/* Compact briefing list */}
      <div className="space-y-3">
        {visibleItems.map((item, i) => (
          <BriefItem key={item.id} item={item} index={i} onArchive={onArchive} />
        ))}
      </div>
    </div>
  );
}
