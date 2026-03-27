import { memo } from 'react';
import type { Hotspot } from '../../types/news';
import './HotspotTooltip.css';

interface HotspotTooltipProps {
  hotspot: Hotspot;
  x: number;
  y: number;
}

const HotspotTooltip = memo(({ hotspot, x, y }: HotspotTooltipProps) => {
  // Offset from cursor
  const offsetX = 15;
  const offsetY = 15;

  // Adjust position to keep tooltip in viewport
  const style: React.CSSProperties = {
    position: 'fixed',
    left: x + offsetX,
    top: y + offsetY,
    transform: 'translateY(-50%)',
    zIndex: 1000,
    pointerEvents: 'none',
  };

  return (
    <div className="hotspot-tooltip" style={style}>
      <div className="tooltip-content">
        <h4 className="tooltip-title">{hotspot.title}</h4>
        <div className="tooltip-meta">
          <span className="tooltip-location">
            {hotspot.geo_name || hotspot.geo_key}
          </span>
          <span className="tooltip-heat">热度 {hotspot.heat_score}</span>
        </div>
        {hotspot.summary && (
          <p className="tooltip-summary">{hotspot.summary}</p>
        )}
      </div>
      <div className="tooltip-arrow" />
    </div>
  );
});

HotspotTooltip.displayName = 'HotspotTooltip';

export default HotspotTooltip;
