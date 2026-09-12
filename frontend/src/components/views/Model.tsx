"use client";

import { BrainCircuit, FlaskConical, Layers, Microscope, TimerReset } from "lucide-react";

import { IcChart, ImportanceBars } from "@/components/charts";
import { AnimatedNumber, Card, Meter, Reveal, SectionTitle } from "@/components/ui";
import { featureLabel, num, pct, shortDate, signedPct } from "@/lib/format";
import type { Dashboard } from "@/lib/types";

export function Model({ data }: { data: Dashboard }) {
  const { ml, meta, performance } = data;
  const rule = performance.find((p) => p.key === "rule");
  const mlPerf = performance.find((p) => p.key === "ml");
  const blended = performance.find((p) => p.key === "blended");

  const importance = ml.importance.map((f) => ({
    label: featureLabel(f.feature),
    value: f.importance,
  }));

  const graded = ml.folds.filter((f) => f.ic !== null);
  const spread = graded
    .map((f) => (f.topDecile ?? 0) - (f.bottomDecile ?? 0))
    .filter((v) => Number.isFinite(v));
  const avgSpread = spread.length ? spread.reduce((a, b) => a + b, 0) / spread.length : 0;

  return (
    <div className="flex flex-col gap-7">
      <SectionTitle
        icon={<BrainCircuit size={16} />}
        title="Model diagnostics"
        subtitle={`The ranker is ${ml.backend}, retrained from scratch at every rebalance on ${ml.features} cross-sectional features. It is only ever shown observations whose ${ml.labelHorizonDays}-day return horizon had already closed, so no fold can learn from a future it would not have seen.`}
      />

      {/* ---------------- headline diagnostics ---------------- */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            l: "Mean information coefficient",
            v: (ml.meanIC ?? 0), d: 3, s: "",
            f: "Average rank correlation between the model's ordering and the return that followed. Live equity factors typically sit between 0.02 and 0.06.",
          },
          {
            l: "Folds with positive IC",
            v: (ml.icHitRate ?? 0) * 100, d: 0, s: "%",
            f: `${graded.filter((f) => (f.ic ?? 0) > 0).length} of ${graded.length} out-of-sample quarters ranked the market the right way round.`,
          },
          {
            l: "Top minus bottom quintile",
            v: avgSpread * 100, d: 2, s: "%",
            f: "Average quarterly return gap between the names the model liked most and least.",
          },
          {
            l: "Weight in the blend",
            v: meta.blendWeight * 100, d: 0, s: "%",
            f: "The remainder is the rule-based composite, which carries the majority share.",
          },
        ].map((t, i) => (
          <Reveal key={t.l} delay={i * 0.06}>
            <Card hover className="h-full">
              <p className="label">{t.l}</p>
              <p className="num mt-2.5 text-[28px] font-semibold leading-none">
                <AnimatedNumber value={t.v} decimals={t.d} suffix={t.s} />
              </p>
              <p className="mt-2.5 text-[11.5px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
                {t.f}
              </p>
            </Card>
          </Reveal>
        ))}
      </div>

      {/* ---------------- the honest finding ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <SectionTitle
            icon={<FlaskConical size={16} />}
            title="Did the machine learning earn its place?"
            subtitle="The proposal set out to test a learning-to-rank model against an interpretable baseline. This is what the walk-forward test actually found."
          />
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { k: "Rule-based score", p: rule, c: "#34d399",
                note: "No fitted parameters. Cannot overfit the test." },
              { k: "ML ranker alone", p: mlPerf, c: "#a78bfa",
                note: "Retrained every quarter on the data available then." },
              { k: "Blend of both", p: blended, c: "#6d8dff",
                note: `${pct(1 - meta.blendWeight, 0)} rule, ${pct(meta.blendWeight, 0)} model.` },
            ].map(({ k, p, c, note }) => (
              <div key={k} className="rounded-xl border p-4" style={{ borderColor: "var(--line)" }}>
                <span className="flex items-center gap-2 text-[12.5px]">
                  <span className="h-2 w-2 rounded-full" style={{ background: c }} />
                  {k}
                </span>
                <p className="num mt-2.5 text-[22px] font-semibold">{num(p?.information_ratio, 2)}</p>
                <p className="label mt-0.5 text-[9px]">Information ratio</p>
                <div className="mt-3">
                  <Meter value={((p?.information_ratio ?? 0) / 1.2) * 100} color={c} height={5} />
                </div>
                <p className="mt-2.5 text-[11px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
                  {note}
                </p>
              </div>
            ))}
          </div>

          <div className="mt-5 rounded-xl border p-4"
               style={{ borderColor: "rgba(251,191,36,.26)", background: "rgba(251,191,36,.05)" }}>
            <p className="mb-1.5 text-[12.5px] font-semibold" style={{ color: "var(--warn)" }}>
              The gradient-boosted ranker did not beat the hand-built score on its own.
            </p>
            <p className="text-[12px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
              A KSE-100 cross-section offers about a hundred rows per quarter, and roughly thirty
              usable quarters. That is a few thousand training examples for {ml.features} noisy
              features, where the signal-to-noise ratio of a quarterly stock return is low by
              nature. Under those conditions a flexible model spends most of its capacity fitting
              noise, while a weighted average of sector-relative z-scores gives up flexibility and
              keeps the signal. The model still earns a minority share of the blend, because its
              errors are not the same errors the rule-based score makes, and combining the two beat
              either alone. Reporting this rather than tuning the model until it wins is the point
              of running the comparison walk-forward.
            </p>
          </div>
        </Card>
      </Reveal>

      {/* ---------------- IC per fold ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <SectionTitle
            icon={<Microscope size={16} />}
            title="Out-of-sample skill, quarter by quarter"
            subtitle="Rank correlation between the model's ordering on the rebalance date and the return actually delivered over the quarter that followed. Every bar is a genuine out-of-sample test."
          />
          <IcChart data={ml.folds.map((f) => ({ date: f.date, ic: f.ic }))} height={250} />
          <p className="mt-3 text-[11.5px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
            The bars swing either side of zero, which is what honest quarterly stock forecasting
            looks like. What matters is that the average sits above zero and that the losing
            quarters are not systematically the same kind of quarter.
          </p>
        </Card>
      </Reveal>

      {/* ---------------- features + folds ---------------- */}
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Reveal>
          <Card className="h-full" padding="p-5">
            <SectionTitle
              icon={<Layers size={16} />}
              title="What the model leans on"
              subtitle="Share of total split gain, averaged over the seed ensemble of the most recent fit."
            />
            <ImportanceBars data={importance} height={440} />
          </Card>
        </Reveal>

        <Reveal delay={0.08}>
          <Card className="h-full" padding="p-5">
            <SectionTitle
              icon={<TimerReset size={16} />}
              title="Walk-forward audit trail"
              subtitle="Each row is one retrain. The training set only ever grows, and it never contains a label whose horizon was still open on the rebalance date."
            />
            <div className="max-h-[440px] overflow-y-auto">
              <table className="w-full text-[12px]">
                <thead className="sticky top-0" style={{ background: "var(--surface-solid)" }}>
                  <tr className="label" style={{ color: "var(--text-dim)" }}>
                    <th className="px-2 pb-2 text-left font-semibold">Rebalance</th>
                    <th className="px-2 pb-2 text-right font-semibold">Train rows</th>
                    <th className="px-2 pb-2 text-right font-semibold">Quarters</th>
                    <th className="px-2 pb-2 text-right font-semibold">IC</th>
                    <th className="px-2 pb-2 text-right font-semibold">Q1 − Q5</th>
                  </tr>
                </thead>
                <tbody>
                  {ml.folds.map((f) => {
                    const sp = f.topDecile !== null && f.bottomDecile !== null
                      ? f.topDecile - f.bottomDecile : null;
                    return (
                      <tr key={f.date} className="border-t" style={{ borderColor: "var(--line)" }}>
                        <td className="num px-2 py-2">{shortDate(f.date)}</td>
                        <td className="num px-2 py-2 text-right" style={{ color: "var(--text-muted)" }}>
                          {f.trainRows.toLocaleString()}
                        </td>
                        <td className="num px-2 py-2 text-right" style={{ color: "var(--text-dim)" }}>
                          {f.trainPeriods}
                        </td>
                        <td className="num px-2 py-2 text-right"
                            style={{ color: f.ic === null ? "var(--text-dim)" : (f.ic ?? 0) > 0 ? "var(--pos)" : "var(--neg)" }}>
                          {f.ic === null ? "warm-up" : num(f.ic, 3)}
                        </td>
                        <td className="num px-2 py-2 text-right"
                            style={{ color: sp === null ? "var(--text-dim)" : sp > 0 ? "var(--pos)" : "var(--neg)" }}>
                          {sp === null ? "—" : signedPct(sp, 1)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </Reveal>
      </div>
    </div>
  );
}
