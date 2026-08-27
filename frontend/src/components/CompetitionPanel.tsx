import type { FC } from 'react'
import { useTaskStore } from '../store/taskStore'
import type { CompetitorProfile } from '../store/taskStore'

function Chip({ text, color }: { text: string; color: string }) {
  return (
    <span
      style={{
        fontSize: 10,
        padding: '2px 8px',
        borderRadius: 20,
        background: color + '1f',
        color,
        border: '1px solid ' + color + '40',
        whiteSpace: 'nowrap',
      }}
    >
      {text}
    </span>
  )
}

const CompetitorCard: FC<{ profile: CompetitorProfile }> = ({ profile }) => (
  <div
    style={{
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid var(--border-subtle)',
      borderRadius: 10,
      padding: '12px 14px',
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
        {profile.name}
      </span>
      {profile.website && (
        <a
          href={`https://${profile.website}`}
          target="_blank"
          rel="noreferrer"
          style={{ fontSize: 10, color: 'var(--accent-cyan)', textDecoration: 'none' }}
        >
          {profile.website}
        </a>
      )}
      <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-disabled)' }}>
        {profile.sites_checked} sites
      </span>
    </div>

    {profile.pricing.length > 0 && (
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {profile.pricing.slice(0, 4).map((p, i) => (
          <Chip key={i} text={p} color="#fbbf24" />
        ))}
      </div>
    )}

    {profile.features.length > 0 && (
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {profile.features.slice(0, 6).map((f, i) => (
          <Chip key={i} text={f} color="#38bdf8" />
        ))}
      </div>
    )}

    {(profile.strengths.length > 0 || profile.weaknesses.length > 0) && (
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {profile.strengths.slice(0, 3).map((s, i) => (
          <Chip key={'s' + i} text={'+' + s} color="#4ade80" />
        ))}
        {profile.weaknesses.slice(0, 3).map((w, i) => (
          <Chip key={'w' + i} text={'−' + w} color="#f87171" />
        ))}
      </div>
    )}
  </div>
)

export const CompetitionPanel: FC = () => {
  const scan = useTaskStore((s) => s.competitionScan)
  if (!scan) return null

  const scanning = scan.status === 'scanning'

  return (
    <div
      style={{
        borderTop: '1px solid var(--border-subtle)',
        background: 'var(--bg-surface)',
        padding: '12px 24px 16px',
        maxHeight: '42%',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
          🕵️ Competition Scout
        </span>
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            padding: '2px 10px',
            borderRadius: 20,
            background: 'rgba(192,132,252,0.12)',
            color: '#c084fc',
            border: '1px solid rgba(192,132,252,0.35)',
          }}
        >
          ⚡ Super Worker · 1 employee · minimum tokens
        </span>
        {scanning && scan.current_target && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 11,
              color: 'var(--accent-cyan)',
            }}
          >
            <span className="spinner" style={{ width: 10, height: 10 }} />
            Browsing {scan.current_target}…
          </span>
        )}
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
        {(
          [
            ['Sites browsed', String(scan.sites_browsed), 'var(--accent-cyan)'],
            ['Competitors', String(scan.profiles.length), '#c084fc'],
            ['LLM calls for data', String(scan.llm_calls), '#fbbf24'],
            ['Tokens saved', '~' + scan.tokens_saved.toLocaleString(), '#4ade80'],
          ] as [string, string, string][]
        ).map(([label, value, color]) => (
          <div key={label}>
            <div
              style={{
                fontSize: 9,
                color: 'var(--text-disabled)',
                textTransform: 'uppercase',
                letterSpacing: 0.8,
              }}
            >
              {label}
            </div>
            <div style={{ fontSize: 13, fontWeight: 700, color, fontVariantNumeric: 'tabular-nums' }}>
              {value}
            </div>
          </div>
        ))}
      </div>

      {/* Competitor cards */}
      {scan.profiles.length > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 10,
          }}
        >
          {scan.profiles.map((p) => (
            <CompetitorCard key={p.name} profile={p} />
          ))}
        </div>
      )}

      {scan.status === 'done' && scan.profiles.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          No competitor data could be gathered — try naming competitors in the task.
        </div>
      )}
    </div>
  )
}
