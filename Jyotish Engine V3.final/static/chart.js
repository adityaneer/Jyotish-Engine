/**
 * Acharavidya — Chart Renderer
 *
 * Renders both South Indian (fixed-rashi) and North Indian (fixed-house)
 * Vedic astrology charts as SVG.
 *
 * South Indian: 4×4 grid with center empty, rashis in fixed positions,
 *               Meena top-left → clockwise.
 *
 * North Indian: Diamond/rhombus layout, houses in fixed positions,
 *               1st house at top, numbered counterclockwise.
 */

const RASHI_NAMES = [
    "Mesha", "Vrishabha", "Mithuna", "Karka",
    "Simha", "Kanya", "Tula", "Vrischika",
    "Dhanu", "Makara", "Kumbha", "Meena"
];

const RASHI_SHORT = [
    "Me", "Vr", "Mi", "Ka", "Si", "Kn",
    "Tu", "Vs", "Dh", "Ma", "Ku", "Mn"
];

const RASHI_SYMBOLS = [
    "♈", "♉", "♊", "♋", "♌", "♍",
    "♎", "♏", "♐", "♑", "♒", "♓"
];

// ══════════════════════════════════════════════════════════════
//  SOUTH INDIAN CHART
//  Fixed rashi positions in a 4×4 grid (corners are cells,
//  center 2×2 is empty/title area)
// ══════════════════════════════════════════════════════════════

// Map rashi index (0-11) to grid position [row, col] in 4×4
// Going clockwise from top-left (Meena=11):
//  11  0  1  2
//  10  _  _  3
//   9  _  _  4
//   8  7  6  5
const SI_POSITIONS = {
    11: [0, 0],  // Meena   — top left
    0:  [0, 1],  // Mesha   — top
    1:  [0, 2],  // Vrishabha — top
    2:  [0, 3],  // Mithuna — top right
    3:  [1, 3],  // Karka   — right
    4:  [2, 3],  // Simha   — right
    5:  [3, 3],  // Kanya   — bottom right
    6:  [3, 2],  // Tula    — bottom
    7:  [3, 1],  // Vrischika — bottom
    8:  [3, 0],  // Dhanu   — bottom left
    9:  [2, 0],  // Makara  — left
    10: [1, 0],  // Kumbha  — left
};

