/**
 * Acharavidya — Orrery Renderer
 *
 * Renders heliocentric (Sun-centered) and geocentric (Earth-centered)
 * solar system models as SVG for the selected date.
 *
 * Uses sidereal ecliptic longitudes aligned with Indian rashi ring.
 * Rashi names are language-aware — passed from the API.
 * Navagraha traditional colours.
 *
 * Rahu & Ketu rendered as a celestial Nāga (serpent) — Rahu is the
 * cobra head, Ketu is the tail, connected by a sinusoidal body.
 */

// Fallback rashi names (Sanskrit) — used if API doesn't provide them
let _orreryRashiNames = [
    "मेष", "वृष", "मिथुन", "कर्क", "सिंह", "कन्या",
    "तुला", "वृश्चिक", "धनु", "मकर", "कुम्भ", "मीन",
];

/**
 * Convert ecliptic longitude to SVG x, y.
 * 0° = right (3 o'clock), CCW = increasing longitude.
 * SVG y-axis is inverted, so we negate sin.
 */
function lonToXY(lon, radius, cx, cy) {
    const rad = (lon * Math.PI) / 180;
    return {
        x: cx + radius * Math.cos(rad),
        y: cy - radius * Math.sin(rad),
    };
}


// ══════════════════════════════════════════════════════════════
//  Common SVG builders
// ══════════════════════════════════════════════════════════════

function svgDefs() {
    return `
    <defs>
        <radialGradient id="starfield" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stop-color="#1a1a2e"/>
            <stop offset="100%" stop-color="#0a0a14"/>
        </radialGradient>
        <radialGradient id="sunGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stop-color="#fbbf24" stop-opacity="1"/>
            <stop offset="40%"  stop-color="#f59e0b" stop-opacity="0.5"/>
            <stop offset="100%" stop-color="#f59e0b" stop-opacity="0"/>
        </radialGradient>
        <radialGradient id="earthGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stop-color="#06b6d4" stop-opacity="1"/>
            <stop offset="40%"  stop-color="#0891b2" stop-opacity="0.5"/>
            <stop offset="100%" stop-color="#0891b2" stop-opacity="0"/>
        </radialGradient>
        <radialGradient id="moonGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stop-color="#e2e8f0" stop-opacity="1"/>
            <stop offset="40%"  stop-color="#cbd5e1" stop-opacity="0.5"/>
            <stop offset="100%" stop-color="#94a3b8" stop-opacity="0"/>
        </radialGradient>
        <!-- Naga body gradient — dark blue-green serpent -->
        <linearGradient id="nagaBody" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"   stop-color="#0f766e" stop-opacity="0.6"/>
            <stop offset="30%"  stop-color="#115e59" stop-opacity="0.8"/>
            <stop offset="50%"  stop-color="#134e4a" stop-opacity="1"/>
            <stop offset="70%"  stop-color="#115e59" stop-opacity="0.8"/>
            <stop offset="100%" stop-color="#5eead4" stop-opacity="0.5"/>
        </linearGradient>
        <filter id="glow">
            <feGaussianBlur stdDeviation="2" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="softGlow">
            <feGaussianBlur stdDeviation="3" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="nagaGlow">
            <feGaussianBlur stdDeviation="1.5" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
    </defs>`;
}

function svgBackground(W, H) {
    // Add some subtle "stars"
    let svg = `<rect width="${W}" height="${H}" fill="url(#starfield)" rx="12"/>`;
    // Scatter a few dim stars
    for (let i = 0; i < 40; i++) {
        const sx = Math.random() * W;
        const sy = Math.random() * H;
        const sr = 0.3 + Math.random() * 0.7;
        const so = 0.2 + Math.random() * 0.4;
        svg += `<circle cx="${sx.toFixed(1)}" cy="${sy.toFixed(1)}" r="${sr.toFixed(1)}" fill="#fff" opacity="${so.toFixed(2)}"/>`;
    }
    return svg;
}

/**
 * Draw the rashi ring — 12 sign boundaries and localized names.
 * @param {number} lagnaRashiIndex  Optional rashi index (0–11) to highlight as Lagna
 */
