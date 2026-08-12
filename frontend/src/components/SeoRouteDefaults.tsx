import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

import { applySeoMetadata, defaultSeoForPath } from '../utils/seo';

export default function SeoRouteDefaults() {
  const { pathname } = useLocation();
  useEffect(() => applySeoMetadata(defaultSeoForPath(pathname)), [pathname]);
  return null;
}
