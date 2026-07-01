/**
 * GitHub OAuth Callback Page
 * 
 * Handles the OAuth redirect and communicates with parent window.
 */
import { useEffect } from 'react';
import { getAuthToken, API_BASE_URL } from '@/api/client';

export default function GitHubCallback() {
  useEffect(() => {
    const search = window.location.search || (window.location.hash.includes('?') ? '?' + window.location.hash.split('?')[1] : '');
    const params = new URLSearchParams(search);
    const code = params.get('code');
    const state = params.get('state');
    const error = params.get('error');

    if (error) {
      window.opener?.postMessage({ type: 'github-error', error }, '*');
      setTimeout(() => window.close(), 100);
      return;
    }

    if (code && state) {
      const origin = window.location.origin + window.location.pathname;
      const redirectUri = origin.replace(/\/$/, '') + '/#/github/callback';
      const query = new URLSearchParams({ code, state, redirect_uri: redirectUri });
      fetch(`${API_BASE_URL}/api/v1/github/connect?${query.toString()}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${getAuthToken()}` },
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            window.opener?.postMessage({ type: 'github-connected', user: data.user }, '*');
          } else {
            window.opener?.postMessage({ type: 'github-error', error: data.message }, '*');
          }
        })
        .catch(err => {
          window.opener?.postMessage({ type: 'github-error', error: err.message }, '*');
        })
        .finally(() => {
          setTimeout(() => window.close(), 100);
        });
    }
  }, []);

  return (
    <div className="flex h-screen items-center justify-center bg-slate-950">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-slate-400 text-sm mt-4">Connecting to GitHub...</p>
      </div>
    </div>
  );
}
