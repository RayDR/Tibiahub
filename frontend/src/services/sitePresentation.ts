import api from './api';

export type NavbarAlignment = 'left' | 'center' | 'right';

export interface SitePresentationSettings {
  navbar_show_icons: boolean;
  navbar_alignment: NavbarAlignment;
  navbar_show_global_search: boolean;
}

export const DEFAULT_SITE_PRESENTATION: SitePresentationSettings = {
  navbar_show_icons: true,
  navbar_alignment: 'center',
  navbar_show_global_search: true,
};

let publicCache: SitePresentationSettings | null = null;
let publicRequest: Promise<SitePresentationSettings> | null = null;

export const sitePresentationApi = {
  getPublic: async (): Promise<SitePresentationSettings> => {
    if (publicCache) return publicCache;
    if (!publicRequest) {
      publicRequest = api
        .get<SitePresentationSettings>('/site-presentation')
        .then(({ data }) => {
          publicCache = data;
          return data;
        })
        .catch(() => DEFAULT_SITE_PRESENTATION)
        .finally(() => {
          publicRequest = null;
        });
    }
    return publicRequest;
  },

  getAdmin: async (): Promise<SitePresentationSettings> => {
    const { data } = await api.get<SitePresentationSettings>('/admin/site-presentation');
    return data;
  },

  updateAdmin: async (payload: SitePresentationSettings): Promise<SitePresentationSettings> => {
    const { data } = await api.put<SitePresentationSettings>('/admin/site-presentation', payload);
    publicCache = data;
    return data;
  },

  clearCache: () => {
    publicCache = null;
  },
};
