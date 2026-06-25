import { useEffect, useState } from "react";
import axios from "axios";
import { Loader2, TrendingUp, RefreshCw, Crown } from "lucide-react";
import { toast } from "sonner";
import { API, formatApiError } from "@/contexts/AuthContext";

/**
 * Live Stripe MRR / ARR widget for the Builder Mode panel.
 *
 * Calls GET /api/founder/stripe-metrics (founder-only), sums active
 * subscriptions by plan and shows MRR, ARR, active sub count plus
 * a per-plan breakdown table. Refreshable.
 */
export default function StripeMetricsCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async (isRefresh = false) => {
    isRefresh ? setRefreshing(true) : setLoading(true);
    try {
      const { data } = await axios.get(`${API}/founder/stripe-metrics`);
      setData(data);
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Could not load Stripe metrics.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { load(false); }, []);

  return (
    <div
      data-testid="stripe-metrics-card"
      className="bg-white border border-[#eee] rounded-lg p-4 mb-6"
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp size={15} style={{ color: "#1A4FFF" }} />
          <h3 className="text-[13.5px] font-semibold">Live Stripe revenue</h3>
          {data?.fetched_at && (
            <span className="text-[11px] text-[#999]">
              · updated {new Date(data.fetched_at).toLocaleTimeString()}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => load(true)}
          disabled={refreshing || loading}
          data-testid="stripe-metrics-refresh"
          className="inline-flex items-center gap-1 text-[12px] font-medium text-[#1A4FFF] hover:opacity-80 disabled:opacity-50"
        >
          {refreshing ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-[#888] text-[13px] py-4">
          <Loader2 size={14} className="animate-spin" /> Loading live Stripe data…
        </div>
      ) : data ? (
        <>
          <div className="grid grid-cols-3 gap-3" data-testid="stripe-metrics-totals">
            <Metric
              label="Active subs"
              value={data.active_subs?.toLocaleString() ?? "0"}
              accent="#1A4FFF"
            />
            <Metric
              label="MRR"
              value={`€${formatEur(data.mrr_eur)}`}
              accent="#1A4FFF"
              big
            />
            <Metric
              label="ARR"
              value={`€${formatEur(data.arr_eur)}`}
              accent="#D4AF37"
              big
            />
          </div>

          {data.seats_mrr_eur > 0 && (
            <p className="text-[11.5px] text-[#666] mt-3" data-testid="stripe-metrics-seats">
              Includes <b>€{formatEur(data.seats_mrr_eur)}/mo</b> from extra-seat add-ons.
            </p>
          )}

          {data.plan_breakdown?.length > 0 ? (
            <div className="mt-5">
              <p className="text-[11px] uppercase tracking-wider text-[#888] font-semibold mb-2">
                Plan breakdown
              </p>
              <div
                className="overflow-x-auto rounded-md border border-[#f1f1f1]"
                data-testid="stripe-metrics-breakdown"
              >
                <table className="w-full text-[12.5px]">
                  <thead className="bg-[#FAFAFB] text-[#666]">
                    <tr>
                      <th className="text-left py-1.5 px-3">Plan</th>
                      <th className="text-right py-1.5 px-3">Subs</th>
                      <th className="text-right py-1.5 px-3">MRR</th>
                      <th className="text-right py-1.5 px-3">% of MRR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.plan_breakdown.map((p) => {
                      const pct = data.mrr_eur > 0
                        ? ((p.mrr_eur / data.mrr_eur) * 100).toFixed(0)
                        : "0";
                      const isEnt = p.label?.startsWith("Enterprise");
                      return (
                        <tr
                          key={p.plan_key}
                          className="border-t border-[#f3f3f3]"
                          data-testid={`stripe-row-${p.plan_key.toLowerCase().replace(/\s+/g, "-")}`}
                        >
                          <td className="py-1.5 px-3 font-medium">
                            <span className="inline-flex items-center gap-1.5">
                              {isEnt && <Crown size={11} style={{ color: "#8a6e1d" }} />}
                              {p.label}
                            </span>
                          </td>
                          <td className="py-1.5 px-3 text-right">{p.count}</td>
                          <td className="py-1.5 px-3 text-right font-semibold">
                            €{formatEur(p.mrr_eur)}
                          </td>
                          <td className="py-1.5 px-3 text-right text-[#666]">{pct}%</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <p
              className="text-[12.5px] text-[#888] mt-4 italic"
              data-testid="stripe-metrics-empty"
            >
              No active subscriptions yet. Numbers will populate as soon as your
              first customer completes checkout.
            </p>
          )}
        </>
      ) : (
        <p className="text-[12.5px] text-[#999]">No data.</p>
      )}
    </div>
  );
}

function formatEur(n) {
  if (n == null) return "0";
  return Number(n).toLocaleString("en-IE", {
    minimumFractionDigits: 0,
    maximumFractionDigits: n >= 1000 ? 0 : 2,
  });
}

function Metric({ label, value, accent = "#1A4FFF", big = false }) {
  return (
    <div className="bg-white border border-[#eee] rounded-lg p-3">
      <span
        className="text-[11px] uppercase tracking-wider font-semibold"
        style={{ color: accent }}
      >
        {label}
      </span>
      <p
        className={`mt-1.5 font-bold ${big ? "text-[22px]" : "text-[20px]"}`}
        style={{ color: "#0A1628" }}
      >
        {value}
      </p>
    </div>
  );
}
