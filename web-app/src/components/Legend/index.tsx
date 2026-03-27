import { memo } from 'react';
import './Legend.css';

const Legend = memo(() => {
  return (
    <div className="legend">
      <div className="legend-item">
        <span className="legend-dot small" />
        <span className="legend-label">低热度</span>
      </div>
      <div className="legend-item">
        <span className="legend-dot medium" />
        <span className="legend-label">中热度</span>
      </div>
      <div className="legend-item">
        <span className="legend-dot large" />
        <span className="legend-label">高热度</span>
      </div>
    </div>
  );
});

Legend.displayName = 'Legend';

export default Legend;
