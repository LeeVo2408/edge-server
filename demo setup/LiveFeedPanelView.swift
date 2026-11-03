//
// LiveFeedPanelView.swift
//  AVP vROC
//
//  Created by Aston Walsh on 20/3/2026.
//

/**
 * @file:       LiveFeedPanelView.swift
 * @brief:      WebRTC integration changes to the existing live-feed panel.
 * @changed by:     Nima Nadali Jelokhani
 * @date:       2026-10-3
 */

import SwiftUI
/**
 * @brief   Provides URL support for the WebRTC connection.
 * @details AVKit and AVFoundation are no longer needed in this panel.
 */
import Foundation

extension Color {
    static let hudBackground = Color(red: 0.0, green: 0.0, blue: 0.0)
}

struct LiveFeedPanelView: View {
    @Environment(AppModel.self) private var appModel

    // Recording is active while the drone is actively flying a path
    private var isRecording: Bool {
        let p = appModel.dronePhase
        return p == "flying_to" || p == "yawing_to" || p == "manual_move"
    }
    
    /**
     * @brief   Owns the observable WebRTC receiver for this panel.
     * @details Replaces loadedStreamURL, AVPlayer, AVPlayerLooper, makeRTSPPlayer(),
     *          and syncPlayer(). SwiftUI observes the receiver's track and status.
     */
    @StateObject private var webRTC = WebRTCStreamClient()

    /**
     * @brief   Defines the MediaMTX WHEP endpoint for this local integration test.
     * @details Uses the reachable address of the machine running MediaMTX and
     *          selects the live stream. This is not a browser-page or HLS URL.
     *          The fixed address bypasses appModel.liveStreamURL and does not
     *          change when appModel.activeCamera changes. Update it if the server
     *          address changes; dynamic source selection is not implemented here.
     */
    // FPV demo: edge VM over Tailscale (MagicDNS name). Use its 100.x IP if the name does not resolve.
    private let webRTCEndpoint = "http://stev-edgeserver:8889/live/whep"

