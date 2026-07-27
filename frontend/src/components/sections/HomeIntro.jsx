/**
 * One-line "what is Zynthoro" explainer for the slim homepage.
 * Kept intentionally short — anything longer belongs on /modules.
 */
export default function HomeIntro() {
  return (
    <section
      data-testid="home-intro"
      className="zy-section pt-16 pb-16 bg-white"
    >
      <div className="zy-container">
        <div className="max-w-3xl mx-auto text-center zy-reveal">
          <p
            className="text-[20px] sm:text-[22px] leading-[1.5] font-medium text-[#0A1628]"
            data-testid="home-intro-oneliner"
          >
            One AI-native platform that replaces the 8–15 disconnected tools your business runs on —
            with <span style={{ color: "var(--zy-blue)" }}>four AI specialists</span> that already know your company.
          </p>
        </div>
      </div>
    </section>
  );
}
