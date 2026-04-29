import { Github, Coffee, ExternalLink } from 'lucide-react'

const LINKS = {
  github:    'https://github.com/MatiSantoro/rosetta',
  issues:    'https://github.com/MatiSantoro/rosetta/issues',
  kofi:      'https://ko-fi.com/matiassantoro',
  cafecito:  'https://cafecito.app/matisantoro',
}

function SupportButton({
  href, label, accent = false,
}: { href: string; label: string; accent?: boolean }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium
                 transition-all duration-150 active:scale-95"
      style={{
        background:  accent ? 'var(--accent)' : 'var(--surface)',
        color:       accent ? 'var(--accent-fg)' : 'var(--text-muted)',
        border:      `1px solid ${accent ? 'var(--accent)' : 'var(--border)'}`,
      }}
    >
      <Coffee size={12} />
      {label}
    </a>
  )
}

interface FooterProps {
  minimal?: boolean   // compact version for authenticated pages
}

export default function Footer({ minimal = false }: FooterProps) {
  if (minimal) {
    return (
      <footer
        className="flex items-center justify-between px-6 py-3 border-t text-xs flex-wrap gap-3"
        style={{ borderColor: 'var(--border)', color: 'var(--text-faint)' }}
      >
        <span>© {new Date().getFullYear()} Matías Santoro</span>

        <div className="flex items-center gap-4">
          <a href={LINKS.issues} target="_blank" rel="noopener noreferrer"
             className="flex items-center gap-1 hover:text-[var(--accent)] transition-colors">
            <Github size={11} /> Report an issue
          </a>
          <a href={LINKS.kofi} target="_blank" rel="noopener noreferrer"
             className="flex items-center gap-1 hover:text-[var(--accent)] transition-colors">
            <Coffee size={11} /> Support
          </a>
        </div>
      </footer>
    )
  }

  return (
    <footer className="w-full mt-12 pt-10 pb-8 px-6" style={{ borderTop: '1px solid var(--border)' }}>
      <div className="max-w-2xl mx-auto space-y-8">

        {/* About */}
        <div className="text-center space-y-3">
          <h3 className="font-display font-bold text-sm tracking-widest uppercase"
              style={{ color: 'var(--accent)' }}>
            About the creator
          </h3>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-muted)' }}>
            I'm <span style={{ color: 'var(--text)' }}>Matías Santoro</span>, a software engineer
            passionate about building things that matter. I believe great code is more than just
            logic — it's about solving real problems for real people.
          </p>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-muted)' }}>
            Every contribution fuels the work I love: learning, creating, and pushing ideas forward.
            Whether it's a side project, an open-source tool, or something in between — your support
            means I can keep doing what drives me. Thanks for being part of the journey. 🙌
          </p>
        </div>

        {/* Support */}
        <div className="flex flex-col items-center gap-3">
          <p className="text-xs font-semibold uppercase tracking-widest"
             style={{ color: 'var(--text-faint)' }}>
            Support this project
          </p>
          <div className="flex items-center gap-3 flex-wrap justify-center">
            <SupportButton href={LINKS.kofi}     label="Ko-fi (USD)"      accent />
            <SupportButton href={LINKS.cafecito}  label="Cafecito (ARS)" />
          </div>
          <p className="text-xs text-center" style={{ color: 'var(--text-faint)' }}>
            Helps cover AWS & Bedrock costs so Rosetta stays free.
          </p>
        </div>

        {/* Links */}
        <div className="flex items-center justify-center gap-6 flex-wrap">
          <a href={LINKS.github} target="_blank" rel="noopener noreferrer"
             className="flex items-center gap-1.5 text-xs transition-colors hover:text-[var(--accent)]"
             style={{ color: 'var(--text-faint)' }}>
            <Github size={13} /> View on GitHub
          </a>
          <a href={LINKS.issues} target="_blank" rel="noopener noreferrer"
             className="flex items-center gap-1.5 text-xs transition-colors hover:text-[var(--accent)]"
             style={{ color: 'var(--text-faint)' }}>
            <ExternalLink size={13} /> Open an Issue
          </a>
        </div>

        {/* Bottom */}
        <div className="flex items-center justify-center gap-2 text-xs"
             style={{ color: 'var(--text-faint)' }}>
          <span>© {new Date().getFullYear()} Matías Santoro</span>
          <span>·</span>
          <span>Built with Claude AI & AWS Bedrock</span>
        </div>

      </div>
    </footer>
  )
}
