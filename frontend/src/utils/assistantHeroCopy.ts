export type AssistantDaypart = 'morning' | 'afternoon' | 'evening';

type CopySet = Record<AssistantDaypart, string[]> & { supporting: string[] };

const COPY: Record<'en' | 'es', CopySet> = {
  en: {
    morning: [
      'What adventure should we start today?',
      'Which task are we crossing off this morning?',
      'Shall we find a good hunt to start the day?',
      'What’s your Tibia goal for today?',
    ],
    afternoon: [
      'What hunt should we plan this afternoon?',
      'Which task do you want off your list today?',
      'Shall we find your next objective?',
      'What part of Tibia should we explore this afternoon?',
    ],
    evening: [
      'What adventure is left for tonight?',
      'What should we hunt tonight?',
      'One more quest before the day ends?',
      'What do you want to discover in Tibia tonight?',
      'Shall we find that hunt you’ve been putting off?',
    ],
    supporting: [
      'Clear your weekly tasks, prepare your next hunt, or find the item your set is missing.',
      'From a pending quest to your next hunting ground, tell me what you have in mind.',
      'Plan a hunt, track down loot, or learn what you need to enter a new area.',
      'Bounty Hunter, quests, bosses, or loot—we can find your next objective.',
      'Missing a task, a quest, or a good hunt? We can start there.',
      'Find creatures, loot, access requirements, and routes without digging through pages.',
    ],
  },
  es: {
    morning: [
      '¿Qué aventura comenzamos hoy?',
      '¿Qué task vamos a tachar esta mañana?',
      '¿Buscamos una buena hunt para empezar el día?',
      '¿Qué objetivo de Tibia tienes para hoy?',
    ],
    afternoon: [
      '¿Qué hunt armamos esta tarde?',
      '¿Qué task quieres sacar de la lista hoy?',
      '¿Buscamos tu próximo objetivo?',
      '¿Qué parte de Tibia exploramos esta tarde?',
    ],
    evening: [
      '¿Qué aventura nos queda para esta noche?',
      '¿Qué hunt hacemos esta noche?',
      '¿Una quest más antes de cerrar el día?',
      '¿Qué quieres descubrir esta noche en Tibia?',
      '¿Buscamos esa hunt que tienes pendiente?',
    ],
    supporting: [
      'Completa tus weekly tasks, prepara tu próxima hunt o encuentra ese item que te falta.',
      'Desde una quest pendiente hasta tu próxima zona de caza: dime qué tienes en mente.',
      'Planea tu próxima hunt, encuentra loot o descubre qué necesitas para entrar a una zona.',
      'Bounty Hunter, quests, bosses o loot: busquemos tu próximo objetivo.',
      '¿Te falta una task, una quest o una buena hunt? Podemos empezar por ahí.',
      'Encuentra criaturas, loot, accesos y rutas sin perder tiempo buscando entre páginas.',
    ],
  },
};

function stableIndex(value: string, length: number): number {
  let hash = 2166136261;
  for (const character of value) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash) % length;
}

export function daypartFromHour(hour: number): AssistantDaypart {
  if (hour >= 5 && hour < 12) return 'morning';
  if (hour >= 12 && hour < 19) return 'afternoon';
  return 'evening';
}

export function assistantHeroSessionSeed(): string {
  const key = 'tibiahub:assistant:hero-copy-seed';
  try {
    const stored = sessionStorage.getItem(key);
    if (stored) return stored;
    const value = typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    sessionStorage.setItem(key, value);
    return value;
  } catch {
    return 'storage-unavailable';
  }
}

export function selectAssistantHeroCopy(language: string, now: Date, sessionSeed: string) {
  const locale = language.startsWith('es') ? 'es' : 'en';
  const daypart = daypartFromHour(now.getHours());
  const localDate = `${now.getFullYear()}-${now.getMonth() + 1}-${now.getDate()}`;
  const seed = `${localDate}:${daypart}:${locale}:${sessionSeed}`;
  return {
    daypart,
    headline: COPY[locale][daypart][stableIndex(`${seed}:headline`, COPY[locale][daypart].length)],
    supporting: COPY[locale].supporting[stableIndex(`${seed}:supporting`, COPY[locale].supporting.length)],
  };
}
