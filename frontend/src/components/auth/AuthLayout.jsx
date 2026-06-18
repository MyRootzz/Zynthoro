import { Link } from "react-router-dom";
import { ZyLogo } from "@/components/ZyLogo";

export default function AuthLayout({ children, eyebrow, title, subtitle }) {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <header className="px-6 sm:px-10 py-6 border-b border-[#eee] flex items-center justify-between">
        <Link to="/" className="inline-flex items-center" style={{ background: "#0A1628", padding: "8px 14px", borderRadius: 8 }}>
          <ZyLogo size={18} />
        </Link>
        <Link to="/" className="text-[13px] text-[#666] hover:text-[#1A4FFF]">← Back to home</Link>
      </header>
      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-[440px]">
          {eyebrow && (
            <p className="zy-eyebrow mb-3" style={{ fontSize: 11 }}>{eyebrow}</p>
          )}
          <h1 className="text-[28px] sm:text-[32px] font-bold tracking-tight text-black leading-[1.1]">
            {title}
          </h1>
          {subtitle && <p className="mt-3 text-[14.5px] text-[#555]">{subtitle}</p>}
          <div className="mt-8">{children}</div>
        </div>
      </main>
    </div>
  );
}
