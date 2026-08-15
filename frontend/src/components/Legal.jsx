import React, { useEffect } from 'react'

// Privacy Policy + Terms, styled in the same funky theme (readable doc treatment).
export default function Legal({ page, onHome, onNav }) {
  useEffect(() => { window.scrollTo(0, 0) }, [page])
  return (
    <div className="mkt">
      <header className="nav">
        <div className="nav-inner">
          <a className="logo" href="#home" onClick={(e) => { e.preventDefault(); onHome?.() }}>
            <span className="m"><svg viewBox="0 0 24 24" fill="#fff"><path d="M4 4l16 8-16 8z" /></svg></span>
            <span className="name">youtube_manager<b>.ai</b></span>
          </a>
          <div className="nav-actions">
            <a className="lnk" href="#privacy" onClick={(e) => { e.preventDefault(); onNav?.('privacy') }}>Privacy</a>
            <a className="lnk" href="#terms" onClick={(e) => { e.preventDefault(); onNav?.('terms') }}>Terms</a>
            <a className="go" href="#home" onClick={(e) => { e.preventDefault(); onHome?.() }}>← Home</a>
          </div>
        </div>
      </header>
      <main className="doc wrap narrow">
        {page === 'terms' ? <Terms /> : <Privacy onNav={onNav} />}
      </main>
      <footer>
        © {new Date().getFullYear()} youtube_manager.ai
        <div className="links">
          <a onClick={() => onNav?.('privacy')}>Privacy</a>
          <a onClick={() => onNav?.('terms')}>Terms</a>
          <a onClick={onHome}>Home</a>
        </div>
      </footer>
    </div>
  )
}

function Privacy() {
  return (
    <>
      <h1>Privacy Policy</h1>
      <p className="updated">Last updated: 25 July 2026</p>
      <p>This Privacy Policy explains how <strong>youtube_manager.ai</strong> (“we”, “us”, the “Service”) — a hosted web service — handles your information. The Service helps you turn a video into a publish-ready, SEO-optimized YouTube post and publish it to YouTube channels you own.</p>

      <div className="callout">
        <strong>The short version.</strong> You bring your own AI keys and connect your own YouTube channels. Your API keys, YouTube access tokens and uploaded videos are <strong>encrypted at rest on our servers</strong> and used only to run the features you ask for. We never sell your data, never use it for advertising, and never read your content except as needed to operate the Service, comply with law, or with your permission. Source videos are deleted after we finish processing them.
      </div>

      <h2>1. What we collect</h2>
      <ul>
        <li><strong>Account information.</strong> When you sign in with Google we receive your name, email address and Google account identifier, used to create and secure your account.</li>
        <li><strong>Your keys &amp; tokens.</strong> The AI API keys you add and the YouTube authorization tokens for channels you connect — <strong>encrypted at rest</strong> and used only to generate metadata and publish on your behalf.</li>
        <li><strong>Your content (transiently).</strong> The videos you provide, their audio/transcripts, and the metadata we generate. Source videos are processed to create your post and then <strong>deleted</strong>; we do not keep a library of your videos.</li>
        <li><strong>Usage events (telemetry).</strong> Lightweight, non-content events such as “app opened”, “draft generated” and “video published”, with timestamps and counts, so we can improve the product. These contain no video content, titles, descriptions, transcripts, or keys.</li>
      </ul>

      <h2>2. How your keys &amp; tokens are protected</h2>
      <p>Your API keys and YouTube tokens are <strong>encrypted at rest</strong> (AES via Fernet) with a key held only by our backend — never exposed to your browser, and shown to you only in masked form. We never sell them, never use them for anything other than the features you invoke, and you can delete them at any time from your account.</p>

      <h2>3. Google user data &amp; the YouTube API</h2>
      <p>The Service uses <strong>YouTube API Services</strong>. By using these features you also agree to the <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer">YouTube Terms of Service</a> and the <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">Google Privacy Policy</a>. We request the <code>youtube.force-ssl</code> scope solely to, on channels you connect: upload the videos you choose; set their title, description, tags, category and thumbnail; set privacy/scheduled-publish time; and optionally post a pinned comment you’ve written. Your token is stored encrypted; revoke access anytime at <a href="https://myaccount.google.com/permissions" target="_blank" rel="noreferrer">Google Account permissions</a>.</p>

      <div className="callout">
        <strong>Limited Use disclosure.</strong> youtube_manager.ai’s use and transfer of information received from Google APIs to any other app adheres to the <a href="https://developers.google.com/terms/api-services-user-data-policy#additional_requirements_for_specific_api_scopes" target="_blank" rel="noreferrer">Google API Services User Data Policy</a>, including the <strong>Limited Use</strong> requirements. We do not transfer or sell Google user data for advertising or similar purposes, do not use it for ads, and no humans read it except with your explicit permission, to comply with law, or for security.
      </div>

      <h2>4. How we use information</h2>
      <ul>
        <li>To authenticate you and keep your account secure.</li>
        <li>To provide the Service’s features — generating metadata and publishing to YouTube on our servers, using the keys and channels you provide.</li>
        <li>To understand aggregate usage and improve the product.</li>
        <li>To respond to your support requests.</li>
      </ul>
      <p>We do <strong>not</strong> use your content or Google user data to train models, and we do not sell any data.</p>

      <h2>5. Sharing &amp; subprocessors</h2>
      <ul>
        <li><strong>Google:</strong> Sign-In and the YouTube Data API.</li>
        <li><strong>Supabase:</strong> authentication and encrypted storage of your account, keys/tokens and usage events.</li>
        <li><strong>Our cloud hosting provider,</strong> which runs the Service.</li>
        <li><strong>The AI &amp; transcription providers used to process your request,</strong> under their terms.</li>
      </ul>

      <h2>6. Retention &amp; deletion</h2>
      <p>Your keys and tokens are kept (encrypted) until you delete them or close your account. Source videos are <strong>deleted after processing</strong> and not retained. Disconnecting a channel removes its token; email us to delete your account and its data. You can revoke YouTube access anytime via Google Account permissions.</p>

      <h2>7. Security</h2>
      <p>Secrets are encrypted at rest (Fernet) and data in transit is encrypted with TLS. Access is least-privilege, secrets are never shipped to the browser, and source media is removed after processing.</p>

      <h2>8. Children</h2>
      <p>The App is not directed to children under 13 (or your country’s minimum age of digital consent).</p>

      <h2>9. Contact</h2>
      <p>Questions? Email <a href="mailto:support@youtube-manager.ai">support@youtube-manager.ai</a>.</p>
    </>
  )
}

