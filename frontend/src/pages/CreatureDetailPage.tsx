import React, { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowLeft,
  Gem,
  Heart,
  Info,
  Loader2,
  MapPin,
  Shield,
  Skull,
  Swords,
  Zap,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import LootDisplay from "../components/LootDisplay";
import ImageWithFallback from "../components/ImageWithFallback";
import type { Creature } from "../types";
import { useAuth } from "../context/AuthContext";
import { activityApi } from "../services/activity";
import MapMetadataPanel from "../components/MapMetadataPanel";
import { Page } from "../components/ui";
import { resolveCyclopediaReturnTarget } from "../utils/cyclopediaNavigation";
import { SuggestCorrectionLink } from "../components/feedback/GitHubFeedbackLink";
import { useSeoMetadata } from "../utils/seo";

const formatNumber = (
  value: number | null | undefined,
  unknown: string,
): string => {
  if (value === null || value === undefined) return unknown;
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return `${value}`;
};

const CreatureDetailPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const [creature, setCreature] = useState<Creature | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showFullOverview, setShowFullOverview] = useState(false);
  const { isAuthenticated } = useAuth();
  useSeoMetadata(creature ? {
    title: `${creature.name} — Tibia creature`,
    description: creature.description || `Stats, loot, hunt zones and related knowledge for ${creature.name}.`,
    canonicalPath: `/creatures/${creature.slug || creature.id}`,
    type: 'article',
    image: `/api/v1/creatures/${creature.id}/image`,
    breadcrumbs: [{ name: 'Home', path: '/' }, { name: 'Cyclopedia', path: '/cyclopedia' }, { name: creature.name, path: `/creatures/${creature.slug || creature.id}` }],
  } : null);

  useEffect(() => {
    const fetchCreature = async () => {
      if (!slug) return;
      try {
        setLoading(true);
        setErrorMessage(null);
        const response = await fetch(
          `/api/v1/creatures/${encodeURIComponent(slug)}`,
        );
        if (!response.ok) {
          throw new Error(t("creatureDetail.notFound"));
        }
        const data = await response.json();
        setCreature(data);

        if (isAuthenticated && data?.id) {
          void activityApi
            .record({
              activity_type: data.is_boss ? "view_boss" : "view_creature",
              entity_type: "creature",
              entity_id: String(data.id),
              metadata: {
                name: data.name,
                slug: data.slug,
                is_boss: !!data.is_boss,
              },
            })
            .catch(() => {
              // Non-blocking history event.
            });
        }

        const canonicalSlug =
          response.headers.get("x-canonical-slug") || data.slug;

        try {
          const current = JSON.parse(
            localStorage.getItem("recentCreatures") || "[]",
          ) as Array<{
            id: number;
            slug?: string;
            name: string;
            image_url?: string;
            viewed_at: string;
          }>;
          const deduped = current.filter((entry) => entry.id !== data.id);
          const updated = [
            {
              id: data.id,
              slug: data.slug,
              name: data.name,
              image_url: data.image_url,
              viewed_at: new Date().toISOString(),
            },
            ...deduped,
          ].slice(0, 20);
          localStorage.setItem("recentCreatures", JSON.stringify(updated));
        } catch {
          // ignore storage errors
        }

        if (canonicalSlug && canonicalSlug !== slug) {
          navigate(`/creatures/${canonicalSlug}`, {
            replace: true,
            state: location.state,
          });
        }
      } catch (error: any) {
        console.error("Failed to load creature details", error);
        setErrorMessage(t("creatureDetail.notFound"));
      } finally {
        setLoading(false);
      }
    };
    void fetchCreature();
  }, [slug, navigate, location, isAuthenticated, t]);

  if (loading) {
    return (
      <Page>
        <div className="flex min-h-[24rem] items-center justify-center text-primary">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="animate-spin" size={48} />
          <p className="text-lg font-semibold">{t("creatureDetail.loading")}</p>
        </div>
        </div>
      </Page>
    );
  }

  if (!creature || errorMessage) {
    return (
      <Page>
        <div className="mx-auto max-w-3xl rounded-2xl border border-danger/20 bg-danger/20 p-6 text-danger">
        <div className="mb-3 flex items-center gap-2 text-lg font-semibold">
          <AlertTriangle className="h-5 w-5" />{" "}
          {t("creatureDetail.unavailable")}
        </div>
        <p className="text-sm text-danger/80">
          {errorMessage || t("creatureDetail.notFound")}
        </p>
        </div>
      </Page>
    );
  }

  const overview = creature.description || t("common.notAvailable");
  const overviewNeedsToggle = overview.length > 300;
  const overviewText = showFullOverview
    ? overview
    : `${overview.slice(0, 300)}${overviewNeedsToggle ? "..." : ""}`;
  const displayRequirements = creature.related_tasks || [];

  const backTarget = resolveCyclopediaReturnTarget(
    (location.state as { from?: string } | null)?.from,
    '/cyclopedia?tab=creatures',
  );

  return (
    <Page>
      <div className="relative mb-8">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-primary/10 to-transparent" />
        <div className="relative z-10">
          <button
            onClick={() => {
              navigate(backTarget);
            }}
            className="group mb-6 flex items-center gap-2 text-content-secondary transition-colors hover:text-content-primary"
          >
            <ArrowLeft
              size={18}
              className="transition-transform group-hover:-translate-x-1"
            />
            {t("creature.backToCyclopedia")}
          </button>

          <div className="flex flex-col items-start gap-8 md:flex-row">
            <motion.div
              initial={{ scale: 0.92, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="relative aspect-square w-full overflow-hidden rounded-3xl bg-surface-raised p-8 shadow-sm md:w-64"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-danger/5" />
              <ImageWithFallback
                src={`/api/v1/creatures/${creature.id}/image`}
                alt={creature.name}
                className="h-full w-full object-contain drop-shadow-lg"
                containerClassName="h-full w-full"
                fallbackLabel={t("creatureDetail.creature")}
              />
            </motion.div>

            <div className="flex-1 space-y-6">
              <div>
                <motion.h1
                  initial={{ y: -20, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  className="mb-2 text-4xl font-serif font-bold tracking-tight text-content-primary md:text-6xl"
                >
                  {creature.name}
                </motion.h1>
                <div className="flex flex-wrap gap-3 text-sm">
                  {creature.is_boss && (
                    <span className="rounded-lg bg-danger-subtle px-3 py-1 font-semibold text-danger">
                      {t("creatureDetail.bossEncounter")}
                    </span>
                  )}
                  <span className="rounded-lg bg-primary-subtle px-3 py-1 font-semibold text-primary">
                    {creature.difficulty ||
                      t("creatureDetail.unknownDifficulty")}
                  </span>
                  <span className="rounded-lg bg-surface px-3 py-1 text-content-secondary">
                    {creature.occurrence ||
                      t("creatureDetail.unknownOccurrence")}
                  </span>
                  <span className="rounded-lg bg-surface px-3 py-1 text-content-secondary">
                    {t("creatureDetail.cyclopediaClass", {
                      value: creature.bestiary_class || t("common.unknown"),
                    })}
                  </span>
                  <span className="rounded-lg bg-surface px-3 py-1 text-content-secondary">
                    {t("creatureDetail.charmPoints", {
                      value: creature.charm_points ?? t("common.unknown"),
                    })}
                  </span>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  {
                    key: "hitpoints",
                    value: formatNumber(
                      creature.hitpoints,
                      t("common.unknown"),
                    ),
                    icon: Heart,
                    color: "text-danger",
                  },
                  {
                    key: "experience",
                    value: formatNumber(
                      creature.experience,
                      t("common.unknown"),
                    ),
                    icon: Gem,
                    color: "text-primary",
                  },
                  {
                    key: "armor",
                    value: formatNumber(creature.armor, t("common.unknown")),
                    icon: Shield,
                    color: "text-content-primary",
                  },
                  {
                    key: "speed",
                    value: formatNumber(creature.speed, t("common.unknown")),
                    icon: Zap,
                    color: "text-primary",
                  },
                  {
                    key: "maxDamage",
                    value: formatNumber(
                      creature.max_damage,
                      t("common.unknown"),
                    ),
                    icon: Swords,
                    color: "text-danger",
                  },
                  {
                    key: "primaryType",
                    value: creature.primary_type || t("common.unknown"),
                    icon: Info,
                    color: "text-info",
                  },
                  {
                    key: "creatureClass",
                    value: creature.creature_class || t("common.unknown"),
                    icon: Skull,
                    color: "text-accent",
                  },
                  {
                    key: "cyclopediaLevel",
                    value: creature.bestiary_level || t("common.unknown"),
                    icon: Gem,
                    color: "text-success",
                  },
                ].map((stat) => (
                  <div
                    key={stat.key}
                    className="flex items-center gap-4 rounded-xl bg-surface-raised p-4 shadow-sm"
                  >
                    <div
                      className={`rounded-lg bg-surface-base p-2 ${stat.color}`}
                    >
                      {typeof stat.icon === "string" ? (
                        stat.icon
                      ) : (
                        <stat.icon size={20} />
                      )}
                    </div>
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wider text-content-muted">
                        {t(`creatureDetail.stats.${stat.key}`)}
                      </div>
                      <div className={`text-lg font-bold ${stat.color}`}>
                        {stat.value}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-12">
        <div className="space-y-8 lg:col-span-8">
          <div className="rounded-2xl bg-surface-raised p-6 shadow-sm">
            <h2 className="mb-4 flex items-center gap-2 text-xl font-serif font-bold text-primary">
              <Info size={20} /> {t("creatureDetail.overview")}
            </h2>
            <p className="mb-2 text-lg leading-relaxed text-content-secondary">
              {overviewText}
            </p>
            {overviewNeedsToggle && (
              <button
                onClick={() => setShowFullOverview((value) => !value)}
                className="mb-4 text-sm font-medium text-primary transition hover:text-primary"
              >
                {t(
                  showFullOverview
                    ? "creatureDetail.showLess"
                    : "creatureDetail.showMore",
                )}
              </button>
            )}
            <p className="text-sm leading-relaxed text-content-secondary">
              {creature.behavior || t("creatureDetail.behaviorUnavailable")}
            </p>
          </div>

          <div className="rounded-2xl bg-surface-raised p-6 shadow-sm">
            <div className="mb-6 flex items-center justify-between gap-4">
              <h2 className="flex items-center gap-2 text-xl font-serif font-bold text-primary">
                <Gem size={20} /> {t("creatureDetail.loot")}
              </h2>
              <div className="text-sm text-content-muted">
                {t("creatureDetail.lootHelp")}
              </div>
            </div>
            <LootDisplay items={creature.loot_items} />
          </div>
        </div>

        <div className="space-y-8 lg:col-span-4">
          <div className="rounded-2xl bg-surface-raised p-6 shadow-sm">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-content-primary">
              <MapPin className="text-primary" size={20} />{" "}
              {t("creatureDetail.locations")}
            </h2>
            <Link to={`/map?entityType=${creature.is_boss ? 'boss' : 'creature'}&slug=${encodeURIComponent(creature.slug || creature.name)}&q=${encodeURIComponent(creature.name)}`} className="app-button-secondary app-button-sm mb-4 inline-flex"><MapPin size={14} />{t('map.openDetails')}</Link>
            <div className="space-y-2 text-sm text-content-secondary">
              {creature.spawn_locations.length > 0 ? (
                creature.spawn_locations.map((spawn) => spawn.hunt_zone ? (
                  <Link
                    key={spawn.id}
                    to={`/hunt-zones/${spawn.hunt_zone.slug || spawn.hunt_zone.id}`}
                    className="block rounded-xl border border-line bg-surface-base/60 p-3 transition hover:border-primary"
                  >
                    <div className="font-semibold text-content-primary">{spawn.hunt_zone.name}</div>
                    <div className="mt-1 text-xs text-content-secondary">
                      {[spawn.hunt_zone.city, spawn.hunt_zone.min_level ? `Level ${spawn.hunt_zone.min_level}+` : null, spawn.hunt_zone.difficulty].filter(Boolean).join(' · ')}
                    </div>
                    {spawn.quantity || spawn.notes ? <div className="mt-2 text-xs text-content-muted">{[spawn.quantity, spawn.notes].filter(Boolean).join(' · ')}</div> : null}
                    {spawn.hunt_zone.requires_quest && spawn.hunt_zone.quest_name ? <div className="mt-2 text-xs font-semibold text-warning">{t('creatureDetail.requiresQuest', { quest: spawn.hunt_zone.quest_name })}</div> : null}
                  </Link>
                ) : null)
              ) : (creature.locations?.length ?? 0) > 0 ? (
                creature.locations!.map((location) => (
                  <div
                    key={location}
                    className="rounded-lg bg-surface px-3 py-2"
                  >
                    {location}
                  </div>
                ))
              ) : (
                <div className="text-content-muted">
                  {t("common.notAvailable")}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-2xl bg-surface-raised p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-bold text-content-primary">
              {t(
                "creatureDetail.relatedTasks",
              )}
            </h2>
            <div className="space-y-2 text-sm text-content-secondary">
              {displayRequirements.length > 0 ? (
                displayRequirements.map((task) => (
                  <div key={task} className="rounded-lg bg-surface px-3 py-2">
                    {task}
                  </div>
                ))
              ) : (
                <div className="text-content-muted">
                  {t("common.notAvailable")}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-2xl bg-surface-raised p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-bold text-content-primary">
              {t("creatureDetail.sourceTitle")}
            </h2>
            <div className="space-y-2 text-sm text-content-secondary">
              {creature.source_url ? (
                <a
                  href={creature.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-block text-primary hover:text-primary"
                >
                  {t("creatureDetail.openSource")}
                </a>
              ) : (
                <div className="text-content-muted">
                  {t("creatureDetail.sourceUnavailable")}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      <MapMetadataPanel entityId={creature.knowledge_entity_id || undefined} />
      <div className="mt-6 flex justify-end"><SuggestCorrectionLink entityType="Creature" entityName={creature.name} /></div>
    </Page>
  );
};

export default CreatureDetailPage;
