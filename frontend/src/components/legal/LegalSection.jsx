export function LegalSection({ id, number, title, children }) {
  return (
    <section id={id} className="mb-10" data-testid={`legal-section-${id}`}>
      <h2 className="text-[22px] md:text-[26px] font-bold tracking-tight text-black mb-4">
        <span className="text-[var(--zy-blue)] mr-3">{number}.</span>
        {title}
      </h2>
      <div className="space-y-4 text-[15px] leading-[1.75] text-black/75">
        {children}
      </div>
    </section>
  );
}

export function LegalList({ items }) {
  return (
    <ul className="list-disc pl-6 space-y-2 text-[15px] leading-[1.75] text-black/75">
      {items.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ul>
  );
}
