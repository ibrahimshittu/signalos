# SignalOS mobile

An Expo SDK 57 investment studio with Supabase email authentication, connected Bybit portfolios,
market reviews, and explicitly confirmed order actions. The interface uses native navigation,
system typography, a restrained blue palette, and shared accessible controls.

The app uses real services, not simulated balances or a mock authentication fallback. Agents
cannot submit trades on your behalf. Read the [root run guide](../README.md) for backend, worker,
Supabase, environment, and signing setup before opening the app.

## Run locally

Requirements: Node.js 22.13+ and a native development environment. For iOS, use Xcode 26.4+ as
specified by [Expo SDK 57](https://docs.expo.dev/versions/v57.0.0/).

```bash
npm ci
test -f .env || cp .env.example .env
```

Fill the three public values in `.env`, start the API on port 8001, then install the native
development build in the iOS simulator:

```bash
npm run ios
```

For iOS, start Metro with the app-specific launch scheme:

```bash
npm run start:ios
```

If Metro is already running, stop it before starting another instance. The launcher targets
`com.signalos.app`. Rebuild the native app after changing native dependencies or identifiers.

`npm ci` automatically applies the pinned ExpoModulesJSI compatibility patch in `patches/`.
It avoids an Xcode 26.2 Swift overload ambiguity in Expo SDK 57 and can be removed after the
corresponding upstream package release is adopted. This legacy workaround does not change the
SDK's supported Xcode requirement.

This project uses Expo SDK 57. During the SDK 57 transition, the physical-device path is an Expo development build rather than Expo Go. See the [official Expo setup guide](https://docs.expo.dev/get-started/set-up-your-environment/).

Web remains useful for quick layout checks:

```bash
npm run web
```

## Verify

### Launch artwork and onboarding background

The iOS launch screen uses `assets/images/signalos-launch-lockup.png`, rendered from the existing
brand SVG. Android retains the centered icon to fit its system splash mask. The welcome screen
uses the bundled `assets/images/studio-architecture.png`; shared main screens reuse it at low
opacity so portfolio data stays legible. No image is downloaded at runtime.

The background was created with the built-in image-generation tool using this art direction:
“Portrait architectural editorial photograph: pale limestone and frosted glass, a deep ink-blue
recessed curved wall, soft daylight, quiet negative space; no text, logos, charts, money, or neon.”

Splash changes require a native rebuild. From `mobile/`, run `npx expo run:ios --device`.
For generated native projects, apply configuration changes with `npx expo prebuild --platform ios
--no-install` first and review the native diff; do not use `--clean` over local native edits.
Verify the actual launch appearance in a release build: Expo's development launcher can display
its own startup UI. See [Expo splash guidance](https://docs.expo.dev/versions/v57.0.0/sdk/splash-screen/).

### Checks

```bash
npm test
npm run lint
npm run typecheck
npx expo export --platform web
```

## Architecture

- `src/app`: Expo Router onboarding, tabs, account, and modal routes.
- `src/domain`: typed API contracts, display mappings, and portfolio-history helpers.
- `src/services`: authenticated HTTP APIs, Supabase authentication, and Expo push registration.
- `src/query`: TanStack Query is the only data-access path used by screens.
- `src/store`: identity-scoped UI state and local equity history; never authentication tokens.
- `src/components`: token-driven UI, bespoke SVG charts, and SignalOS-specific rows.

SignalOS always uses the live FastAPI service; production screens have no mock-data fallback. Set
`EXPO_PUBLIC_SIGNALOS_API_URL` to the FastAPI host and configure the Supabase public client values. On a
physical iPhone, use your Mac's LAN address rather than `127.0.0.1`, for example:

```sh
EXPO_PUBLIC_SIGNALOS_API_URL=http://192.168.1.20:8001 npm start
```

## Proposal notifications

1. Link the **SignalOS** EAS project and put its real UUID in `expo.extra.eas.projectId` in
   `app.json`. Do not reuse another application's project or a placeholder UUID.
2. Configure the project's APNs credentials (and FCM v1 credentials for Android) using the
   [Expo push setup guide](https://docs.expo.dev/push-notifications/push-notifications-setup/).
3. Apply the notifications config plugin to the native project, preserving any native edits,
   and rebuild the development client. A JavaScript reload cannot add a native module or push
   entitlements. Review the generated native diff before building a physical device.
4. In Account → Notifications, choose **Enable on this device**. Registration is opt-in; the app
   never requests notification permission on launch. Foreground/token-change events refresh an
   existing registration. Tapping a proposal opens an authenticated detail route, never a trade.
5. Run the backend notification worker with the same database/project configuration. Verify a
   real device receives a notification; a server ticket or bundle export is not delivery evidence.

Sign-out first revokes this installation's backend registration. If revocation fails, sign-out
reports an error and can be retried; it does not silently leave a known push registration active.
An expired/revoked auth session can still leave a registration on the server. Notification bodies
contain no market, position, balance, or user identifiers, and details always require authorization.

The currently unlinked build shows setup status rather than claiming notifications are enabled.

## Dependency security checkpoint — 5 September 2026

The three Metro overrides pin `0.84.5`, the version used by `@expo/metro@56.0.2`. Without them,
React Native's transitive dependency graph retained older Metro copies using the vulnerable
`image-size` parsers. Recheck/remove the overrides when the SDK resolves the patched versions
without them. iOS export, Jest, TypeScript, and lint pass with these pins.

The npm audit after remediation reports **0 critical, 0 high, 14 moderate**. These are primarily
two advisory chains: `decode-uri-component` through Router's `query-string`, and `uuid` through
Xcode/Expo tooling. The latter inspected call site uses `uuid.v4()`, not the advisory's affected
buffer-taking v3/v5/v6 calls. Malformed deep-link query decoding still needs a compatible upstream
fix and review before release. Revisit by **12 September 2026**. Do not use `npm audit fix --force`:
its proposed Expo/Router downgrades cross SDK generations.