function svgRashiRing(cx, cy, innerR, outerR, lagnaRashiIndex) {
    let svg = '';
    // Ring fill — subtle dark band
    svg += `<circle cx="${cx}" cy="${cy}" r="${outerR}" fill="none" stroke="#2a2a4a" stroke-width="1"/>`;
    svg += `<circle cx="${cx}" cy="${cy}" r="${innerR}" fill="none" stroke="#2a2a4a" stroke-width="1"/>`;

    // If lagna rashi is known, draw a highlighted arc segment for it
    if (lagnaRashiIndex != null && lagnaRashiIndex >= 0 && lagnaRashiIndex < 12) {
        const startDeg = lagnaRashiIndex * 30;
        const endDeg   = startDeg + 30;
        // Draw filled arc between innerR and outerR
        const startRad1 = (startDeg * Math.PI) / 180;
        const endRad1   = (endDeg * Math.PI) / 180;
        // Outer arc (CCW in math, but SVG y is inverted so we negate sin)
        const oS = { x: cx + outerR * Math.cos(startRad1), y: cy - outerR * Math.sin(startRad1) };
        const oE = { x: cx + outerR * Math.cos(endRad1),   y: cy - outerR * Math.sin(endRad1)   };
        const iS = { x: cx + innerR * Math.cos(startRad1), y: cy - innerR * Math.sin(startRad1) };
        const iE = { x: cx + innerR * Math.cos(endRad1),   y: cy - innerR * Math.sin(endRad1)   };
        // SVG arc: largeArcFlag=0 (30° < 180°), sweepFlag=0 (CCW in screen coords)
        const arcPath = `M ${oS.x.toFixed(2)} ${oS.y.toFixed(2)} `
            + `A ${outerR} ${outerR} 0 0 0 ${oE.x.toFixed(2)} ${oE.y.toFixed(2)} `
            + `L ${iE.x.toFixed(2)} ${iE.y.toFixed(2)} `
            + `A ${innerR} ${innerR} 0 0 1 ${iS.x.toFixed(2)} ${iS.y.toFixed(2)} Z`;
        svg += `<path d="${arcPath}" fill="#fbbf24" opacity="0.15"/>`;
        svg += `<path d="${arcPath}" fill="none" stroke="#fbbf24" stroke-width="1.2" opacity="0.6"/>`;
    }

    for (let i = 0; i < 12; i++) {
        const angle = i * 30;
        // Boundary line
        const p1 = lonToXY(angle, innerR, cx, cy);
        const p2 = lonToXY(angle, outerR, cx, cy);
        svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="#3a3a5a" stroke-width="0.5"/>`;

        // Rashi name at midpoint of each 30° segment
        const midAngle = angle + 15;
        const midR = (innerR + outerR) / 2;
        const mid = lonToXY(midAngle, midR, cx, cy);
        const isLagna = (lagnaRashiIndex != null && i === lagnaRashiIndex);
        const nameColor = isLagna ? '#fbbf24' : '#7a7a9a';
        const nameWeight = isLagna ? 'font-weight="700"' : '';
        const nameSize = isLagna ? '10' : '9';
        svg += `<text x="${mid.x}" y="${mid.y}" text-anchor="middle" dominant-baseline="central" font-size="${nameSize}" fill="${nameColor}" ${nameWeight} font-family="sans-serif">${_orreryRashiNames[i]}</text>`;
    }
    return svg;
}

/**
 * Draw a planet body with label and optional glow ring.
 */
function svgPlanet(lon, radius, cx, cy, body, planetR = 5, rashiInnerR = 999) {
    const pos = lonToXY(lon, radius, cx, cy);
    let svg = '';

    // Subtle glow ring behind planet
    svg += `<circle cx="${pos.x}" cy="${pos.y}" r="${planetR + 4}" fill="${body.color}" opacity="0.15"/>`;

    // Planet body
    svg += `<circle cx="${pos.x}" cy="${pos.y}" r="${planetR}" fill="${body.color}" filter="url(#glow)" stroke="#000" stroke-width="0.3"/>`;

    // Label — outward by default; flip inward if it would enter the rashi ring
    let labelR = radius + planetR + 10;
    if (labelR >= rashiInnerR - 4) {
        // Place label inward (toward center) to avoid rashi ring overlap
        labelR = radius - planetR - 9;
    }
    const labelPos = lonToXY(lon, labelR, cx, cy);
    let label = body.label;
    const KV = window.KVLocale || {};
    if (body.is_retrograde && body.key !== 'rahu' && body.key !== 'ketu') {
        const rSym = KV.retrogradeSymbol ? KV.retrogradeSymbol() : 'ᴿ';
        label += ' ' + rSym;
    }
    if (body.is_combust) {
        const cSym = KV.combustSymbol ? KV.combustSymbol() : 'ᶜ';
        label += ' ' + cSym;
    }
    svg += `<text x="${labelPos.x}" y="${labelPos.y}" text-anchor="middle" dominant-baseline="central" font-size="8.5" fill="${body.color}" font-weight="600" opacity="0.9" style="paint-order:stroke;stroke:#0a0a14;stroke-width:3px;">${label}</text>`;

    return svg;
}


// ══════════════════════════════════════════════════════════════
//  NĀGA (Rahu-Ketu Serpent)
//
//  Rahu = ascending lunar node = Serpent's HEAD (cobra hood)
//  Ketu = descending lunar node = Serpent's TAIL
//  Always exactly 180° apart on the ecliptic.
//
//  We draw a sinusoidal serpent body connecting them across the
//  geocentric chart, with a stylised cobra head at Rahu and a
//  tapered tail at Ketu.
// ══════════════════════════════════════════════════════════════

/**
 * Draw the Rahu-Ketu Nāga on the geocentric orrery.
 *
 * @param {number} rahuLon   Rahu's tropical longitude (degrees)
 * @param {number} ketuLon   Ketu's tropical longitude (degrees)
 * @param {number} nagaR     Orbit radius for the Naga ring
 * @param {number} cx        Center x
 * @param {number} cy        Center y
 * @param {string} rahuLabel Localized label for Rahu
 * @param {string} ketuLabel Localized label for Ketu
 * @returns {string}         SVG markup
 */
function svgNaga(rahuLon, ketuLon, nagaR, cx, cy, rahuLabel, ketuLabel) {
    let svg = '';

    // -- Naga orbit ring (dashed, teal) --
    svg += `<circle cx="${cx}" cy="${cy}" r="${nagaR}" fill="none" stroke="#0f766e" stroke-width="0.5" stroke-dasharray="3,5" opacity="0.4"/>`;

    // -- Sinusoidal serpent body --
    // Two halves: Ketu→Rahu and Rahu→Ketu, each sweeping 180°
    const numWaves = 5;
    const amplitude = 10;
    const steps = 80;

    for (let half = 0; half < 2; half++) {
        const startLon = half === 0 ? ketuLon : rahuLon;

        let points = [];
        for (let i = 0; i <= steps; i++) {
            const t = i / steps;
            const lon = startLon + t * 180;
            const wave = amplitude * Math.sin(t * numWaves * Math.PI);
            // Taper: thinnest at ends, thickest at center
            const taper = 0.2 + 0.8 * Math.sin(t * Math.PI);
            const r = nagaR + wave * taper;
            const p = lonToXY(lon, r, cx, cy);
            points.push(p);
        }

        if (points.length > 1) {
            let d = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
            for (let i = 1; i < points.length; i++) {
                d += ` L ${points[i].x.toFixed(1)} ${points[i].y.toFixed(1)}`;
            }
            // Outer body — dark teal
            svg += `<path d="${d}" fill="none" stroke="#0d9488" stroke-width="3" stroke-linecap="round" opacity="0.6" filter="url(#nagaGlow)"/>`;
            // Inner shimmer — lighter teal
            svg += `<path d="${d}" fill="none" stroke="#5eead4" stroke-width="1" stroke-linecap="round" opacity="0.35"/>`;
        }
    }

    // -- Scales pattern (diamonds along the body for texture) --
    for (let half = 0; half < 2; half++) {
        const startLon = half === 0 ? ketuLon : rahuLon;
        for (let i = 1; i < 10; i++) {
            const t = i / 10;
            const lon = startLon + t * 180;
            const p = lonToXY(lon, nagaR, cx, cy);
            const sz = 0.5 + 1.0 * Math.sin(t * Math.PI);
            svg += `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${sz.toFixed(1)}" fill="#5eead4" opacity="0.25"/>`;
        }
    }

    // ── RAHU: Cobra Hood — a rounded hood shape, not pointy ──
    const rahuPos = lonToXY(rahuLon, nagaR, cx, cy);
    const rahuRad = (rahuLon * Math.PI) / 180;
    const perpRad = rahuRad + Math.PI / 2;

    // Cobra hood: a wide, rounded fan shape opening outward
    // Draw as a filled bezier "fan" with neck at the base
    const neckW = 3;   // narrow neck where body meets hood
    const hoodW = 13;  // wide hood spread
    const hoodFwd = 14; // how far forward the hood extends
    const hoodBack = 4; // how far back the neck starts

    // Neck points (narrow, where serpent body meets)
    const n1X = rahuPos.x - hoodBack * Math.cos(rahuRad) + neckW * Math.cos(perpRad);
    const n1Y = rahuPos.y + hoodBack * Math.sin(rahuRad) - neckW * Math.sin(perpRad);
    const n2X = rahuPos.x - hoodBack * Math.cos(rahuRad) - neckW * Math.cos(perpRad);
    const n2Y = rahuPos.y + hoodBack * Math.sin(rahuRad) + neckW * Math.sin(perpRad);

    // Hood side points (wide)
    const h1X = rahuPos.x + 2 * Math.cos(rahuRad) + hoodW * Math.cos(perpRad);
    const h1Y = rahuPos.y - 2 * Math.sin(rahuRad) - hoodW * Math.sin(perpRad);
    const h2X = rahuPos.x + 2 * Math.cos(rahuRad) - hoodW * Math.cos(perpRad);
    const h2Y = rahuPos.y - 2 * Math.sin(rahuRad) + hoodW * Math.sin(perpRad);

    // Hood top (rounded tip)
    const topX = rahuPos.x + hoodFwd * Math.cos(rahuRad);
    const topY = rahuPos.y - hoodFwd * Math.sin(rahuRad);

    // Control points for smooth curves
    const cp1X = rahuPos.x + (hoodFwd * 0.8) * Math.cos(rahuRad) + (hoodW * 0.7) * Math.cos(perpRad);
    const cp1Y = rahuPos.y - (hoodFwd * 0.8) * Math.sin(rahuRad) - (hoodW * 0.7) * Math.sin(perpRad);
    const cp2X = rahuPos.x + (hoodFwd * 0.8) * Math.cos(rahuRad) - (hoodW * 0.7) * Math.cos(perpRad);
    const cp2Y = rahuPos.y - (hoodFwd * 0.8) * Math.sin(rahuRad) + (hoodW * 0.7) * Math.sin(perpRad);

    // Hood path: neck → left side → top → right side → neck
    svg += `<path d="M ${n1X.toFixed(1)} ${n1Y.toFixed(1)} `
        + `Q ${h1X.toFixed(1)} ${h1Y.toFixed(1)} ${cp1X.toFixed(1)} ${cp1Y.toFixed(1)} `
        + `Q ${topX.toFixed(1)} ${topY.toFixed(1)} ${cp2X.toFixed(1)} ${cp2Y.toFixed(1)} `
        + `Q ${h2X.toFixed(1)} ${h2Y.toFixed(1)} ${n2X.toFixed(1)} ${n2Y.toFixed(1)} Z" `
        + `fill="#115e59" stroke="#14b8a6" stroke-width="0.8" filter="url(#nagaGlow)" opacity="0.9"/>`;

    // Inner hood pattern — subtle U-shaped markings
    const markFwd = 5;
    const markW = 5;
    const m1X = rahuPos.x + markFwd * Math.cos(rahuRad) + markW * Math.cos(perpRad);
    const m1Y = rahuPos.y - markFwd * Math.sin(rahuRad) - markW * Math.sin(perpRad);
    const m2X = rahuPos.x + markFwd * Math.cos(rahuRad) - markW * Math.cos(perpRad);
    const m2Y = rahuPos.y - markFwd * Math.sin(rahuRad) + markW * Math.sin(perpRad);
    const mTopX = rahuPos.x + (hoodFwd * 0.65) * Math.cos(rahuRad);
    const mTopY = rahuPos.y - (hoodFwd * 0.65) * Math.sin(rahuRad);
    svg += `<path d="M ${m1X.toFixed(1)} ${m1Y.toFixed(1)} Q ${mTopX.toFixed(1)} ${mTopY.toFixed(1)} ${m2X.toFixed(1)} ${m2Y.toFixed(1)}" fill="none" stroke="#5eead4" stroke-width="0.7" opacity="0.5"/>`;

    // Eyes — two small glowing dots on either side of the snout
    const eyeR = 1.2;
    const eyeOff = 4;
    const eyeFwd = 7;
    const e1X = rahuPos.x + eyeFwd * Math.cos(rahuRad) + eyeOff * Math.cos(perpRad);
    const e1Y = rahuPos.y - eyeFwd * Math.sin(rahuRad) - eyeOff * Math.sin(perpRad);
    const e2X = rahuPos.x + eyeFwd * Math.cos(rahuRad) - eyeOff * Math.cos(perpRad);
    const e2Y = rahuPos.y - eyeFwd * Math.sin(rahuRad) + eyeOff * Math.sin(perpRad);
    svg += `<circle cx="${e1X.toFixed(1)}" cy="${e1Y.toFixed(1)}" r="${eyeR + 1}" fill="#ef4444" opacity="0.25"/>`;
    svg += `<circle cx="${e1X.toFixed(1)}" cy="${e1Y.toFixed(1)}" r="${eyeR}" fill="#ef4444" opacity="0.9"/>`;
    svg += `<circle cx="${e2X.toFixed(1)}" cy="${e2Y.toFixed(1)}" r="${eyeR + 1}" fill="#ef4444" opacity="0.25"/>`;
    svg += `<circle cx="${e2X.toFixed(1)}" cy="${e2Y.toFixed(1)}" r="${eyeR}" fill="#ef4444" opacity="0.9"/>`;

    // Rahu label — placed inward (toward center) to avoid rashi ring overlap
    const rahuLabelR = nagaR - 18;
    const rL = lonToXY(rahuLon, rahuLabelR, cx, cy);
    svg += `<text x="${rL.x}" y="${rL.y}" text-anchor="middle" dominant-baseline="central" font-size="9" fill="#5eead4" font-weight="700" style="paint-order:stroke;stroke:#0a0a14;stroke-width:3px;" filter="url(#nagaGlow)">☊ ${rahuLabel}</text>`;

    // ── KETU: Tapered serpent tail — smooth curve, not triangle ──
    const ketuPos = lonToXY(ketuLon, nagaR, cx, cy);
    const ketuRad = (ketuLon * Math.PI) / 180;
    const kPerp = ketuRad + Math.PI / 2;

    // Tail: starts wide (body width) and tapers to a thin curved tip
    const tailLen = 18;
    const baseW = 4;   // wide at body junction
    const midW = 2.5;
    const tipOff = 2;  // slight curve at the very end

    // Base (wide end, where body meets tail)
    const tb1X = ketuPos.x + baseW * Math.cos(kPerp);
    const tb1Y = ketuPos.y - baseW * Math.sin(kPerp);
    const tb2X = ketuPos.x - baseW * Math.cos(kPerp);
    const tb2Y = ketuPos.y + baseW * Math.sin(kPerp);

    // Mid-tail
    const midFwd = tailLen * 0.5;
    const tm1X = ketuPos.x + midFwd * Math.cos(ketuRad) + midW * Math.cos(kPerp);
    const tm1Y = ketuPos.y - midFwd * Math.sin(ketuRad) - midW * Math.sin(kPerp);
    const tm2X = ketuPos.x + midFwd * Math.cos(ketuRad) - midW * Math.cos(kPerp);
    const tm2Y = ketuPos.y - midFwd * Math.sin(ketuRad) + midW * Math.sin(kPerp);

    // Tip — slightly curved to one side for organic feel
    const tipX = ketuPos.x + tailLen * Math.cos(ketuRad) + tipOff * Math.cos(kPerp);
    const tipY = ketuPos.y - tailLen * Math.sin(ketuRad) - tipOff * Math.sin(kPerp);

    // Tail path: filled bezier that tapers
    svg += `<path d="M ${tb1X.toFixed(1)} ${tb1Y.toFixed(1)} `
        + `C ${tm1X.toFixed(1)} ${tm1Y.toFixed(1)} ${tm1X.toFixed(1)} ${tm1Y.toFixed(1)} ${tipX.toFixed(1)} ${tipY.toFixed(1)} `
        + `C ${tm2X.toFixed(1)} ${tm2Y.toFixed(1)} ${tm2X.toFixed(1)} ${tm2Y.toFixed(1)} ${tb2X.toFixed(1)} ${tb2Y.toFixed(1)} Z" `
        + `fill="#115e59" stroke="#14b8a6" stroke-width="0.6" opacity="0.85"/>`;

    // Faint glow at the tail tip (moksha fire — small, subtle)
    svg += `<circle cx="${tipX.toFixed(1)}" cy="${tipY.toFixed(1)}" r="3.5" fill="#f59e0b" opacity="0.2"/>`;
    svg += `<circle cx="${tipX.toFixed(1)}" cy="${tipY.toFixed(1)}" r="1.5" fill="#fbbf24" opacity="0.7"/>`;

    // Ketu label — placed inward (toward center) to avoid rashi ring overlap
    const ketuLabelR = nagaR - 18;
    const kL = lonToXY(ketuLon, ketuLabelR, cx, cy);
    svg += `<text x="${kL.x}" y="${kL.y}" text-anchor="middle" dominant-baseline="central" font-size="9" fill="#5eead4" font-weight="700" style="paint-order:stroke;stroke:#0a0a14;stroke-width:3px;" filter="url(#nagaGlow)">☋ ${ketuLabel}</text>`;

    return svg;
}


