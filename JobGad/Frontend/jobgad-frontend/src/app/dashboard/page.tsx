'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { AppShell } from '@/components/layout/AppShell'
import { ScoreRing, ProgressBar, StatCard, Badge, SkeletonCard, EmptyState } from '@/components/ui'
import { dashboard, type GraduateDashboard } from '@/lib/api'
import {
  ArrowRight, Briefcase, Mic, FileEdit, ChevronRight,
  TrendingUp, AlertCircle
} from 'lucide-react'

export default function DashboardPage() {
  const { user } = useAuth()
  const router = useRouter()
  const [data, setData] = useState<GraduateDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    dashboard.graduate()
      .then(setData)
      .catch(() => setError('Could not load dashboard. Please refresh.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <AppShell title="Dashboard">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
          {[1, 2, 3, 4].map(i => <SkeletonCard key={i} rows={2} />)}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <SkeletonCard rows={5} />
          <SkeletonCard rows={5} />
        </div>
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell title="Dashboard">
        <EmptyState
          icon={<AlertCircle size={32} />}
          title="Failed to load dashboard"
          description={error}
        />
      </AppShell>
    )
  }

  const d = data!
  const iri = d.coaching?.current_iri ?? 0
  const completeness = d.profile?.completeness ?? 0

  const statusColor: Record<string, string> = {
    pending: 'var(--yellow)',
    reviewed: 'var(--blue-core)',
    shortlisted: 'var(--green)',
    accepted: 'var(--green)',
    rejected: 'var(--red)',
  }

  return (
    <AppShell
      title={`Good day, ${d.user?.full_name?.split(' ')[0] ?? 'there'}`}
      subtitle="Here is your career progress overview"
    >
      {/* ── Profile completeness banner ── */}
      {completeness < 80 && (
        <div style={{
          background: 'rgba(37,99,235,0.08)',
          border: '1px solid rgba(37,99,235,0.2)',
          borderRadius: 10,
          padding: '13px 18px',
          marginBottom: 24,
          display: 'flex',
          alignItems: 'center',
          gap: 14,
        }}>
          <AlertCircle size={16} style={{ color: 'var(--blue-bright)', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>
              Your profile is <strong>{Math.round(completeness)}% complete.</strong> Complete it to get better job matches.
            </span>
          </div>
          <Link href="/profile" className="btn btn-primary btn-sm" style={{ textDecoration: 'none', flexShrink: 0 }}>
            Complete profile <ChevronRight size={13} />
          </Link>
        </div>
      )}

      {/* ── Stat cards ── */}
      <div className="stagger" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14, marginBottom: 24 }}>
        <StatCard
          label="IRI Score"
          value={iri > 0 ? iri.toFixed(1) : '—'}
          sub={d.coaching?.readiness_level ?? 'No sessions yet'}
          color="var(--blue-bright)"
        />
        <StatCard
          label="Job Matches"
          value={d.job_matches?.total ?? 0}
          sub={`${d.job_matches?.new_this_week ?? 0} new this week`}
        />
        <StatCard
          label="Applications"
          value={d.applications?.total_applications ?? 0}
          sub={`${d.applications?.shortlisted ?? 0} shortlisted`}
          color={((d.applications?.shortlisted ?? 0) > 0) ? 'var(--green)' : undefined}
        />
        <StatCard
          label="CVs Generated"
          value={d.generated_cvs ?? 0}
          sub="tailored documents"
        />
      </div>

      {/* ── Main grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>

        {/* IRI + coaching breakdown */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <div>
              <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Interview Readiness</h3>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                {d.coaching?.total_sessions ?? 0} session{(d.coaching?.total_sessions ?? 0) !== 1 ? 's' : ''} completed
              </p>
            </div>
            <ScoreRing score={iri} size={64} />
          </div>

          {iri > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                ['Communication',   d.coaching?.communication ?? 0],
                ['Confidence',      d.coaching?.confidence ?? 0],
                ['Technical',       d.coaching?.technical_accuracy ?? 0],
                ['Structure',       d.coaching?.structure ?? 0],
              ].map(([label, val]) => (
                <ProgressBar key={label as string} label={label as string} value={val as number} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No coaching sessions yet"
              description="Start a session to track your interview readiness."
              action={
                <Link href="/coaching" className="btn btn-primary btn-sm" style={{ textDecoration: 'none' }}>
                  Start coaching <Mic size={13} />
                </Link>
              }
            />
          )}
        </div>

        {/* Profile completeness + skills */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Profile Health</h3>
            <Link href="/profile" style={{ fontSize: 12, color: 'var(--blue-bright)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
              Edit <ChevronRight size={12} />
            </Link>
          </div>

          <div style={{ marginBottom: 20 }}>
            <ProgressBar label="Profile completeness" value={completeness} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              { label: 'Headline', done: !!d.profile?.headline },
              { label: 'CV uploaded', done: false },
              { label: 'Skills added', done: (d.profile?.skills_count ?? 0) > 0 },
              { label: 'Target role set', done: !!d.profile?.target_role },
            ].map(item => (
              <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                  background: item.done ? 'var(--green)' : 'var(--bg-overlay)',
                  border: item.done ? 'none' : '1px solid var(--border-strong)',
                }} />
                <span style={{ fontSize: 13, color: item.done ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                  {item.label}
                </span>
                {item.done && <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--green)' }}>Done</span>}
              </div>
            ))}
          </div>

          <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {d.profile?.skills_count ?? 0} skills · Target: {d.profile?.target_role ?? 'Not set'}
            </span>
          </div>
        </div>
      </div>

      {/* ── Bottom grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

        {/* Top job matches */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Top Job Matches</h3>
            <Link href="/jobs" style={{ fontSize: 12, color: 'var(--blue-bright)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
              View all <ChevronRight size={12} />
            </Link>
          </div>

          {((d.job_matches?.total ?? 0) > 0) ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{
                background: 'var(--bg-elevated)', borderRadius: 8, padding: '12px 14px',
                display: 'flex', alignItems: 'center', gap: 12,
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 2 }}>
                    {d.job_matches?.top_match_title ?? 'Top match'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Best match this week</div>
                </div>
                <span className="badge badge-green" style={{ fontSize: 12 }}>
                  {Math.round(d.job_matches?.top_match_score ?? 0)}%
                </span>
              </div>
              <Link href="/jobs" className="btn btn-ghost btn-sm" style={{ textDecoration: 'none', justifyContent: 'center' }}>
                <Briefcase size={13} /> View {d.job_matches.total} matches
              </Link>
            </div>
          ) : (
            <EmptyState
              title="No matches yet"
              description="Run job matching to find relevant roles."
              action={
                <Link href="/jobs" className="btn btn-primary btn-sm" style={{ textDecoration: 'none' }}>
                  Run matching <ArrowRight size={13} />
                </Link>
              }
            />
          )}
        </div>

        {/* Recent applications */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Recent Applications</h3>
            <Link href="/applications" style={{ fontSize: 12, color: 'var(--blue-bright)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
              View all <ChevronRight size={12} />
            </Link>
          </div>

          {(d.recent_applications?.length ?? 0) > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(d.recent_applications ?? []).slice(0, 4).map(app => (
                <div key={app.id} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '10px 12px', background: 'var(--bg-elevated)',
                  borderRadius: 8,
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {app.job?.title}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{app.job?.company}</div>
                  </div>
                  <Badge label={app.status} />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No applications yet"
              description="Apply to jobs from the matches page."
              action={
                <Link href="/jobs" className="btn btn-primary btn-sm" style={{ textDecoration: 'none' }}>
                  Browse jobs <ArrowRight size={13} />
                </Link>
              }
            />
          )}
        </div>
      </div>

      {/* ── Next steps ── */}
      {(d.next_steps?.length ?? 0) > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <TrendingUp size={16} style={{ color: 'var(--blue-bright)' }} />
            <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Recommended next steps</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
            {d.next_steps.slice(0, 3).map((step, i) => (
              <Link key={i} href={step.link} style={{ textDecoration: 'none' }}>
                <div className="card-interactive" style={{
                  background: 'var(--bg-elevated)', borderRadius: 8,
                  border: '1px solid var(--border-default)', padding: '12px 14px',
                }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--blue-mid)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 6 }}>
                    Step {step.priority}
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 4 }}>{step.action}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>{step.description}</div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </AppShell>
  )
}