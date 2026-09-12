import { ExternalLink, Github, MessageSquarePlus } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { TIBIAHUB_BRAND } from '../../assets/brand';
import { buildIssueUrl } from '../feedback/GitHubFeedbackLink';
import { Container } from '../ui';

type FooterLink = {
  label: string;
  to?: string;
  href?: string;
  external?: boolean;
};

const GITHUB_REPOSITORY = 'https://github.com/RayDR/Tibiahub';
const TIBIA_WIKI = 'https://tibia.fandom.com';

function FooterNavLink({ item }: { item: FooterLink }) {
  const className = 'inline-flex min-h-8 items-center gap-1.5 text-sm text-content-secondary transition hover:text-primary';

  if (item.to) {
    return <Link to={item.to} className={className}>{item.label}</Link>;
  }

  return (
    <a
      href={item.href}
      target={item.external ? '_blank' : undefined}
      rel={item.external ? 'noopener noreferrer' : undefined}
      className={className}
    >
      {item.label}
      {item.external ? <ExternalLink className="size-3.5" aria-hidden="true" /> : null}
    </a>
  );
}

export default function SiteFooter({ dataVersion }: { dataVersion?: string }) {
  const { i18n } = useTranslation();
  const isSpanish = i18n.resolvedLanguage?.startsWith('es') ?? false;
  const year = new Date().getFullYear();
  const suggestionUrl = buildIssueUrl({ template: 'feature-request.yml', title: '[Suggestion] ' });

  const copy = isSpanish
    ? {
        footerLabel: 'Pie de página de TibiaHub',
        shortcutsLabel: 'Accesos del pie de página',
        knowledgeHub: 'Centro de conocimiento de la comunidad',
        tagline: 'Hecho por la comunidad de Tibia, para la comunidad de Tibia.',
        about: 'TibiaHub reúne Cyclopedia, hunts, mapa, herramientas y espacios de comunidad en una sola experiencia pensada para jugadores.',
        aboutLabel: 'Acerca de',
        legalLabel: 'Legal',
        explore: 'Explorar',
        cyclopedia: 'Cyclopedia',
        community: 'Comunidad',
        information: 'Información',
        home: 'Inicio',
        huntPlanner: 'Hunt Planner',
        map: 'Mapa',
        guild: 'Gremio',
        creatures: 'Criaturas',
        bosses: 'Bosses',
        loot: 'Loot',
        quests: 'Quests',
        huntZones: 'Zonas de caza',
        npcs: 'NPCs',
        sourceCode: 'Código fuente',
        suggest: 'Sugerir una mejora',
        gameData: 'Referencia de datos',
        dataVersion: 'Versión de datos',
        unavailable: 'no disponible',
        copyright: `© ${year} TibiaHub. Proyecto independiente de la comunidad.`,
        disclaimer: 'Tibia y los recursos oficiales del juego pertenecen a CipSoft GmbH. TibiaHub es un proyecto independiente de fans y no está afiliado, patrocinado ni operado por CipSoft GmbH.',
        attribution: 'Los datos y recursos de terceros conservan la atribución y los derechos de sus respectivas fuentes y propietarios.',
      }
    : {
        footerLabel: 'TibiaHub footer',
        shortcutsLabel: 'Footer shortcuts',
        knowledgeHub: 'Community knowledge hub',
        tagline: 'Made by the Tibia community, for the Tibia community.',
        about: 'TibiaHub brings Cyclopedia, hunts, maps, tools and community spaces into one player-focused experience.',
        aboutLabel: 'About',
        legalLabel: 'Legal',
        explore: 'Explore',
        cyclopedia: 'Cyclopedia',
        community: 'Community',
        information: 'Information',
        home: 'Home',
        huntPlanner: 'Hunt Planner',
        map: 'Map',
        guild: 'Guild',
        creatures: 'Creatures',
        bosses: 'Bosses',
        loot: 'Loot',
        quests: 'Quests',
        huntZones: 'Hunt Zones',
        npcs: 'NPCs',
        sourceCode: 'Source code',
        suggest: 'Suggest an improvement',
        gameData: 'Data reference',
        dataVersion: 'Data version',
        unavailable: 'unavailable',
        copyright: `© ${year} TibiaHub. Independent community project.`,
        disclaimer: 'Tibia and official game assets belong to CipSoft GmbH. TibiaHub is an independent fan project and is not affiliated with, sponsored by, or operated by CipSoft GmbH.',
        attribution: 'Third-party data and resources retain the attribution and rights of their respective sources and owners.',
      };

  const groups: Array<{ title: string; links: FooterLink[] }> = [
    {
      title: copy.explore,
      links: [
        { label: copy.home, to: '/' },
        { label: copy.huntPlanner, to: '/planner' },
        { label: copy.map, to: '/map' },
        { label: copy.guild, to: '/guild' },
      ],
    },
    {
      title: copy.cyclopedia,
      links: [
        { label: copy.creatures, to: '/cyclopedia?tab=creatures' },
        { label: copy.bosses, to: '/cyclopedia?tab=bosses' },
        { label: copy.loot, to: '/cyclopedia?tab=items' },
        { label: copy.quests, to: '/cyclopedia?tab=quests' },
        { label: copy.huntZones, to: '/cyclopedia?tab=zones' },
        { label: copy.npcs, to: '/cyclopedia?tab=npcs' },
      ],
    },
    {
      title: copy.community,
      links: [
        { label: copy.guild, to: '/guild' },
        { label: copy.sourceCode, href: GITHUB_REPOSITORY, external: true },
        { label: copy.suggest, href: suggestionUrl, external: true },
      ],
    },
    {
      title: copy.information,
      links: [
        { label: copy.gameData, href: TIBIA_WIKI, external: true },
        { label: copy.aboutLabel, href: '#tibiahub-footer-about' },
        { label: copy.legalLabel, href: '#tibiahub-footer-legal' },
      ],
    },
  ];

  return (
    <footer className="relative mt-16 border-t border-line bg-surface-base/90" aria-label={copy.footerLabel}>
      <Container>
        <div className="flex flex-col gap-5 py-5 lg:flex-row lg:items-center lg:justify-between">
          <a href="#tibiahub-footer-about" className="inline-flex min-w-0 items-center gap-3 self-start">
            <img
              src={TIBIAHUB_BRAND.logoCandidates.golden}
              alt=""
              aria-hidden="true"
              className="size-10 shrink-0 object-contain [image-rendering:auto]"
            />
            <span className="min-w-0">
              <strong className="block font-heading text-lg font-semibold text-content-primary">TibiaHub</strong>
              <span className="block text-xs text-content-muted sm:text-sm">{copy.tagline}</span>
            </span>
          </a>

          <nav className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm" aria-label={copy.shortcutsLabel}>
            <a href="#tibiahub-footer-about" className="text-content-secondary hover:text-primary">{copy.aboutLabel}</a>
            <a href="#tibiahub-footer-legal" className="text-content-secondary hover:text-primary">{copy.legalLabel}</a>
            <a href={suggestionUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-content-secondary hover:text-primary">
              <MessageSquarePlus className="size-4" aria-hidden="true" />
              {copy.suggest}
            </a>
            <a href={GITHUB_REPOSITORY} target="_blank" rel="noopener noreferrer" aria-label="GitHub" className="grid size-9 place-items-center rounded-lg border border-line bg-surface-raised text-content-secondary transition hover:border-primary/50 hover:text-primary">
              <Github className="size-4" aria-hidden="true" />
            </a>
          </nav>
        </div>
      </Container>

      <div className="border-t border-line/70 bg-surface-raised/35">
        <Container>
          <div className="grid gap-9 py-10 sm:grid-cols-2 xl:grid-cols-[minmax(18rem,1.45fr)_repeat(4,minmax(0,1fr))]">
            <section id="tibiahub-footer-about" className="scroll-mt-24 sm:col-span-2 xl:col-span-1">
              <div className="flex items-center gap-3">
                <img
                  src={TIBIAHUB_BRAND.logoCandidates.heraldic}
                  alt="TibiaHub"
                  className="size-14 object-contain"
                />
                <div>
                  <h2 className="font-heading text-xl font-semibold text-content-primary">TibiaHub</h2>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">{copy.knowledgeHub}</p>
                </div>
              </div>
              <p className="mt-4 max-w-md text-sm leading-6 text-content-secondary">{copy.about}</p>
              <a href={GITHUB_REPOSITORY} target="_blank" rel="noopener noreferrer" className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-lg border border-line bg-surface-base/45 px-3 text-sm font-medium text-content-secondary transition hover:border-primary/50 hover:text-primary">
                <Github className="size-4" aria-hidden="true" />
                GitHub
                <ExternalLink className="size-3.5" aria-hidden="true" />
              </a>
            </section>

            {groups.map((group) => (
              <nav key={group.title} aria-label={group.title}>
                <h2 className="text-xs font-bold uppercase tracking-[0.08em] text-content-primary">{group.title}</h2>
                <ul className="mt-3 space-y-1.5">
                  {group.links.map((item) => (
                    <li key={`${group.title}:${item.label}`}>
                      <FooterNavLink item={item} />
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>

          <div id="tibiahub-footer-legal" className="scroll-mt-24 border-t border-line/70 py-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="max-w-4xl space-y-1.5 text-xs leading-5 text-content-muted">
                <p className="font-medium text-content-secondary">{copy.copyright}</p>
                <p>{copy.disclaimer}</p>
                <p>{copy.attribution}</p>
              </div>

              <div className="flex shrink-0 flex-col gap-1 text-xs text-content-muted lg:text-right">
                <span>{copy.dataVersion}: <strong className="font-medium text-content-secondary">{dataVersion || copy.unavailable}</strong></span>
                <a href={TIBIA_WIKI} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:text-primary-hover lg:justify-end">
                  {copy.gameData}: TibiaWiki
                  <ExternalLink className="size-3" aria-hidden="true" />
                </a>
              </div>
            </div>
          </div>
        </Container>
      </div>
    </footer>
  );
}
