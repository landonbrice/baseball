export default function MobilityCard({ mobility }) {
  if (!mobility || !mobility.videos || mobility.videos.length === 0) return null;

  return (
    <div style={{ background: 'var(--color-white)', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ padding: '10px 14px', borderBottom: '0.5px solid var(--color-cream-border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 14 }}>🧘</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>Mobility</span>
          <span style={{ fontSize: 11, color: 'var(--color-ink-muted)' }}>— Week {mobility.week}</span>
        </div>
      </div>
      <div style={{ padding: '8px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {mobility.videos.map((video, i) => (
          <a
            key={video.id || i}
            href={video.youtube_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '8px 10px',
              borderRadius: 8,
              background: 'var(--color-cream-bg)',
              textDecoration: 'none',
              color: 'inherit',
            }}
          >
            <span style={{
              fontSize: 18,
              width: 32,
              height: 32,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 8,
              background: 'var(--color-maroon)',
              color: 'white',
              flexShrink: 0,
            }}>
              ▶
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink-primary)' }}>
                {video.title}
              </div>
              <div style={{ fontSize: 11, color: 'var(--color-ink-muted)' }}>
                {video.type}
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