function renderSouthIndian(svgEl, chartData, labels) {
    const W = 400, H = 400;
    const cellW = W / 4, cellH = H / 4;
    const lagna = chartData.lagna.index;

    let svg = '';

    // Background — warm ivory
    svg += `<rect width="${W}" height="${H}" fill="#faf7f2" rx="8"/>`;

    // Outer border — deep teal
    svg += `<rect x="1" y="1" width="${W-2}" height="${H-2}" fill="none" stroke="#0e7490" stroke-width="2" rx="8"/>`;

    // Grid lines — muted cyan
    for (let i = 1; i < 4; i++) {
        // Vertical lines
        if (i === 1 || i === 3) {
            svg += `<line x1="${cellW*i}" y1="0" x2="${cellW*i}" y2="${H}" stroke="#a5f3fc" stroke-width="1"/>`;
        } else {
            svg += `<line x1="${cellW*i}" y1="0" x2="${cellW*i}" y2="${cellH}" stroke="#a5f3fc" stroke-width="1"/>`;
            svg += `<line x1="${cellW*i}" y1="${cellH*3}" x2="${cellW*i}" y2="${H}" stroke="#a5f3fc" stroke-width="1"/>`;
        }
        // Horizontal lines
        if (i === 1 || i === 3) {
            svg += `<line x1="0" y1="${cellH*i}" x2="${W}" y2="${cellH*i}" stroke="#a5f3fc" stroke-width="1"/>`;
        } else {
            svg += `<line x1="0" y1="${cellH*i}" x2="${cellW}" y2="${cellH*i}" stroke="#a5f3fc" stroke-width="1"/>`;
            svg += `<line x1="${cellW*3}" y1="${cellH*i}" x2="${W}" y2="${cellH*i}" stroke="#a5f3fc" stroke-width="1"/>`;
        }
    }

    // Center box — light teal wash
    svg += `<rect x="${cellW}" y="${cellH}" width="${cellW*2}" height="${cellH*2}" fill="#ecfeff" stroke="#a5f3fc" stroke-width="1"/>`;

    // Center title
    const lb = labels || {};
    const centerTitle = lb.chartTitle || 'Sunrise Chart';
    const lagnaLabel = lb.lagna || 'Lagna';
    svg += `<text x="${W/2}" y="${H/2 - 12}" text-anchor="middle" font-size="13" font-weight="600" fill="#155e75">${centerTitle}</text>`;
    svg += `<text x="${W/2}" y="${H/2 + 8}" text-anchor="middle" font-size="11" fill="#78716c">${lagnaLabel}: ${chartData.lagna.name}</text>`;
    const KV = window.KVLocale || {};
    const _localNum = KV.localNum || (n => String(n));
    const _rSym = KV.retrogradeSymbol ? KV.retrogradeSymbol() : 'ᴿ';
    const _cSym = KV.combustSymbol ? KV.combustSymbol() : 'ᶜ';
    const _degStr = (v) => _localNum(Number(v).toFixed(1)) + '°';
    svg += `<text x="${W/2}" y="${H/2 + 24}" text-anchor="middle" font-size="10" fill="#a8a29e">${_degStr(chartData.lagna.degree)}</text>`;

    // Draw each rashi cell
    for (let ri = 0; ri < 12; ri++) {
        const [row, col] = SI_POSITIONS[ri];
        const x = col * cellW;
        const y = row * cellH;
        const isLagna = (ri === lagna);

        // Highlight lagna rashi — light teal
        if (isLagna) {
            svg += `<rect x="${x+1}" y="${y+1}" width="${cellW-2}" height="${cellH-2}" fill="#ecfeff"/>`;
        }

        // Rashi label (top-left of cell)
        const labelColor = isLagna ? '#0e7490' : '#a8a29e';
        const labelWeight = isLagna ? '600' : '400';
        svg += `<text x="${x+5}" y="${y+14}" font-size="9" fill="${labelColor}" font-weight="${labelWeight}">${RASHI_SHORT[ri]}</text>`;

        // Lagna marker — diagonal line in lagna rashi
        if (isLagna) {
            svg += `<line x1="${x}" y1="${y}" x2="${x+20}" y2="${y+20}" stroke="#0e7490" stroke-width="1.5"/>`;
        }

        // Grahas in this rashi — wrap into rows of 3 max
        const grahasHere = chartData.rashi_grahas[String(ri)] || [];
        if (grahasHere.length > 0) {
            const grahaLabels = grahasHere.map(abbrev => {
                const g = chartData.grahas.find(g => g.abbrev === abbrev);
                let label = abbrev;
                if (g && g.is_retrograde) label += _rSym;
                if (g && g.is_combust)    label += _cSym;
                if (g && g.is_combust) return `<tspan fill="#b45309">${label}</tspan>`;
                return label;
            });

            // Split into rows of up to 3 labels each
            const perRow = 3;
            const rows = [];
            for (let r = 0; r < grahaLabels.length; r += perRow) {
                rows.push(grahaLabels.slice(r, r + perRow).join(' '));
            }
            const lineH = 15;
            const startY = y + cellH / 2 - ((rows.length - 1) * lineH) / 2 + 5;
            for (let r = 0; r < rows.length; r++) {
                svg += `<text x="${x + cellW/2}" y="${startY + r * lineH}" text-anchor="middle" font-size="12" font-weight="600" fill="#292524">${rows[r]}</text>`;
            }
        }
    }

    svgEl.innerHTML = svg;
}


// ══════════════════════════════════════════════════════════════
//  NORTH INDIAN CHART
//
//  Structure: outer square + 2 corner-diagonals + inscribed diamond
//  (connecting midpoints of adjacent sides).
//
//  The diagonals divide the inner diamond into 4 Kendra houses
//  (1, 4, 7, 10). The diagonals also split each of the 4 outer
//  corner triangles into 2, giving 8 corner houses (2–3, 5–6,
//  8–9, 11–12).  Total: 4 + 8 = 12 houses.
//
//  Houses are numbered counterclockwise starting from top:
//    1 (top kendra) → 2 (upper-left) → 3 (left-upper) →
//    4 (left kendra) → 5 (lower-left) → 6 (bottom-left) →
//    7 (bottom kendra) → 8 (bottom-right) → 9 (right-lower) →
//   10 (right kendra) → 11 (right-upper) → 12 (upper-right)
// ══════════════════════════════════════════════════════════════

