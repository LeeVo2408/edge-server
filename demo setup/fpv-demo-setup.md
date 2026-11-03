# FPV Live-Feed Demo Setup

How to demonstrate the vROC live feed without the DJI dock: a laptop webcam stands in for the
drone camera, and the video travels through the real edge server to the Apple Vision Pro over
WebRTC. The three devices sit on different networks and are joined with Tailscale.

## Why this demo is representative

The webcam publishes to the same MediaMTX path, `/live`, that the edge server's ESDK relay
(`rtsp_streamer.cc`) publishes to when a drone is connected. Everything downstream of that point is
the production path: MediaMTX on the edge server, the network, and the WebRTC player in the vROC
live-feed panel. On the real dock, only the source changes.

## Architecture

```text
[Webcam laptop]                  [Edge server VM: stev-edgeserver]      [Apple Vision Pro]
 phone hotspot                    home / lab network                     UTS Wi-Fi
 ffmpeg ── RTSP push ──────────▶ MediaMTX  :8554/live
                                    │  WHEP signalling   :8889
                                    │  WebRTC media      :8189 (UDP, TCP fallback)
                                    └──────────── WebRTC video ───────────▶ vROC live-feed panel
        ◀────────────── all three joined over Tailscale (100.x addresses) ──────────────▶
```

| Device | Role | Network |
|---|---|---|
| Windows laptop | Webcam source (stands in for the drone camera) | Phone hotspot |
| Edge server VM (`stev-edgeserver`, VMware Fusion on the Mac) | Relays the stream with MediaMTX | Home or lab network |
| Apple Vision Pro (or the visionOS simulator on the Mac) | Plays the feed in vROC | UTS Wi-Fi |

| Address | Used by |
|---|---|
| `rtsp://stev-edgeserver:8554/live` | Webcam laptop (publish), VLC (test playback) |
| `http://stev-edgeserver:8889/live` | Browser test page (MediaMTX built-in WebRTC viewer) |
| `http://stev-edgeserver:8889/live/whep` | vROC app (WebRTC/WHEP) |

## Prerequisites

