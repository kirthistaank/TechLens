/**
 * ArticleCard — displays a single article with score badge, summary sections,
 * and user feedback actions (save, important, open tracking, rating, archive).
 */

import { useState } from "react";
import { recordOpen, rateArticle, toggleImportant, toggleSave } from "../api/client";

/** Unified shape accepted by ArticleCard — works for both Article and DigestItem. */
type CardData = {
  id: number;
  title: string;
  url: string;
  source: string;
  score: number | null;
  recommendation: "READ" | "SKIM" | "IGNORE" | null;
  technical_insights: string[];
  categories: string[];
  estimated_reading_minutes?: number | null;
  what_happened?: string | null;
  why_it_matters?: string | null;
  architecture_implication?: string | null;
  tradeoffs?: string | null;
  is_archived?: boolean;
  is_saved?: boolean;
  is_important?: boolean;
  opened_at?: string | null;
  user_rating?: "up" | "down" | null;
};

/** Colour and label config for each recommendation tier. */
const BADGE: Record<string, { bg: string; label: string }> = {
  READ:   { bg: "bg-green-600",  label: "READ" },
  SKIM:   { bg: "bg-amber-500",  label: "SKIM" },
  IGNORE: { bg: "bg-gray-400",   label: "IGNORE" },
};

interface Props {
  data: CardData;
  onArchive?: (id: number) => void;
  /** Called after save/important/rating so parent can update its local copy. */
  onFeedback?: (id: number, patch: Partial<CardData>) => void;
}

/**
 * Renders a card for a single article with recommendation badge, score,
 * structured summary, feedback actions, and a link to the original article.
 */
export default function ArticleCard({ data, onArchive, onFeedback }: Props) {
  const [saved, setSaved]         = useState(data.is_saved ?? false);
  const [important, setImportant] = useState(data.is_important ?? false);
  const [rating, setRating]       = useState<"up" | "down" | null>(data.user_rating ?? null);
  const [opened, setOpened]       = useState(!!data.opened_at);

  const rec   = data.recommendation ?? "IGNORE";
  const badge = BADGE[rec] ?? BADGE.IGNORE;

  const whatHappened = data.what_happened ?? null;
  const whyMatters   = data.why_it_matters ?? null;
  const architecture = data.architecture_implication ?? null;
  const tradeoffs    = data.tradeoffs ?? null;

  const handleSave = async () => {
    const next = !saved;
    setSaved(next);
    await toggleSave(data.id).catch(() => setSaved(!next));
    onFeedback?.(data.id, { is_saved: next });
  };

  const handleImportant = async () => {
    const next = !important;
    setImportant(next);
    await toggleImportant(data.id).catch(() => setImportant(!next));
    onFeedback?.(data.id, { is_important: next });
  };

  const handleRate = async (r: "up" | "down") => {
    const next = rating === r ? null : r;
    setRating(next);
    await rateArticle(data.id, next).catch(() => setRating(rating));
    onFeedback?.(data.id, { user_rating: next });
  };

  const handleOpen = () => {
    if (!opened) {
      setOpened(true);
      recordOpen(data.id);
    }
  };

  return (
    <div className={`bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-shadow ${opened ? "border-l-4 border-l-blue-200" : ""}`}>
      {/* Header row */}
      <div className="flex flex-wrap items-center gap-2 mb-3 text-sm">
        <span className={`${badge.bg} text-white px-2.5 py-0.5 rounded font-semibold text-xs`}>
          {badge.label}
        </span>
        <span className="text-gray-500">{data.source}</span>
        {data.score !== null && (
          <span className="text-gray-400">Score: {data.score?.toFixed(0)}/100</span>
        )}
        {data.estimated_reading_minutes && (
          <span className="text-gray-400">{data.estimated_reading_minutes} min</span>
        )}
        {opened && <span className="text-xs text-blue-400">Opened</span>}
        {saved && <span className="text-xs text-blue-500">🔖 Saved</span>}
        {important && <span className="text-xs text-amber-500">★ Important</span>}
      </div>

      {/* Title */}
      <h2 className="text-lg font-semibold text-gray-900 mb-3 leading-snug">
        <a href={data.url} target="_blank" rel="noopener noreferrer"
           onClick={handleOpen}
           className="hover:text-blue-700 hover:underline">
          {data.title}
        </a>
      </h2>

      {/* Summary sections */}
      {whatHappened && (
        <div className="mb-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">What happened</span>
          <p className="text-sm text-gray-700 mt-0.5">{whatHappened}</p>
        </div>
      )}
      {whyMatters && (
        <div className="mb-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">Why it matters</span>
          <p className="text-sm text-gray-700 mt-0.5">{whyMatters}</p>
        </div>
      )}
      {data.technical_insights.length > 0 && (
        <div className="mb-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">Technical insights</span>
          <ul className="list-disc list-inside mt-0.5 space-y-0.5">
            {data.technical_insights.map((insight, i) => (
              <li key={i} className="text-sm text-gray-700">{insight}</li>
            ))}
          </ul>
        </div>
      )}
      {architecture && (
        <div className="mb-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">Architecture</span>
          <p className="text-sm text-gray-700 mt-0.5">{architecture}</p>
        </div>
      )}
      {tradeoffs && (
        <div className="mb-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">Tradeoffs</span>
          <p className="text-sm text-gray-700 mt-0.5">{tradeoffs}</p>
        </div>
      )}

      {/* Categories */}
      {data.categories.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {data.categories.map((cat) => (
            <span key={cat}
                  className="bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded-full border border-blue-100">
              {cat}
            </span>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between">
        {/* Left: primary link */}
        <a href={data.url} target="_blank" rel="noopener noreferrer"
           onClick={handleOpen}
           className="text-sm text-blue-600 hover:text-blue-800 font-medium">
          Read original →
        </a>

        {/* Right: feedback actions */}
        <div className="flex items-center gap-3">
          {/* Rating */}
          <button onClick={() => handleRate("up")}
                  title="Good recommendation"
                  className={`text-base transition-colors ${rating === "up" ? "text-green-500" : "text-gray-300 hover:text-green-400"}`}>
            👍
          </button>
          <button onClick={() => handleRate("down")}
                  title="Bad recommendation"
                  className={`text-base transition-colors ${rating === "down" ? "text-red-400" : "text-gray-300 hover:text-red-300"}`}>
            👎
          </button>

          {/* Save */}
          <button onClick={handleSave}
                  title={saved ? "Remove from saved" : "Save for later"}
                  className={`text-base transition-colors ${saved ? "text-blue-500" : "text-gray-300 hover:text-blue-400"}`}>
            🔖
          </button>

          {/* Important */}
          <button onClick={handleImportant}
                  title={important ? "Remove important flag" : "Mark as important"}
                  className={`text-base transition-colors ${important ? "text-amber-400" : "text-gray-300 hover:text-amber-300"}`}>
            ⭐
          </button>

          {/* Archive */}
          {onArchive && (
            <button onClick={() => onArchive(data.id)}
                    title={data.is_archived ? "Unarchive" : "Archive"}
                    className="text-sm text-gray-400 hover:text-gray-600 transition-colors">
              {data.is_archived ? "Unarchive" : "Archive"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