function renderNorthIndian(svgEl, chartData, labels) {
    const W = 400, H = 400;
    const S = 10;                  // inset from canvas edge
    const E = W - S;               // 390
    const midX = W / 2, midY = H / 2;
    const lagna = chartData.lagna.index;

    let svg = '';

    // ── Background — warm ivory ──
    svg += `<rect width="${W}" height="${H}" fill="#faf7f2" rx="8"/>`;

    // ── Outer square — deep teal ──
    svg += `<rect x="${S}" y="${S}" width="${E-S}" height="${E-S}" fill="none" stroke="#0e7490" stroke-width="2"/>`;

    // ── Diagonals (corner to corner) — muted cyan ──
    svg += `<line x1="${S}" y1="${S}" x2="${E}" y2="${E}" stroke="#a5f3fc" stroke-width="1"/>`;
    svg += `<line x1="${E}" y1="${S}" x2="${S}" y2="${E}" stroke="#a5f3fc" stroke-width="1"/>`;

    // ── Inscribed diamond (midpoint to adjacent midpoint) ──
    const mT = [midX, S];
    const mR = [E, midY];
    const mB = [midX, E];
    const mL = [S, midY];

    svg += `<line x1="${mT[0]}" y1="${mT[1]}" x2="${mR[0]}" y2="${mR[1]}" stroke="#a5f3fc" stroke-width="1"/>`;
    svg += `<line x1="${mR[0]}" y1="${mR[1]}" x2="${mB[0]}" y2="${mB[1]}" stroke="#a5f3fc" stroke-width="1"/>`;
    svg += `<line x1="${mB[0]}" y1="${mB[1]}" x2="${mL[0]}" y2="${mL[1]}" stroke="#a5f3fc" stroke-width="1"/>`;
    svg += `<line x1="${mL[0]}" y1="${mL[1]}" x2="${mT[0]}" y2="${mT[1]}" stroke="#a5f3fc" stroke-width="1"/>`;

    // ── House centroid positions ──
    // Computed from actual triangle/quadrilateral vertex centroids,
    // adjusted inward for clean text placement.
    //
    // Kendra houses (◇ = inside diamond, larger quadrilateral regions)
    // Corner houses (△ = outside diamond, smaller triangle regions)
    const niPos = [
        { x: midX,  y: 100  },  // H1  — top kendra       ◇
        { x: 110,   y: 48   },  // H2  — upper-left        △
        { x: 48,    y: 110  },  // H3  — left-upper        △
        { x: 105,   y: midY },  // H4  — left kendra       ◇
        { x: 48,    y: 290  },  // H5  — left-lower        △
        { x: 110,   y: 352  },  // H6  — lower-left        △
        { x: midX,  y: 300  },  // H7  — bottom kendra     ◇
        { x: 290,   y: 352  },  // H8  — lower-right       △
        { x: 352,   y: 290  },  // H9  — right-lower       △
        { x: 295,   y: midY },  // H10 — right kendra      ◇
        { x: 352,   y: 110  },  // H11 — right-upper       △
        { x: 290,   y: 48   },  // H12 — upper-right       △
    ];

    // ── Draw houses ──
    for (let h = 0; h < 12; h++) {
        const rashiIdx = (lagna + h) % 12;
        const pos = niPos[h];
        const isLagna = (h === 0);

        // Rashi label
        const rFill = isLagna ? '#0e7490' : '#78716c';
        const rWt   = isLagna ? '600' : '400';
        svg += `<text x="${pos.x}" y="${pos.y}" text-anchor="middle" font-size="9" fill="${rFill}" font-weight="${rWt}">${RASHI_SHORT[rashiIdx]}</text>`;

        // Grahas in this rashi — wrap into rows of 3 max
        const grahasHere = chartData.rashi_grahas[String(rashiIdx)] || [];
        if (grahasHere.length > 0) {
            const KV2 = window.KVLocale || {};
            const _rSym2 = KV2.retrogradeSymbol ? KV2.retrogradeSymbol() : 'ᴿ';
            const _cSym2 = KV2.combustSymbol ? KV2.combustSymbol() : 'ᶜ';
            const grahaLabels = grahasHere.map(abbrev => {
                const g = chartData.grahas.find(g => g.abbrev === abbrev);
                let label = abbrev;
                if (g && g.is_retrograde) label += _rSym2;
                if (g && g.is_combust)    label += _cSym2;
                if (g && g.is_combust) return `<tspan fill="#b45309">${label}</tspan>`;
                return label;
            });

            const perRow = 3;
            const rows = [];
            for (let r = 0; r < grahaLabels.length; r += perRow) {
                rows.push(grahaLabels.slice(r, r + perRow).join(' '));
            }
            const lineH = 13;
            const baseY = pos.y + 14;
            for (let r = 0; r < rows.length; r++) {
                svg += `<text x="${pos.x}" y="${baseY + r * lineH}" text-anchor="middle" font-size="9" font-weight="600" fill="#292524">${rows[r]}</text>`;
            }
        }
    }

    // ── Ascendant marker ──
    const lb = labels || {};
    const ascLabel = lb.asc || 'Asc';
    svg += `<text x="${midX}" y="${S + 28}" text-anchor="middle" font-size="10" fill="#0e7490" font-weight="600">${ascLabel}</text>`;

    svgEl.innerHTML = svg;
}