    /**
     * @brief   Starts the receiver using the configured WHEP endpoint.
     * @details Constructs a URL and asks WebRTCStreamClient to begin asynchronous
     *          negotiation. Returns without connecting if URL construction fails.
     *          Constructing a URL does not verify server reachability or playback.
     *
     * @return  Void. Connection progress is published by the receiver.
     */
    private func startWebRTC() {
        guard let url = URL(string: webRTCEndpoint) else { return }
        webRTC.connect(to: url)
    }

   
    var body: some View {
        CockpitPanel(
            title: "LIVE FEED · \(appModel.activeCamera)",
            icon: "video.fill",
            panelID: .livefeed,
            expandedPanels: Binding(
                get: { appModel.expandedPanels },
                set: { appModel.expandedPanels = $0 }
            )
        ) {
            VStack(spacing: 16) {
                ZStack {
                    /**
                     * @brief   Displays the received WebRTC track instead of VideoPlayer.
                     * @details Requires WebRTCVideoView in the app target. Disables hit
                     *          testing on the video surface and retains the original grid.
                     *          The existing NoSignalView is used when no track is available.
                     */
                    if let track = webRTC.videoTrack {
                        WebRTCVideoView(track: track)
                            .allowsHitTesting(false)
                        Canvas { ctx, size in
                            let sp: CGFloat = 56
                            var p = Path()
                            var y: CGFloat = 0
                            while y <= size.height {
                                p.move(to: CGPoint(x: 0, y: y))
                                p.addLine(to: CGPoint(x: size.width, y: y))
                                y += sp
                            }
                            ctx.stroke(p, with: .color(.white.opacity(0.018)), lineWidth: 0.5)
                        }
                    } else {
                        NoSignalView()
                    }
                    /**
                     * @brief   Uses track availability to control the existing HUD crosshair.
                     * @details Replaces the AVPlayer existence check. A non-nil track does
                     *          not prove frames are arriving; HUD drawing code is unchanged.
                     */
                    LiveFeedHUD(showCrosshair: webRTC.videoTrack != nil)
                        .environment(appModel)
                }
                .frame(width: 1920, height: 1080)
                .frame(maxWidth: .infinity)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                /**
                 * @brief   Starts and stops the connection with the panel lifecycle.
                 * @details On appearance, starts WHEP negotiation. On disappearance,
                 *          disconnects the receiver and requests server-session cleanup.
                 *          Replaces the liveStreamURL observer and syncPlayer() calls.
                 */
                .onAppear { startWebRTC() }
                .onDisappear { webRTC.disconnect() }
                /**
                 * @brief   Shows the receiver's status at the bottom-left of the panel.
                 * @details Displays setup progress or errors for this integration test.
                 *          Connected describes peer state, not confirmed frame playback.
                 */
                .overlay(alignment: .bottomLeading) {
                    Text(webRTC.status)
                }
                
                if appModel.expandedPanels.contains(.livefeed) {
                    Divider()
                    VStack(alignment: .leading, spacing: 16) {
                        Text("CAMERA PAYLOAD")
                            .font(.system(.subheadline, design: .monospaced, weight: .semibold))
                            .foregroundStyle(.secondary)
                            .tracking(1)
                            .padding(.bottom, 25)
                        HStack(spacing: 10) {
                            ForEach(appModel.cameraOptions, id: \.self) { cam in
                                let active = appModel.activeCamera == cam
                                Button { appModel.activeCamera = cam } label: {
                                    VStack(spacing: 6) {
                                        Image(systemName: cameraIcon(cam))
                                            .font(.system(size: 22, weight: .semibold))
                                        Text(cam)
                                            .font(.system(.subheadline, design: .monospaced, weight: .bold))
                                    }
                                    .frame(maxWidth: .infinity)
                                    .frame(height: 72)
                                    .background(RoundedRectangle(cornerRadius: 12)
                                        .fill(active ? Color.accentColor.opacity(0.18) : Color.primary.opacity(0.06)))
                                    .overlay(RoundedRectangle(cornerRadius: 12)
                                        .strokeBorder(active ? Color.accentColor.opacity(0.7) : Color.primary.opacity(0.15), lineWidth: 1.5))
                                    .foregroundStyle(active ? Color.accentColor : .secondary)
                                }
                                .frame(maxWidth: .infinity)
                                .frame(height: 72)
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(.bottom, 40)
                    }
                    Divider()
                    VStack(spacing: 8) {
                        HStack(spacing: 20) {
                            DataRow(label: "SHUTTER",   value: appModel.shutterSpeed,                         valueSize: 26)
                            DataRow(label: "ISO",       value: "AUTO",                                         valueSize: 26)
                        }
                        HStack(spacing: 20) {
                            DataRow(label: "FORMAT",    value: "RAW+JPEG",                                     valueSize: 26)
                            DataRow(label: "SD CARD",   value: "\(appModel.sdPhotosRemaining)", unit: "remain", valueSize: 26)
                        }
                        HStack(spacing: 20) {
                            DataRow(label: "EV",        value: "±0",                                           valueSize: 26)
                            DataRow(label: "RECORDING",
                                    value: isRecording ? "ACTIVE" : "STOPPED",
                                    valueColor: isRecording ? .red : .secondary,
                                    valueSize: 26)
                        }
                    }
                }
            }
        }
    }

    private func cameraIcon(_ name: String) -> String {
        switch name.lowercased() {
        case let s where s.contains("ir"):      return "thermometer.medium"
        case let s where s.contains("thermal"): return "thermometer.medium"
        case let s where s.contains("zoom"):    return "plus.magnifyingglass"
        case let s where s.contains("fpv"):     return "eye.fill"
        default:                                return "camera.fill"
        }
    }
}

// MARK: - No Signal

private struct NoSignalView: View {
    var body: some View {
        ZStack {
            Color.black
            VStack(spacing: 18) {
                Image(systemName: "video.slash.fill")
                    .font(.system(size: 52, weight: .medium))
                    .foregroundStyle(Color.white.opacity(0.30))
                VStack(spacing: 8) {
                    Text("NO FOOTAGE AVAILABLE")
                        .font(.system(.title3, design: .monospaced, weight: .bold))
                        .foregroundStyle(.white.opacity(0.70))
                        .tracking(2.5)
                    /**
                     * @brief   Replaces the REST-start instruction with a waiting message.
                     * @details The WebRTC test connects from the panel's appearance handler;
                     *          it does not call the previous /livestream/start endpoint.
                     */
                    Text("Waiting for live video")
                        .font(.system(.subheadline, design: .monospaced))
                        .foregroundStyle(.white.opacity(0.28))
                        .tracking(0.8)
                }
            }
        }
    }
}

// MARK: - HUD

private struct LiveFeedHUD: View {
    @Environment(AppModel.self) private var appModel
    var showCrosshair: Bool = true

    private let tapeTopGuard:    CGFloat = 150
    private let tapeBottomGuard: CGFloat = 250
    private let tapeSideInset:   CGFloat = 14
    private let tapeW:           CGFloat = 68

    // Recording while actively flying
    private var isRecording: Bool {
        let p = appModel.dronePhase
        return p == "flying_to" || p == "yawing_to" || p == "manual_move"
    }

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let h = geo.size.height
            let tapeTop    = tapeTopGuard
            let tapeBottom = h - tapeBottomGuard
            let tapeH      = max(0, tapeBottom - tapeTop)
            let tapeCY     = tapeTop + tapeH / 2

            ZStack {
                HUDSpeedTape(speed: appModel.speedMS, target: appModel.targetSpeed)
                    .frame(width: tapeW, height: tapeH)
                    .position(x: tapeSideInset + tapeW / 2, y: tapeCY)

                HUDAltitudeTape(altitude: appModel.altitude, target: appModel.targetAltitude)
                    .frame(width: tapeW, height: tapeH)
                    .position(x: w - tapeSideInset - tapeW / 2, y: tapeCY)

                Text("SPD")
                    .font(.system(size: 13, weight: .bold, design: .monospaced))
                    .foregroundStyle(.white.opacity(0.55))
                    .tracking(2.5)
                    .position(x: tapeSideInset + tapeW / 2, y: tapeBottom + 18)

                Text("ALT")
                    .font(.system(size: 13, weight: .bold, design: .monospaced))
                    .foregroundStyle(.white.opacity(0.55))
                    .tracking(2.5)
                    .position(x: w - tapeSideInset - tapeW / 2, y: tapeBottom + 18)

                VStack(alignment: .leading, spacing: 6) {
                    HUDDataBlock(label: "ELAPSED", value: appModel.missionElapsed, unit: "")
                    if appModel.notamActive {
                        HStack(spacing: 6) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.system(size: 13, weight: .semibold))
                                .foregroundStyle(.orange)
                            Text("NOTAM")
                                .font(.system(size: 13, weight: .bold, design: .monospaced))
                                .foregroundStyle(.orange)
                                .tracking(1.2)
                        }
                        .padding(.horizontal, 10).padding(.vertical, 6)
                        .background(Color.hudBackground.opacity(0.45))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                }
                .padding(.top, 18).padding(.leading, 14)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)

                VStack {
                    HStack(spacing: 10) {
                        ZStack {
                            Circle()
                                .fill(isRecording ? Color.red : Color.gray.opacity(0.25))
                                .frame(width: 10, height: 10)
                            if isRecording {
                                Circle()
                                    .fill(Color.red.opacity(0.35))
                                    .frame(width: 18, height: 18)
                            }
                        }
                        HStack(spacing: 8) {
                            Image(systemName: "airplane.circle.fill")
                                .font(.system(size: 15, weight: .semibold))
                                .foregroundStyle(.white.opacity(0.55))
                            Text(appModel.droneID)
                                .font(.system(size: 16, weight: .bold, design: .monospaced))
                                .foregroundStyle(.white)
                                .tracking(1.2)
                        }
                        .padding(.horizontal, 16).padding(.vertical, 9)
                        .background(Color.hudBackground.opacity(0.52))
                        .clipShape(Capsule())
                        .overlay(Capsule().strokeBorder(.white.opacity(0.18), lineWidth: 1))
                    }
                    Spacer()
                }
                .padding(.top, 18)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)

