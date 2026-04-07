import { useRef, useEffect, useCallback, useState, useMemo, type MouseEvent as ReactMouseEvent } from 'react';
import Globe from 'react-globe.gl';
import * as THREE from 'three';
import { useGlobeStore } from '../../stores/globeStore';
import { useGeoLayerStore } from '../../stores/geoLayerStore';
import type { Hotspot } from '../../types/news';
import './GlobeScene.css';

/** Local-first GeoJSON URL 鈥?falls back to GitHub CDN if static assets not yet prepared */
const LOCAL_COUNTRIES_GEOJSON = (() => {
  const base = (import.meta.env.VITE_API_URL || '/api').replace(/\/api$/, '');
  return `${base}/static/geodata/countries/ne_110m_admin_0_map_units.geojson`;
})();
const CDN_COUNTRIES_GEOJSON =
  'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_map_units.geojson';

interface GlobeSceneProps {
  hotspots: Hotspot[];
  onHotspotClick: (eventId: string) => void;
  onAdmin1RegionClick?: (regionHotspots: Hotspot[], regionName: string, countryName: string, geoKey?: string) => void;
  onBackToGlobal?: () => void;
  /** Breadcrumb path entries below the country level, e.g. ['骞夸笢鐪?, '骞垮窞甯?] */
  regionBreadcrumb?: string[];
  /** If provided, a back arrow appears on the last breadcrumb segment to navigate up one level */
  onRegionBreadcrumbBack?: () => void;
  /** If provided, country name in breadcrumb is clickable to jump back to country-level panel */
  onCountryBreadcrumbClick?: () => void;
}

type GeoFeature = {
  type: 'Feature';
  geometry: object;
  properties?: {
    ISO_A3?: string;
    ADM0_A3?: string;
    NAME?: string;
    NAME_ZH?: string;
    [key: string]: unknown;
  };
};

async function loadGeoFeatures(primaryUrl: string, fallbackUrl: string): Promise<GeoFeature[]> {
  const tryLoad = async (url: string): Promise<GeoFeature[]> => {
    const response = await fetch(url);
    if (!response.ok) throw new Error('not ok');
    const data = (await response.json()) as { features?: GeoFeature[] };
    return data?.features ?? [];
  };

  try {
    return await tryLoad(primaryUrl);
  } catch {
    return tryLoad(fallbackUrl);
  }
}

function countryCode(feature: GeoFeature): string {
  const p = feature.properties;
  const isoA3 = String(p?.ISO_A3 || '').toUpperCase();
  const adm0A3 = String(p?.ADM0_A3 || '').toUpperCase();
  if (isoA3 && isoA3 !== '-99') return isoA3;
  if (adm0A3 && adm0A3 !== '-99') return adm0A3;
  return String(p?.NAME || '');
}

function canonicalCountryIso3(code: string): string {
  return code.toUpperCase() === 'TWN' ? 'CHN' : code.toUpperCase();
}

function canonicalCountryIso2(code: string): string {
  return code.toUpperCase() === 'TW' ? 'CN' : code.toUpperCase();
}

function buildChinaTaiwanRegionFeature(feature: GeoFeature): GeoFeature {
  return {
    ...feature,
    properties: {
      ...(feature.properties || {}),
      iso_3166_2: 'CN-TW',
      NAME: 'Taiwan',
      name: 'Taiwan',
      NAME_ZH: '鍙版咕',
      admin: 'China',
      geonunit: 'China',
    },
  };
}

function countryDataIso3(feature: GeoFeature): string {
  const p = feature.properties || {};
  const isoA3 = String(p.ISO_A3 || '').toUpperCase();
  const adm0A3 = String(p.ADM0_A3 || '').toUpperCase();
  const type = String(p.TYPE || '');
  const base = isoA3 && isoA3 !== '-99' ? isoA3 : adm0A3;

  if (base === 'TWN') return 'CHN';
  if ((type === 'Dependency' || type === 'Geo unit') && adm0A3 && adm0A3 !== '-99') {
    return canonicalCountryIso3(adm0A3);
  }
  return canonicalCountryIso3(base);
}

function countryDisplayName(feature: GeoFeature): string {
  const p = feature.properties || {};
  const name = String(p.NAME || p.NAME_LONG || p.GEOUNIT || p.ADMIN || '');
  if (name === 'Taiwan') return 'Taiwan';
  return name || countryCode(feature);
}

function normalizeByLog(value: number, maxValue: number): number {
  if (value <= 0 || maxValue <= 0) return 0;
  return Math.min(1, Math.log1p(value) / Math.log1p(maxValue));
}

function resolveCompositeIntensity(
  heat: number,
  count: number,
  maxHeat: number,
  maxCount: number,
): number {
  if (heat <= 0 && count <= 0) return 0;
  const heatNorm = normalizeByLog(heat, maxHeat);
  const countNorm = normalizeByLog(count, maxCount);
  return Math.min(1, Math.max(0.06, heatNorm * 0.68 + countNorm * 0.32));
}

function compositeToRgba(score: number): { r: number; g: number; b: number; a: number } {
  if (score <= 0) return { r: 2, g: 2, b: 4, a: 0.96 };
  if (score < 0.12) return { r: 45, g: 110, b: 255, a: 0.38 };
  if (score < 0.24) return { r: 38, g: 190, b: 255, a: 0.48 };
  if (score < 0.40) return { r: 54, g: 205, b: 110, a: 0.56 };
  if (score < 0.58) return { r: 215, g: 225, b: 64, a: 0.66 };
  if (score < 0.78) return { r: 247, g: 156, b: 45, a: 0.80 };
  return { r: 235, g: 56, b: 42, a: 0.94 };
}

