export interface AnnouncementPageState<T> {
  items: T[];
  nextSkip: number;
  hasMore: boolean;
  initialError: boolean;
  additionalError: boolean;
}

export function emptyAnnouncementPage<T>(): AnnouncementPageState<T> {
  return {
    items: [],
    nextSkip: 0,
    hasMore: true,
    initialError: false,
    additionalError: false,
  };
}

interface LoadAnnouncementWindowOptions<T> {
  state: AnnouncementPageState<T>;
  reset: boolean;
  limit: number;
  guildName: string;
  request: (skip: number, limit: number, guildName: string) => Promise<T[]>;
}

export interface AnnouncementWindowResult<T> {
  state: AnnouncementPageState<T>;
  requestedSkip: number;
  error: unknown | null;
}

export async function loadAnnouncementWindow<T>({
  state,
  reset,
  limit,
  guildName,
  request,
}: LoadAnnouncementWindowOptions<T>): Promise<AnnouncementWindowResult<T>> {
  const requestedSkip = reset ? 0 : state.nextSkip;
  try {
    const rows = await request(requestedSkip, limit, guildName);
    return {
      requestedSkip,
      error: null,
      state: {
        items: reset ? rows : [...state.items, ...rows],
        nextSkip: requestedSkip + rows.length,
        hasMore: rows.length === limit,
        initialError: false,
        additionalError: false,
      },
    };
  } catch (error) {
    return {
      requestedSkip,
      error,
      state: {
        items: reset ? [] : state.items,
        nextSkip: reset ? 0 : state.nextSkip,
        hasMore: reset ? true : state.hasMore,
        initialError: reset,
        additionalError: !reset,
      },
    };
  }
}