                VStack(alignment: .trailing, spacing: 6) {
                    HUDDataBlock(
                        label: "V/S",
                        value: String(format: "%+.1f", appModel.verticalSpeed) + " m/s",
                        unit: "",
                        alignment: .trailing
                    )
                    HUDStatusBadge(icon: "checkmark.shield.fill", text: "ZONE OK", color: .green)
                }
                .padding(.top, 18).padding(.trailing, 14)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)

                if showCrosshair {
                    HUDCrosshair()
                        .frame(width: w, height: h)
                }

                VStack(spacing: 0) {
                    HUDHeadingTape(heading: appModel.heading)
                        .frame(width: w * 0.52, height: 40)
                        .padding(.bottom, 5)
                    HUDDataBar()
                        .environment(appModel)
                        .frame(maxWidth: .infinity)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
            }
        }
    }
}

// MARK: - HUD sub-views (unchanged from original except HUDDataBar)

private struct HUDCrosshair: View {
    var body: some View {
        GeometryReader { geo in
            let cx = geo.size.width  / 2
            let cy = geo.size.height / 2
            Canvas { ctx, _ in
                let arm: CGFloat = 50; let gap: CGFloat = 16
                var h = Path()
                h.move(to: CGPoint(x: cx - arm - gap, y: cy)); h.addLine(to: CGPoint(x: cx - gap, y: cy))
                h.move(to: CGPoint(x: cx + gap, y: cy));       h.addLine(to: CGPoint(x: cx + arm + gap, y: cy))
                var v = Path()
                v.move(to: CGPoint(x: cx, y: cy - arm - gap)); v.addLine(to: CGPoint(x: cx, y: cy - gap))
                v.move(to: CGPoint(x: cx, y: cy + gap));       v.addLine(to: CGPoint(x: cx, y: cy + arm + gap))
                ctx.stroke(h, with: .color(.green.opacity(0.72)), lineWidth: 4)
                ctx.stroke(v, with: .color(.green.opacity(0.72)), lineWidth: 4)
                var dot = Path(); dot.addEllipse(in: CGRect(x: cx - 3, y: cy - 3, width: 6, height: 6))
                ctx.fill(dot, with: .color(.green.opacity(0.72)))
            }
        }
    }
}

