# Privacy Policy

**Last updated:** 2026-03-26

This privacy policy describes how the ACA Newsletter Aggregator mobile application ("the App") collects, uses, and protects your information.

## Information We Collect

### Account Authentication

The App requires authentication to access your personal newsletter digest content. Your session is managed via secure HTTP-only cookies. We do not store passwords on your device.

### Device Tokens (Push Notifications)

When you enable push notifications, your device generates a unique push token. This token is:

- Sent to our server solely for delivering push notifications about new digests
- Stored on our server associated with your account
- Not shared with third parties beyond Apple Push Notification Service (APNs)
- Deleted from our server when you disable notifications or delete your account

You can disable push notifications at any time through your device Settings.

### Speech Data

The App supports speech-to-text input for search functionality via your device's built-in speech recognition. Speech processing occurs:

- **On-device** using iOS Speech Recognition framework
- Audio data is processed locally and is **not** sent to our servers
- We do not record, store, or transmit any audio data
- Apple may process speech data according to their own privacy policy when on-device recognition is unavailable

### Shared URLs

When you share a URL to the App (via the iOS Share Sheet), the URL is:

- Sent to our server for content extraction and ingestion into your newsletter feed
- Processed to extract article text, metadata, and images
- Stored as part of your content library
- Not shared with other users or third parties

### Content Data

The App syncs newsletter digest content from our server, including:

- Article summaries and full text
- Article metadata (titles, authors, publication dates, source URLs)
- Generated digest content (daily/weekly summaries)
- Podcast audio files (streamed, not permanently stored on device)

### Device Information

We collect minimal device information required for app functionality:

- Device type and iOS version (for compatibility)
- App version (for update notifications)
- Timezone (for digest scheduling)

We do **not** collect device identifiers (IDFA/IDFV) for advertising or tracking purposes.

## How We Use Your Information

Your information is used exclusively to:

1. Authenticate your access to the App
2. Deliver push notifications you have opted into
3. Process URLs you share with the App
4. Sync your personalized newsletter digest content
5. Improve app stability and performance

## Data Storage and Security

- All network communication uses HTTPS/TLS encryption
- Authentication tokens are stored in iOS Keychain (encrypted at rest)
- Server-side data is stored in encrypted databases
- We follow industry-standard security practices

## Third-Party Services

The App communicates with:

- **Our API server** for content delivery and authentication
- **Apple Push Notification Service (APNs)** for push notifications
- **Apple Speech Recognition** for on-device voice input (when used)

We do not integrate third-party analytics, advertising, or tracking SDKs in the mobile app.

## Data Retention

- Account data is retained while your account is active
- Push notification tokens are deleted when notifications are disabled or your account is deleted
- Shared URL content is retained as part of your content library until you delete it
- You may request deletion of all your data by contacting us

## Children's Privacy

The App is not directed at children under 13. We do not knowingly collect personal information from children.

## Your Rights

You have the right to:

- Access your personal data
- Request deletion of your data
- Disable push notifications at any time
- Opt out of speech recognition features
- Export your content data

## Changes to This Policy

We may update this privacy policy from time to time. Changes will be noted by updating the "Last updated" date above. Continued use of the App after changes constitutes acceptance.

## Contact

For privacy questions or data requests, please open an issue on the project repository or contact the project maintainer.
