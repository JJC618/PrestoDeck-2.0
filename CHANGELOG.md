# Changelog

### 1.2.4

- Reset paged playlist and speaker menus to page one whenever they are opened.
- Reset the Presto event loop on launch so repeated editor runs or soft reboots cannot leave duplicate playback refresh tasks active.
- Treated an empty but recent Spotify playback state as a valid bridge cache result, preventing idle-state request bursts from reaching Spotify.
- Added bridge health counters for actual Spotify playback-state fetches, making API activity easier to verify independently of Presto-to-bridge requests.

### 1.2.3

- Prevented player redraws from consuming a pending menu redraw, fixing occasional partial playlist, speaker, search, or queue screens.

### 1.2.2

- Added SD-card usage counters that place the most frequently selected playlists and speakers first without additional Spotify API calls.
- Added SD-card-backed autocomplete suggestions from up to 500 recent searches, which can be tapped to complete the current search text without making an API call.

### 1.1.2

- Added setup support for choosing the Raspberry Pi album-art cache size.
- Added automatic Pillow installation for bridge album-art overlay processing.
- Added a fullscreen album-art top overlay that is baked into cached 480px artwork for better progress-bar readability.
- Added human-triggered fresh playback refreshes after selecting a playlist or playing a selected search result.
- Kept the queue screen view-only so selecting a displayed queue item cannot replace Spotify's active queue.

### 1.0.2

- Reduced playback `/state` bursts after track changes by shortening retry windows and using a longer bridge cache for routine state checks.
- Added a manual Raspberry Pi album-art cache clear endpoint.

### 1.0.1

- Added a single estimated track-end `/state` refresh 3 seconds after the current track should naturally finish, with pause/resume handling.

### 1.0.0

- First stable public release after soak testing confirmed controlled idle Spotify API usage.
- Promoted the Presto app and Raspberry Pi bridge to matching `1.0.0` versions.
- Added a human-triggered `/state` refresh when exiting fullscreen album art so the player view catches up promptly without increasing idle polling.

### 0.3.13

- Treated successful non-JSON Spotify command responses as empty success so shuffle/repeat do not roll back after Spotify accepts the command.

### 0.3.12

- Updated the bridge playback cache immediately after shuffle and repeat commands so the Presto does not redraw stale button states.

### 0.3.11

- Treated blank Spotify command responses as successful empty JSON so controls do not mark the bridge unavailable.

### 0.3.10

- Updated shuffle and repeat icons immediately when pressed, with rollback if Spotify rejects the command.

### 0.3.9

- Updated playlist additions to Spotify's current `/playlists/{playlist_id}/items` endpoint, generated Spotify scopes with spaces, and kept playlist-add errors generic unless Spotify reports a permission issue.

### 0.3.8

- Show a clearer message when Spotify rejects a playlist add as permission denied.

### 0.3.7

- Kept the bridge marked available after Spotify returns a command-specific client error, and handled empty successful command responses cleanly.

### 0.3.6

- Reduced normal bridge health checks to quiet the Raspberry Pi logs while keeping faster checks during blocked or failed bridge states.

### 0.3.5

- Restored the cached `250x250` player artwork from the bridge when exiting fullscreen album-art mode.

### 0.3.4

- Pulled fullscreen album art from the bridge once when the idle fullscreen view opens, then reused it in memory for the active track.

### 0.3.3

- Limited automatic recently-played fallback calls after Spotify returns no active track.

### 0.3.2

- Preloaded matching `480x480` album art on the bridge when the player requests `250x250` art for a new track.

### 0.3.1

- Prevented the player screen from showing `Loading Spotify...` after the bridge fails.

### 0.3.0

- Made the Raspberry Pi bridge compulsory for all Spotify API communication.
- Removed the Presto-side local Spotify API client and the old optional bridge setting.
- Added `spotify_url.py` for the small URL-encoding helpers still needed by bridge requests.
- Renamed the missing bridge URL boot error to `(bridge url missing)`.
- Kept stopped or unreachable bridge services under `(bridge unavailable)`.
- Improved startup handling for rejected Pi-side Spotify credentials.
- Hardened album-art requests so old clients cannot trigger playback-state lookups.
- Updated the release test script to match the new bridge-only file layout.

### 0.2.12

- Show a clearer bridge unavailable boot error when the Raspberry Pi service cannot be reached.

### 0.2.11

- Show bridge failure instead of a stale API-block countdown when the bridge health check fails.

### 0.2.10

- Removed Presto-side Spotify fallback calls.
- Kept album-art fetching bridge-only so Spotify traffic is logged from one place.

### 0.2.9

- Reduced idle Spotify API usage by polling playback every 60 seconds.
- Stopped automatic queue preloading from normal playback state refreshes.

### 0.2.8

- Limited album-art network fetching to one request per track and reused local cached art for fullscreen redraws.

### 0.2.7

- Reduced Spotify API calls by letting album-art requests use the already-known track image instead of refreshing playback state.

### 0.2.6

- Fixed speaker paging so all detected devices are available across pages.
- Centred page counters between the navigation arrows.

### 0.2.5

- Made the search keyboard respond on press-down for faster typing.

### 0.2.4

- Added Spotify API blocked messages to search results and speaker selection screens.
- Improved blocked-message readability on the Presto.

### 0.2.3

- Added boot checks for SD card mount failures and missing SD card icons.
- Added troubleshooting guidance for red boot error messages.

### 0.2.2

- Centred player visuals, including album art, placeholder icon, and play/pause control positioning.

### 0.2.1

- Improved startup and blocked-message text centring.
- Hid the loading message on the player screen when Spotify is API-blocked.

### 0.2.0

- Added startup diagnostics, bridge health details, and visible Spotify API blocked states.
- Added version reporting for the Presto app and Raspberry Pi bridge.

### 0.1.0

- Added playlist and speaker paging controls.
