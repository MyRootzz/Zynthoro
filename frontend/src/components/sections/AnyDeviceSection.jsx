import { Smartphone, Tablet, Monitor } from "lucide-react";

/**
 * "Works on any device" reassurance section (Fix 13).
 *
 * Pure CSS mockups of dashboard frames on phone, tablet and desktop —
 * no external image dependencies so it stays fast and deploy-safe.
 */
export default function AnyDeviceSection() {
  return (
    <section
      data-testid="any-device-section"
      className="zy-section"
      style={{ background: "var(--zy-grey-light)" }}
    >
      <div className="zy-container">
        <div className="max-w-3xl mx-auto text-center mb-12">
          <p className="zy-eyebrow mb-3">Built for every device</p>
          <h2 className="zy-h2">Works on any device. Truly.</h2>
          <p className="zy-body mt-4">
            iOS, Android, tablet or desktop — Zynthoro is fully responsive.
            The same data, the same AI assistants, in your pocket or on the wall.
          </p>
          <div className="flex items-center justify-center gap-2 mt-4 flex-wrap">
            <Badge icon={Smartphone} label="iPhone / Android" />
            <Badge icon={Tablet} label="iPad / Tablet" />
            <Badge icon={Monitor} label="Desktop / Laptop" />
          </div>
        </div>

        <div className="flex items-end justify-center gap-4 sm:gap-8 mt-12">
          {/* Phone */}
          <DeviceMockup variant="phone" />
          {/* Tablet */}
          <div className="hidden sm:block">
            <DeviceMockup variant="tablet" />
          </div>
          {/* Desktop */}
          <DeviceMockup variant="desktop" />
        </div>
      </div>
    </section>
  );
}

function Badge({ icon: Icon, label }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 text-[12px] font-semibold px-3 py-1 rounded-full"
      style={{ background: "#EAF0FF", color: "#1A4FFF" }}
    >
      <Icon size={12} /> {label}
    </span>
  );
}

function MiniDashboard({ scale = 1 }) {
  return (
    <div
      className="absolute inset-0 p-2 flex gap-2"
      style={{ fontSize: 6 * scale }}
    >
      <div className="w-[28%] rounded-sm flex flex-col gap-1 p-1.5" style={{ background: "#1A4FFF" }}>
        <div className="text-[#D4AF37] font-extrabold text-[8px] mb-1">ZY</div>
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="h-1 rounded-sm" style={{ background: "rgba(255,255,255,0.3)" }} />
        ))}
      </div>
      <div className="flex-1 flex flex-col gap-1.5">
        <div className="h-2 w-1/2 rounded-sm bg-[#1A4FFF]/30" />
        <div className="grid grid-cols-3 gap-1 mt-0.5">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-5 rounded-sm border border-[#eee] bg-white" />
          ))}
        </div>
        <div className="flex-1 rounded-sm border border-[#eee] bg-white" />
      </div>
    </div>
  );
}

function DeviceMockup({ variant }) {
  if (variant === "phone") {
    return (
      <div
        className="relative shrink-0 rounded-[24px] shadow-xl"
        style={{
          width: 140,
          height: 280,
          background: "#0A1628",
          padding: 7,
          border: "1px solid #1f2c44",
        }}
        aria-hidden="true"
      >
        <div className="absolute top-1.5 left-1/2 -translate-x-1/2 w-12 h-2 rounded-full bg-black" />
        <div className="relative w-full h-full rounded-[18px] bg-white overflow-hidden">
          <MiniDashboard scale={0.9} />
        </div>
      </div>
    );
  }
  if (variant === "tablet") {
    return (
      <div
        className="relative shrink-0 rounded-[18px] shadow-xl"
        style={{
          width: 260,
          height: 340,
          background: "#0A1628",
          padding: 9,
          border: "1px solid #1f2c44",
        }}
        aria-hidden="true"
      >
        <div className="relative w-full h-full rounded-[10px] bg-white overflow-hidden">
          <MiniDashboard scale={1.2} />
        </div>
      </div>
    );
  }
  // desktop
  return (
    <div className="relative shrink-0" aria-hidden="true">
      <div
        className="rounded-[10px] shadow-xl"
        style={{
          width: 440,
          height: 280,
          background: "#0A1628",
          padding: 10,
          border: "1px solid #1f2c44",
        }}
      >
        <div className="relative w-full h-full rounded bg-white overflow-hidden">
          <MiniDashboard scale={1.6} />
        </div>
      </div>
      <div className="mx-auto mt-1 h-1.5 w-32 rounded-b-md bg-[#0A1628]" />
      <div className="mx-auto mt-0.5 h-1 w-44 rounded-md bg-[#1f2c44]" />
    </div>
  );
}