private struct HUDSpeedTape: View {
    let speed: Double; let target: Double
    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width; let h = geo.size.height
            let cx = w / 2; let cy = h / 2
            let pxPerUnit: CGFloat = h / 20.0
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 10).fill(Color.hudBackground.opacity(0.38))
                Rectangle().fill(Color.green.opacity(0.70)).frame(width: 3).clipShape(RoundedRectangle(cornerRadius: 10))
                Canvas { ctx, size in
                    ctx.clip(to: Path(CGRect(x: 0, y: 0, width: size.width, height: size.height)))
                    let halfRange = Double(size.height / pxPerUnit / 2) + 2
                    let minVal = max(0.0, speed - halfRange); let maxVal = speed + halfRange
                    var val = floor(minVal)
                    while val <= ceil(maxVal) {
                        guard val >= 0 else { val += 1; continue }
                        let offset = CGFloat(speed - val) * pxPerUnit; let y = cy + offset
                        let isMajor = Int(val.rounded()) % 5 == 0
                        let tickW: CGFloat = isMajor ? 20 : 10
                        let tickStartX = size.width - 4; let tickEndX = tickStartX - tickW
                        var tick = Path(); tick.move(to: CGPoint(x: tickStartX, y: y)); tick.addLine(to: CGPoint(x: tickEndX, y: y))
                        ctx.stroke(tick, with: .color(Color.white.opacity(isMajor ? 0.50 : 0.18)), lineWidth: isMajor ? 1.5 : 0.8)
                        if isMajor && abs(y - cy) > 28 {
                            ctx.draw(Text(String(format: "%.0f", val)).font(.system(size: 12, weight: .medium, design: .monospaced)).foregroundStyle(Color.white.opacity(0.55)), at: CGPoint(x: tickEndX - 4, y: y), anchor: .trailing)
                        }
                        val += 1
                    }
                    let bugOffset = CGFloat(speed - target) * pxPerUnit; let bugY = cy + bugOffset
                    if bugY >= 20 && bugY <= size.height - 8 {
                        var line = Path(); line.move(to: CGPoint(x: 4, y: bugY)); line.addLine(to: CGPoint(x: size.width - 4, y: bugY))
                        ctx.stroke(line, with: .color(Color.orange.opacity(0.78)), style: StrokeStyle(lineWidth: 1.5, dash: [5, 3]))
                        ctx.draw(Text(String(format: "TGT %.0f", target)).font(.system(size: 15, weight: .bold, design: .monospaced)).foregroundStyle(Color.orange.opacity(0.85)), at: CGPoint(x: 6, y: bugY - 11), anchor: .leading)
                    }
                }
                ZStack {
                    Rectangle().fill(Color.hudBackground.opacity(0.78)).overlay(Rectangle().fill(Color.green.opacity(0.28)).frame(height: 1), alignment: .top).overlay(Rectangle().fill(Color.green.opacity(0.28)).frame(height: 1), alignment: .bottom)
                    VStack(spacing: 1) {
                        Text(String(format: "%.1f", speed)).font(.system(size: 22, weight: .bold, design: .monospaced)).foregroundStyle(.green)
                        Text("m/s").font(.system(size: 10, weight: .semibold, design: .monospaced)).foregroundStyle(.white.opacity(0.38))
                    }
                }.frame(width: w, height: 48).position(x: cx, y: cy)
            }
        }
    }
}

