// Charts for the post on approval voting and proportionality.
// Observable Plot draws each chart from the analysis output in /components/data/posts/.
// Each chart replaces a fallback PNG. If a script or a data file fails to load, the PNG stays.
(function () {
  const dataPath = "/components/data/posts/2026-11-10-approval-voting-proportionality/";

  // One entry for each scenario: the label, a short label for narrow screens, and the keys in each output file.
  const scenarios = [
    { label: "First Past the Post (2024 result)", short: "First Past the Post", results: "actual", congruence: "2024 actual (First Past the Post)" },
    { label: "Approval, favorite only", short: "Favorite only", results: "Bullet: favourite only", congruence: "Approval: Bullet: favourite only" },
    { label: "Approval, rated 8 or more", short: "Rated 8 or more", results: "Approve if rated 8+", congruence: "Approval: Approve if rated 8+" },
    { label: "Approval, rated 7 or more", short: "Rated 7 or more", results: "Approve if rated 7+", congruence: "Approval: Approve if rated 7+" },
    { label: "Approval, rated 6 or more", short: "Rated 6 or more", results: "Approve if rated 6+", congruence: "Approval: Approve if rated 6+" },
    { label: "Approval, within 2 of favorite", short: "Within 2 of favorite", results: "Within 2 points of own top", congruence: "Approval: Within 2 points of own top" },
    { label: "Proportional allocation", short: "Proportional", results: "proportional", congruence: "Proportional allocation" },
  ];

  const parties = [
    { key: "green", name: "Grn", anchor: "end", dx: -3 },
    { key: "labour", name: "Lab", anchor: "start", dx: 3 },
    { key: "liberal-democrats", name: "LD", anchor: "middle", dx: 0 },
    { key: "conservative", name: "Con", anchor: "middle", dx: 0 },
    { key: "reform-uk", name: "Ref", anchor: "middle", dx: 0 },
  ];

  const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

  // Colors from the validated default chart palette, with separate steps for the dark surface.
  function palette() {
    return darkQuery.matches
      ? { bar: "#3987e5", grid: "#444444", muted: "#c3c2b7", surface: "#1e1e1e" }
      : { bar: "#2a78d6", grid: "#e4e3df", muted: "#52514e", surface: "#fcfcfb" };
  }

  function gallagherValue(results, key) {
    if (key === "actual") return results.actual.gallagher_vs_sincere;
    if (key === "proportional") return results.proportional.gallagher;
    return results.scenarios[key].gallagher;
  }

  function gallagherChart(results, width) {
    const colors = palette();
    const narrow = width < 560;
    const rows = scenarios.map((s) => ({ label: narrow ? s.short : s.label, value: gallagherValue(results, s.results) }));
    return Plot.plot({
      width,
      height: 320,
      marginLeft: narrow ? 140 : 220,
      marginRight: 30,
      marginBottom: 48,
      style: { background: "transparent", fontSize: narrow ? "12px" : "13px" },
      x: { domain: [0, 40], grid: true, label: "Gallagher index (0 means seats match first choices)", labelAnchor: "center", labelOffset: 40, labelArrow: "none" },
      y: { domain: rows.map((d) => d.label), label: null, padding: 0.35 },
      marks: [
        Plot.barX(rows, {
          x: "value",
          y: "label",
          fill: colors.bar,
          rx: 2,
          title: (d) => `${d.label}\nGallagher index: ${d.value.toFixed(1)}`,
          tip: true,
        }),
        Plot.text(rows, { x: "value", y: "label", text: (d) => d.value.toFixed(0), dx: 6, textAnchor: "start" }),
        Plot.ruleX([0]),
      ],
    });
  }

  function medianChart(congruence, width) {
    const colors = palette();
    const narrow = width < 560;
    const voter = congruence.voter_median;
    const rows = scenarios.map((s) => {
      const r = congruence.scenarios[s.congruence];
      return { label: narrow ? s.short : s.label, median: r.median_mp, gap: r.median_gap };
    });
    const marks = parties.map((p) => ({ ...p, position: congruence.party_position[p.key] }));
    return Plot.plot({
      width,
      height: 360,
      marginLeft: narrow ? 140 : 220,
      marginTop: 40,
      marginBottom: 48,
      style: { background: "transparent", fontSize: narrow ? "12px" : "13px" },
      x: { domain: [0, 10], grid: true, label: "Left (0) to right (10)", labelAnchor: "center", labelOffset: 40, labelArrow: "none" },
      y: { domain: rows.map((d) => d.label), label: null },
      marks: [
        Plot.ruleX(marks, { x: "position", stroke: colors.grid, strokeWidth: 1 }),
        // Plot needs a constant offset and anchor, so each group of party labels gets its own mark.
        ...[["end", -3], ["start", 3], ["middle", 0]].map(([anchor, dx]) =>
          Plot.text(
            marks.filter((d) => d.anchor === anchor),
            { x: "position", frameAnchor: "top", dy: -14, dx, text: "name", textAnchor: anchor, fill: colors.muted },
          ),
        ),
        Plot.ruleX([voter], { stroke: colors.muted, strokeDasharray: "4,3", strokeWidth: 1.5 }),
        Plot.text([voter], { x: (d) => d, frameAnchor: "bottom", dy: -6, dx: 5, textAnchor: "start", text: () => `Median voter (${voter.toFixed(0)})`, fill: colors.muted }),
        Plot.link(rows, { x1: "median", x2: () => voter, y1: "label", y2: "label", stroke: colors.grid, strokeWidth: 3 }),
        Plot.dot(rows, {
          x: "median",
          y: "label",
          r: 6,
          fill: colors.bar,
          stroke: colors.surface,
          strokeWidth: 2,
          title: (d) => `${d.label}\nMedian MP: ${d.median.toFixed(1)}\nGap to median voter: ${d.gap.toFixed(1)}`,
          tip: true,
        }),
        Plot.text(rows, { x: "median", y: "label", text: (d) => d.median.toFixed(1), dx: -12, textAnchor: "end" }),
      ],
    });
  }

  function mount(id, draw, data) {
    const container = document.getElementById(id);
    if (!container) return;
    const render = () => {
      const width = Math.max(300, Math.floor(container.clientWidth));
      container.replaceChildren(draw(data, width));
    };
    render();
    let frame = 0;
    window.addEventListener("resize", () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(render);
    });
    darkQuery.addEventListener("change", render);
  }

  async function load() {
    if (typeof Plot === "undefined") return;
    const [results, congruence] = await Promise.all(
      ["results.json", "congruence.json"].map((file) => fetch(dataPath + file).then((response) => response.json())),
    );
    mount("chart-gallagher", gallagherChart, results);
    mount("chart-median", medianChart, congruence);
  }

  document.addEventListener("DOMContentLoaded", () => {
    load().catch(() => {
      // Keep the fallback PNGs.
    });
  });
})();
