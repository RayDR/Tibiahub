import {
  BookOpenCheck,
  Compass,
  Crown,
  Flame,
  MapPinned,
  Sparkles,
  Swords,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  CyclopediaDiscovery as DiscoveryPayload,
  DiscoveryCard,
  discoveryApi,
} from "../services/discovery";

export default function CyclopediaDiscovery() {
  const { t } = useTranslation();
  const [data, setData] = useState<DiscoveryPayload | null>(null);
  useEffect(() => {
    let active = true;
    void discoveryApi
      .load()
      .then((value) => {
        if (active) setData(value);
      })
      .catch(() => {
        if (active) setData(null);
      });
    return () => {
      active = false;
    };
  }, []);
  if (!data) return null;
  return (
    <section
      className="mx-auto max-w-6xl space-y-5"
      aria-label={t("cyclopedia.discovery.label")}
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(18rem,.6fr)]">
        <DiscoveryGroup
          icon={<Sparkles />}
          title={t("cyclopedia.discovery.featuredCreatures")}
          items={data.featured_creatures.map((item) => ({
            ...item,
            image_url: `/api/v1/creatures/${item.id}/image`,
          }))}
          href={(item) => `/creatures/${item.slug || item.id}`}
          meta={(item) =>
            item.experience
              ? t("cyclopedia.cards.experience", {
                  value: item.experience.toLocaleString(),
                })
              : ""
          }
        />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
          <BoostCard
            icon={<Flame />}
            title={t("cyclopedia.discovery.boostedCreature")}
            item={data.boosted_creature}
            state={data.boosted_state}
          />
          <BoostCard
            icon={<Crown />}
            title={t("cyclopedia.discovery.boostedBoss")}
            item={data.boosted_boss}
            state={data.boosted_state}
          />
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <DiscoveryGroup
          icon={<Swords />}
          title={t("cyclopedia.discovery.popularHunts")}
          items={data.popular_hunts}
          href={(item) =>
            `/cyclopedia?tab=zones&q=${encodeURIComponent(item.name)}`
          }
          meta={(item) =>
            `${item.city || t("common.unknown")} · ${t("cyclopedia.zones.level", { level: item.recommended_level || 0 })}`
          }
        />
        <DiscoveryGroup
          icon={<BookOpenCheck />}
          title={t("cyclopedia.discovery.recentQuests")}
          items={data.recent_quests}
          href={(item) => `/quests/${item.id}`}
          meta={(item) => item.summary || t("cyclopedia.quests.noDetails")}
        />
        <DiscoveryGroup
          icon={<MapPinned />}
          title={t("cyclopedia.discovery.latestKnowledge")}
          items={data.latest_knowledge}
          href={(item) => discoveryLink(item)}
          meta={(item) =>
            t(`cyclopedia.discovery.types.${item.entity_type}`, {
              defaultValue: item.entity_type || t("common.unknown"),
            })
          }
        />
        <DiscoveryGroup
          icon={<Compass />}
          title={t("cyclopedia.discovery.trending")}
          items={data.trending}
          href={(item) => discoveryLink(item)}
          meta={(item) =>
            t("cyclopedia.discovery.searches", {
              count: item.search_count || 0,
            })
          }
        />
      </div>
    </section>
  );
}

function DiscoveryGroup({
  icon,
  title,
  items,
  href,
  meta,
}: {
  icon: React.ReactNode;
  title: string;
  items: DiscoveryCard[];
  href: (item: DiscoveryCard) => string;
  meta: (item: DiscoveryCard) => string;
}) {
  const { t } = useTranslation();
  return (
    <article className="rounded-2xl bg-surface-raised p-5 shadow-sm">
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        <span className="text-primary [&>svg]:size-5">{icon}</span>
        {title}
      </h2>
      {items.length ? (
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {items.slice(0, 6).map((item) => (
            <Link
              key={String(item.id)}
              to={href(item)}
              className="group flex min-w-0 items-center gap-3 rounded-xl bg-surface p-3 hover:bg-surface-active"
            >
              {item.image_url ? (
                <img
                  src={item.image_url}
                  alt=""
                  className="size-11 shrink-0 rounded-lg object-contain"
                  loading="lazy"
                />
              ) : (
                <span className="grid size-11 shrink-0 place-items-center rounded-lg bg-primary-subtle text-primary">
                  <Sparkles className="size-4" />
                </span>
              )}
              <span className="min-w-0">
                <strong className="block truncate text-sm">{item.name}</strong>
                <span className="line-clamp-1 text-xs text-content-muted">
                  {meta(item)}
                </span>
              </span>
            </Link>
          ))}
        </div>
      ) : (
        <p className="mt-4 rounded-xl bg-surface p-4 text-sm text-content-muted">
          {t("cyclopedia.discovery.empty")}
        </p>
      )}
    </article>
  );
}
function BoostCard({
  icon,
  title,
  item,
  state,
}: {
  icon: React.ReactNode;
  title: string;
  item: DiscoveryCard | null;
  state: string;
}) {
  const { t } = useTranslation();
  return (
    <article className="rounded-2xl bg-gradient-to-br from-accent-subtle to-surface-raised p-4 shadow-sm">
      <div className="flex items-center gap-2 text-accent">
        <span className="[&>svg]:size-5">{icon}</span>
        <h2 className="font-semibold">{title}</h2>
      </div>
      {item ? (
        <Link
          to={discoveryLink(item)}
          className="mt-3 block text-lg font-semibold"
        >
          {item.name}
        </Link>
      ) : (
        <p className="mt-3 text-sm text-content-secondary">
          {t(`cyclopedia.discovery.boostedState.${state}`)}
        </p>
      )}
    </article>
  );
}
function discoveryLink(item: DiscoveryCard) {
  const type = item.entity_type || "";
  const tab =
    type === "quest"
      ? "quests"
      : type === "item"
        ? "items"
        : type === "hunt_zone"
          ? "zones"
          : type === "boss"
            ? "bosses"
            : "creatures";
  return `/cyclopedia?tab=${tab}&q=${encodeURIComponent(item.name)}`;
}