function Terms() {
  return (
    <>
      <h1>Terms of Service</h1>
      <p className="updated">Last updated: 19 July 2026</p>
      <p>These Terms govern your use of <strong>youtube_manager.ai</strong> (the “App”). By using the App you agree to these Terms.</p>

      <h2>1. What the App does</h2>
      <p>The App is a hosted web service that helps you generate SEO metadata for your videos and upload them to YouTube channels you own and connect. You provide your own AI API keys and authorize your own YouTube channels.</p>

      <h2>2. Your responsibilities</h2>
      <ul>
        <li>You must own or have rights to the videos, thumbnails and content you upload.</li>
        <li>You are responsible for complying with the <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer">YouTube Terms</a>, the <a href="https://developers.google.com/youtube/terms/api-services-terms-of-service" target="_blank" rel="noreferrer">YouTube API Services Terms</a>, and all applicable laws for the content you publish.</li>
        <li>You are responsible for keeping your credentials and API keys secure, and for any costs with the AI providers whose keys you supply.</li>
        <li>You agree not to use the App to publish spam, infringing, or policy-violating content, or to abuse the YouTube API.</li>
      </ul>

      <h2>3. Third-party services</h2>
      <p>The App works with Google/YouTube and the AI providers you configure. Your use of those services is governed by their own terms. We are not responsible for third-party services.</p>

      <h2>4. Your content</h2>
      <p>You retain all rights to your content. The App does not claim ownership of anything you create or upload, and does not retain your source videos after processing.</p>

      <h2>5. No warranty</h2>
      <p>The App is provided “as is”, without warranties of any kind. We do not guarantee any particular result, ranking, or performance, or that the service will be uninterrupted or error-free.</p>

      <h2>6. Limitation of liability</h2>
      <p>To the maximum extent permitted by law, youtube_manager.ai will not be liable for any indirect, incidental, special or consequential damages, or loss of data, revenue or profits, arising from your use of the App.</p>

      <h2>7. Termination</h2>
      <p>You may stop using the App and delete your local data and account at any time. We may suspend access if these Terms are violated or to protect the service.</p>

      <h2>8. Contact</h2>
      <p>Questions? Email <a href="mailto:support@youtube-manager.ai">support@youtube-manager.ai</a>.</p>
    </>
  )
}