private struct HUDAltitudeTape: View {
    let altitude: Double; let target: Double
    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width; let h = geo.size.height
            let cx = w / 2; let cy = h / 2
            let pxPerUnit: CGFloat = h / 80.0
            ZStack(alignment: .trailing) {
                RoundedRectangle(cornerRadius: 10).fill(Color.hudBackground.opacity(0.38))
                Rectangle().fill(Color.green.opacity(0.70)).frame(width: 3).clipShape(RoundedRectangle(cornerRadius: 10))
                Canvas { ctx, size in
                    ctx.clip(to: Path(CGRect(x: 0, y: 0, width: size.width, height: size.height)))
                    let halfRange = Double(size.height / pxPerUnit / 2) + 5
                    let minVal = max(0.0, altitude - halfRange); let maxVal = altitude + halfRange
                    var val = floor(minVal / 2) * 2
                    while val <= ceil(maxVal) {
                        guard val >= 0 else { val += 2; continue }
                        let offset = CGFloat(altitude - val) * pxPerUnit; let y = cy + offset
                        let isMajor = Int(val.rounded()) % 10 == 0
                        let tickW: CGFloat = isMajor ? 20 : 10
                        var tick = Path(); tick.move(to: CGPoint(x: 4, y: y)); tick.addLine(to: CGPoint(x: 4 + tickW, y: y))
                        ctx.stroke(tick, with: .color(Color.white.opacity(isMajor ? 0.50 : 0.18)), lineWidth: isMajor ? 1.5 : 0.8)
                        if isMajor && abs(y - cy) > 28 {
                            ctx.draw(Text(String(format: "%.0f", val)).font(.system(size: 12, weight: .medium, design: .monospaced)).foregroundStyle(Color.white.opacity(0.55)), at: CGPoint(x: 4 + tickW + 4, y: y), anchor: .leading)
                        }
                        val += 2
                    }
                    let bugOffset = CGFloat(altitude - target) * pxPerUnit; let bugY = cy + bugOffset
                    if bugY >= 20 && bugY <= size.height - 8 {
                        var line = Path(); line.move(to: CGPoint(x: 4, y: bugY)); line.addLine(to: CGPoint(x: size.width - 4, y: bugY))
                        ctx.stroke(line, with: .color(Color.orange.opacity(0.78)), style: StrokeStyle(lineWidth: 1.5, dash: [5, 3]))
                        ctx.draw(Text(String(format: "TGT %.0f", target)).font(.system(size: 15, weight: .bold, design: .monospaced)).foregroundStyle(Color.orange.opacity(0.85)), at: CGPoint(x: size.width - 6, y: bugY - 11), anchor: .trailing)
                    }
                }
                ZStack {
                    Rectangle().fill(Color.hudBackground.opacity(0.78)).overlay(Rectangle().fill(Color.green.opacity(0.28)).frame(height: 1), alignment: .top).overlay(Rectangle().fill(Color.green.opacity(0.28)).frame(height: 1), alignment: .bottom)
                    VStack(spacing: 1) {
                        Text(String(format: "%.0f", altitude)).font(.system(size: 22, weight: .bold, design: .monospaced)).foregroundStyle(.green)
                        Text("m AGL").font(.system(size: 10, weight: .semibold, design: .monospaced)).foregroundStyle(.white.opacity(0.38))
                    }
                }.frame(width: w, height: 48).position(x: cx, y: cy)
            }
        }
    }
}

