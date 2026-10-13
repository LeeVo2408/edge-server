## Naming conventions

### Files

- `UpperCamelCase.swift`, matching the primary type the file declares —
  `SpeedDialView.swift` declares `SpeedDialView`.
- No underscores, no lowercase runs.

| Wrong | Correct |
|---|---|
| `Altdialview.swift` | `AltitudeDialView.swift` |
| `Leftforearmview.swift` | `LeftForearmView.swift` |

- A file holding several small related types is named for the group — plural or
  by role: `SupportPanels.swift`, `TileOverlays.swift`. Keep these under the
  file-length limit.
- Test files mirror the type under test with a `Tests` suffix:
  `MissionExecutorTests.swift`.

### Folders

- The app folder is `apps/avp-vroc/vROC_dev`; the project and test target
  share the name.
- Every folder inside it is `PascalCase`: `Views`, `Models`, `Services`,
  `Networking`, `Resources`.
- Top-level monorepo paths are lowercase kebab-case.
- No spaces in any path segment.

### Types

- `UpperCamelCase`. Protocols read as capabilities (`-able`, `-ing`) or nouns.
- Views end in `View`. Cockpit panels end in `PanelView`.
- Services end in `Service` when they are broadly stateless and do work, or
  `Manager` when they own their lifecycle and state. Never both for the same type.

### Properties and functions

- `lowerCamelCase`. Functions are verbs (`moveDroneCoordinate`); properties are
  nouns (`batteryPercent`, `expandedPanels`).
- Booleans read as assertions.

| Wrong | Correct |
|---|---|
| `enteringOps` | `hasEnteredOperation` |
| `emergencyLanding` | `emergencyLandingConfirmed` |

- Spell out units in the name. Ambiguous units are dangerous.

| Wrong | Correct |
|---|---|
| `speedMS` | `speedMetresPerSecond` |
| `alt` | `altitudeMetres` |
| `hdg` | `headingDegrees` |
| `battery` | `batteryPercent` or `batteryFraction` |

- Keep functions modular: one task per function. A function should not absorb
  work that belongs to another.
- No abbreviations except those well understood in context: `gps`, `mqtt`,
  `url`, `id`.
- Avoid single-letter names outside a tight scope (loop indices, coordinate math).

### Constants

Declared with `static let` inside a namespace-scoped `enum`:

```swift
// MQTT broker connection details (for use with simulated telemetry)
enum BridgeConfig {
    static let host    = "localhost"  // set to the bridge machine's IP for live telemetry
    static let port    = 1883         // MQTT broker
    static let apiPort = 3000         // HTTP API sim

    static var apiBase: URL {
        URL(string: "http://\(host):\(apiPort)")!
    }
}
```

## Commenting

Comments explain **why**, not **what**. The code should be self-explanatory.

Good — each comment carries information the signature cannot:

```swift
// Class name is in the key because the memory cache is shared between all
// overlay types and tile paths collide across providers
private func cacheKey(_ p: MKTileOverlayPath) -> String

// Stored here because @Observable requires properties in the primary type
var activeWarnings: Set<WarningKind> = []
```

Bad — the comment restates the declaration:

```swift
// toggle a panel: collapse if already open
func toggle(_ panel: PanelID)

// battery
var batteryPercent: Double
```