// ══════════════════════════════════════════════════════════════
//  HELIOCENTRIC ORRERY — Sun at center
// ══════════════════════════════════════════════════════════════

/**
 * Draw a small Lagna marker (▲) at the exact sidereal longitude on the rashi ring.
 */
function svgLagnaMarker(lon, innerR, outerR, cx, cy) {
    if (lon == null) return '';
    let svg = '';
    const markerR = outerR + 2;
    const pos = lonToXY(lon, markerR, cx, cy);
    // Small golden triangle pointing inward
    const rad = (lon * Math.PI) / 180;
    const sz = 5;
    // Triangle vertices: tip toward center, base outward
    const tipR = innerR - 2;
    const tip = lonToXY(lon, tipR, cx, cy);
    const baseR = outerR + 4;
    const perpRad = rad + Math.PI / 2;
    const b1 = {
        x: cx + baseR * Math.cos(rad) + sz * Math.cos(perpRad),
        y: cy - baseR * Math.sin(rad) - sz * Math.sin(perpRad),
    };
    const b2 = {
        x: cx + baseR * Math.cos(rad) - sz * Math.cos(perpRad),
        y: cy - baseR * Math.sin(rad) + sz * Math.sin(perpRad),
    };
    svg += `<polygon points="${b1.x.toFixed(1)},${b1.y.toFixed(1)} ${b2.x.toFixed(1)},${b2.y.toFixed(1)} ${tip.x.toFixed(1)},${tip.y.toFixed(1)}" fill="#fbbf24" opacity="0.8" filter="url(#glow)"/>`;

    // "Lagna" label just outside the triangle
    const KV = window.KVLocale || {};
    const lagnaWord = KV.L ? KV.L('lagnaWord') : 'Lagna';
    const labelR = outerR + 14;
    const labelPos = lonToXY(lon, labelR, cx, cy);
    svg += `<text x="${labelPos.x}" y="${labelPos.y}" text-anchor="middle" dominant-baseline="central" font-size="8" fill="#fbbf24" font-weight="700" style="paint-order:stroke;stroke:#0a0a14;stroke-width:3px;">${lagnaWord}</text>`;
    return svg;
}