private struct HUDDataBlock: View {
    let label: String; let value: String; let unit: String
    var color: Color = .white
    var alignment: HorizontalAlignment = .leading
    var body: some View {
        VStack(alignment: alignment, spacing: 1) {
            Text(label).font(.system(size: 14, weight: .semibold, design: .monospaced)).foregroundStyle(.white.opacity(0.70)).tracking(1.5)
            HStack(alignment: .lastTextBaseline, spacing: 5) {
                Text(value).font(.system(size: 30, weight: .semibold, design: .monospaced)).foregroundStyle(color)
                if !unit.isEmpty { Text(unit).font(.system(size: 13, design: .monospaced)).foregroundStyle(.white.opacity(0.7)) }
            }
        }
        .padding(.horizontal, 11).padding(.vertical, 7)
        .background(Color.hudBackground.opacity(0.45))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

private struct HUDStatusBadge: View {
    let icon: String; let text: String; var color: Color = .green
    var body: some View {
        HStack(spacing: 7) {
            Image(systemName: icon).font(.system(size: 15, weight: .semibold))
            Text(text).font(.system(size: 16, weight: .semibold, design: .monospaced))
        }
        .foregroundStyle(color)
        .padding(.horizontal, 11).padding(.vertical, 7)
        .background(Color.hudBackground.opacity(0.45))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

private struct HUDHeadingTape: View {
    let heading: Double
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 8).fill(Color.hudBackground.opacity(0.60))
            GeometryReader { geo in
                let cx = geo.size.width / 2; let cy = geo.size.height / 2
                let ppd: CGFloat = geo.size.width / 80
                ZStack {
                    Canvas { ctx, size in
                        ctx.clip(to: Path(CGRect(x: 0, y: 0, width: size.width, height: size.height)))
                        let halfRange = Double(size.width / ppd / 2) + 15
                        var deg = floor(heading - halfRange)
                        while deg <= ceil(heading + halfRange) {
                            let x = cx + CGFloat(deg - heading) * ppd
                            let intDeg = ((Int(deg.rounded()) % 360) + 360) % 360
                            if intDeg % 10 == 0 {
                                var tick = Path(); tick.move(to: CGPoint(x: x, y: cy + 4)); tick.addLine(to: CGPoint(x: x, y: cy + 14))
                                ctx.stroke(tick, with: .color(Color.white.opacity(0.45)), lineWidth: 1.5)
                                if abs(x - cx) > 30 {
                                    ctx.draw(Text("\(intDeg)").font(.system(size: 11, design: .monospaced)).foregroundStyle(Color.white.opacity(0.55)), at: CGPoint(x: x, y: cy - 6), anchor: .bottom)
                                }
                            } else if intDeg % 5 == 0 {
                                var tick = Path(); tick.move(to: CGPoint(x: x, y: cy + 7)); tick.addLine(to: CGPoint(x: x, y: cy + 14))
                                ctx.stroke(tick, with: .color(Color.white.opacity(0.22)), lineWidth: 0.8)
                            }
                            deg += 1
                        }
                    }
                    ZStack {
                        RoundedRectangle(cornerRadius: 5).fill(Color.hudBackground.opacity(0.80)).frame(width: 66, height: 24)
                        Text(String(format: "%03.0f°", heading)).font(.system(size: 15, weight: .bold, design: .monospaced)).foregroundStyle(.green)
                    }.position(x: cx, y: cy)
                    Triangle().fill(Color.green).frame(width: 8, height: 6).position(x: cx, y: 4)
                }
            }
        }
    }
}

// MARK: - HUD Data Bar

private struct HUDDataBar: View {
    @Environment(AppModel.self) private var appModel

    private var batteryColor: Color {
        appModel.batteryPercent > 0.5 ? .green : appModel.batteryPercent > 0.25 ? .orange : .red
    }
    private func windColor(_ spd: Double) -> Color { spd < 5 ? .green : spd < 9 ? .orange : .red }

    // Phase-derived display flags — mirrors RightForearmView exactly
    private var showTakeoffSpinner: Bool { appModel.dronePhase == "taking_off" }
    private var showLandingSpinner: Bool { appModel.dronePhase == "landing" || appModel.dronePhase == "rth_facing_home" }
    private var showTakeoffButton:  Bool { appModel.dronePhase == "idle" }

    /// Mode label — identical logic to RightForearmView.currentModeLabel
    private var modeLabel: String {
        if showTakeoffSpinner { return "TAKEOFF" }
        if showLandingSpinner { return "LANDING" }
        if showTakeoffButton  { return "GROUNDED" }
        switch appModel.flightMode {
        case .auto:     return "AUTO"
        case .manual:   return "MANUAL"
        case .rth:      return "RTH"
        case .hold:     return "HOLD"
        case .grounded: return "GROUNDED"
        }
    }

    /// Mode accent colour — identical logic to RightForearmView.currentModeColor
    private var modeColor: Color {
        if showTakeoffSpinner || showLandingSpinner || showTakeoffButton { return .secondary }
        switch appModel.flightMode {
        case .auto:     return .cyan
        case .manual:   return .purple
        case .rth:      return .orange
        case .hold:     return .yellow
        case .grounded: return .secondary
        }
    }

