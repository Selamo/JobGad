'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { AppShell } from '@/components/layout/AppShell'
import { ScoreRing, ProgressBar, StatCard, Badge, SkeletonCard, EmptyState } from '@/components/ui'
import { dashboard, admin, type GraduateDashboard, type HRDashboard } from '@/lib/api'
import { ArrowRight, Briefcase, Mic, ChevronRight, TrendingUp, AlertCircle, Building2, ShieldCheck, Users } from 'lucide-react'

export default function DashboardPage() {
  const { user } = useAuth()
  const [data, setData]       = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

 useEffect(() => {
    if (!user) return
    const fetchData = async () => {
      try {
        if (user.role === 'superadmin' || user.role === 'admin') {
          const res = await admin.dashboard()
          setData(res)
        } else if (user.role === 'hr') {
          const res = await dashboard.hr()
          setData(res)
        } else {
          const res = await dashboard.graduate()
          setData(res)
        }
      } catch {
        setError('Could not load dashboard. Please refresh.')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [user])
  if (loading) {
    return (
      <AppShell title="Dashboard">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
          {[1,2,3,4].map(i => <SkeletonCard key={i} rows={2} />)}
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
        <EmptyState icon={<AlertCircle size={32} />} title="Failed to load dashboard" description={error} />
      </AppShell>
    )
  }

  // ── SUPERADMIN DASHBOARD ──────────────────────────────────────────────────
  if (user?.role === 'superadmin' || user?.role === 'admin') {
    const totalUsers       = data?.users?.total ?? 0
    const totalCompanies   = data?.companies?.total ?? 0
    const totalJobs        = data?.jobs?.active ?? 0
    const totalApps        = data?.applications?.total ?? 0
    const pendingCompanies = data?.companies?.pending_approval ?? 0
    const pendingHR        = data?.hr_profiles?.pending_approval ?? 0

    return (
      <AppShell
        title={`Welcome, ${user?.full_name?.split(' ')[0] ?? 'Admin'}`}
        subtitle="Platform administration overview"
      >
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14, marginBottom: 24 }}>
          <StatCard label="Total Users"     value={totalUsers}     color="var(--blue-bright)" />
          <StatCard label="Total Companies" value={totalCompanies} />
          <StatCard label="Active Jobs"     value={totalJobs}      color="var(--cyan-bright)" />
          <StatCard label="Applications"    value={totalApps} />
          <StatCard label="Pending Companies" value={pendingCompanies} color={pendingCompanies > 0 ? 'var(--yellow)' : undefined} />
          <StatCard label="Pending HR"      value={pendingHR}      color={pendingHR > 0 ? 'var(--yellow)' : undefined} />
        </div>

        {/* Users by role breakdown */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
          <div className="card">
            <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Users by Role</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Object.entries(data?.users?.by_role ?? {}).map(([role, count]) => (
                <div key={role} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'var(--bg-elevated)', borderRadius: 8 }}>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{role}</span>
                  <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 16, fontWeight: 500, color: 'var(--blue-bright)' }}>{count as number}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Platform Overview</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                { label: 'Approved Companies', value: data?.companies?.by_status?.approved ?? 0, color: 'var(--green)' },
                { label: 'Pending Companies',  value: pendingCompanies, color: pendingCompanies > 0 ? 'var(--yellow)' : 'var(--text-primary)' },
                { label: 'Active Jobs',        value: totalJobs, color: 'var(--cyan-bright)' },
                { label: 'Total Applications', value: totalApps, color: 'var(--text-primary)' },
              ].map(s => (
                <div key={s.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'var(--bg-elevated)', borderRadius: 8 }}>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{s.label}</span>
                  <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 16, fontWeight: 500, color: s.color }}>{s.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Pending alerts */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {pendingCompanies > 0 && (
            <div style={{ background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 10, padding: '13px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Building2 size={15} style={{ color: 'var(--yellow)' }} />
                <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>
                  <strong>{pendingCompanies}</strong> company registration{pendingCompanies > 1 ? 's' : ''} awaiting approval
                </span>
              </div>
              <Link href="/admin" className="btn btn-ghost btn-sm" style={{ textDecoration: 'none' }}>
                Review <ChevronRight size={13} />
              </Link>
            </div>
          )}
          {pendingHR > 0 && (
            <div style={{ background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 10, padding: '13px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <ShieldCheck size={15} style={{ color: 'var(--yellow)' }} />
                <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>
                  <strong>{pendingHR}</strong> HR account{pendingHR > 1 ? 's' : ''} awaiting approval
                </span>
              </div>
              <Link href="/admin" className="btn btn-ghost btn-sm" style={{ textDecoration: 'none' }}>
                Review <ChevronRight size={13} />
              </Link>
            </div>
          )}
          {pendingCompanies === 0 && pendingHR === 0 && (
            <div style={{ textAlign: 'center', padding: '32px 24px' }}>
              <CheckCircle2 size={32} style={{ color: 'var(--green)', margin: '0 auto 12px' }} />
              <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>No pending approvals — everything is up to date.</p>
            </div>
          )}
        </div>
      </AppShell>
    )
  }

  // ── HR DASHBOARD ──────────────────────────────────────────────────────────
  if (user?.role === 'hr') {
    const d = data as HRDashboard
    return (
      <AppShell
        title={`Welcome, ${d?.user?.full_name?.split(' ')[0] ?? 'there'}`}
        subtitle="Your recruitment overview"
      >
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14, marginBottom: 24 }}>
          <StatCard label="Active Jobs"   value={d?.jobs?.active      ?? 0} color="var(--blue-bright)" />
          <StatCard label="Total Jobs"    value={d?.jobs?.total       ?? 0} />
          <StatCard label="Applications"  value={d?.applications?.total       ?? 0} />
          <StatCard label="Shortlisted"   value={d?.applications?.shortlisted ?? 0} color="var(--green)" />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <Briefcase size={16} style={{ color: 'var(--blue-bright)' }} />
              <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Company</h3>
            </div>
            <div style={{ marginBottom: 8 }}>
              <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                {d?.company?.name ?? 'Your Company'}
              </p>
              <Badge label={d?.company?.status ?? 'pending'} />
            </div>
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border-subtle)' }}>
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {d?.jobs?.active ?? 0} active · {d?.jobs?.closed ?? 0} closed
              </p>
            </div>
            <Link href="/hr" className="btn btn-primary btn-sm" style={{ textDecoration: 'none', marginTop: 14, display: 'inline-flex' }}>
              Manage jobs <ChevronRight size={13} />
            </Link>
          </div>

          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <Users size={16} style={{ color: 'var(--green)' }} />
              <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Applications</h3>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                { label: 'Total',       value: d?.applications?.total       ?? 0, color: 'var(--text-primary)' },
                { label: 'Pending',     value: d?.applications?.pending     ?? 0, color: 'var(--yellow)' },
                { label: 'Shortlisted', value: d?.applications?.shortlisted ?? 0, color: 'var(--green)' },
              ].map(s => (
                <div key={s.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'var(--bg-elevated)', borderRadius: 8 }}>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{s.label}</span>
                  <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 16, fontWeight: 500, color: s.color }}>{s.value}</span>
                </div>
              ))}
            </div>
            <Link href="/hr" className="btn btn-ghost btn-sm" style={{ textDecoration: 'none', marginTop: 14, display: 'inline-flex' }}>
              View applications <ChevronRight size={13} />
            </Link>
          </div>
        </div>
      </AppShell>
    )
  }

  // ── GRADUATE DASHBOARD ────────────────────────────────────────────────────
  const d = data as GraduateDashboard
  const iri          = d?.coaching?.current_iri ?? 0
  const completeness = d?.profile?.completeness ?? 0

  return (
    <AppShell
      title={`Good day, ${d?.user?.full_name?.split(' ')[0] ?? 'there'}`}
      subtitle="Here is your career progress overview"
    >
      {completeness < 80 && (
        <div style={{ background: 'rgba(37,99,235,0.08)', border: '1px solid rgba(37,99,235,0.2)', borderRadius: 10, padding: '13px 18px', marginBottom: 24, display: 'flex', alignItems: 'center', gap: 14 }}>
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

      <div className="stagger" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14, marginBottom: 24 }}>
        <StatCard label="IRI Score"     value={iri > 0 ? iri.toFixed(1) : '—'} sub={d?.coaching?.readiness_level ?? 'No sessions yet'} color="var(--blue-bright)" />
        <StatCard label="Job Matches"   value={d?.job_matches?.total ?? 0} sub={`${d?.job_matches?.new_this_week ?? 0} new this week`} />
        <StatCard label="Applications"  value={d?.applications?.total_applications ?? 0} sub={`${d?.applications?.shortlisted ?? 0} shortlisted`} color={(d?.applications?.shortlisted ?? 0) > 0 ? 'var(--green)' : undefined} />
        <StatCard label="CVs Generated" value={d?.generated_cvs ?? 0} sub="tailored documents" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <div>
              <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Interview Readiness</h3>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                {d?.coaching?.total_sessions ?? 0} session{(d?.coaching?.total_sessions ?? 0) !== 1 ? 's' : ''} completed
              </p>
            </div>
            <ScoreRing score={iri} size={64} />
          </div>
          {iri > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                ['Communication', d?.coaching?.communication ?? 0],
                ['Confidence',    d?.coaching?.confidence ?? 0],
                ['Technical',     d?.coaching?.technical_accuracy ?? 0],
                ['Structure',     d?.coaching?.structure ?? 0],
              ].map(([label, val]) => (
                <ProgressBar key={label as string} label={label as string} value={val as number} />
              ))}
            </div>
          ) : (
            <EmptyState title="No coaching sessions yet" description="Start a session to track your interview readiness."
              action={
                <Link href="/coaching" className="btn btn-primary btn-sm" style={{ textDecoration: 'none' }}>
                  Start coaching <Mic size={13} />
                </Link>
              }
            />
          )}
        </div>

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
              { label: 'Headline set',    done: !!d?.profile?.headline },
              { label: 'CV uploaded',     done: false },
              { label: 'Skills added',    done: (d?.profile?.skills_count ?? 0) > 0 },
              { label: 'Target role set', done: !!d?.profile?.target_role },
            ].map(item => (
              <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0, background: item.done ? 'var(--green)' : 'var(--bg-overlay)', border: item.done ? 'none' : '1px solid var(--border-strong)' }} />
                <span style={{ fontSize: 13, color: item.done ? 'var(--text-primary)' : 'var(--text-muted)' }}>{item.label}</span>
                {item.done && <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--green)' }}>Done</span>}
              </div>
            ))}
          </div>
          <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {d?.profile?.skills_count ?? 0} skills · Target: {d?.profile?.target_role ?? 'Not set'}
            </span>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Top Job Matches</h3>
            <Link href="/jobs" style={{ fontSize: 12, color: 'var(--blue-bright)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
              View all <ChevronRight size={12} />
            </Link>
          </div>
          {(d?.job_matches?.total ?? 0) > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ background: 'var(--bg-elevated)', borderRadius: 8, padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 2 }}>{d?.job_matches?.top_match_title ?? 'Top match'}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Best match this week</div>
                </div>
                <span className="badge badge-green">{Math.round(d?.job_matches?.top_match_score ?? 0)}%</span>
              </div>
              <Link href="/jobs" className="btn btn-ghost btn-sm" style={{ textDecoration: 'none', justifyContent: 'center' }}>
                <Briefcase size={13} /> View {d.job_matches.total} matches
              </Link>
            </div>
          ) : (
            <EmptyState title="No matches yet" description="Run job matching to find relevant roles."
              action={
                <Link href="/jobs" className="btn btn-primary btn-sm" style={{ textDecoration: 'none' }}>
                  Run matching <ArrowRight size={13} />
                </Link>
              }
            />
          )}
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Recent Applications</h3>
            <Link href="/applications" style={{ fontSize: 12, color: 'var(--blue-bright)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
              View all <ChevronRight size={12} />
            </Link>
          </div>
          {(d?.recent_applications?.length ?? 0) > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(d?.recent_applications ?? []).slice(0, 4).map(app => (
                <div key={app.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', background: 'var(--bg-elevated)', borderRadius: 8 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{app.job?.title}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{app.job?.company}</div>
                  </div>
                  <Badge label={app.status} />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No applications yet" description="Apply to jobs from the matches page."
              action={
                <Link href="/jobs" className="btn btn-primary btn-sm" style={{ textDecoration: 'none' }}>
                  Browse jobs <ArrowRight size={13} />
                </Link>
              }
            />
          )}
        </div>
      </div>

      {(d?.next_steps?.length ?? 0) > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <TrendingUp size={16} style={{ color: 'var(--blue-bright)' }} />
            <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Recommended next steps</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
            {d.next_steps.slice(0, 3).map((step, i) => (
              <Link key={i} href={step.link} style={{ textDecoration: 'none' }}>
                <div className="card-interactive" style={{ background: 'var(--bg-elevated)', borderRadius: 8, border: '1px solid var(--border-default)', padding: '12px 14px' }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--blue-mid)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 6 }}>Step {step.priority}</div>
                  <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{step.action}</div>
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