import type { CSSProperties } from 'react';

export const TRACKER_DEMO_URL = 'https://calorie-app-pmjb9bbwfmikr8yqgicxdc.streamlit.app/?demo=1';
export const TRACKER_LOGIN_URL = 'https://calorie-app-pmjb9bbwfmikr8yqgicxdc.streamlit.app/';

const baseLink: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  minHeight: 48, padding: '12px 22px', borderRadius: 12,
  textDecoration: 'none', font: 'inherit', fontWeight: 600,
};

/** Add to the existing website; no account data, credentials or iframe needed. */
export default function MayBloomTrackerLinks({ compact = false }: { compact?: boolean }) {
  const links = (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
      <a href={TRACKER_DEMO_URL} target="_blank" rel="noopener noreferrer"
         style={{ ...baseLink, background: '#A34669', color: '#FFFFFF', border: '1px solid #A34669' }}>
        体验追踪器
      </a>
      <a href={TRACKER_LOGIN_URL} target="_blank" rel="noopener noreferrer"
         style={{ ...baseLink, background: '#FFFFFF', color: '#386863', border: '1px solid #B8CFC5' }}>
        学员登入
      </a>
    </div>
  );
  if (compact) return <nav aria-label="生活记录工具">{links}</nav>;
  return (
    <section aria-labelledby="may-bloom-tracker-heading" style={{
      background: '#FCF9FB', borderRadius: 20, padding: 'clamp(24px, 4vw, 40px)', color: '#382E34',
    }}>
      <h2 id="may-bloom-tracker-heading" style={{ margin: '0 0 12px', color: '#A34669' }}>
        May Bloom Lifestyle Tracker
      </h2>
      <p style={{ margin: '0 0 24px', lineHeight: 1.6 }}>
        记录饮食与运动，查看每日热量余额，接收 May 的记录点评。
      </p>
      {links}
    </section>
  );
}
