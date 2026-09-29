# Android helper checkpoint

Updated: 2026-09-30. Owner: `android_validate` subagent during the current root
turn; recheck live agents before assigning follow-up work.

## Source implementation

- API-28-compatible bounded response reading reuses `TransportIO.kt`; native
  JSON responses are limited to 65,536 bytes. Header reading stops exactly at
  CRLF CRLF, preserving the following TLS bytes.
- Starting an attempt reserves process-wide ownership before network dispatch.
  Ownership stays reserved until the asynchronous WebView proxy cleanup finishes.
  Old activity/network/expiry callbacks carry the original attempt and cannot
  change a later attempt. Manifest uses `singleTask` for pairing deep links.
- Native router HTTP disables redirects, pins the router leaf certificate,
  uses 10-second connect / 15-second read timeouts, and tracks pending requests
  for closure. Relay sockets are tracked before connecting and use an explicit
  connect timeout. A scheduled expiry closes active relays and pending requests;
  challenge lifetimes follow the core's 600-second maximum.
- WebView uses only the loopback proxy; implicit localhost/link-local proxy
  bypass rules are removed. The relay accepts only a VK/OK HTTPS CONNECT
  authority on port 443, then adds authentication inside pinned router TLS.
  VK certificate errors are cancelled. Completion, cancellation, expiry and
  activity destruction destroy the WebView and close the session.
- Tokens use the shared 16,384-byte UTF-8 limit and reject control characters
  and blank values. Pairing objects have a redacted string representation;
  link input is excluded from Android view state saving. No credentials,
  tokens, redirect URLs or certificates are printed in failure handling.

## Checks and limitations

- Source checkpoint `18baa7d` is published. Android job in
  [PR CI run 36637150431](https://github.com/RATOR2000/csqtt-openwrt/actions/runs/36637150431)
  **passed** `./gradlew testDebugUnitTest lintDebug assembleDebug --no-daemon`:
  Kotlin compilation, all 13 JVM unit tests, lint and debug APK assembly.
  Reviewed the exact broker/core schemas at that checkpoint: claim consumes a
  pairing grant and returns `id`, `redirect_uri`, `session`, `expires_at`; the
  helper sends `id`/`token` for results and uses the session for result, cancel
  and CONNECT authentication. The core's private `session_token` stays on the
  router. Expiry is Unix seconds in all components, converted to milliseconds
  only for Android timers; the core accepts 30–600-second configured lifetimes.
- Compared WebView navigation/bridge/CONNECT allowlists against the broker and
  original v2.1.9 `CaptchaUriPolicy`: all use VK/OK roots `vk.com`, `vk.ru`,
  `ok.ru`, `okcdn.ru` and their subdomains. Helper/broker restrict HTTPS to port
  443 and reject URL user information. The JS interceptor reads the original
  `captchaNotRobot.check` response's `response.success_token` field.
- Found and reported a broker request-body mismatch: a valid 16,384-byte token
  containing JSON quotes/backslashes can exceed its 32,768-byte body limit.
  Root's current broker source raises that limit to 65,536; broker validation
  is recorded by the root separately from this Android CI result.
  No further Android source change was required by this contract comparison.
- `git diff --check -- android-helper docs/ANDROID_STATUS.md` passed locally;
  Git emitted only line-ending normalization warnings. Targeted source search
  found no logging calls or remaining `readNBytes` invocation.
- Previous root CI snapshot `450df5`: Android Kotlin compilation and existing
  unit tests passed; lint failed on `InputStream.readNBytes` requiring API 33.
  The newer `18baa7d` Android CI pass validates these lifecycle changes and the
  API-28-compatible bounded read replacement at build/unit/lint level.
- Added JVM regression cases for concurrent attempt reservation and stale
  cleanup, UTF-8 token boundaries/controls, strict CONNECT authorities, malformed
  pairing links, response size limits, zero-length reads, truncated/oversized
  headers and preservation of TLS payload bytes. The complete 13-test JVM suite
  passed in the CI run above.
- Local environment inspection found Java 8 and no local Android SDK/JDK 21
  configured for the Gradle build. No Android build was attempted locally.
- No Android device/WebView runtime test, router connection, live VK challenge
  or end-to-end authenticated CAPTCHA relay test has been performed. Source
  review and JVM tests do not establish those acceptance results.

## Next concrete step

Keep the debug APK as build validation material. Device acceptance must cover
rotation/destruction during claim and proxy installation, duplicate Start,
submission racing expiry/cancel, unavailable router, router/VK certificate
failure, blocked non-VK requests and cleanup before a new pairing attempt.