- Every device is signed in to the same tailnet. Exit nodes are turned off on all of them.
- Edge server repo is cloned on the VM and the image builds (`docker compose up -d --build`).
- vROC repo is on the `webrtc` branch (PR #23) on the Mac: `git fetch origin && git switch webrtc`.
- ffmpeg is installed on the webcam laptop: `winget install Gyan.FFmpeg`.
- The Tailscale app is installed and connected on the Vision Pro. If it is not available, use the
  visionOS simulator on a Mac running Tailscale.

## Files

| File | Where it goes | What it does |
|---|---|---|
| `setup-edge-demo.sh` | Edge server repo root, on the VM | Joins Tailscale, writes the MediaMTX WebRTC settings, restarts the container, checks ports |
| `start-webcam.ps1` | Webcam laptop | Picks a camera, pings the edge server, pushes the webcam to `/live` |
| `LiveFeedPanelView.swift` | `apps/avp-vroc/vROC_dev/Views/NewCockpit/` | Points the WHEP endpoint at the edge server over Tailscale |

## Step 1: Edge server VM

1. Copy `setup-edge-demo.sh` to the root of the edge server repo on the VM.
2. Run it:

   ```sh
   bash setup-edge-demo.sh
   ```

3. Note the Tailscale IP it prints. Check that ports 8554, 8889 and 8189 all show `OK`.

The script adds these lines to `infrastructure/.env`. Without them, MediaMTX advertises the VM's
LAN IP, which the headset cannot reach from another network, and the panel stays black.

```sh
MTX_WEBRTCADDITIONALHOSTS=<edge Tailscale IP>
MTX_WEBRTCLOCALTCPADDRESS=:8189
MTX_PATHS_LIVE_SOURCE=publisher
```

The second line lets WebRTC fall back to TCP when UDP is blocked, which is common on university
Wi-Fi. The third defines the `live` path: the image ships the MediaMTX binary without its default
`mediamtx.yml`, so no paths exist until one is defined, and publishing fails with
`path 'live' is not configured`. The real DJI relay publishes to the same path, so this setting
belongs in `infrastructure/.env.example` as well.

## Step 2: Webcam laptop

1. Connect the laptop to a phone hotspot so it is on a genuinely different network.
2. Confirm Tailscale is connected. `tailscale ping stev-edgeserver` should succeed.
3. Start the stream:

   ```powershell
   .\start-webcam.ps1
   ```

   If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope Process Bypass` first. If the
   MagicDNS name does not resolve, pass the IP: `.\start-webcam.ps1 -Edge 100.x.y.z`.

4. **Checkpoint:** open `http://<edge Tailscale IP>:8889/live` in a browser on the laptop. If the
   webcam appears, the source, the edge server and Tailscale are all working, and any later fault
   is in the app.

The script encodes H.264 with the baseline profile, no B-frames and a keyframe every second.
WebRTC needs the first two, and the third keeps start-up and latency low. Audio is dropped with
`-an` because the vROC panel is video-only (see Known limitations).

Equivalent manual command:

```powershell
ffmpeg -f dshow -rtbufsize 100M -i video="<camera name>" -vf "scale=1280:-2,fps=30" -an `
  -c:v libx264 -preset ultrafast -tune zerolatency -profile:v baseline -bf 0 -pix_fmt yuv420p -g 30 `
  -b:v 2500k -f rtsp -rtsp_transport tcp rtsp://stev-edgeserver:8554/live
```

List camera names with `ffmpeg -list_devices true -f dshow -i dummy`.

## Step 3: vROC app

1. On the `webrtc` branch, replace
   `apps/avp-vroc/vROC_dev/Views/NewCockpit/LiveFeedPanelView.swift` with the demo copy. The only
   change is the endpoint:

   ```swift
   private let webRTCEndpoint = "http://stev-edgeserver:8889/live/whep"
   ```

   If the name does not resolve on the headset, use the edge server's `100.x` IP instead.

2. Test in the visionOS simulator first, with Tailscale running on the Mac: `./scripts/run-app.sh`.
3. Make sure the webcam stream is already running, then open the live-feed panel. The status
   should change from `Connecting` to `Connected` and the video should appear.
4. Build to the Vision Pro with Tailscale connected on the headset and repeat.

## Demo script (about 3 minutes)

1. **Three networks.** Show the Tailscale admin console with the laptop, the edge server and the
   Vision Pro, each on a different network.
2. **Go live.** Mirror the Vision Pro to the projector with AirPlay. Start the webcam stream, open
   the live-feed panel, and wave at the camera.
3. **Show latency.** Hold a phone stopwatch up to the webcam next to the projected feed so the
   audience can read the delay. The FPV target is under 1 second end to end.
4. **Show recovery.** Stop the webcam stream, then restart it and reopen the panel. The client does
   not reconnect automatically yet, so the panel has to be reopened.
5. **Show the source is interchangeable.** Push a recorded drone clip to the same path:

   ```powershell
   ffmpeg -re -stream_loop -1 -i drone_test.mp4 -an -c:v libx264 -preset ultrafast -tune zerolatency `
     -profile:v baseline -bf 0 -pix_fmt yuv420p -g 30 -f rtsp -rtsp_transport tcp rtsp://stev-edgeserver:8554/live
   ```

   Explain that on the real dock, the DJI Edge SDK publishes to this same path and nothing
   downstream changes.

For two-way audio, run the RoIP demo alongside: the Mumble desktop client on the laptop joins the
Murmur server over Tailscale, the headset hears the laptop mic, and push-to-talk on the headset
plays through the laptop speakers.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Browser test page shows nothing | Webcam not reaching the edge server | Check `start-webcam.ps1` output; `tailscale ping stev-edgeserver`; confirm port 8554 is `OK` on the VM |
| Browser works, headset panel stays black | MediaMTX advertising the LAN IP | On the VM, `grep MTX_ infrastructure/.env` should show the Tailscale IP; rerun the setup script |
| Panel shows an error immediately | Stream not running when the panel opened | Start the webcam first, then reopen the panel |
| Panel says `Connected` but no picture | `Connected` reports the peer connection, not frames | Check the browser test page; confirm the encoder settings (baseline, `-bf 0`) |
| Name `stev-edgeserver` does not resolve | MagicDNS off or not available on that device | Use the `100.x` IP in the script and the Swift endpoint |
| Feed is laggy or stutters | Traffic relayed through Tailscale DERP servers | `tailscale ping stev-edgeserver` should say `direct`; try a phone hotspot instead of uni Wi-Fi |
| `path 'live' is not configured` | MediaMTX has no paths defined | Add `MTX_PATHS_LIVE_SOURCE=publisher` to `infrastructure/.env` and recreate the container |
| Mac/laptop `tailscale ping` times out; edge shows `offline` | Tailscale service on the VM stuck after login | On the VM: `sudo systemctl restart tailscaled`, wait a minute, ping again |
| `publisher already exists` on push | Another source is publishing to `/live` | Stop the other ffmpeg; do not run the dock relay and the webcam together |

## Known limitations

- **Video only.** The vROC WebRTC client opens a receive-only video channel. Adding audio needs an
  audio transceiver in `WebRTCStreamClient.swift` and Opus audio from the source; WebRTC does not
  carry AAC.
- **No automatic reconnect.** If the stream drops, the panel must be reopened.
- **Fixed endpoint.** The panel uses a hard-coded WHEP URL and ignores `stream_status` over MQTT.
- **No authentication.** MediaMTX and Mosquitto accept anonymous connections on the tailnet. Broker
  authentication is on the edge server's next-steps list.
- **Branch is behind `dev`.** `webrtc` is 39 commits behind `dev`, so the demo build lacks the newer
  HUD and alert work until PR #23 is updated and merged.
- **Not yet verified end to end.** PR #23 notes that full WebRTC playback had not been tested on
  hardware; this demo is that test.

## Before the demo

- [ ] Full dry run across the three networks, the day before.
- [ ] Screen-record a successful run as a backup video.
- [ ] Phone hotspot charged and tested with Tailscale (`direct`, not `via DERP`).
- [ ] AirPlay mirroring to the venue projector tested.
- [ ] Phone stopwatch ready for the latency shot.