void heatToRgba;

/** Normalize heat to [0,1] 鈥?any active country glows visibly. */
function normalizeHeat(heat: number): number {
  if (heat <= 0) return 0;
  return Math.min(1, 0.15 + 0.65 * (1 - Math.exp(-heat / 25)));
}

/**
 * 5-stage heat gradient: green 鈫?cyan 鈫?yellow 鈫?orange 鈫?red.
 * Each stage has 2 brightness sub-levels for finer granularity.
 */
function heatToRgba(heat: number): { r: number; g: number; b: number; a: number } {
  const t = normalizeHeat(heat);
  // Stage 1 鈥?green (very low)
  if (t < 0.08) return { r: 40,  g: 180, b: 80,  a: 0.32 };
  if (t < 0.18) return { r: 60,  g: 210, b: 90,  a: 0.46 };
  // Stage 2 鈥?cyan / teal (low)
  if (t < 0.30) return { r: 40,  g: 200, b: 180, a: 0.52 };
  if (t < 0.42) return { r: 50,  g: 180, b: 230, a: 0.60 };
  // Stage 3 鈥?yellow (medium)
  if (t < 0.54) return { r: 210, g: 220, b: 50,  a: 0.65 };
  if (t < 0.65) return { r: 240, g: 230, b: 40,  a: 0.72 };
  // Stage 4 鈥?orange (high)
  if (t < 0.76) return { r: 245, g: 155, b: 40,  a: 0.80 };
  if (t < 0.88) return { r: 250, g: 120, b: 30,  a: 0.87 };
  // Stage 5 鈥?red (very high)
  if (t < 0.95) return { r: 240, g: 55,  b: 35,  a: 0.92 };
  return               { r: 220, g: 20,  b: 20,  a: 0.97 };
}

/** Country subtitle labels used in hover text */
const ZH_NAMES: Record<string, string> = {
  AFG: '阿富汗',
  ALB: '阿尔巴尼亚',
  DZA: '阿尔及利亚',
  AND: '安道尔',
  AGO: '安哥拉',
  ARG: '阿根廷',
  ARM: '亚美尼亚',
  AUS: '澳大利亚',
  AUT: '奥地利',
  AZE: '阿塞拜疆',
  BHS: '巴哈马',
  BHR: '巴林',
  BGD: '孟加拉国',
  BLR: '白俄罗斯',
  BEL: '比利时',
  BLZ: '伯利兹',
  BEN: '贝宁',
  BTN: '不丹',
  BOL: '玻利维亚',
  BIH: '波黑',
  BWA: '博茨瓦纳',
  CHN: '中国',
  BRA: '巴西',
  BRN: '文莱',
  BGR: '保加利亚',
  BFA: '布基纳法索',
  BDI: '布隆迪',
  KHM: '柬埔寨',
  CMR: '喀麦隆',
  DEU: '德国',
  CAN: '加拿大',
  CAF: '中非',
  TCD: '乍得',
  CHL: '智利',
  TWN: '台湾',
  HKG: '香港',
  COL: '哥伦比亚',
  COM: '科摩罗',
  COD: '刚果（金）',
  COG: '刚果（布）',
  CRI: '哥斯达黎加',
  HRV: '克罗地亚',
  CUB: '古巴',
  CYP: '塞浦路斯',
  CZE: '捷克',
  DNK: '丹麦',
  DJI: '吉布提',
  DOM: '多米尼加共和国',
  ECU: '厄瓜多尔',
  EGY: '埃及',
  SLV: '萨尔瓦多',
  GNQ: '赤道几内亚',
  ERI: '厄立特里亚',
  EST: '爱沙尼亚',
  SWZ: '斯威士兰',
  ETH: '埃塞俄比亚',
  FRA: '法国',
  FIN: '芬兰',
  GAB: '加蓬',
  GMB: '冈比亚',
  GEO: '格鲁吉亚',
  GHA: '加纳',
  GRC: '希腊',
  GRL: '格陵兰',
  GTM: '危地马拉',
  GIN: '几内亚',
  GNB: '几内亚比绍',
  GUY: '圭亚那',
  HTI: '海地',
  HND: '洪都拉斯',
  HUN: '匈牙利',
  ISL: '冰岛',
  IND: '印度',
  IDN: '印度尼西亚',
  IRN: '伊朗',
  IRQ: '伊拉克',
  IRL: '爱尔兰',
  ISR: '以色列',
  ITA: '意大利',
  CIV: '科特迪瓦',
  JAM: '牙买加',
  JPN: '日本',
  JOR: '约旦',
  KAZ: '哈萨克斯坦',
  KEN: '肯尼亚',
  KWT: '科威特',
  KGZ: '吉尔吉斯斯坦',
  LAO: '老挝',
  LVA: '拉脱维亚',
  LBN: '黎巴嫩',
  LSO: '莱索托',
  LBR: '利比里亚',
  LBY: '利比亚',
  LTU: '立陶宛',
  LUX: '卢森堡',
  MDG: '马达加斯加',
  MWI: '马拉维',
  MYS: '马来西亚',
  MLI: '马里',
  MRT: '毛里塔尼亚',
  MEX: '墨西哥',
  MDA: '摩尔多瓦',
  MNG: '蒙古',
  MNE: '黑山',
  MAR: '摩洛哥',
  MOZ: '莫桑比克',
  MMR: '缅甸',
  NAM: '纳米比亚',
  NPL: '尼泊尔',
  NLD: '荷兰',
  NZL: '新西兰',
  NIC: '尼加拉瓜',
  NER: '尼日尔',
  NGA: '尼日利亚',
  PRK: '朝鲜',
  MKD: '北马其顿',
  NOR: '挪威',
  OMN: '阿曼',
  PAK: '巴基斯坦',
  PAN: '巴拿马',
  PNG: '巴布亚新几内亚',
  PRY: '巴拉圭',
  PER: '秘鲁',
  PHL: '菲律宾',
  POL: '波兰',
  PRT: '葡萄牙',
  PRI: '波多黎各',
  QAT: '卡塔尔',
  ROU: '罗马尼亚',
  RUS: '俄罗斯',
  RWA: '卢旺达',
  SAU: '沙特阿拉伯',
  SEN: '塞内加尔',
  SRB: '塞尔维亚',
  SLE: '塞拉利昂',
  SGP: '新加坡',
  SVK: '斯洛伐克',
  SVN: '斯洛文尼亚',
  SOM: '索马里',
  ZAF: '南非',
  KOR: '韩国',
  SSD: '南苏丹',
  ESP: '西班牙',
  LKA: '斯里兰卡',
  SDN: '苏丹',
  SUR: '苏里南',
  SWE: '瑞典',
  CHE: '瑞士',
  SYR: '叙利亚',
  TJK: '塔吉克斯坦',
  TZA: '坦桑尼亚',
  THA: '泰国',
  TGO: '多哥',
  TTO: '特立尼达和多巴哥',
  TUN: '突尼斯',
  TUR: '土耳其',
  TKM: '土库曼斯坦',
  UGA: '乌干达',
  UKR: '乌克兰',
  ARE: '阿联酋',
  GBR: '英国',
  USA: '美国',
  URY: '乌拉圭',
  UZB: '乌兹别克斯坦',
  VEN: '委内瑞拉',
  VNM: '越南',
  PSE: '巴勒斯坦',
  YEM: '也门',
  ZMB: '赞比亚',
  ZWE: '津巴布韦',
  GUF: '法属圭亚那',
  VAT: '梵蒂冈',
  FJI: '斐济',
  KOS: '科索沃',
  ESH: '西撒哈拉',
  SGS: '南乔治亚和南桑威奇群岛',
  BMU: '百慕大',
  CYM: '开曼群岛',
  FLK: '福克兰群岛',
  GUM: '关岛',
  MNP: '北马里亚纳群岛',
  VIR: '美属维尔京群岛',
  ASM: '美属萨摩亚',
  JEY: '泽西岛',
  GGY: '根西岛',
  IMN: '马恩岛',
  SHN: '圣赫勒拿',
  PCN: '皮特凯恩群岛',
  MSR: '蒙特塞拉特',
  VGB: '英属维尔京群岛',
  TCA: '特克斯和凯科斯群岛',
  AIA: '安圭拉',
};