    var body: some View {
        HStack(spacing: 0) {
            // Battery
            DataBarCell {
                VStack(spacing: 4) {
                    Text("BAT").font(.system(size: 15, weight: .bold, design: .monospaced)).foregroundStyle(.white.opacity(0.70)).tracking(1.2)
                    HStack(spacing: 8) {
                        HorizontalBatteryIcon(percent: appModel.batteryPercent)
                        Text("\(Int(appModel.batteryPercent * 100))%").font(.system(size: 20, weight: .bold, design: .monospaced)).foregroundStyle(batteryColor)
                    }
                    Text("\(appModel.batteryMinutesRemaining) min").font(.system(size: 15, design: .monospaced)).foregroundStyle(.white.opacity(0.70))
                }
            }

            DataBarDivider()

            // Mode + Status (status always white, mode uses accent colour)
            DataBarCell {
                VStack(spacing: 4) {
                    Text("MODE").font(.system(size: 15, weight: .bold, design: .monospaced)).foregroundStyle(.white.opacity(0.70)).tracking(1.2)
                    Text(modeLabel)
                        .font(.system(size: 20, weight: .black, design: .monospaced))
                        .foregroundStyle(modeColor)
                        .tracking(1.5)
                    Text(appModel.droneStatus)
                        .font(.system(size: 14, weight: .semibold, design: .monospaced))
                        .foregroundStyle(.white)
                }
            }

            DataBarDivider()

            // Wind compass
            DataBarCell {
                VStack(spacing: 6) {
                    CompassWithWindOverlay(heading: appModel.heading, windSpeed: appModel.windSpeedAircraft, windBearing: appModel.windDirection)
                        .frame(width: 110, height: 110)
                    Text("WIND").font(.system(size: 15, weight: .bold, design: .monospaced)).foregroundStyle(.cyan)
                    VStack(spacing: 1) {
                        Text(String(format: "%.1f m/s", appModel.windSpeedAircraft)).font(.system(size: 17, weight: .bold, design: .monospaced)).foregroundStyle(windColor(appModel.windSpeedAircraft))
                        Text(String(format: "from %03.0f°", appModel.windDirection)).font(.system(size: 13, design: .monospaced)).foregroundStyle(.white.opacity(0.70))
                    }
                }
            }

            DataBarDivider()

            // RTK
            DataBarCell {
                VStack(spacing: 4) {
                    Text("RTK").font(.system(size: 15, weight: .bold, design: .monospaced)).foregroundStyle(.white.opacity(0.70)).tracking(1.2)
                    HStack(spacing: 6) {
                        Circle().fill(appModel.rtkStatus == "FIXED" ? Color.green : Color.orange).frame(width: 9, height: 9)
                        Text(appModel.rtkStatus).font(.system(size: 20, weight: .bold, design: .monospaced)).foregroundStyle(appModel.rtkStatus == "FIXED" ? .green : .orange)
                    }
                    Text("\(appModel.gpsSatellites) SAT").font(.system(size: 15, design: .monospaced)).foregroundStyle(.white.opacity(0.70))
                }
            }

            DataBarDivider()

            // Datalink
            DataBarCell {
                VStack(spacing: 4) {
                    Text("LINK").font(.system(size: 15, weight: .bold, design: .monospaced)).foregroundStyle(.white.opacity(0.70)).tracking(1.2)
                    HStack(alignment: .bottom, spacing: 3) {
                        ForEach(0..<4, id: \.self) { i in
                            let thresholds = [200, 150, 100, 50]
                            let active = appModel.primaryLinkUp && appModel.primaryLatencyMS < thresholds[i]
                            RoundedRectangle(cornerRadius: 2).fill(active ? Color.green : Color.white.opacity(0.12)).frame(width: 6, height: CGFloat(8 + i * 6))
                        }
                    }
                    Text(appModel.primaryLinkUp ? "\(appModel.primaryLatencyMS) ms" : "LOST").font(.system(size: 16, weight: .bold, design: .monospaced)).foregroundStyle(appModel.primaryLinkUp ? .green : .red)
                }
            }
        }
        .padding(.vertical, 14)
        .background(Color.hudBackground.opacity(0.72))
    }
}

// MARK: - Compass

private struct CompassWithWindOverlay: View {
    let heading: Double; let windSpeed: Double; let windBearing: Double
    private let cardinals = ["N", "E", "S", "W"]

    private func windGeometry(_ spd: Double) -> (Int, CGFloat) {
        let dashLen: CGFloat = 8; let gap: CGFloat = 5
        let count: Int = spd < 2 ? 1 : spd < 5 ? 2 : spd < 8 ? 3 : 4
        return (count, CGFloat(count) * dashLen + CGFloat(max(0, count - 1)) * gap)
    }