// ══════════════════════════════════════════════════════════════
//  Graha Details Table
// ══════════════════════════════════════════════════════════════

function renderGrahaTable(containerEl, chartData, labels) {
    const KV = window.KVLocale || {};
    const _ln = KV.localNum || (n => String(n));
    const _pa = KV.padaAbbrev ? KV.padaAbbrev() : 'Pa';
    const _rL = KV.retrogradeSymbol ? KV.retrogradeSymbol() : 'R';
    const _cL = KV.combustSymbol ? KV.combustSymbol() : 'C';
    const _deg = (v) => _ln(Number(v).toFixed(1)) + '°';

    const lb = labels || { graha: 'Graha', rashi: 'Rashi', degree: 'Degree', nakshatra: 'Nakshatra', status: 'Status', lagna: 'Lagna' };
    let html = '<table>';
    html += `<thead><tr><th></th><th>${lb.graha}</th><th>${lb.rashi}</th><th>${lb.degree}</th><th>${lb.nakshatra}</th><th>${lb.status}</th></tr></thead>`;
    html += '<tbody>';

    // Lagna row
    const lagNak = chartData.lagna.nakshatra_name
        ? `${chartData.lagna.nakshatra_name} ${_pa}${_ln(chartData.lagna.nakshatra_pada)}`
        : '—';
    html += `<tr>
        <td>⬆</td>
        <td><strong>${lb.lagna}</strong></td>
        <td>${chartData.lagna.name}</td>
        <td>${_deg(chartData.lagna.degree)}</td>
        <td>${lagNak}</td>
        <td>—</td>
    </tr>`;

    for (const g of chartData.grahas) {
        // Status badges
        let badges = [];
        if (g.is_retrograde) badges.push(`<span class="badge badge-retro">${_rL}</span>`);
        if (g.is_combust)    badges.push(`<span class="badge badge-combust">${_cL}</span>`);
        const statusHtml = badges.length > 0 ? badges.join(' ') : '—';

        html += `<tr>
            <td>${g.symbol}</td>
            <td>${g.name}</td>
            <td>${g.rashi_name}</td>
            <td>${_deg(g.degree_in_rashi)}</td>
            <td>${g.nakshatra_name} ${_pa}${_ln(g.nakshatra_pada)}</td>
            <td>${statusHtml}</td>
        </tr>`;
    }

    html += '</tbody></table>';
    containerEl.innerHTML = html;
}


// ══════════════════════════════════════════════════════════════
//  Exports
// ══════════════════════════════════════════════════════════════

window.ChartRenderer = {
    renderSouthIndian,
    renderNorthIndian,
    renderGrahaTable,
};