/** Compute bbox center of a GeoJSON feature geometry */
function computeLngBounds(lngs: number[]): { min: number; max: number; span: number; center: number } | null {
  if (lngs.length === 0) return null;

  const rawMin = Math.min(...lngs);
  const rawMax = Math.max(...lngs);
  const rawSpan = rawMax - rawMin;

  if (rawSpan <= 180) {
    return {
      min: rawMin,
      max: rawMax,
      span: rawSpan,
      center: (rawMin + rawMax) / 2,
    };
  }

  const shifted = lngs.map((lng) => (lng < 0 ? lng + 360 : lng));
  const shiftedMin = Math.min(...shifted);
  const shiftedMax = Math.max(...shifted);
  const shiftedCenter = (shiftedMin + shiftedMax) / 2;
  const normalizedCenter = shiftedCenter > 180 ? shiftedCenter - 360 : shiftedCenter;

  return {
    min: shiftedMin,
    max: shiftedMax,
    span: shiftedMax - shiftedMin,
    center: normalizedCenter,
  };
}

function getFeatureBboxCenter(feat: GeoFeature): { lat: number; lng: number } | null {
  try {
    const geom = feat.geometry as any;
    if (!geom) return null;
    const coords: number[][] = [];
    if (geom.type === 'Polygon') {
      (geom.coordinates[0] as number[][]).forEach((c) => coords.push(c));
    } else if (geom.type === 'MultiPolygon') {
      (geom.coordinates as number[][][][]).forEach((poly) =>
        (poly[0] as number[][]).forEach((c) => coords.push(c))
      );
    }
    if (!coords.length) return null;
    const lngs = coords.map((c) => c[0]);
    const lats = coords.map((c) => c[1]);
    const lngBounds = computeLngBounds(lngs);
    if (!lngBounds) return null;
    return {
      lat: (Math.min(...lats) + Math.max(...lats)) / 2,
      lng: lngBounds.center,
    };
  } catch {
    return null;
  }
}

