import { Amplify } from 'aws-amplify'
import {
  signInWithRedirect,
  signOut as amplifySignOut,
  getCurrentUser,
  fetchAuthSession,
} from 'aws-amplify/auth'
import { Hub } from 'aws-amplify/utils'

// ── Configure Amplify ───────────────────────────────────────────────────────

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId:       import.meta.env.VITE_USER_POOL_ID,
      userPoolClientId: import.meta.env.VITE_CLIENT_ID,
      loginWith: {
        oauth: {
          domain:          import.meta.env.VITE_COGNITO_DOMAIN,
          scopes:          ['openid', 'email', 'profile'],
          redirectSignIn:  [import.meta.env.VITE_REDIRECT_SIGNIN  ?? 'http://localhost:5173/auth/callback'],
          redirectSignOut: [import.meta.env.VITE_REDIRECT_SIGNOUT ?? 'http://localhost:5173/'],
          responseType:    'code',
        },
      },
    },
  },
})

// ── Auth helpers ────────────────────────────────────────────────────────────

export async function getAccessToken(): Promise<string> {
  const session = await fetchAuthSession()
  const token = session.tokens?.accessToken?.toString()
  if (!token) throw new Error('Not authenticated')
  return token
}

export async function isAuthenticated(): Promise<boolean> {
  try {
    await getCurrentUser()
    return true
  } catch {
    return false
  }
}

export async function getUser() {
  try {
    return await getCurrentUser()
  } catch {
    return null
  }
}

export function signInWithGoogle() {
  return signInWithRedirect({ provider: 'Google' })
}

export function signOut() {
  return amplifySignOut()
}

/** Listen for auth events (signedIn after OAuth redirect) */
export function onAuthEvent(
  onSignIn: () => void,
  onSignOut: () => void,
): () => void {
  return Hub.listen('auth', ({ payload }) => {
    if (payload.event === 'signedIn')  onSignIn()
    if (payload.event === 'signedOut') onSignOut()
  })
}