function renderHeliocentric(svgEl, data, lagnaRashiIndex, lagnaLon) {
    const W = 500, H = 500;
    const cx = W / 2, cy = H / 2;

    // Orbit visual radii — well-spaced for readability
    const orbitRadii = {
        mercury:  55,
        venus:    85,
        earth:   115,
        mars:    145,
        jupiter: 175,
        saturn:  200,
    };

    const rashiInner = 215;
    const rashiOuter = 242;

    let svg = svgDefs();
    svg += svgBackground(W, H);
    svg += svgRashiRing(cx, cy, rashiInner, rashiOuter, lagnaRashiIndex);

    // Orbit circles (dashed, subtle)
    for (const [, r] of Object.entries(orbitRadii)) {
        svg += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4" opacity="0.5"/>`;
    }

    // Sun at center
    svg += `<circle cx="${cx}" cy="${cy}" r="20" fill="url(#sunGlow)"/>`;
    svg += `<circle cx="${cx}" cy="${cy}" r="10" fill="#fbbf24" filter="url(#softGlow)"/>`;
    svg += `<text x="${cx}" y="${cy + 1}" text-anchor="middle" dominant-baseline="central" font-size="10" fill="#1a1a2e" font-weight="bold">☉</text>`;

    // Planets — pass rashiInner so labels near the ring flip inward
    const planetSizes = { mercury: 4, venus: 5, earth: 6, mars: 5, jupiter: 7, saturn: 6 };
    for (const body of data) {
        const r = orbitRadii[body.key];
        if (!r) continue;
        svg += svgPlanet(body.longitude, r, cx, cy, body, planetSizes[body.key] || 5, rashiInner);
    }

    // Lagna marker on the rashi ring
    svg += svgLagnaMarker(lagnaLon, rashiInner, rashiOuter, cx, cy);

    svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svgEl.innerHTML = svg;
}