    var body: some View {
        GeometryReader { geo in
            let r = min(geo.size.width, geo.size.height) / 2
            let cx = geo.size.width / 2; let cy = geo.size.height / 2
            let relativeWindBearing = windBearing - heading
            let windRad = CGFloat((relativeWindBearing - 90.0) * .pi / 180.0)
            let cosW = cos(windRad); let sinW = sin(windRad)
            ZStack {
                Circle().stroke(Color.primary.opacity(0.3), lineWidth: 2).frame(width: r * 2, height: r * 2)
                Circle().stroke(Color.primary.opacity(0.07), lineWidth: 2).frame(width: r * 1.3, height: r * 1.3)
                Canvas { ctx, _ in
                    for i in 0..<36 {
                        let angle = Double(i) * 10.0 * .pi / 180.0 - .pi / 2.0
                        let major = i % 9 == 0; let len: CGFloat = major ? 10 : 5
                        let inner = r - len - (major ? 3 : 2); let outer = r - (major ? 3 : 2)
                        var p = Path(); p.move(to: CGPoint(x: cx + cos(angle) * inner, y: cy + sin(angle) * inner)); p.addLine(to: CGPoint(x: cx + cos(angle) * outer, y: cy + sin(angle) * outer))
                        ctx.stroke(p, with: .color(Color.primary.opacity(major ? 0.4 : 0.20)), lineWidth: major ? 1.5 : 0.8)
                    }
                    let dashLen: CGFloat = 8; let gap: CGFloat = 5; let headLen: CGFloat = 9; let headWidth: CGFloat = 6; let shaftStart: CGFloat = 6
                    let (dashCount, totalLength) = windGeometry(windSpeed)
                    let maxTip = r - 6; let rawTip = shaftStart + totalLength + headLen
                    let scale = rawTip > maxTip ? maxTip / rawTip : 1.0; let tipDist = rawTip * scale
                    let tip = CGPoint(x: cx + cosW * tipDist, y: cy + sinW * tipDist)
                    let shaftEnd = tipDist - headLen
                    for i in 0..<dashCount {
                        let segStart = (shaftStart + CGFloat(i) * (dashLen + gap)) * scale
                        let segEnd = min((shaftStart + CGFloat(i) * (dashLen + gap) + dashLen) * scale, shaftEnd)
                        guard segEnd > segStart else { continue }
                        var seg = Path(); seg.move(to: CGPoint(x: cx + cosW * segStart, y: cy + sinW * segStart)); seg.addLine(to: CGPoint(x: cx + cosW * segEnd, y: cy + sinW * segEnd))
                        ctx.stroke(seg, with: .color(Color.cyan.opacity(0.90)), lineWidth: 2.0)
                    }
                    let baseCenter = CGPoint(x: tip.x - cosW * headLen * scale, y: tip.y - sinW * headLen * scale)
                    let leftPt = CGPoint(x: baseCenter.x - sinW * headWidth, y: baseCenter.y + cosW * headWidth)
                    let rightPt = CGPoint(x: baseCenter.x + sinW * headWidth, y: baseCenter.y - cosW * headWidth)
                    var head = Path(); head.move(to: tip); head.addLine(to: leftPt); head.addLine(to: rightPt); head.closeSubpath()
                    ctx.fill(head, with: .color(Color.cyan.opacity(0.90)))
                    var dot = Path(); dot.addEllipse(in: CGRect(x: cx - 4, y: cy - 4, width: 8, height: 8))
                    ctx.fill(dot, with: .color(.white.opacity(0.70)))
                    var tab = Path(); tab.addRoundedRect(in: CGRect(x: cx - 2, y: cy - r + 2, width: 4, height: 12), cornerSize: CGSize(width: 2, height: 2))
                    ctx.fill(tab, with: .color(.green))
                }
                ForEach(0..<4, id: \.self) { i in
                    let screenAngle = Double(i) * 90.0 - heading
                    let rad = CGFloat((screenAngle - 90.0) * .pi / 180.0)
                    Text(cardinals[i]).font(.system(size: 14, weight: .bold, design: .monospaced)).foregroundStyle(i == 0 ? Color.red : Color.white.opacity(0.60)).position(x: cx + cos(rad) * (r - 10), y: cy + sin(rad) * (r - 10))
                }
            }
        }
    }
}

private struct HorizontalBatteryIcon: View {
    let percent: Double
    private var color: Color { percent > 0.5 ? .green : percent > 0.25 ? .orange : .red }
    var body: some View {
        HStack(spacing: 0) {
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 3).fill(.white.opacity(0.12)).frame(width: 28, height: 14)
                RoundedRectangle(cornerRadius: 2).fill(color).frame(width: max(3, 28 * percent), height: 14).padding(1)
            }
            Rectangle().fill(.white.opacity(0.30)).frame(width: 3, height: 7).clipShape(RoundedRectangle(cornerRadius: 1))
        }
    }
}

private struct DataBarCell<Content: View>: View {
    @ViewBuilder let content: () -> Content
    var body: some View { content().frame(maxWidth: .infinity) }
}

private struct DataBarDivider: View {
    var body: some View { Rectangle().fill(.white.opacity(0.12)).frame(width: 1, height: 64) }
}

struct HUDTag: View {
    let label: String; let value: String
    var body: some View {
        HStack(spacing: 6) {
            Text(label).font(.system(size: 14, weight: .semibold, design: .monospaced)).foregroundStyle(.white.opacity(0.6))
            Text(value).font(.system(size: 15, weight: .medium, design: .monospaced)).foregroundStyle(.green)
        }
        .padding(.horizontal, 10).padding(.vertical, 5)
        .background(Color.hudBackground.opacity(0.55))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}
