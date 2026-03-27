import { memo, useId } from 'react';
import './FilterBar.css';

interface FilterBarProps {
  scope: 'all' | 'china' | 'world';
  onScopeChange: (scope: 'all' | 'china' | 'world') => void;
  crawlCount: number;
  onCrawlCountChange: (n: number) => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

const FilterBar = memo(
  ({
    scope,
    onScopeChange,
    crawlCount,
    onCrawlCountChange,
    onRefresh,
    isRefreshing,
  }: FilterBarProps) => {
    const countId = useId();
    const options = [
      { value: 'all' as const, label: '全部' },
      { value: 'china' as const, label: '国内' },
      { value: 'world' as const, label: '国际' },
    ];

    return (
      <div className="filter-bar">
        <div className="filter-tabs">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`filter-tab ${scope === option.value ? 'active' : ''}`}
              onClick={() => onScopeChange(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="filter-crawl-controls" title="本次更新从各渠道抓取的新闻条数上限（后台任务）">
          <label htmlFor={countId} className="filter-crawl-label">
            数量
          </label>
          <input
            id={countId}
            className="filter-crawl-input"
            type="number"
            min={5}
            max={500}
            step={5}
            value={crawlCount}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (Number.isFinite(v)) onCrawlCountChange(Math.min(500, Math.max(5, v)));
            }}
          />
        </div>
        {onRefresh && (
          <button
            type="button"
            className="filter-refresh"
            title="按当前筛选与数量拉取新闻（后台爬虫）"
            disabled={isRefreshing}
            onClick={onRefresh}
          >
            <span className="filter-refresh-icon" aria-hidden>
              ↻
            </span>
            <span className="filter-refresh-label">更新</span>
          </button>
        )}
      </div>
    );
  }
);

FilterBar.displayName = 'FilterBar';

export default FilterBar;