// ══════════════════════════════════════════════════════════════
//  GEOCENTRIC ORRERY — Earth at center
// ══════════════════════════════════════════════════════════════

function renderGeocentric(svgEl, data, lagnaRashiIndex, lagnaLon) {
    const W = 500, H = 500;
    const cx = W / 2, cy = H / 2;

    // Orbit radii — outer orbits compressed to leave gap to rashi ring
    const orbitRadii = {
        moon:     42,
        sun:      70,
        mercury:  98,
        venus:   126,
        mars:    152,
        jupiter: 174,
        saturn:  192,
    };

    // Naga (Rahu-Ketu) ring between Saturn and zodiac
    const nagaR = 202;

    const rashiInner = 215;
    const rashiOuter = 242;

    let svg = svgDefs();
    svg += svgBackground(W, H);

    // Orbit circles (dashed, subtle) — draw BEFORE rashi ring
    for (const [, r] of Object.entries(orbitRadii)) {
        svg += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4" opacity="0.5"/>`;
    }

    // Rashi ring drawn on top of orbits so names are always readable
    svg += svgRashiRing(cx, cy, rashiInner, rashiOuter, lagnaRashiIndex);

    // Earth at center
    svg += `<circle cx="${cx}" cy="${cy}" r="18" fill="url(#earthGlow)"/>`;
    svg += `<circle cx="${cx}" cy="${cy}" r="9" fill="#06b6d4" filter="url(#softGlow)"/>`;
    svg += `<text x="${cx}" y="${cy + 1}" text-anchor="middle" dominant-baseline="central" font-size="9" fill="#0a0a14" font-weight="bold">🜨</text>`;

    // Planet sizes
    const planetSizes = { moon: 5, sun: 8, mercury: 4, venus: 5, mars: 5, jupiter: 7, saturn: 6 };

    // Planets (excluding Rahu/Ketu — drawn as Naga)
    // Pass rashiInner so labels near the ring flip inward automatically
    for (const body of data) {
        const r = orbitRadii[body.key];
        if (!r) continue; // skip rahu, ketu — handled as Naga
        svg += svgPlanet(body.longitude, r, cx, cy, body, planetSizes[body.key] || 5, rashiInner);
    }

    // -- Nāga: Rahu (head) + Ketu (tail) as a celestial serpent --
    let rahuBody = null, ketuBody = null;
    for (const body of data) {
        if (body.key === 'rahu') rahuBody = body;
        if (body.key === 'ketu') ketuBody = body;
    }
    if (rahuBody && ketuBody) {
        svg += svgNaga(rahuBody.longitude, ketuBody.longitude, nagaR, cx, cy, rahuBody.label, ketuBody.label, rashiInner);
    }

    // Lagna marker on the rashi ring
    svg += svgLagnaMarker(lagnaLon, rashiInner, rashiOuter, cx, cy);

    svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svgEl.innerHTML = svg;
}


// ══════════════════════════════════════════════════════════════
//  Exports
// ══════════════════════════════════════════════════════════════

window.OrreryRenderer = {
    renderHeliocentric,
    renderGeocentric,
};
