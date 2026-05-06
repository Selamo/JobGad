'use client'
import Link from 'next/link'
import { ArrowRight, ChevronRight, Target, Mic, FileText, Zap, CheckCircle2 } from 'lucide-react'

export default function LandingPage() {
  return (
    <div style={{ background: 'var(--bg-base)', minHeight: '100vh', color: 'var(--text-primary)' }}>

      {/* NAVBAR */}
      <nav style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50,
        background: 'rgba(13,13,20,0.85)', backdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border-subtle)',
        height: 60, display: 'flex', alignItems: 'center',
        padding: '0 40px', justifyContent: 'space-between',
      }}>
        <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em' }}>
          Job<span style={{ color: 'var(--blue-core)' }}>Gad</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Link href="/login" className="btn btn-ghost btn-sm" style={{ textDecoration: 'none' }}>
            Sign in
          </Link>
          <Link href="/register" className="btn btn-primary btn-sm" style={{ textDecoration: 'none' }}>
            Get started
          </Link>
        </div>
      </nav>

      {/* HERO */}
      <section style={{
        paddingTop: 140, paddingBottom: 100,
        textAlign: 'center', position: 'relative', overflow: 'hidden',
        backgroundImage: 'radial-gradient(rgba(255,255,255,0.04) 1px, transparent 1px)',
        backgroundSize: '28px 28px',
      }}>
        <div style={{
          position: 'absolute', top: '10%', left: '50%', transform: 'translateX(-50%)',
          width: 700, height: 400,
          background: 'radial-gradient(ellipse, rgba(37,99,235,0.1) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        <div style={{ maxWidth: 740, margin: '0 auto', padding: '0 24px', position: 'relative' }}>
          <span className="badge badge-blue" style={{ marginBottom: 24, display: 'inline-flex', fontSize: 12 }}>
            AI-Powered Career Platform
          </span>

          <h1 style={{
            fontFamily: 'Outfit, sans-serif',
            fontSize: 'clamp(38px, 6vw, 68px)',
            fontWeight: 800, lineHeight: 1.08,
            letterSpacing: '-0.03em',
            color: 'var(--text-primary)',
            marginBottom: 24,
          }}>
            Launch your career<br />
            <span style={{
              background: 'linear-gradient(135deg, var(--blue-bright) 0%, var(--cyan-bright) 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}>
              with confidence
            </span>
          </h1>

          <p style={{
            fontSize: 17, color: 'var(--text-secondary)',
            lineHeight: 1.7, maxWidth: 520,
            margin: '0 auto 40px',
          }}>
            JobGad matches graduates to relevant jobs, trains you with AI interview coaching,
            and generates tailored CVs — all in one platform.
          </p>

          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Link href="/register" className="btn btn-primary btn-lg" style={{ textDecoration: 'none' }}>
              Start for free <ArrowRight size={16} />
            </Link>
            <Link href="/login" className="btn btn-ghost btn-lg" style={{ textDecoration: 'none' }}>
              Sign in <ChevronRight size={16} />
            </Link>
          </div>
        </div>

        {/* Stats */}
        <div style={{
          display: 'flex', justifyContent: 'center',
          gap: 48, marginTop: 80, flexWrap: 'wrap', padding: '0 24px',
        }}>
          {[
            ['500+', 'Jobs Listed'],
            ['95%',  'Match Accuracy'],
            ['3min', 'Avg CV Generate'],
            ['10K+', 'Graduates Trained'],
          ].map(([val, lbl]) => (
            <div key={lbl} style={{ textAlign: 'center' }}>
              <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 30, fontWeight: 500, color: 'var(--blue-bright)' }}>
                {val}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 5 }}>{lbl}</div>
            </div>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section style={{ padding: '90px 24px', maxWidth: 1100, margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: 60 }}>
          <h2 style={{
            fontFamily: 'Outfit, sans-serif', fontSize: 38, fontWeight: 700,
            letterSpacing: '-0.02em', marginBottom: 12,
          }}>
            Everything you need to land the job
          </h2>
          <p style={{ fontSize: 15, color: 'var(--text-secondary)' }}>
            Four powerful tools built for fresh graduates
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
          {[
            {
              icon: <Target size={22} />,
              color: 'var(--blue-core)',
              title: 'Semantic Job Matching',
              desc: 'AI analyzes your profile and skills to surface the most relevant jobs using vector similarity search.',
            },
            {
              icon: <Mic size={22} />,
              color: 'var(--cyan-core)',
              title: 'Live Interview Coaching',
              desc: 'Practice with an AI interviewer that adapts to your readiness level and gives real-time feedback.',
            },
            {
              icon: <FileText size={22} />,
              color: 'var(--purple)',
              title: 'Tailored CV Generation',
              desc: 'Generate a job-specific CV in seconds. Gemini AI tailors your experience to each application.',
            },
            {
              icon: <Zap size={22} />,
              color: 'var(--green)',
              title: 'Skill Gap Analysis',
              desc: 'Instantly see which skills you are missing for any role and get a personalized learning roadmap.',
            },
          ].map(f => (
            <div key={f.title} className="card card-interactive">
              <div style={{
                width: 46, height: 46, borderRadius: 10,
                background: `${f.color}18`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: f.color, marginBottom: 18,
              }}>
                {f.icon}
              </div>
              <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 16, fontWeight: 600, marginBottom: 10 }}>
                {f.title}
              </h3>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section style={{
        padding: '90px 24px',
        background: 'var(--bg-surface)',
        borderTop: '1px solid var(--border-subtle)',
        borderBottom: '1px solid var(--border-subtle)',
      }}>
        <div style={{ maxWidth: 760, margin: '0 auto', textAlign: 'center' }}>
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 36, fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 12 }}>
            How it works
          </h2>
          <p style={{ fontSize: 15, color: 'var(--text-secondary)', marginBottom: 60 }}>
            Four steps from sign-up to job offer
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {[
              { step: '01', title: 'Build your profile',       desc: 'Upload your CV or link GitHub and LinkedIn. Our AI automatically extracts your skills.' },
              { step: '02', title: 'Run AI job matching',      desc: 'Get ranked job matches based on semantic similarity between your profile and job requirements.' },
              { step: '03', title: 'Train with AI coaching',   desc: 'Practice realistic interview questions. Your IRI score tracks your readiness from 0 to 100.' },
              { step: '04', title: 'Apply with a tailored CV', desc: 'Generate a job-specific CV in one click and apply directly through the platform.' },
            ].map((s, i) => (
              <div key={s.step} style={{
                display: 'flex', gap: 24, textAlign: 'left',
                paddingBottom: i < 3 ? 32 : 0,
                borderBottom: i < 3 ? '1px solid var(--border-subtle)' : 'none',
                marginBottom: i < 3 ? 32 : 0,
              }}>
                <div style={{
                  fontFamily: 'DM Mono, monospace', fontSize: 13,
                  fontWeight: 500, color: 'var(--blue-mid)',
                  minWidth: 32, paddingTop: 4, flexShrink: 0,
                }}>
                  {s.step}
                </div>
                <div style={{ flex: 1 }}>
                  <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 17, fontWeight: 600, marginBottom: 7 }}>
                    {s.title}
                  </h3>
                  <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.65 }}>{s.desc}</p>
                </div>
                <CheckCircle2 size={20} style={{ color: 'var(--blue-dim)', flexShrink: 0, marginTop: 4 }} />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section style={{ padding: '110px 24px', textAlign: 'center' }}>
        <div style={{ maxWidth: 560, margin: '0 auto' }}>
          <h2 style={{
            fontFamily: 'Outfit, sans-serif', fontSize: 42, fontWeight: 800,
            letterSpacing: '-0.025em', marginBottom: 18, lineHeight: 1.1,
          }}>
            Ready to accelerate{' '}
            <span style={{
              background: 'linear-gradient(135deg, var(--blue-bright) 0%, var(--cyan-bright) 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}>
              your career?
            </span>
          </h2>
          <p style={{ fontSize: 16, color: 'var(--text-secondary)', marginBottom: 36, lineHeight: 1.7 }}>
            Join thousands of graduates who found their first job through JobGad.
          </p>
          <Link href="/register" className="btn btn-primary btn-lg" style={{ textDecoration: 'none' }}>
            Create free account <ArrowRight size={16} />
          </Link>
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{
        borderTop: '1px solid var(--border-subtle)',
        padding: '24px 40px',
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', flexWrap: 'wrap', gap: 12,
      }}>
        <div style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 700, color: 'var(--text-muted)', fontSize: 16 }}>
          Job<span style={{ color: 'var(--blue-core)' }}>Gad</span>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Built for graduates. Powered by AI.
        </div>
      </footer>
    </div>
  )
}