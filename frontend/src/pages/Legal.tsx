import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

const LAST_UPDATED = 'April 2026'

export default function Legal() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      <div className="max-w-2xl mx-auto px-6 py-10">

        {/* Back */}
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-sm mb-8 transition-colors"
          style={{ color: 'var(--text-muted)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--accent)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
        >
          <ArrowLeft size={14} />
          Back
        </button>

        {/* Header */}
        <div className="mb-10">
          <span className="font-display font-black text-2xl" style={{ color: 'var(--accent)' }}>ROSETTA</span>
          <h1 className="font-display text-3xl font-bold mt-2 mb-1" style={{ color: 'var(--text)' }}>
            Terms of Service & Privacy Policy
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-faint)' }}>Last updated: {LAST_UPDATED}</p>
        </div>

        <div className="space-y-10" style={{ color: 'var(--text-muted)', lineHeight: 1.75 }}>

          {/* ToS */}
          <section>
            <h2 className="font-display font-bold text-lg mb-3" style={{ color: 'var(--text)' }}>Terms of Service</h2>

            <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>1. Acceptance</h3>
            <p className="text-sm mb-4">
              By using Rosetta, you agree to these terms. If you do not agree, do not use the service.
            </p>

            <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>2. Description of Service</h3>
            <p className="text-sm mb-4">
              Rosetta is a tool that translates infrastructure-as-code files between formats (Terraform, AWS CDK,
              CloudFormation, SAM) using AI models hosted on Amazon Bedrock. The service is provided as-is with
              no guarantees of accuracy or fitness for any particular purpose.
            </p>

            <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>3. Your Responsibility</h3>
            <p className="text-sm mb-4">
              You are solely responsible for reviewing and validating all translated output before deploying it
              to any environment. Never deploy auto-translated infrastructure code without human review.
              Rosetta is a productivity tool, not a replacement for engineering judgment.
            </p>

            <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>4. Acceptable Use</h3>
            <p className="text-sm mb-4">
              You agree not to upload files containing secrets, passwords, credentials, or personally identifiable
              information. You agree not to attempt to abuse, circumvent rate limits, or reverse-engineer the service.
            </p>

            <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>5. No Warranty</h3>
            <p className="text-sm mb-4">
              Rosetta is provided "as is" without warranty of any kind. The maintainer is not liable for any
              damages arising from the use or inability to use the service, including but not limited to
              infrastructure incidents caused by translated code.
            </p>

            <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>6. Third-Party Services</h3>
            <p className="text-sm mb-4">
              Rosetta uses Amazon Bedrock (Claude AI) for translation. Your uploaded files are sent to Amazon Web
              Services for processing. Rosetta is an independent project and is not affiliated with, endorsed by,
              or sponsored by HashiCorp, Amazon Web Services, or Anthropic.
            </p>

            <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>7. Changes</h3>
            <p className="text-sm">
              These terms may be updated at any time. Continued use of the service after changes constitutes
              acceptance of the new terms.
            </p>
          </section>

          <hr style={{ borderColor: 'var(--border)' }} />

          {/* Privacy */}
          <section>
            <h2 className="font-display font-bold text-lg mb-3" style={{ color: 'var(--text)' }}>Privacy Policy</h2>

            <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>What we collect</h3>
            <p className="text-sm mb-4">
              When you sign in with Google, we receive your name and email address via AWS Cognito. We store
              a minimal user identifier to enforce per-user rate limits and associate jobs with your account.
            </p>

            <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>Your uploaded files</h3>
            <p className="text-sm mb-4">
              Files you upload are stored encrypted in AWS S3 for up to <strong>7 days</strong>, then permanently
              deleted by an automatic lifecycle policy. They are used solely to perform the requested translation.
              We do not read, analyze, sell, or share your infrastructure code for any other purpose.
            </p>

            <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>AI processing</h3>
            <p className="text-sm mb-4">
              Your file contents are sent to Amazon Bedrock (Claude AI) for translation. Amazon's data processing
              terms apply. We do not use your files to train AI models.
            </p>

            <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>Cookies & analytics</h3>
            <p className="text-sm mb-4">
              We do not use tracking cookies or third-party analytics. Authentication state is stored locally
              in your browser via AWS Amplify.
            </p>

            <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>Contact</h3>
            <p className="text-sm">
              For privacy concerns, open an issue at{' '}
              <a
                href="https://github.com/MatiSantoro/rosetta/issues"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'var(--accent)' }}
              >
                github.com/MatiSantoro/rosetta
              </a>.
            </p>
          </section>

        </div>
      </div>
    </div>
  )
}