/** Map bbox span 鈫?camera altitude (large country 鈫?higher, small 鈫?closer) */
function getFeatureAltitude(feat: GeoFeature): number {
  try {
    const geom = feat.geometry as any;
    if (!geom) return 1.0;
    const coords: number[][] = [];
    if (geom.type === 'Polygon') {
      (geom.coordinates[0] as number[][]).forEach((c) => coords.push(c));
    } else if (geom.type === 'MultiPolygon') {
      (geom.coordinates as number[][][][]).forEach((poly) =>
        (poly[0] as number[][]).forEach((c) => coords.push(c))
      );
    }
    if (!coords.length) return 1.0;
    const lngs = coords.map((c) => c[0]);
    const lats = coords.map((c) => c[1]);
    const lngBounds = computeLngBounds(lngs);
    if (!lngBounds) return 1.0;
    const span = Math.max(
      Math.max(...lats) - Math.min(...lats),
      lngBounds.span
    );
    return Math.max(0.3, Math.min(2.4, span / 58));
  } catch {
    return 1.0;
  }
}

const GlobeScene: React.FC<GlobeSceneProps> = ({
  hotspots: rawHotspots,
  onAdmin1RegionClick,
  onBackToGlobal,
  regionBreadcrumb,
  onRegionBreadcrumbBack,
  onCountryBreadcrumbClick,
}) => {
  const hotspots = rawHotspots.filter((h: Hotspot) => h.center != null && h.center.length >= 2);
  const globeRef = useRef<any>(null);
  const resumeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clickOriginRef = useRef<{ x: number; y: number } | null>(null);
  const isDraggingRef = useRef(false);
  const hoveredFeatureRef = useRef<GeoFeature | null>(null);
  const clickTargetRef = useRef<GeoFeature | null>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [countries, setCountries] = useState<GeoFeature[]>([]);
  const [hoveredCountry, setHoveredCountry] = useState<string | null>(null);
  const [hoveredCountryEntry, setHoveredCountryEntry] = useState<{
    name: string; heat: number; count: number;
  } | null>(null);
  const [hoveredAdmin1, setHoveredAdmin1] = useState<string | null>(null);
  const [hoveredAdmin1Entry, setHoveredAdmin1Entry] = useState<{
    name: string; heat: number; count: number;
  } | null>(null);
  const [selectedAdmin1Code, setSelectedAdmin1Code] = useState<string | null>(null);
  const [pointer, setPointer] = useState({ x: 0, y: 0 });

  const {
    globeRotation,
    autoRotateSpeed,
  } = useGlobeStore();

  const {
    countryHeatMap,
    countryEventCountMap,
    countryHotspots,
    fetchCountryHotspots,
    selectCountry,
    backToGlobal,
    layer,
    selectedCountryName,
    selectedCountryCode,
    admin1Features,
    admin1HeatMap,
    admin1EventCountMap,
    admin1Hotspots,
    isLoadingAdmin1,
  } = useGeoLayerStore();

  const maxCountryHeat = useMemo(
    () => Math.max(1, ...countryHotspots.map((item) => item.heat_total || 0)),
    [countryHotspots]
  );
  const maxCountryEventCount = useMemo(
    () => Math.max(1, ...countryHotspots.map((item) => item.event_count || 0)),
    [countryHotspots]
  );
  const maxAdmin1Heat = useMemo(
    () => Math.max(1, ...admin1Hotspots.map((item) => item.heat_total || 0)),
    [admin1Hotspots]
  );
  const maxAdmin1EventCount = useMemo(
    () => Math.max(1, ...admin1Hotspots.map((item) => item.event_count || 0)),
    [admin1Hotspots]
  );
  const globeMaterial = useMemo(
    () =>
      new THREE.MeshPhongMaterial({
        color: new THREE.Color(0x020202),
        emissive: new THREE.Color(0x040404),
        emissiveIntensity: 0.35,
        specular: new THREE.Color(0x222222),
        shininess: 12,
        opacity: 1,
        transparent: false,
      }),
    []
  );
  useEffect(() => {
    fetchCountryHotspots();
  }, [fetchCountryHotspots]);

  useEffect(() => {
    let cancelled = false;
    loadGeoFeatures(LOCAL_COUNTRIES_GEOJSON, CDN_COUNTRIES_GEOJSON)
      .then((features) => { if (!cancelled) setCountries(features); })
      .catch(() => { /* offline or both unavailable */ });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      setPointer({ x: e.clientX, y: e.clientY });
      if (e.buttons > 0 && clickOriginRef.current) {
        const dx = e.clientX - clickOriginRef.current.x;
        const dy = e.clientY - clickOriginRef.current.y;
        if (Math.sqrt(dx * dx + dy * dy) > 5) isDraggingRef.current = true;
      }
    };
    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  useEffect(() => {
    const updateDimensions = () => {
      const container = document.querySelector('.globe-container');
      if (container) {
        setDimensions({ width: container.clientWidth, height: container.clientHeight });
      }
    };
    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  // Ref so the async timer always sees the latest layer without stale closure
  const layerRef = useRef(layer);
  layerRef.current = layer;

  const scheduleResumeAutoRotate = useCallback(() => {
    if (resumeTimerRef.current) clearTimeout(resumeTimerRef.current);
    resumeTimerRef.current = setTimeout(() => {
      const g = globeRef.current;
      // Never re-enable auto-rotation while viewing a country / region
      if (g && globeRotation && layerRef.current !== 'country') {
        g.controls().autoRotate = true;
      }
    }, 5000);
  }, [globeRotation]);

  useEffect(() => {
    if (globeRef.current) {
      const globe = globeRef.current;
      const c = globe.controls();
      c.autoRotate = globeRotation;
      c.autoRotateSpeed = autoRotateSpeed;
      c.enableDamping = true;
      c.dampingFactor = 0.08;
      c.minDistance = 110;
      c.maxDistance = 600;
      c.rotateSpeed = 0.5;
      c.zoomSpeed = 0.55;
      const onStart = () => {
        c.autoRotate = false;
        if (resumeTimerRef.current) clearTimeout(resumeTimerRef.current);
      };
      const onEnd = () => scheduleResumeAutoRotate();
      c.addEventListener?.('start', onStart);
      c.addEventListener?.('end', onEnd);
      return () => {
        c.removeEventListener?.('start', onStart);
        c.removeEventListener?.('end', onEnd);
      };
    }
    return undefined;
  }, [globeRotation, autoRotateSpeed, scheduleResumeAutoRotate]);

  /** Extract admin1_code from a Natural Earth admin1 feature */
  const admin1Code = useCallback((feat: GeoFeature): string => {
    const p = feat.properties || {};
    // iso_3166_2 is like "GB-ENG" 鈥?use the part after the dash as key
    const iso2 = String(p['iso_3166_2'] || '');
    if (iso2.includes('-')) return iso2.split('-').slice(1).join('-');
    return String(p['name'] || p['NAME'] || '');
  }, []);

  /** Lookup admin1 heat by NE code with name-based fallback (fixes CN/JP GeoNames vs NE code mismatch) */
  const getAdmin1Heat = useCallback(
    (feat: GeoFeature): number => {
      const code = admin1Code(feat);
      const hit = admin1HeatMap.get(code);
      if (hit !== undefined) return hit;
      const name = String(feat.properties?.['name'] || feat.properties?.['NAME'] || '').toLowerCase();
      return name ? (admin1HeatMap.get(name) ?? 0) : 0;
    },
    [admin1HeatMap, admin1Code]
  );

  const getAdmin1EventCount = useCallback(
    (feat: GeoFeature): number => {
      const code = admin1Code(feat);
      const hit = admin1EventCountMap.get(code);
      if (hit !== undefined) return hit;
      const name = String(feat.properties?.['name'] || feat.properties?.['NAME'] || '').toLowerCase();
      return name ? (admin1EventCountMap.get(name) ?? 0) : 0;
    },
    [admin1EventCountMap, admin1Code]
  );

  const displayPolygons = useMemo(() => {
    if (layer !== 'country') return countries;
    if (admin1Features.length === 0) return countries;
    if (selectedCountryCode !== 'CN') return admin1Features;

    const hasTaiwanRegion = admin1Features.some((feature) => admin1Code(feature as GeoFeature) === 'TW');
    if (hasTaiwanRegion) return admin1Features;

    const taiwanCountryFeature = countries.find((feature) => countryCode(feature).toUpperCase() === 'TWN');
    if (!taiwanCountryFeature) return admin1Features;

    return [...admin1Features, buildChinaTaiwanRegionFeature(taiwanCountryFeature)];
  }, [layer, countries, admin1Features, selectedCountryCode, admin1Code]);

  const polygonCapColor = useCallback(
    (d: object) => {
      const feat = d as GeoFeature;
      if (layer === 'country') {
        const a1code = admin1Code(feat);
        const heat = getAdmin1Heat(feat);
        const count = getAdmin1EventCount(feat);
        const isHover = hoveredAdmin1 === a1code && !!a1code;
        const isSelected = !!selectedAdmin1Code && selectedAdmin1Code === a1code;
        if (isSelected) return 'rgba(255, 230, 130, 0.72)';
        if (heat > 0 || count > 0) {
          const score = resolveCompositeIntensity(heat, count, maxAdmin1Heat, maxAdmin1EventCount);
          const { r, g, b, a } = compositeToRgba(score);
          if (isHover) return `rgba(${Math.min(255, r + 50)},${Math.min(255, g + 50)},${Math.min(255, b + 40)},${Math.min(0.95, a + 0.2)})`;
          return `rgba(${r},${g},${b},${a})`;
        }
        if (isHover) return 'rgba(255, 200, 80, 0.22)';
        return 'rgba(8, 12, 28, 0.92)';
      }
      const code = countryDataIso3(feat);
      const heat = countryHeatMap.get(code) ?? 0;
      const count = countryEventCountMap.get(code) ?? 0;
      const isHover = hoveredFeatureRef.current === feat;
      if (heat > 0 || count > 0) {
        const score = resolveCompositeIntensity(heat, count, maxCountryHeat, maxCountryEventCount);
        const { r, g, b, a } = compositeToRgba(score);
        if (isHover) return `rgba(${Math.min(255, r + 40)},${Math.min(255, g + 40)},${Math.min(255, b + 30)},${Math.min(0.95, a + 0.2)})`;
        return `rgba(${r},${g},${b},${a})`;
      }
      if (isHover) return 'rgba(255, 255, 255, 0.14)';
      return 'rgba(2, 2, 4, 0.96)';
    },
    [
      hoveredCountry,
      hoveredAdmin1,
      selectedAdmin1Code,
      countryHeatMap,
      countryEventCountMap,
      layer,
      admin1Code,
      getAdmin1Heat,
      getAdmin1EventCount,
      maxCountryHeat,
      maxCountryEventCount,
      maxAdmin1Heat,
      maxAdmin1EventCount,
    ]
  );

  const polygonSideColor = useCallback(
    (d: object) => {
      const feat = d as GeoFeature;
      if (layer === 'country') {
        const a1code = admin1Code(feat);
        const heat = getAdmin1Heat(feat);
        const count = getAdmin1EventCount(feat);
        const isHover = hoveredAdmin1 === a1code && !!a1code;
        if (heat > 0 || count > 0) return isHover ? 'rgba(255, 160, 40, 0.28)' : 'rgba(60, 40, 10, 0.35)';
        return isHover ? 'rgba(255, 200, 80, 0.12)' : 'rgba(0,0,0,0.85)';
      }
      const code = countryDataIso3(feat);
      const heat = countryHeatMap.get(code) ?? 0;
      const count = countryEventCountMap.get(code) ?? 0;
      const isHover = hoveredFeatureRef.current === feat;
      if (heat > 0 || count > 0) return isHover ? 'rgba(120, 170, 255, 0.2)' : 'rgba(20, 40, 80, 0.35)';
      return isHover ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.92)';
    },
    [hoveredCountry, hoveredAdmin1, countryHeatMap, countryEventCountMap, layer, admin1Code, getAdmin1Heat, getAdmin1EventCount]
  );

  const polygonStrokeColor = useCallback(
    (d: object) => {
      const feat = d as GeoFeature;
      if (layer === 'country') {
        const a1code = admin1Code(feat);
        const heat = getAdmin1Heat(feat);
        const count = getAdmin1EventCount(feat);
        const isHover = hoveredAdmin1 === a1code && !!a1code;
        const isSelected = !!selectedAdmin1Code && selectedAdmin1Code === a1code;
        if (isSelected) return 'rgba(255, 240, 160, 1.0)';
        if (heat > 0 || count > 0) return isHover ? 'rgba(255, 220, 120, 0.95)' : 'rgba(200, 150, 60, 0.6)';
        return isHover ? 'rgba(255, 220, 80, 0.92)' : 'rgba(120, 100, 60, 0.4)';
      }
      const code = countryDataIso3(feat);
      const heat = countryHeatMap.get(code) ?? 0;
      const count = countryEventCountMap.get(code) ?? 0;
      const isHover = hoveredFeatureRef.current === feat;
      if (heat > 0 || count > 0) return isHover ? 'rgba(200, 230, 255, 0.95)' : 'rgba(140, 180, 255, 0.65)';
      return isHover ? 'rgba(255, 255, 255, 0.95)' : 'rgba(255, 255, 255, 0.38)';
    },
    [hoveredCountry, hoveredAdmin1, selectedAdmin1Code, countryHeatMap, countryEventCountMap, layer, admin1Code, getAdmin1Heat, getAdmin1EventCount]
  );

  const polygonAltitude = useCallback(
    (d: object) => {
      const feat = d as GeoFeature;
      if (layer === 'country') {
        const a1code = admin1Code(feat);
        const heat = getAdmin1Heat(feat);
        const count = getAdmin1EventCount(feat);
        const isHover = hoveredAdmin1 === a1code && !!a1code;
        const isSelected = !!selectedAdmin1Code && selectedAdmin1Code === a1code;
        if (isSelected) return 0.04;
        return isHover ? 0.028 : (heat > 0 || count > 0) ? 0.008 : 0.005;
      }
      const code = countryDataIso3(feat);
      const heat = countryHeatMap.get(code) ?? 0;
      const count = countryEventCountMap.get(code) ?? 0;
      const isHover = hoveredFeatureRef.current === feat;
      return isHover ? 0.022 : (heat > 0 || count > 0) ? 0.0055 : 0.0035;
    },
    [hoveredCountry, hoveredAdmin1, selectedAdmin1Code, layer, admin1Code, getAdmin1Heat, getAdmin1EventCount, countryHeatMap, countryEventCountMap]
  );

  const polygonLabel = useCallback(
    (_d: object) => {
      // Disable react-globe.gl built-in tooltip; we render our own custom tooltips
      return '';
    },
    []
  );

  const handlePolygonHover = useCallback((polygon: object | null) => {
    hoveredFeatureRef.current = polygon ? (polygon as GeoFeature) : null;
    if (polygon) {
      if (layer === 'country') {
        const feat = polygon as GeoFeature;
        const code = admin1Code(feat);
        const name = String(feat.properties?.['name'] || feat.properties?.['NAME'] || code);
        setHoveredAdmin1(code);
        const entry = admin1Hotspots.find(
          (a) => a.admin1_code === code || (a.admin1_name || '').toLowerCase() === name.toLowerCase()
        );
        setHoveredAdmin1Entry(
          entry
            ? { name: entry.admin1_name || name, heat: entry.heat_total, count: entry.event_count }
            : { name, heat: 0, count: 0 }
        );
        setHoveredCountry(null);
      } else {
        const feat = polygon as GeoFeature;
        const dataCode = countryDataIso3(feat);
        const featureCode = countryCode(feat).toUpperCase();
        setHoveredCountry(dataCode);
        setHoveredAdmin1(null);
        setHoveredAdmin1Entry(null);
        const entry = countryHotspots.find((c) => canonicalCountryIso3(c.iso_a3 || c.country_code || '') === dataCode);
        const enName = countryDisplayName(feat);
        const zhName = ZH_NAMES[featureCode] || ZH_NAMES[dataCode];
        const displayName = zhName ? `${enName} · ${zhName}` : enName;
        setHoveredCountryEntry(
          entry
            ? { name: displayName, heat: entry.heat_total, count: entry.event_count }
            : { name: displayName, heat: 0, count: 0 }
        );
      }
    } else {
      setHoveredCountry(null);
      setHoveredCountryEntry(null);
      setHoveredAdmin1(null);
      setHoveredAdmin1Entry(null);
    }
  }, [layer, admin1Code, admin1Hotspots, countryHotspots]);

  /** ISO-3 -> ISO-2 lookup (for country click drill-down) */
  const ISO3_TO_ISO2: Record<string, string> = {
    GBR: 'GB', USA: 'US', CHN: 'CN', JPN: 'JP', KOR: 'KR', DEU: 'DE',
    FRA: 'FR', IND: 'IN', RUS: 'RU', AUS: 'AU', CAN: 'CA', BRA: 'BR',
    ITA: 'IT', ESP: 'ES', TWN: 'TW', HKG: 'HK', IRN: 'IR', UKR: 'UA',
    ISR: 'IL', TUR: 'TR', SAU: 'SA', ARE: 'AE', SGP: 'SG', IDN: 'ID',
  };

  const flyTo = useCallback(
    (lat: number, lng: number, altitude: number, durationMs = 1200) => {
      const g = globeRef.current;
      if (!g) return;
      const c = g.controls();
      c.autoRotate = false;
      if (resumeTimerRef.current) clearTimeout(resumeTimerRef.current);
      g.pointOfView({ lat, lng, altitude }, durationMs);
    },
    []
  );

  const clearGeoInteractionState = useCallback(() => {
    setHoveredCountry(null);
    setHoveredCountryEntry(null);
    setHoveredAdmin1(null);
    setHoveredAdmin1Entry(null);
    setSelectedAdmin1Code(null);
    hoveredFeatureRef.current = null;
    clickTargetRef.current = null;
  }, []);

  const stopOverlayInteraction = useCallback((event: ReactMouseEvent<HTMLElement>) => {
    event.stopPropagation();
    clickTargetRef.current = null;
    clickOriginRef.current = null;
    isDraggingRef.current = false;
  }, []);

  const handleBackToGlobal = useCallback(() => {
    clearGeoInteractionState();
    backToGlobal();
    onBackToGlobal?.();
    flyTo(22, 105, 2.45, 1000);
  }, [backToGlobal, clearGeoInteractionState, flyTo, onBackToGlobal]);

  const handlePolygonClick = useCallback(
    (polygon: object) => {
      if (isDraggingRef.current) return;
      const feat = polygon as GeoFeature;
      if (layer === 'country') {
        if (admin1Features.length === 0) {
          if (isLoadingAdmin1) return; // still loading 鈥?ignore click
          // GeoJSON failed / country has no admin1 file.
          // Reset to global so the code below re-enters the country cleanly.
          backToGlobal();
          // fall through to the global-layer handler 鈫?
        } else {
          const a1code = admin1Code(feat);
          const regionName = String(feat.properties?.['name'] || feat.properties?.['NAME'] || a1code);
          const featureName = regionName.toLowerCase();
          const nameEntry = admin1Hotspots.find(
            (a) => (a.admin1_name || '').toLowerCase() === featureName
          );
          const resolvedCode = nameEntry?.admin1_code || a1code;
          const matchingHotspots = hotspots.filter((h) => {
            if (selectedCountryCode === 'CN' && (resolvedCode === 'TW' || a1code === 'TW')) {
              return h.geo_key === 'TW'
                || h.geo_key?.startsWith('A1:TW:')
                || (h.iso_a3 != null && h.iso_a3.toUpperCase() === 'TWN');
            }
            if (!h.geo_key) return false;
            if (h.geo_key.startsWith('A1:')) {
              const parts = h.geo_key.split(':');
              if (parts[1] !== selectedCountryCode) return false;
              return (
                parts[2] === resolvedCode ||
                parts[2] === a1code ||
                parts[2].toLowerCase() === featureName
              );
            }
            return false;
          });
          setSelectedAdmin1Code(a1code);
          const fullGeoKey = `A1:${(selectedCountryCode || '').toUpperCase()}:${resolvedCode || a1code}`;
          onAdmin1RegionClick?.(matchingHotspots, regionName, selectedCountryName || '', fullGeoKey);
          return;
        }
      }
      // Global-layer click (or fallthrough after backToGlobal above)
      const featureIso3 = countryCode(feat).toUpperCase();
      const iso3 = countryDataIso3(feat);
      const iso2 = featureIso3 === 'TWN' ? 'CN' : canonicalCountryIso2(ISO3_TO_ISO2[iso3] || iso3.slice(0, 2));
      const targetFeature = featureIso3 === 'TWN'
        ? (countries.find((country) => countryCode(country).toUpperCase() === 'CHN') ?? feat)
        : feat;
      const enName = countryDisplayName(feat);
      const zhName = ZH_NAMES[featureIso3] || ZH_NAMES[iso3];
      const displayName = zhName ? `${enName} · ${zhName}` : enName;
      const center = getFeatureBboxCenter(targetFeature);
      if (center) {
        const alt = getFeatureAltitude(targetFeature);
        flyTo(center.lat, center.lng, alt, 1200);
      }
      if (globeRef.current) globeRef.current.controls().autoRotate = false;
      setSelectedAdmin1Code(null);
      setHoveredAdmin1(null);
      setHoveredAdmin1Entry(null);
      selectCountry(iso2, displayName, iso3);
      const countryHotspots = hotspots.filter(
        (h) => {
          if (iso2 === 'CN') {
            return h.geo_key === 'CN'
              || h.geo_key === 'TW'
              || (h.iso_a3 != null && ['CHN', 'TWN'].includes(h.iso_a3.toUpperCase()));
          }
          return h.geo_key === iso2 || (h.iso_a3 && h.iso_a3.toUpperCase() === iso3);
        }
      );
      onAdmin1RegionClick?.(countryHotspots, displayName, '', iso2);
    },
    [layer, selectCountry, admin1Code, admin1Features, isLoadingAdmin1, backToGlobal, hotspots, selectedCountryCode, selectedCountryName, admin1Hotspots, onAdmin1RegionClick, flyTo, countries]
  );

  /** Bright white-blue dot color that stands out against any country heat colour */
  const pointColor = useCallback(() => 'rgba(180, 230, 255, 0.92)', []);

  /** Dot radius scales gently with heat */
  const pointRadius = useCallback((d: object) => {
    const h = d as Hotspot;
    return 0.14 + Math.log10((h.heat_score || 1) + 1) * 0.045;
  }, []);

  return (
    <div
      className="globe-container"
      onMouseDown={(e) => {
        clickOriginRef.current = { x: e.clientX, y: e.clientY };
        isDraggingRef.current = false;
        clickTargetRef.current = hoveredFeatureRef.current;
      }}
      onMouseUp={() => {
        if (!clickOriginRef.current) return;
        if (isDraggingRef.current) return;
        const feat = clickTargetRef.current;
        clickOriginRef.current = null;
        clickTargetRef.current = null;
        if (feat) handlePolygonClick(feat);
      }}
    >
      <div className="globe-canvas-wrap">
        <Globe
          ref={globeRef}
          width={dimensions.width}
          height={dimensions.height}
          backgroundColor="rgba(0,0,0,0)"
          rendererConfig={{ alpha: true, premultipliedAlpha: false, antialias: true }}
          globeImageUrl={undefined}
          bumpImageUrl={undefined}
          globeMaterial={globeMaterial}
          showGraticules={false}
          showAtmosphere
          atmosphereColor="#2a2a2e"
          atmosphereAltitude={0.12}
          polygonsData={displayPolygons}
          polygonGeoJsonGeometry={(d: object) => (d as GeoFeature).geometry as any}
          polygonCapColor={polygonCapColor}
          polygonSideColor={polygonSideColor}
          polygonStrokeColor={polygonStrokeColor}
          polygonAltitude={polygonAltitude}
          polygonLabel={polygonLabel}
          polygonsTransitionDuration={layer === 'country' ? 700 : 0}
          onPolygonHover={handlePolygonHover}
          onPolygonClick={() => { /* handled by onMouseUp + hoveredFeatureRef */ }}
          pointsData={layer === 'country' ? [] : hotspots}
          pointLat={(d: object) => (d as Hotspot).center?.[1] ?? 0}
          pointLng={(d: object) => (d as Hotspot).center?.[0] ?? 0}
          pointColor={pointColor}
          pointAltitude={() => 0.028}
          pointRadius={pointRadius}
          pointLabel={() => ''}
          pointsTransitionDuration={300}
          onGlobeReady={() => {
            const g = globeRef.current;
            if (g) {
              g.pointOfView({ lat: 22, lng: 105, altitude: 2.45 });
            }
          }}
        />
      </div>

      {layer === 'country' && selectedCountryName && (
        <div
          className="geo-layer-indicator"
          onMouseDown={stopOverlayInteraction}
          onMouseUp={stopOverlayInteraction}
          onClick={stopOverlayInteraction}
        >
          <button className="geo-breadcrumb-btn" onClick={handleBackToGlobal} title="Back to global view">
            Globe
          </button>
          <span className="geo-breadcrumb-sep">›</span>
          {onCountryBreadcrumbClick ? (
            <button className="geo-breadcrumb-btn geo-breadcrumb-btn--region" onClick={onCountryBreadcrumbClick}>
              {selectedCountryName}
            </button>
          ) : (
            <span className="geo-layer-label">{selectedCountryName}</span>
          )}
          {regionBreadcrumb && regionBreadcrumb.length > 0 && regionBreadcrumb.map((seg, i) => {
            const isLast = i === regionBreadcrumb.length - 1;
            return (
              <span key={i}>
                <span className="geo-breadcrumb-sep">›</span>
                {isLast && onRegionBreadcrumbBack ? (
                  <button className="geo-breadcrumb-btn geo-breadcrumb-btn--region" onClick={onRegionBreadcrumbBack}>
                    ← {seg}
                  </button>
                ) : (
                  <span className="geo-layer-label">{seg}</span>
                )}
              </span>
            );
          })}
        </div>
      )}

      {layer !== 'country' && hoveredCountryEntry && (
        <div
          className="admin1-tooltip"
          style={{ left: pointer.x + 14, top: pointer.y - 44 }}
        >
          <div className="admin1-tooltip-name">{hoveredCountryEntry.name}</div>
          {hoveredCountryEntry.count > 0 && (
            <div className="admin1-tooltip-heat">
              {hoveredCountryEntry.count} news · heat {hoveredCountryEntry.heat}
            </div>
          )}
        </div>
      )}

      {layer === 'country' && hoveredAdmin1Entry && (
        <div
          className="admin1-tooltip"
          style={{ left: pointer.x + 14, top: pointer.y - 44 }}
        >
          <div className="admin1-tooltip-name">{hoveredAdmin1Entry.name}</div>
          {hoveredAdmin1Entry.count > 0 && (
            <div className="admin1-tooltip-heat">
              {hoveredAdmin1Entry.count} news · heat {hoveredAdmin1Entry.heat}
            </div>
          )}
        </div>
      )}

      {layer === 'country' && isLoadingAdmin1 && (
        <div className="geo-layer-loading">Loading regional boundaries...</div>
      )}
    </div>
  );
};

export default GlobeScene;

